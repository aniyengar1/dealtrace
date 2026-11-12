-- Application-role immutability, not protection against a DBA who can alter DDL.
-- All financial inputs needed for reproduction are copied into immutable JSON.
CREATE TABLE earnings_historical_observations (
 id UUID PRIMARY KEY,
 company_id UUID NOT NULL REFERENCES companies(id),
 period_start DATE NOT NULL,
 period_end DATE NOT NULL CHECK(period_start<=period_end),
 guidance_id UUID,
 actual_id UUID,
 outcome TEXT CHECK(outcome IN ('below','within','above')),
 status TEXT NOT NULL CHECK(status IN ('eligible','blocked')),
 public_available_at TIMESTAMPTZ NOT NULL,
 payload JSONB NOT NULL,
 recorded_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
 CHECK((status='eligible' AND outcome IS NOT NULL AND guidance_id IS NOT NULL AND actual_id IS NOT NULL) OR status='blocked')
);
CREATE TABLE earnings_live_predictions (
 id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
 company_id UUID NOT NULL REFERENCES companies(id),
 metric TEXT NOT NULL CHECK(metric='quarterly_consolidated_revenue'),
 period_start DATE NOT NULL,
 period_end DATE NOT NULL CHECK(period_start<=period_end),
 method_version TEXT NOT NULL,
 guidance_id UUID NOT NULL,
 historical_ids UUID[] NOT NULL,
 p_below NUMERIC NOT NULL CHECK(p_below BETWEEN 0 AND 1),
 p_within NUMERIC NOT NULL CHECK(p_within BETWEEN 0 AND 1),
 p_above NUMERIC NOT NULL CHECK(p_above BETWEEN 0 AND 1),
 announcement JSONB NOT NULL,
 publication_check JSONB NOT NULL,
 snapshot JSONB NOT NULL,
 made_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
 lock_deadline TIMESTAMPTZ NOT NULL,
 UNIQUE(company_id,period_start,period_end,metric,method_version),
 CHECK(p_below+p_within+p_above=1)
);
CREATE TABLE earnings_live_results (
 id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
 prediction_id UUID NOT NULL REFERENCES earnings_live_predictions(id),
 evidence_hash TEXT NOT NULL,
 status TEXT NOT NULL CHECK(status IN ('scored','blocked')),
 outcome TEXT CHECK(outcome IN ('below','within','above')),
 brier NUMERIC CHECK(brier BETWEEN 0 AND 2),
 supersedes_id UUID REFERENCES earnings_live_results(id),
 snapshot JSONB NOT NULL,
 scored_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
 UNIQUE(prediction_id,evidence_hash),
 CHECK((status='scored' AND outcome IS NOT NULL AND brier IS NOT NULL) OR
       (status='blocked' AND outcome IS NULL AND brier IS NULL))
);
CREATE FUNCTION earnings_deny_mutation() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'Crosscheck immutable record: % is forbidden', TG_OP USING ERRCODE='55000'; END $$;
CREATE FUNCTION earnings_observation_stamp() RETURNS trigger LANGUAGE plpgsql SET search_path=pg_catalog,public,pg_temp AS $$
BEGIN
 NEW.recorded_at:=clock_timestamp();
 IF NEW.payload->>'status' IS DISTINCT FROM NEW.status OR
    NEW.payload->>'company' IS DISTINCT FROM (SELECT ticker FROM companies WHERE id=NEW.company_id) OR
    NEW.payload->>'period_start' IS DISTINCT FROM NEW.period_start::text OR
    NEW.payload->>'period_end' IS DISTINCT FROM NEW.period_end::text THEN
  RAISE EXCEPTION 'Historical payload identity/status mismatch';
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER earnings_observation_clock BEFORE INSERT ON earnings_historical_observations
 FOR EACH ROW EXECUTE FUNCTION earnings_observation_stamp();
CREATE FUNCTION earnings_prediction_guard() RETURNS trigger LANGUAGE plpgsql SET search_path=pg_catalog,public,pg_temp AS $$
DECLARE
 day DATE; zone TEXT; anchor DATE; g JSONB; hist JSONB; n INTEGER; stamp TIMESTAMPTZ; nb NUMERIC; nw NUMERIC; pb NUMERIC; pw NUMERIC;
BEGIN
 NEW.made_at:=clock_timestamp();
 IF NEW.announcement->>'event_kind' IS DISTINCT FROM 'results_release' OR
    NEW.announcement->>'verification_status' NOT IN ('independently_verified','user_verified') OR
    NEW.announcement->>'verification_status' IS NULL THEN
  RAISE EXCEPTION 'Verified results-publication timing required';
 END IF;
 zone:=NEW.announcement->>'timezone'; day:=(NEW.announcement->>'release_date')::date;
 IF zone IS NULL OR day IS NULL OR NOT EXISTS(SELECT 1 FROM pg_timezone_names WHERE name=zone) THEN
  RAISE EXCEPTION 'Release date and documented timezone required';
 END IF;
 IF NEW.announcement->>'time_precision' IN ('minute','second') AND
    NEW.announcement->>'timestamp_verified'='true' THEN
  IF NEW.announcement->>'timestamp_kind' IS DISTINCT FROM 'results_publication' OR
     coalesce(NEW.announcement->>'timestamp_source_quote','')='' OR
     coalesce(NEW.announcement->>'release_timestamp','') !~ '(Z|[+-][0-9]{2}:[0-9]{2})$' THEN
   RAISE EXCEPTION 'Verified publication timestamp and source evidence required, not call time';
  END IF;
  NEW.lock_deadline:=(NEW.announcement->>'release_timestamp')::timestamptz;
  IF (NEW.lock_deadline AT TIME ZONE zone)::date<>day THEN RAISE EXCEPTION 'Publication date/timezone mismatch'; END IF;
 ELSE
  -- Date-only and before-open/after-close evidence use midnight, never 09:30.
  NEW.lock_deadline:=day::timestamp AT TIME ZONE zone;
 END IF;
 anchor:=day-14;
 IF NEW.made_at>=NEW.lock_deadline OR NEW.made_at<NEW.lock_deadline-interval '14 days' OR NEW.period_end>=day THEN
  RAISE EXCEPTION 'Outside conservative 14-day pre-publication lock window';
 END IF;
 stamp:=(NEW.announcement->>'checked_at')::timestamptz;
 IF stamp IS NULL OR stamp>NEW.made_at OR stamp<NEW.made_at-interval '10 minutes' OR
    coalesce(NEW.announcement->>'source_url','')='' OR coalesce(NEW.announcement->>'time_precision','')='' THEN
  RAISE EXCEPTION 'Fresh announcement check and provenance required';
 END IF;
 stamp:=(NEW.publication_check->>'checked_at')::timestamptz;
 IF NEW.publication_check->>'status' IS DISTINCT FROM 'not_observed' OR
    NEW.publication_check#>>'{sec,success}' IS DISTINCT FROM 'true' OR
    NEW.publication_check#>>'{official_ir,success}' IS DISTINCT FROM 'true' OR
    stamp IS NULL OR stamp>NEW.made_at OR stamp<NEW.made_at-interval '2 minutes' OR
    NEW.publication_check->>'target_start' IS DISTINCT FROM NEW.period_start::text OR
    NEW.publication_check->>'target_end' IS DISTINCT FROM NEW.period_end::text THEN
  RAISE EXCEPTION 'Fresh SEC and official publication checks required';
 END IF;
 IF EXISTS(SELECT 1 FROM earnings_actuals WHERE company_id=NEW.company_id AND period_end=NEW.period_end
           AND period_start<=NEW.period_start AND filed_date<=(NEW.made_at AT TIME ZONE zone)::date) THEN
  RAISE EXCEPTION 'Target results already present in SEC actuals';
 END IF;
 SELECT payload || jsonb_build_object('id',id) INTO g FROM guidance_versions
  WHERE id=NEW.guidance_id AND company_id=NEW.company_id AND metric=NEW.metric
  AND period_start=NEW.period_start AND period_end=NEW.period_end AND status<>'withdrawn'
  AND greatest(filed_date,issued_end)<anchor;
 IF g IS NULL THEN RAISE EXCEPTION 'Guidance unavailable at fixed 14-day horizon'; END IF;
 SELECT count(*),jsonb_agg(jsonb_build_object('id',id,'recorded_at',recorded_at,'payload',payload) ORDER BY id)
  INTO n,hist FROM earnings_historical_observations
  WHERE id=ANY(NEW.historical_ids) AND status='eligible' AND recorded_at<NEW.made_at AND public_available_at<NEW.made_at;
 IF n<6 OR n<>cardinality(NEW.historical_ids) THEN RAISE EXCEPTION 'Insufficient, duplicate or unavailable historical observations'; END IF;
 IF EXISTS(SELECT 1 FROM earnings_historical_observations WHERE id=ANY(NEW.historical_ids)
           GROUP BY company_id,period_start,period_end HAVING count(*)>1) THEN
  RAISE EXCEPTION 'Historical quarter versions cannot be double counted';
 END IF;
 IF NEW.method_version='quarter-frequency-v1' THEN
  IF n>80 OR EXISTS(SELECT 1 FROM earnings_historical_observations WHERE id=ANY(NEW.historical_ids) GROUP BY company_id HAVING count(*)>8) THEN
   RAISE EXCEPTION 'Quarter-frequency-v1 window exceeds eight quarters per company';
  END IF;
  IF (NEW.snapshot#>>'{baseline,as_of}')::timestamptz IS NULL OR
     (NEW.snapshot#>>'{baseline,as_of}')::timestamptz>NEW.made_at OR
     EXISTS(SELECT 1 FROM earnings_historical_observations WHERE id=ANY(NEW.historical_ids) AND
       (recorded_at>(NEW.snapshot#>>'{baseline,as_of}')::timestamptz OR public_available_at>(NEW.snapshot#>>'{baseline,as_of}')::timestamptz)) THEN
   RAISE EXCEPTION 'Historical input unavailable at declared probability as-of';
  END IF;
  IF NEW.snapshot#>>'{baseline,mode}'='company' THEN
   IF EXISTS(SELECT 1 FROM earnings_historical_observations WHERE id=ANY(NEW.historical_ids) AND company_id<>NEW.company_id) THEN
    RAISE EXCEPTION 'Company rate contains another company';
   END IF;
  ELSIF NEW.snapshot#>>'{baseline,mode}'='pooled' THEN
   IF n<12 OR (SELECT count(DISTINCT company_id) FROM earnings_historical_observations WHERE id=ANY(NEW.historical_ids))<2 THEN
    RAISE EXCEPTION 'Insufficient pooled history';
   END IF;
  ELSE RAISE EXCEPTION 'Unknown empirical-rate mode'; END IF;
  SELECT count(*) FILTER(WHERE outcome='below'),count(*) FILTER(WHERE outcome='within') INTO nb,nw
   FROM earnings_historical_observations WHERE id=ANY(NEW.historical_ids);
  pb:=round(nb::numeric(50,30)/n,24); pw:=round(nw::numeric(50,30)/n,24);
  -- PostgreSQL round uses ties away from zero, while the application uses half
  -- even. Denominators <=80 cannot produce an exact 25th-place half tie here.
  IF NEW.p_below<>pb OR NEW.p_within<>pw OR NEW.p_above<>1-pb-pw THEN
   RAISE EXCEPTION 'Probabilities do not reproduce empirical historical counts';
  END IF;
 END IF;
 NEW.snapshot:=NEW.snapshot || jsonb_build_object('locked_guidance',g,'historical_observations',hist,
  'guidance_cutoff_exclusive',anchor,'snapshot_version','self-contained-live-v1');
 RETURN NEW;
END $$;
CREATE TRIGGER earnings_prediction_validate BEFORE INSERT ON earnings_live_predictions
 FOR EACH ROW EXECUTE FUNCTION earnings_prediction_guard();
CREATE FUNCTION earnings_result_guard() RETURNS trigger LANGUAGE plpgsql SET search_path=pg_catalog,public,pg_temp AS $$
DECLARE p earnings_live_predictions; expected NUMERIC; yb INTEGER; yw INTEGER; ya INTEGER;
BEGIN
 NEW.scored_at:=clock_timestamp();
 SELECT * INTO STRICT p FROM earnings_live_predictions WHERE id=NEW.prediction_id;
 IF NEW.supersedes_id IS NOT NULL AND NOT EXISTS(SELECT 1 FROM earnings_live_results WHERE id=NEW.supersedes_id AND prediction_id=NEW.prediction_id) THEN
  RAISE EXCEPTION 'Correction must reference this prediction';
 END IF;
 IF NEW.status='scored' THEN
  IF (NEW.snapshot->>'actual_publication_lower_bound')::timestamptz IS NULL OR
     p.made_at>=(NEW.snapshot->>'actual_publication_lower_bound')::timestamptz OR
     (NEW.snapshot->>'evidence_available_at')::timestamptz IS NULL OR
     (NEW.snapshot->>'evidence_available_at')::timestamptz>NEW.scored_at OR
     NEW.snapshot->>'guidance_id' IS DISTINCT FROM p.guidance_id::text THEN
   RAISE EXCEPTION 'Outcome availability, prospective timing and locked guidance required';
  END IF;
  yb:=CASE WHEN NEW.outcome='below' THEN 1 ELSE 0 END;
  yw:=CASE WHEN NEW.outcome='within' THEN 1 ELSE 0 END;
  ya:=CASE WHEN NEW.outcome='above' THEN 1 ELSE 0 END;
  expected:=(p.p_below-yb)*(p.p_below-yb)+(p.p_within-yw)*(p.p_within-yw)+(p.p_above-ya)*(p.p_above-ya);
  IF NEW.brier IS DISTINCT FROM expected THEN RAISE EXCEPTION 'Incorrect unscaled multiclass Brier score'; END IF;
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER earnings_result_validate BEFORE INSERT ON earnings_live_results
 FOR EACH ROW EXECUTE FUNCTION earnings_result_guard();
DO $$
DECLARE t TEXT;
BEGIN
 FOREACH t IN ARRAY ARRAY['earnings_historical_observations','earnings_live_predictions','earnings_live_results'] LOOP
  EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY',t);
  EXECUTE format('REVOKE ALL ON %I FROM anon,authenticated,service_role',t);
  EXECUTE format('GRANT SELECT ON %I TO anon,authenticated,service_role',t);
  EXECUTE format('CREATE POLICY %I ON %I FOR SELECT TO anon,authenticated USING(true)',t||'_read',t);
  EXECUTE format('CREATE POLICY %I ON %I FOR ALL TO service_role USING(true) WITH CHECK(true)',t||'_service',t);
  EXECUTE format('CREATE TRIGGER %I BEFORE UPDATE OR DELETE ON %I FOR EACH ROW EXECUTE FUNCTION earnings_deny_mutation()',t||'_immutable_rows',t);
  EXECUTE format('CREATE TRIGGER %I BEFORE TRUNCATE ON %I FOR EACH STATEMENT EXECUTE FUNCTION earnings_deny_mutation()',t||'_immutable_truncate',t);
 END LOOP;
END $$;
GRANT INSERT(id,company_id,period_start,period_end,guidance_id,actual_id,outcome,status,public_available_at,payload)
 ON earnings_historical_observations TO service_role;
GRANT INSERT(company_id,metric,period_start,period_end,method_version,guidance_id,historical_ids,
 p_below,p_within,p_above,announcement,publication_check,snapshot,lock_deadline) ON earnings_live_predictions TO service_role;
GRANT INSERT(prediction_id,evidence_hash,status,outcome,brier,supersedes_id,snapshot) ON earnings_live_results TO service_role;

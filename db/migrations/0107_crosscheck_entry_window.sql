-- Owner-authorized operational entry change; no probabilities/history changes.
-- Refuse to change prospective policy after the first live prediction.
-- Serialize against concurrent inserts while checking this precondition.
LOCK TABLE earnings_live_predictions IN ACCESS EXCLUSIVE MODE;
DO $$ BEGIN
 IF EXISTS(SELECT 1 FROM earnings_live_predictions) THEN
  RAISE EXCEPTION '17-day entry policy requires an empty live prediction ledger';
 END IF;
END $$;
CREATE FUNCTION earnings_lock_opening(deadline TIMESTAMPTZ,zone TEXT) RETURNS TIMESTAMPTZ
LANGUAGE sql STABLE STRICT SET search_path=pg_catalog,public,pg_temp AS $$
 SELECT ((deadline AT TIME ZONE zone)-interval '17 days') AT TIME ZONE zone
$$;
CREATE OR REPLACE FUNCTION earnings_prediction_guard() RETURNS trigger LANGUAGE plpgsql SET search_path=pg_catalog,public,pg_temp AS $$
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
 -- Preserve historical D-15 horizon, but never select not-yet-public
 -- guidance during the additional three live-entry days.
 anchor:=least(day-14,(NEW.made_at AT TIME ZONE 'America/New_York')::date);
 IF NEW.made_at>=NEW.lock_deadline OR NEW.made_at<earnings_lock_opening(NEW.lock_deadline,zone) OR NEW.period_end>=day THEN
  RAISE EXCEPTION 'Outside conservative 17-calendar-day pre-publication lock window';
 END IF;
 stamp:=(NEW.announcement#>>'{prelock_schedule_check,checked_at}')::timestamptz;
 IF stamp IS NULL OR stamp>NEW.made_at OR stamp<NEW.made_at-interval '10 minutes' OR
    coalesce(NEW.announcement->>'source_url','')='' OR coalesce(NEW.announcement->>'time_precision','')='' THEN
  RAISE EXCEPTION 'Fresh announcement check and provenance required';
 END IF;
 stamp:=(NEW.publication_check->>'checked_at')::timestamptz;
 IF NEW.publication_check->>'status' IS DISTINCT FROM 'not_observed' OR
    NEW.publication_check#>>'{sec,success}' IS DISTINCT FROM 'true' OR
    NEW.publication_check#>>'{official_ir,success}' IS DISTINCT FROM 'true' OR
    stamp IS NULL OR stamp>NEW.made_at OR stamp<NEW.made_at-interval '10 minutes' OR
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
 IF g IS NULL THEN RAISE EXCEPTION 'Guidance unavailable at original D-15 horizon or actual public cutoff'; END IF;
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
  'guidance_cutoff_exclusive',anchor,'live_entry_policy',jsonb_build_object('version','live-entry-17-calendar-days-v1','calendar_days',17,'opening',earnings_lock_opening(NEW.lock_deadline,zone)),'snapshot_version','self-contained-live-v1');
 RETURN NEW;
END $$;

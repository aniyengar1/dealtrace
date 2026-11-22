-- Owner-approved current-state policy v2. Durable source timestamps never expire.
-- Existing immutable rows, snapshots, database clocks and financial selection
-- guards remain unchanged. Old migrations and checkpoint tags are preserved.
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
 anchor:=day-14;
 IF NEW.made_at>=NEW.lock_deadline OR NEW.made_at<NEW.lock_deadline-interval '14 days' OR NEW.period_end>=day THEN
  RAISE EXCEPTION 'Outside conservative 14-day pre-publication lock window';
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

CREATE OR REPLACE FUNCTION earnings_owner_pdf_prediction_guard() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog,public,pg_temp AS $$
DECLARE retrieved TIMESTAMPTZ;
BEGIN
 IF NEW.announcement->>'verification_method' IS DISTINCT FROM 'owner_pdf_document_review_v1' THEN RETURN NEW; END IF;
 retrieved:=(NEW.announcement->>'owner_retrieved_at')::timestamptz;
 IF NEW.announcement->>'verification_status' IS DISTINCT FROM 'user_verified' OR retrieved IS NULL OR retrieved>NEW.made_at OR
    NEW.announcement->>'source_sha256' IS NULL OR NEW.announcement->>'source_sha256' !~ '^[0-9a-f]{64}$' OR
    coalesce(NEW.announcement->>'owner_retrieved_at','') !~ '(Z|[+-][0-9]{2}:[0-9]{2})$' OR coalesce(NEW.announcement->>'owner_intake_id','')='' OR coalesce(NEW.announcement->>'supplied_by','')='' OR
    NEW.announcement#>>'{prelock_schedule_check,method}' IS DISTINCT FROM 'owner_browser' THEN
  RAISE EXCEPTION 'Durable owner PDF provenance and separate current owner check required';
 END IF;
 RETURN NEW;
END $$;

CREATE FUNCTION earnings_current_state_guard() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog,public,pg_temp AS $$
DECLARE s JSONB; p JSONB; rec JSONB; d JSONB; page JSONB; observed TIMESTAMPTZ;
        oldest TIMESTAMPTZ; zone TEXT; roles TEXT[]:=ARRAY[]::text[]; ticker TEXT; host TEXT;
BEGIN
 s:=NEW.announcement->'prelock_schedule_check';p:=NEW.publication_check;
 SELECT c.ticker INTO ticker FROM companies c WHERE c.id=NEW.company_id;
 IF s->>'policy_version' IS DISTINCT FROM 'current-state-checks-v2' OR p->>'policy_version' IS DISTINCT FROM 'current-state-checks-v2' OR
    s->>'status' IS DISTINCT FROM 'unchanged' OR s->>'method' NOT IN ('automated_http','owner_browser') OR s->>'method' IS NULL OR
    s->>'company' IS DISTINCT FROM ticker OR s->>'target_start' IS DISTINCT FROM NEW.period_start::text OR s->>'target_end' IS DISTINCT FROM NEW.period_end::text OR
    s->>'source_url' IS DISTINCT FROM NEW.announcement->>'source_url' THEN
  RAISE EXCEPTION 'Explicit current schedule verification and exact target required';
 END IF;
 IF NEW.announcement#>>'{fiscal_period,start}' IS DISTINCT FROM NEW.period_start::text OR NEW.announcement#>>'{fiscal_period,end}' IS DISTINCT FROM NEW.period_end::text THEN RAISE EXCEPTION 'Durable announcement fiscal period mismatch'; END IF;
 IF s#>>'{observed_schedule,release_date}' IS DISTINCT FROM NEW.announcement->>'release_date' OR
    s#>>'{observed_schedule,timezone}' IS DISTINCT FROM NEW.announcement->>'timezone' OR
    s#>>'{observed_schedule,time_precision}' IS DISTINCT FROM NEW.announcement->>'time_precision' OR
    s#>>'{observed_schedule,release_time}' IS DISTINCT FROM NEW.announcement->>'release_time' THEN
  RAISE EXCEPTION 'Changed or unresolved schedule; append evidence and review before locking';
 END IF;
 IF NEW.announcement->>'timestamp_verified'='true' AND (s#>>'{observed_schedule,release_timestamp}' IS DISTINCT FROM NEW.announcement->>'release_timestamp' OR s#>>'{observed_schedule,timestamp_kind}' IS DISTINCT FROM NEW.announcement->>'timestamp_kind' OR s#>>'{observed_schedule,timestamp_source_quote}' IS DISTINCT FROM NEW.announcement->>'timestamp_source_quote') THEN RAISE EXCEPTION 'Unresolved current exact publication timing'; END IF;
 IF p#>>'{sec,status}' IS DISTINCT FROM 'clear' OR p#>>'{sec,success}' IS DISTINCT FROM 'true' OR
    p#>'{sec,possible_results_filings}' IS DISTINCT FROM '[]'::jsonb OR
    p#>>'{sec,manifest,url}' IS DISTINCT FROM ('https://data.sec.gov/submissions/CIK'||(SELECT cik FROM companies WHERE id=NEW.company_id)||'.json') THEN
  RAISE EXCEPTION 'Independent SEC submissions check required; absence alone is insufficient';
 END IF;
 FOREACH zone IN ARRAY ARRAY['sec','official_ir'] LOOP
  observed:=(p#>>ARRAY[zone,'checked_at'])::timestamptz;
  IF observed IS NULL OR observed>NEW.made_at OR observed<NEW.made_at-interval '10 minutes' THEN
   RAISE EXCEPTION 'Stale or future current publication component check';
  END IF;
 END LOOP;
 IF s->>'method'='automated_http' THEN
  IF s->>'verification_status' IS DISTINCT FROM 'independently_verified' OR p#>>'{official_ir,method}' IS DISTINCT FROM 'automated_http' THEN
   RAISE EXCEPTION 'Automatic checks cannot claim owner verification';
  END IF;
  RETURN NEW;
 END IF;
 rec:=s->'owner_record';d:=rec->'data';zone:=d->>'timezone';
 host:=CASE ticker WHEN 'PD' THEN 'investor.pagerduty.com' WHEN 'GTLB' THEN 'ir.gitlab.com'
 WHEN 'CRM' THEN 'investor.salesforce.com' WHEN 'CRWD' THEN 'ir.crowdstrike.com'
 WHEN 'OKTA' THEN 'investor.okta.com' WHEN 'IOT' THEN 'investors.samsara.com'
 WHEN 'MDB' THEN 'investors.mongodb.com' WHEN 'S' THEN 'investors.sentinelone.com'
 WHEN 'ADBE' THEN 'www.adobe.com' WHEN 'LULU' THEN 'corporate.lululemon.com' END;
 IF host IS NULL OR rec->>'policy_version' IS DISTINCT FROM 'current-state-checks-v2' OR
    rec#>>'{assessment,status}' IS DISTINCT FROM 'usable' OR coalesce(rec->>'id','')='' OR
    (rec->>'ingested_at')::timestamptz IS NULL OR (rec->>'ingested_at')::timestamptz>NEW.made_at OR
    d->>'company' IS DISTINCT FROM ticker OR d->>'announcement_id' IS DISTINCT FROM NEW.announcement->>'id' OR
    d->>'personally_checked' IS DISTINCT FROM 'true' OR btrim(coalesce(d->>'observer',''))='' OR btrim(coalesce(d->>'attestation',''))='' OR
    d->'contradictions' IS DISTINCT FROM '[]'::jsonb OR d->>'precision' NOT IN ('second','minute') OR d->>'precision' IS NULL OR
    zone IS NULL OR NOT EXISTS(SELECT 1 FROM pg_timezone_names WHERE name=zone) OR
    s->>'verification_status' IS DISTINCT FROM 'user_verified' OR p#>>'{official_ir,verification_status}' IS DISTINCT FROM 'user_verified' OR
    p#>>'{official_ir,method}' IS DISTINCT FROM 'owner_browser' OR
    s->>'owner_check_id' IS DISTINCT FROM rec->>'id' OR p#>>'{official_ir,owner_check_id}' IS DISTINCT FROM rec->>'id' OR
    p#>'{official_ir,owner_record}' IS DISTINCT FROM rec THEN
  RAISE EXCEPTION 'Complete attributed owner-browser current-state attestation required';
 END IF;
 IF d#>>'{schedule,event_kind}' IS DISTINCT FROM 'results_release' OR
    d#>'{schedule}' IS DISTINCT FROM s->'observed_schedule' OR
    d#>>'{publication,status}' IS DISTINCT FROM 'not_observed' OR
    d#>>'{publication,target_start}' IS DISTINCT FROM NEW.period_start::text OR d#>>'{publication,target_end}' IS DISTINCT FROM NEW.period_end::text OR
    d#>>'{publication,preliminary_results_checked}' IS DISTINCT FROM 'true' OR d#>>'{publication,pagination_complete}' IS DISTINCT FROM 'true' OR
    (d#>>'{publication,coverage_from}')::date IS NULL OR (d#>>'{publication,coverage_from}')::date>NEW.period_start OR
    (d#>>'{publication,coverage_through}')::date IS NULL OR (d#>>'{publication,coverage_through}')::date<>(NEW.made_at AT TIME ZONE zone)::date OR
    d#>>'{automation_gap,provenance}' IS DISTINCT FROM 'owner_reported' OR btrim(coalesce(d#>>'{automation_gap,reason}',''))='' OR
    split_part(d#>>'{automation_gap,url}','/',3) IS DISTINCT FROM host OR d#>>'{automation_gap,url}' NOT LIKE 'https://%' THEN
  RAISE EXCEPTION 'Owner schedule/publication coverage incomplete, changed or contradictory';
 END IF;
 IF jsonb_typeof(d->'pages') IS DISTINCT FROM 'array' OR jsonb_array_length(d->'pages')=0 THEN RAISE EXCEPTION 'Owner pages missing'; END IF;
 FOR page IN SELECT value FROM jsonb_array_elements(d->'pages') LOOP
  IF page->>'url' NOT LIKE 'https://%' OR split_part(page->>'url','/',3) IS DISTINCT FROM host OR
     (page ? 'final_url' AND (page->>'final_url' NOT LIKE 'https://%' OR split_part(page->>'final_url','/',3) IS DISTINCT FROM host)) OR
     page->>'complete' IS DISTINCT FROM 'true' OR btrim(coalesce(page->>'coverage',''))='' OR jsonb_typeof(page->'roles') IS DISTINCT FROM 'array' OR
     jsonb_array_length(page->'roles')=0 OR coalesce(page->>'checked_at','') !~ '(Z|[+-][0-9]{2}:[0-9]{2})$' THEN
   RAISE EXCEPTION 'Owner page URL, coverage or time missing';
  END IF;
  observed:=(page->>'checked_at')::timestamptz;
  IF observed>NEW.made_at OR observed>(rec->>'ingested_at')::timestamptz OR observed<NEW.made_at-interval '10 minutes' OR
     (observed AT TIME ZONE zone)<>(page->>'checked_at')::timestamp OR
     (d->>'precision'='minute' AND extract(second FROM observed)<>0) THEN RAISE EXCEPTION 'Stale, future or inconsistent owner page time'; END IF;
  oldest:=least(oldest,observed);
  IF (page->'roles') ? 'schedule' AND page->>'url' IS DISTINCT FROM NEW.announcement->>'source_url' THEN RAISE EXCEPTION 'Owner schedule URL mismatch'; END IF;
  roles:=roles||ARRAY(SELECT jsonb_array_elements_text(page->'roles'));
 END LOOP;
 IF NOT roles@>ARRAY['schedule','news_inventory','results_inventory'] OR NOT roles<@ARRAY['schedule','news_inventory','results_inventory'] OR
    (s->>'checked_at')::timestamptz IS DISTINCT FROM oldest OR (p#>>'{official_ir,checked_at}')::timestamptz IS DISTINCT FROM oldest OR
    (p->>'checked_at')::timestamptz IS DISTINCT FROM least(oldest,(p#>>'{sec,checked_at}')::timestamptz) THEN
  RAISE EXCEPTION 'Owner page roles or oldest-check timestamp do not reproduce';
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER earnings_prediction_validate_state BEFORE INSERT ON earnings_live_predictions
 FOR EACH ROW EXECUTE FUNCTION earnings_current_state_guard();

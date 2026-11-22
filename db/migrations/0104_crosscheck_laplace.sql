-- Add a distinct fixed-prior method; retain 0103 and empirical enforcement intact.
CREATE FUNCTION earnings_laplace_prediction_guard() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog,public,pg_temp AS $$
DECLARE n INTEGER; nb INTEGER; nw INTEGER; pb NUMERIC; pw NUMERIC; stamp TIMESTAMPTZ;
BEGIN
 IF NEW.method_version<>'quarter-frequency-laplace-v1' THEN RETURN NEW; END IF;
 SELECT count(*),count(*) FILTER(WHERE outcome='below'),count(*) FILTER(WHERE outcome='within')
 INTO n,nb,nw FROM earnings_historical_observations WHERE id=ANY(NEW.historical_ids);
 IF n>80 OR EXISTS(SELECT 1 FROM earnings_historical_observations WHERE id=ANY(NEW.historical_ids)
                   GROUP BY company_id HAVING count(*)>8) THEN RAISE EXCEPTION 'Laplace window exceeds eight quarters per company'; END IF;
 stamp:=(NEW.snapshot#>>'{baseline,as_of}')::timestamptz;
 IF stamp IS NULL OR stamp>NEW.made_at OR EXISTS(SELECT 1 FROM earnings_historical_observations WHERE id=ANY(NEW.historical_ids)
     AND (recorded_at>stamp OR public_available_at>stamp)) THEN RAISE EXCEPTION 'Laplace historical input unavailable at declared as-of'; END IF;
 IF NEW.snapshot#>>'{baseline,mode}'='company' THEN
  IF n<6 OR EXISTS(SELECT 1 FROM earnings_historical_observations WHERE id=ANY(NEW.historical_ids) AND company_id<>NEW.company_id) THEN
   RAISE EXCEPTION 'Laplace company rate requires six own quarters'; END IF;
 ELSIF NEW.snapshot#>>'{baseline,mode}'='pooled' THEN
  IF n<12 OR (SELECT count(DISTINCT company_id) FROM earnings_historical_observations WHERE id=ANY(NEW.historical_ids))<2 THEN
   RAISE EXCEPTION 'Laplace pooled rate requires twelve quarters from two companies'; END IF;
 ELSE RAISE EXCEPTION 'Unknown Laplace mode'; END IF;
 IF NEW.snapshot#>'{baseline,policy,prior_counts}' IS DISTINCT FROM '{"below":1,"within":1,"above":1}'::jsonb THEN
  RAISE EXCEPTION 'Laplace fixed add-one prior required'; END IF;
 -- With n<=80, denominators<=83 cannot produce a 25th-place half tie.
 pb:=round((nb+1)::numeric(50,30)/(n+3),24);pw:=round((nw+1)::numeric(50,30)/(n+3),24);
 IF NEW.p_below<>pb OR NEW.p_within<>pw OR NEW.p_above<>1-pb-pw THEN
  RAISE EXCEPTION 'Probabilities do not reproduce Laplace historical counts'; END IF;
 RETURN NEW;
END $$;
-- Alphabetically after earnings_prediction_validate: original timing, snapshot,
-- availability and immutability protections remain in force for both methods.
CREATE TRIGGER earnings_prediction_validate_laplace BEFORE INSERT ON earnings_live_predictions
 FOR EACH ROW EXECUTE FUNCTION earnings_laplace_prediction_guard();

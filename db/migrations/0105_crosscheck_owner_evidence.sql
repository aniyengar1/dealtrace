-- A fresh local hash check must never turn stale owner retrieval into fresh source evidence.
CREATE FUNCTION earnings_owner_pdf_prediction_guard() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog,public,pg_temp AS $$
DECLARE retrieved TIMESTAMPTZ;
BEGIN
 IF NEW.announcement->>'verification_method'<>'owner_pdf_document_review_v1' OR
    NEW.announcement->>'verification_method' IS NULL THEN RETURN NEW; END IF;
 retrieved:=(NEW.announcement->>'owner_retrieved_at')::timestamptz;
 IF NEW.announcement->>'verification_status' IS DISTINCT FROM 'user_verified' OR
    retrieved IS NULL OR retrieved>NEW.made_at OR retrieved<NEW.made_at-interval '10 minutes' OR
    NEW.announcement->>'source_sha256' !~ '^[0-9a-f]{64}$' OR NEW.announcement->>'source_sha256' IS NULL OR
    coalesce(NEW.announcement->>'owner_intake_id','')='' OR coalesce(NEW.announcement->>'supplied_by','')='' THEN
  RAISE EXCEPTION 'Fresh owner source retrieval and PDF provenance required; local hashing is not source refresh';
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER earnings_prediction_validate_owner_pdf BEFORE INSERT ON earnings_live_predictions
 FOR EACH ROW EXECUTE FUNCTION earnings_owner_pdf_prediction_guard();

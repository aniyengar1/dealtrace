"""Part C validation: submit Splunk + Zendesk's full extraction (every
chunk/section the live pipeline calls) as one Vertex batch job, and
compare the output field-for-field against their already-completed live
runs (data/output/runs/20261113T001420Z_splunk_gemini-3.6-flash_v12 and
20261113T001948Z_zendesk_gemini-3.6-flash_v12).

    python -m src.batch_test submit     # writes job metadata to /tmp, prints job name
    python -m src.batch_test poll <job_name> <dest_uri>

Deliberately ignores the per-chunk content-hash cache (this is a fresh
model/mode combination -- "batch" -- that cache was never populated for,
so every request here is a genuinely new call regardless).
"""

import json
import sys
from pathlib import Path

from src import extract
from src.bulk_run import (
    _build_batch_request_body,
    download_batch_results,
    poll_batch_job,
    submit_batch_job,
)
from src.schemas import BackgroundExtraction, ValuationExtraction

BUCKET = "just-rhythm-506202-j8-dealtrace-batch"
MODEL = "gemini-3.6-flash"
DATA_SECTIONS = Path(__file__).resolve().parent.parent / "data" / "sections"

# (slug, section_key, schema, target_chunks) -- mirrors run.py's
# SECTION_SCHEMAS/OPINION_SCHEMA dispatch and SECTION_TARGET_CHUNKS
# exactly, so the chunk boundaries (and therefore the prompts) match the
# live run call-for-call.
PLAN = [
    ("splunk", "background_of_the_merger", BackgroundExtraction, 3),
    ("splunk", "opinion_of_qatalyst_partners_lp", ValuationExtraction, None),
    ("splunk", "opinion_of_morgan_stanley_co_llc", ValuationExtraction, None),
    ("zendesk", "background_of_the_merger", BackgroundExtraction, 3),
    ("zendesk", "opinion_of_qatalyst_partners_lp", ValuationExtraction, None),
    ("zendesk", "opinion_of_goldman_sachs_co_llc", ValuationExtraction, None),
]


def build_requests() -> list[dict]:
    requests = []
    for slug, section_key, schema, target_chunks in PLAN:
        section = json.loads((DATA_SECTIONS / slug / f"{section_key}.json").read_text())
        paragraphs = section["paragraphs"]
        chunks = (
            extract.chunk_paragraphs_by_count(paragraphs, target_chunks)
            if target_chunks
            else extract.chunk_paragraphs(paragraphs)
        )
        for i, chunk in enumerate(chunks):
            prompt = extract._build_prompt(chunk)
            body = _build_batch_request_body(prompt, schema, MODEL)
            requests.append({"meta": {"slug": slug, "section_key": section_key, "chunk": i, "schema": schema.__name__}, "body": body})
    return requests


def cmd_submit() -> None:
    requests = build_requests()
    print(f"Built {len(requests)} requests across {len(PLAN)} sections for 2 deals.")
    meta_path = Path("/tmp/dealtrace_batch_test_meta.json")
    meta_path.write_text(json.dumps([r["meta"] for r in requests], indent=2))
    job, dest_uri = submit_batch_job(BUCKET, "splunk-zendesk-test", [r["body"] for r in requests], MODEL)
    print(f"job_name={job.name}")
    print(f"dest_uri={dest_uri}")
    print(f"state={job.state}")
    Path("/tmp/dealtrace_batch_test_job.json").write_text(json.dumps({"job_name": job.name, "dest_uri": dest_uri}, indent=2))


def cmd_poll() -> None:
    info = json.loads(Path("/tmp/dealtrace_batch_test_job.json").read_text())
    import time

    start = time.monotonic()
    job = poll_batch_job(info["job_name"], timeout_seconds=3600.0)
    elapsed = time.monotonic() - start
    print(f"final_state={job.state}")
    print(f"elapsed_seconds={elapsed:.0f}")
    if str(job.state).endswith("JOB_STATE_SUCCEEDED"):
        results = download_batch_results(info["dest_uri"], "splunk-zendesk-test")
        out_path = Path("/tmp/dealtrace_batch_test_results.json")
        out_path.write_text(json.dumps(results, indent=2, default=str))
        print(f"downloaded {len(results)} result lines -> {out_path}")
    else:
        print(f"error={job.error}")


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in ("submit", "poll"):
        raise SystemExit("Usage: python -m src.batch_test submit|poll")
    if sys.argv[1] == "submit":
        cmd_submit()
    else:
        cmd_poll()

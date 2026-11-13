"""Bulk LLM extraction over deal_candidates (background section only).

    python -m src.bulk_run --pilot 10                      # live path
    python -m src.bulk_run --pilot 10 --mode batch          # batch path
    python -m src.bulk_run                                  # full run (hard stops apply)

No validation, no DB load here -- those happen in a later pass over
whatever this writes to data/output/bulk_runs/, same separation of
concerns as the single-deal pipeline's own extract/validate split.

Queue order: classification='public_company_acquisition', then DEFM14A ->
SC 14D9 -> S-4 -> SC TO-T, newest filed_date first within each tier.
Candidates without a found background section, or with one over
MAX_BACKGROUND_WORDS, are skipped and logged -- never silently dropped.
(SC TO-T rows with a matching SC 14D9 were already folded into that SC
14D9 row by src.classify, so every remaining SC TO-T row here genuinely
has no better document to use.)

Resumable two ways: a per-candidate result file in BULK_OUTPUT_DIR means
a re-run skips already-done candidates outright (no new spend); within a
candidate, extract.py's own per-chunk content-hash cache means a re-run
after a partial failure never re-pays for a chunk already extracted.

Hard stops (checked before each new candidate starts, live path; before
each new batch job, batch path): BULK_SPEND_CAP_USD and BULK_DEADLINE.
Spend tracking is read from extract.session_cost_summary(), which is
never reset mid-run, so it reflects the TRUE total across every worker
thread for this process -- see extract.py's Usage/session-call-log
design. Unknown pricing for any call is itself treated as a hard stop
(never silently assumed free or billed at a guessed rate).
"""

import argparse
import json
import logging
import os
import statistics
import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from google.genai import _transformers, types
from pydantic import BaseModel

from src import extract, sections
from src.discover import DOC_CACHE_DIR
from src.env import load_env
from src.load_db import connect
from src.schemas import BackgroundExtraction

load_env()

MAX_BACKGROUND_WORDS = 25000
BULK_OUTPUT_DIR = Path(__file__).resolve().parent.parent / "data" / "output" / "bulk_runs"
BULK_LOG_DIR = Path(__file__).resolve().parent.parent / "data" / "output" / "bulk_logs"
BULK_LOG_EVERY = 10
# Safety-check cadence and auto-pause thresholds, checked over a rolling
# window of the most recently completed deals (not the whole run so far)
# -- a problem introduced partway through should trip this quickly, not
# get diluted by a large clean history before it.
SAFETY_CHECK_EVERY = 50
MAX_ROLLING_FAILURE_RATE = 0.10
MIN_ROLLING_QUOTE_MATCH_MEDIAN = 0.90
# "Batch jobs must not be submitted after BULK_DEADLINE minus this many
# hours; anything after that goes through the live path" -- batch has no
# turnaround guarantee, so this margin protects against a batch job that
# never finishes before the credit expires.
BATCH_SUBMIT_MARGIN_HOURS = 36
BATCH_POLL_INTERVAL_SECONDS = 30.0

_FORM_PRIORITY_SQL = """
  CASE
    WHEN primary_form_type LIKE 'DEFM14A%' THEN 0
    WHEN primary_form_type LIKE 'SC 14D9%' THEN 1
    WHEN primary_form_type LIKE 'S-4%' THEN 2
    WHEN primary_form_type LIKE 'SC TO-T%' THEN 3
    ELSE 4
  END
"""

_CANDIDATE_COLUMNS = [
    "id",
    "target_cik",
    "target_name",
    "primary_form_type",
    "primary_accession",
    "primary_filed_date",
    "background_section_found",
    "background_word_count",
]


# --- logging -----------------------------------------------------------------


def setup_logging() -> logging.Logger:
    """Logs to both stdout and a timestamped file in BULK_LOG_DIR -- this
    is meant to run for hours under caffeinate in the background, so the
    file is the durable record even if the terminal that launched it is
    long gone by the time anyone checks on it.
    """
    BULK_LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_path = BULK_LOG_DIR / f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}_bulk_run.log"
    logger = logging.getLogger("bulk_run")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    fmt = logging.Formatter("%(asctime)s %(message)s")
    file_handler = logging.FileHandler(log_path)
    file_handler.setFormatter(fmt)
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(fmt)
    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)
    logger.info(f"[bulk] logging to {log_path}")
    return logger


_logger = logging.getLogger("bulk_run")


# --- adaptive concurrency ----------------------------------------------------


class AdaptiveConcurrency:
    """Starts at `initial`; raises to `high` once `raise_after_seconds`
    have passed with zero 429s recorded anywhere in this process. Any new
    429 drops capacity by 1 (floor `floor`) immediately and restarts the
    clean-time clock, so a single noisy patch doesn't get immediately
    followed by another raise.

    acquire()/release() gate actual concurrent work; the ThreadPoolExecutor
    itself is sized to `high` so there are always enough OS threads to
    reach full capacity once raised, but at most `capacity` of them are
    ever let through the gate at once.
    """

    def __init__(self, initial: int, high: int, floor: int = 1, raise_after_seconds: float = 1800.0):
        self._capacity = initial
        self._high = high
        self._floor = floor
        self._raise_after = raise_after_seconds
        self._cond = threading.Condition()
        self._in_use = 0
        self._clean_since = time.monotonic()
        self._last_checked_ts = time.time()
        self._raised_since_last_backoff = False

    def acquire(self) -> None:
        with self._cond:
            while self._in_use >= self._capacity:
                self._cond.wait(timeout=1.0)
            self._in_use += 1

    def release(self) -> None:
        with self._cond:
            self._in_use -= 1
            self._cond.notify_all()

    @property
    def capacity(self) -> int:
        with self._cond:
            return self._capacity

    def tick(self) -> Optional[str]:
        """Call periodically from a monitor thread. Returns a short
        description of what changed, or None."""
        now_ts = time.time()
        new_events = extract.rate_limit_events_since(self._last_checked_ts)
        self._last_checked_ts = now_ts
        with self._cond:
            if new_events > 0:
                if self._capacity > self._floor:
                    self._capacity -= 1
                self._clean_since = time.monotonic()
                self._raised_since_last_backoff = False
                self._cond.notify_all()
                return f"backed off to {self._capacity} ({new_events} 429(s) observed)"
            if (
                not self._raised_since_last_backoff
                and self._capacity < self._high
                and (time.monotonic() - self._clean_since) >= self._raise_after
            ):
                self._capacity = self._high
                self._raised_since_last_backoff = True
                self._cond.notify_all()
                return f"raised to {self._capacity} ({self._raise_after / 60:.0f} clean minutes)"
        return None


# --- queue -----------------------------------------------------------------


def queue_candidates(conn) -> list[dict]:
    rows = conn.execute(
        f"""
        SELECT {", ".join(_CANDIDATE_COLUMNS)}
        FROM deal_candidates
        WHERE classification = 'public_company_acquisition'
        ORDER BY {_FORM_PRIORITY_SQL}, primary_filed_date DESC
        """
    ).fetchall()
    return [dict(zip(_CANDIDATE_COLUMNS, row)) for row in rows]


def classify_for_queue(row: dict) -> tuple[bool, str]:
    """Returns (should_process, skip_reason). skip_reason is "" when
    should_process is True."""
    if not row["background_section_found"]:
        return False, "no background section found"
    wc = row["background_word_count"]
    if wc is not None and wc > MAX_BACKGROUND_WORDS:
        return False, f"background section too long ({wc} words > {MAX_BACKGROUND_WORDS})"
    return True, ""


def _accession_nodash(accession: str) -> str:
    return accession.replace("-", "")


def load_cached_html(target_cik: str, primary_accession: str) -> Optional[str]:
    path = DOC_CACHE_DIR / f"{target_cik}_{_accession_nodash(primary_accession)}.html"
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8", errors="replace")


def result_path(target_cik: str, primary_accession: str) -> Path:
    BULK_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    return BULK_OUTPUT_DIR / f"{target_cik}_{_accession_nodash(primary_accession)}.json"


# --- spend / deadline hard stops --------------------------------------------


def spend_cap_hit(cap_usd: float, calibration_multiplier: float) -> tuple[bool, str]:
    summary = extract.session_cost_summary()
    if summary["cost_unknown_for_some_calls"]:
        return True, "pricing unknown for at least one call -- treating as a hard stop"
    spent = summary["total_cost_usd"] * calibration_multiplier
    if spent >= cap_usd:
        return True, f"spend cap hit (${spent:.2f} >= ${cap_usd:.2f} at calibration x{calibration_multiplier})"
    return False, ""


def deadline_hit(deadline: Optional[datetime]) -> bool:
    return deadline is not None and datetime.now(timezone.utc) >= deadline


# --- rolling safety check / auto-pause ---------------------------------------


def rolling_quality_check(recent_done_results: list[dict]) -> dict:
    """Free (no LLM, no new fetch) validation+sanity re-check of a window
    of recently-completed results -- the same logic bulk_quality_check.py
    runs standalone, applied here as an inline, continuous safety net.
    Deferred import to avoid a circular import (bulk_quality_check itself
    imports from this module).
    """
    from src.bulk_quality_check import check_one

    reports = [check_one(r) for r in recent_done_results]
    rates = [r["validation_pass_rate"] for r in reports if r.get("validation_pass_rate") is not None]
    quote_rates = [r["quote_match_rate"] for r in reports if r.get("quote_match_rate") is not None]
    failure_rate = (1 - statistics.mean(rates)) if rates else None
    quote_match_median = statistics.median(quote_rates) if quote_rates else None
    return {"n": len(reports), "failure_rate": failure_rate, "quote_match_median": quote_match_median}


def check_auto_pause(quality: dict) -> Optional[str]:
    """None if nothing is wrong; otherwise the reason to pause."""
    if quality["failure_rate"] is not None and quality["failure_rate"] > MAX_ROLLING_FAILURE_RATE:
        return (
            f"rolling failure rate {quality['failure_rate']:.1%} > {MAX_ROLLING_FAILURE_RATE:.0%} "
            f"over the last {quality['n']} deals"
        )
    if quality["quote_match_median"] is not None and quality["quote_match_median"] < MIN_ROLLING_QUOTE_MATCH_MEDIAN:
        return (
            f"rolling quote-match median {quality['quote_match_median']:.1%} < "
            f"{MIN_ROLLING_QUOTE_MATCH_MEDIAN:.0%} over the last {quality['n']} deals"
        )
    return None


def write_pause_reason(reason: str, stats: dict) -> Path:
    BULK_LOG_DIR.mkdir(parents=True, exist_ok=True)
    path = BULK_LOG_DIR / "PAUSED.json"
    path.write_text(
        json.dumps(
            {"reason": reason, "paused_at": datetime.now(timezone.utc).isoformat(), **stats},
            indent=2,
            default=str,
        )
    )
    return path


# --- live path ---------------------------------------------------------------


def process_candidate_live(row: dict, model: str) -> dict:
    """Resumable: returns the cached result immediately if this candidate
    already has a result file on disk, without touching the LLM."""
    out_path = result_path(row["target_cik"], row["primary_accession"])
    if out_path.exists():
        return json.loads(out_path.read_text())

    should_process, skip_reason = classify_for_queue(row)
    if not should_process:
        result = {"status": "skipped", "reason": skip_reason, "row": row, "cost_usd": 0.0}
        out_path.write_text(json.dumps(result, indent=2, default=str))
        return result

    html = load_cached_html(row["target_cik"], row["primary_accession"])
    if html is None:
        result = {"status": "skipped", "reason": "cached document missing on disk", "row": row, "cost_usd": 0.0}
        out_path.write_text(json.dumps(result, indent=2, default=str))
        return result

    try:
        found = sections.extract_sections(html)
        section = found.get("background_of_the_merger")
        if section is None:
            result = {"status": "skipped", "reason": "section finder found nothing on re-check", "row": row, "cost_usd": 0.0}
            out_path.write_text(json.dumps(result, indent=2, default=str))
            return result

        instance, usage = extract.extract_section(section["paragraphs"], BackgroundExtraction, model=model)
        provider = extract._resolve_provider()
        cost_usd = extract._compute_cost_usd(provider, model, usage, mode="live")
        result = {
            "status": "done",
            "row": row,
            "model": model,
            "provider": provider,
            "n_events": len(instance.events),
            "n_proposals": len(instance.proposals),
            "usage": {
                "prompt_tokens": usage.prompt_tokens,
                "output_tokens": usage.output_tokens,
                "thinking_tokens": usage.thinking_tokens,
                "calls": usage.calls,
                "cache_hits": usage.cache_hits,
            },
            "cost_usd": cost_usd,
            "events": [e.model_dump(mode="json") for e in instance.events],
            "proposals": [p.model_dump(mode="json") for p in instance.proposals],
        }
    except extract.ExtractionError as exc:
        # An expected, already-understood failure mode (daily quota,
        # malformed-output retries exhausted, transient-retry budget
        # exhausted) -- recorded like any other failed candidate, not an
        # auto-pause trigger on its own.
        result = {"status": "failed", "reason": str(exc), "row": row, "cost_usd": 0.0}
        out_path.write_text(json.dumps(result, indent=2, default=str))
        return result
    except Exception as exc:
        # Anything else is, by definition, a failure mode this pipeline
        # hasn't seen and doesn't have a specific handler for -- the
        # caller treats this as the "unexpected error class" auto-pause
        # trigger. Deliberately NOT written to disk: unlike a genuine
        # extraction failure (same input, same deterministic malformed
        # output every time), there's no reason to believe retrying this
        # candidate after whatever caused the pause gets investigated
        # would fail the same way, so a resume should retry it fresh
        # rather than permanently blacklist it on one occurrence.
        return {"status": "error", "reason": f"{type(exc).__name__}: {exc}", "row": row, "cost_usd": 0.0}

    out_path.write_text(json.dumps(result, indent=2, default=str))
    return result


@dataclass
class BulkStats:
    lock: threading.Lock = field(default_factory=threading.Lock)
    done: int = 0
    failed: int = 0
    skipped: int = 0
    errors: int = 0
    start_time: float = field(default_factory=time.monotonic)

    def record(self, status: str) -> int:
        with self.lock:
            if status == "done":
                self.done += 1
            elif status == "failed":
                self.failed += 1
            elif status == "error":
                self.errors += 1
            else:
                self.skipped += 1
            return self.done + self.failed + self.skipped + self.errors


def run_bulk_live(
    *,
    model: str,
    limit: Optional[int] = None,
    concurrency: int = 4,
    concurrency_high: int = 6,
    spend_cap_usd: float = 260.0,
    calibration_multiplier: float = 1.0,
    deadline: Optional[datetime] = None,
    logger: Optional[logging.Logger] = None,
) -> dict:
    log = logger or _logger
    extract.reset_session_calls()
    with connect() as conn:
        candidates = queue_candidates(conn)
    log.info(f"[bulk] queued {len(candidates)} public_company_acquisition candidates")

    stats = BulkStats()
    skip_log: list[dict] = []
    stop_event = threading.Event()
    stop_reason: list[str] = []
    gate = AdaptiveConcurrency(initial=concurrency, high=concurrency_high)
    since_last_safety_check: list[dict] = []
    safety_lock = threading.Lock()

    def monitor_loop() -> None:
        while not stop_event.is_set():
            change = gate.tick()
            if change:
                log.info(f"[bulk] concurrency {change}")
            hit, reason = spend_cap_hit(spend_cap_usd, calibration_multiplier)
            if hit:
                stop_reason.append(reason)
                log.warning(f"[bulk] STOPPING: {reason}")
                stop_event.set()
                break
            if deadline_hit(deadline):
                stop_reason.append(f"deadline reached ({deadline.isoformat()})")
                log.warning(f"[bulk] STOPPING: deadline reached ({deadline.isoformat()})")
                stop_event.set()
                break
            time.sleep(15.0)

    monitor_thread = threading.Thread(target=monitor_loop, daemon=True)
    monitor_thread.start()

    def worker(row: dict) -> dict:
        if stop_event.is_set():
            return {"status": "skipped", "reason": "stopped", "row": row, "cost_usd": 0.0}
        gate.acquire()
        try:
            return process_candidate_live(row, model)
        finally:
            gate.release()

    attempted: list[dict] = []
    with ThreadPoolExecutor(max_workers=concurrency_high) as pool:
        futures = {}
        submitted = 0
        for row in candidates:
            if limit is not None and submitted >= limit:
                break
            should_process, reason = classify_for_queue(row)
            if not should_process:
                stats.record("skipped")
                skip_log.append({"target_cik": row["target_cik"], "accession": row["primary_accession"], "reason": reason})
                continue
            futures[pool.submit(worker, row)] = row
            submitted += 1

        for future in as_completed(futures):
            row = futures[future]
            result = future.result()
            n = stats.record(result["status"])
            attempted.append(result)

            if result["status"] == "skipped":
                skip_log.append(
                    {"target_cik": row["target_cik"], "accession": row["primary_accession"], "reason": result.get("reason")}
                )
            elif result["status"] == "error":
                reason = f"unexpected error class: {result['reason']}"
                stop_reason.append(reason)
                log.error(f"[bulk] STOPPING: {reason}")
                write_pause_reason(
                    reason,
                    {"done": stats.done, "failed": stats.failed, "skipped": stats.skipped, "errors": stats.errors},
                )
                stop_event.set()
            elif result["status"] == "done":
                with safety_lock:
                    since_last_safety_check.append(result)
                    if len(since_last_safety_check) >= SAFETY_CHECK_EVERY:
                        window = list(since_last_safety_check)
                        since_last_safety_check.clear()
                        quality = rolling_quality_check(window)
                        log.info(
                            f"[bulk] safety check (n={quality['n']}): "
                            f"failure_rate={quality['failure_rate']}, "
                            f"quote_match_median={quality['quote_match_median']}"
                        )
                        pause_reason = check_auto_pause(quality)
                        if pause_reason:
                            log.error(f"[bulk] AUTO-PAUSE: {pause_reason}")
                            write_pause_reason(
                                pause_reason,
                                {
                                    "done": stats.done,
                                    "failed": stats.failed,
                                    "skipped": stats.skipped,
                                    "errors": stats.errors,
                                    "quality": quality,
                                },
                            )
                            stop_reason.append(pause_reason)
                            stop_event.set()

            if n % BULK_LOG_EVERY == 0:
                elapsed_hr = (time.monotonic() - stats.start_time) / 3600
                cost_summary = extract.session_cost_summary()
                spent = cost_summary["total_cost_usd"] * calibration_multiplier
                n_attempted = stats.done + stats.failed
                rate = n_attempted / elapsed_hr if elapsed_hr > 0 else 0.0
                per_deal = spent / n_attempted if n_attempted > 0 else 0.0
                log.info(
                    f"[bulk] done={stats.done} failed={stats.failed} skipped={stats.skipped} errors={stats.errors} "
                    f"concurrency={gate.capacity} deals/hr={rate:.1f} spent=${spent:.2f} $/deal=${per_deal:.4f}"
                )

    stop_event.set()
    return {
        "done": stats.done,
        "failed": stats.failed,
        "skipped": stats.skipped,
        "errors": stats.errors,
        "skip_log": skip_log,
        "stop_reason": stop_reason[0] if stop_reason else None,
        "cost_summary": extract.session_cost_summary(),
        "results": attempted,
    }


# --- batch path --------------------------------------------------------------


def _build_batch_request_body(prompt: str, schema: type[BaseModel], model: str) -> dict:
    """The exact wire format Vertex's live generateContent uses (confirmed
    by intercepting a real live call's outgoing request body for this
    model) -- _transformers.t_schema is the SDK's own (private, but
    verified-by-comparison) pydantic-to-Gemini-JSON-Schema converter, so
    this never hand-guesses the schema encoding.
    """
    schema_dict = _transformers.t_schema(None, schema).model_dump(mode="json", exclude_none=True, by_alias=True)
    return {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": extract.GENERATION_TEMPERATURE,
            "responseMimeType": "application/json",
            "responseSchema": schema_dict,
        },
    }


def write_batch_jsonl(requests: list[dict], out_path: Path) -> None:
    with out_path.open("w") as f:
        for req in requests:
            f.write(json.dumps({"request": req}) + "\n")


def gcs_upload(local_path: Path, gcs_uri: str) -> None:
    subprocess.run(["gcloud", "storage", "cp", str(local_path), gcs_uri], check=True, capture_output=True, text=True)


def gcs_download(gcs_uri: str, local_path: Path) -> None:
    subprocess.run(["gcloud", "storage", "cp", gcs_uri, str(local_path)], check=True, capture_output=True, text=True)


def gcs_ls(gcs_prefix: str) -> list[str]:
    result = subprocess.run(["gcloud", "storage", "ls", gcs_prefix], check=True, capture_output=True, text=True)
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def submit_batch_job(bucket: str, job_tag: str, requests: list[dict], model: str) -> "types.BatchJob":
    input_local = Path(f"/tmp/dealtrace_batch_{job_tag}_input.jsonl")
    write_batch_jsonl(requests, input_local)
    input_uri = f"gs://{bucket}/batch/{job_tag}/input.jsonl"
    dest_uri = f"gs://{bucket}/batch/{job_tag}/output/"
    gcs_upload(input_local, input_uri)

    client = extract._get_client()
    job = client.batches.create(
        model=model,
        src=input_uri,
        config=types.CreateBatchJobConfig(display_name=f"dealtrace-{job_tag}", dest=dest_uri),
    )
    return job, dest_uri


def poll_batch_job(job_name: str, timeout_seconds: float = 3600.0) -> "types.BatchJob":
    client = extract._get_client()
    start = time.monotonic()
    terminal_states = {
        types.JobState.JOB_STATE_SUCCEEDED,
        types.JobState.JOB_STATE_FAILED,
        types.JobState.JOB_STATE_CANCELLED,
        types.JobState.JOB_STATE_PAUSED,
    }
    while True:
        job = client.batches.get(name=job_name)
        if job.state in terminal_states:
            return job
        if time.monotonic() - start > timeout_seconds:
            return job
        time.sleep(BATCH_POLL_INTERVAL_SECONDS)


def download_batch_results(dest_uri: str, job_tag: str) -> list[dict]:
    files = [f for f in gcs_ls(dest_uri.rstrip("/") + "/**") if f.endswith(".jsonl")]
    results = []
    for i, gcs_path in enumerate(files):
        local_path = Path(f"/tmp/dealtrace_batch_{job_tag}_output_{i}.jsonl")
        gcs_download(gcs_path, local_path)
        with local_path.open() as f:
            for line in f:
                line = line.strip()
                if line:
                    results.append(json.loads(line))
    return results


def batch_should_be_used(deadline: Optional[datetime]) -> bool:
    if deadline is None:
        return True
    return datetime.now(timezone.utc) < (deadline - timedelta(hours=BATCH_SUBMIT_MARGIN_HOURS))


# --- CLI ---------------------------------------------------------------------


def _parse_deadline(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    return datetime.fromisoformat(value).astimezone(timezone.utc)


def main() -> None:
    parser = argparse.ArgumentParser(description="Bulk extraction over deal_candidates.")
    parser.add_argument("--pilot", type=int, default=None, help="Process only N attempted candidates")
    parser.add_argument("--model", default="gemini-3.6-flash", help="Explicit model (default: the locked model)")
    parser.add_argument("--concurrency", type=int, default=int(os.environ.get("BULK_CONCURRENCY", 4)))
    parser.add_argument(
        "--concurrency-high", type=int, default=int(os.environ.get("BULK_CONCURRENCY_HIGH", 6)),
        help="Ceiling the adaptive controller may raise to after a clean period",
    )
    parser.add_argument("--spend-cap-usd", type=float, default=float(os.environ.get("BULK_SPEND_CAP_USD", 260.0)))
    parser.add_argument("--calibration-multiplier", type=float, default=1.0)
    parser.add_argument("--deadline", default=os.environ.get("BULK_DEADLINE"))
    parser.add_argument("--mode", choices=["live", "batch"], default="live")
    args = parser.parse_args()

    log = setup_logging()
    deadline = _parse_deadline(args.deadline)
    log.info(
        f"[bulk] starting: model={args.model} concurrency={args.concurrency}->{args.concurrency_high} "
        f"spend_cap=${args.spend_cap_usd} calibration=x{args.calibration_multiplier} deadline={deadline}"
    )
    if args.mode == "live":
        result = run_bulk_live(
            model=args.model,
            limit=args.pilot,
            concurrency=args.concurrency,
            concurrency_high=args.concurrency_high,
            spend_cap_usd=args.spend_cap_usd,
            calibration_multiplier=args.calibration_multiplier,
            deadline=deadline,
            logger=log,
        )
        log.info(json.dumps({k: v for k, v in result.items() if k != "results"}, indent=2, default=str))
    else:
        raise SystemExit("--mode batch: use src.batch_test for the Part C gold-deal test; full batch-mode queue integration isn't wired into main() yet.")


if __name__ == "__main__":
    main()

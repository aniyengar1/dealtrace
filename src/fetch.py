"""Fetch a company's DEFM14A merger proxy from SEC EDGAR.

Looks up the company CIK via EDGAR's full-text company search, then uses the
data.sec.gov submissions API to locate the DEFM14A filing. Downloads the
primary HTML document to data/raw/ along with a sidecar JSON manifest
(accession number, source URL, fetch time, SHA-256 hash).

Respects SEC fair-access rules: identifying User-Agent, max 2 req/s,
exponential backoff on 429/5xx, and a local cache so repeat runs don't
re-download.
"""

import hashlib
import json
import time
from dataclasses import dataclass
from pathlib import Path

import requests

USER_AGENT = "DealTrace research anirudhiyengar.06@gmail.com"
MIN_REQUEST_INTERVAL = 0.5  # seconds -> max 2 req/s
MAX_RETRIES = 5
BACKOFF_BASE = 1.5

DATA_RAW = Path(__file__).resolve().parent.parent / "data" / "raw"

_last_request_time = 0.0


class FetchError(RuntimeError):
    pass


@dataclass
class FetchResult:
    company: str
    cik: str
    accession_number: str
    form_type: str
    filing_date: str
    primary_document: str
    source_url: str
    html_path: Path
    manifest_path: Path
    sha256: str
    fetched_at: str
    from_cache: bool


def _throttled_get(url: str, **kwargs) -> requests.Response:
    """GET with a shared rate limiter (<=2 req/s) and retry/backoff on 429/5xx."""
    global _last_request_time

    headers = kwargs.pop("headers", {})
    headers.setdefault("User-Agent", USER_AGENT)

    last_exc: Exception | None = None
    for attempt in range(MAX_RETRIES):
        elapsed = time.monotonic() - _last_request_time
        if elapsed < MIN_REQUEST_INTERVAL:
            time.sleep(MIN_REQUEST_INTERVAL - elapsed)

        try:
            response = requests.get(url, headers=headers, timeout=30, **kwargs)
        except requests.RequestException as exc:
            last_exc = exc
            response = None
        finally:
            _last_request_time = time.monotonic()

        if response is not None:
            if response.status_code == 200:
                return response
            if response.status_code not in (429, 500, 502, 503, 504):
                response.raise_for_status()
            last_exc = requests.HTTPError(
                f"{response.status_code} for {url}", response=response
            )

        sleep_time = BACKOFF_BASE ** attempt
        time.sleep(sleep_time)

    raise FetchError(f"Failed to fetch {url} after {MAX_RETRIES} attempts") from last_exc


def _lookup_cik(company_name: str) -> tuple[str, str]:
    """Look up a 10-digit zero-padded CIK and canonical name via EDGAR company search."""
    url = (
        "https://www.sec.gov/cgi-bin/browse-edgar"
        f"?action=getcompany&company={company_name}&type=DEFM14A"
        "&dateb=&owner=include&count=40&output=atom"
    )
    response = _throttled_get(url)

    import re

    text = response.text
    cik_match = re.search(r"<cik>(\d+)</cik>", text)
    name_match = re.search(r"<conformed-name>([^<]+)</conformed-name>", text)
    if not cik_match:
        raise FetchError(f"Could not find CIK for company '{company_name}'")

    cik = cik_match.group(1).zfill(10)
    name = name_match.group(1).strip() if name_match else company_name
    return cik, name


def _find_defm14a(cik: str) -> dict:
    """Use the data.sec.gov submissions API to find the DEFM14A filing."""
    url = f"https://data.sec.gov/submissions/CIK{cik}.json"
    response = _throttled_get(url)
    submissions = response.json()

    recent = submissions["filings"]["recent"]
    for i, form in enumerate(recent["form"]):
        if form == "DEFM14A":
            return {
                "accession_number": recent["accessionNumber"][i],
                "filing_date": recent["filingDate"][i],
                "primary_document": recent["primaryDocument"][i],
                "form_type": form,
            }

    raise FetchError(f"No DEFM14A filing found for CIK {cik}")


def fetch_defm14a(company_name: str, force: bool = False) -> FetchResult:
    """Fetch the DEFM14A for a given company name, caching to data/raw/."""
    DATA_RAW.mkdir(parents=True, exist_ok=True)

    cik, canonical_name = _lookup_cik(company_name)
    filing = _find_defm14a(cik)

    accession_plain = filing["accession_number"]
    accession_nodash = accession_plain.replace("-", "")
    primary_document = filing["primary_document"]

    source_url = (
        f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/"
        f"{accession_nodash}/{primary_document}"
    )

    slug = canonical_name.lower().replace(" ", "_").replace(".", "")
    html_path = DATA_RAW / f"{slug}_defm14a.html"
    manifest_path = DATA_RAW / f"{slug}_defm14a.manifest.json"

    if html_path.exists() and manifest_path.exists() and not force:
        manifest = json.loads(manifest_path.read_text())
        return FetchResult(
            company=canonical_name,
            cik=cik,
            accession_number=accession_plain,
            form_type=filing["form_type"],
            filing_date=filing["filing_date"],
            primary_document=primary_document,
            source_url=source_url,
            html_path=html_path,
            manifest_path=manifest_path,
            sha256=manifest["sha256"],
            fetched_at=manifest["fetched_at"],
            from_cache=True,
        )

    response = _throttled_get(source_url)
    html_bytes = response.content
    sha256 = hashlib.sha256(html_bytes).hexdigest()
    fetched_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    html_path.write_bytes(html_bytes)

    manifest = {
        "company": canonical_name,
        "cik": cik,
        "accession_number": accession_plain,
        "form_type": filing["form_type"],
        "filing_date": filing["filing_date"],
        "primary_document": primary_document,
        "source_url": source_url,
        "fetched_at": fetched_at,
        "sha256": sha256,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2))

    return FetchResult(
        company=canonical_name,
        cik=cik,
        accession_number=accession_plain,
        form_type=filing["form_type"],
        filing_date=filing["filing_date"],
        primary_document=primary_document,
        source_url=source_url,
        html_path=html_path,
        manifest_path=manifest_path,
        sha256=sha256,
        fetched_at=fetched_at,
        from_cache=False,
    )


if __name__ == "__main__":
    result = fetch_defm14a("splunk")
    print(f"Company: {result.company} (CIK {result.cik})")
    print(f"Accession: {result.accession_number}, filed {result.filing_date}")
    print(f"Source: {result.source_url}")
    print(f"Saved to: {result.html_path} (sha256={result.sha256[:16]}...)")
    print(f"From cache: {result.from_cache}")

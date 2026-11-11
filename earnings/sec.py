"""SEC-only cached transport, sharing src.fetch's limiter and retry implementation."""
from datetime import datetime, timezone
import hashlib
import json
import time
from pathlib import Path
from urllib.parse import urlparse
import fcntl
import src.fetch as transport

CACHE = Path(__file__).resolve().parents[1] / 'data' / 'cache' / 'earnings'


def fetch(url, *, refresh=False, cache=CACHE):
    parsed = urlparse(url)
    if parsed.scheme != 'https' or parsed.hostname not in ('www.sec.gov', 'sec.gov', 'data.sec.gov') or parsed.username or parsed.password or parsed.port:
        raise ValueError('Only HTTPS SEC sources are permitted')
    cache.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha256(url.encode()).hexdigest()
    index = cache / f'{key}.json'
    if index.exists() and not refresh:
        manifest = json.loads(index.read_text())
        body = (cache / manifest['body']).read_bytes()
        if hashlib.sha256(body).hexdigest() != manifest['sha256']:
            raise ValueError('SEC cache integrity failure')
        return body, manifest
    # src.fetch's limiter is process-local. Serialize Crosscheck processes and
    # pass its last-request timestamp through to the existing limiter.
    with (cache / 'sec.lock').open('a+') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        stamp = cache / 'last-request.json'
        if stamp.exists():
            elapsed = max(0, time.time() - json.loads(stamp.read_text())['wall_time'])
            transport._last_request_time = max(transport._last_request_time, time.monotonic() - elapsed)
        try:
            response = transport._throttled_get(url, allow_redirects=False)
        finally:
            stamp.write_text(json.dumps({'wall_time': time.time()}))
        body = response.content
    sha = hashlib.sha256(body).hexdigest()
    body_name = f'{key}-{sha}.body'
    (cache / body_name).write_bytes(body)
    manifest = {'url': url, 'sha256': sha, 'body': body_name,
                'fetched_at': datetime.now(timezone.utc).isoformat()}
    # Every fetched version is retained; the URL index only points at the latest.
    (cache / f'{key}-{sha}.manifest.json').write_text(json.dumps(manifest, indent=2))
    index.write_text(json.dumps(manifest, indent=2))
    return body, manifest

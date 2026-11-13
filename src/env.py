"""Shared environment loading for every entrypoint in this pipeline.

Loads .env (secrets: DATABASE_URL, GEMINI_API_KEY -- gitignored) first,
then config/runtime.env (non-secret runtime config: which provider,
which GCP project/location, spend caps -- committed to git) with
override=True, so runtime.env always wins for the keys it defines,
regardless of what .env (or the shell) also set for them. runtime.env
intentionally holds only non-secret keys, so this override is scoped to
those few keys in practice, not a blanket override of .env.
"""

from pathlib import Path

from dotenv import load_dotenv

_ROOT = Path(__file__).resolve().parent.parent


def load_env() -> None:
    load_dotenv(_ROOT / ".env")
    load_dotenv(_ROOT / "config" / "runtime.env", override=True)

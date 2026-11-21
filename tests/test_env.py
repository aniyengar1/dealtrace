import os

import pytest

from src.env import load_env


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for key in ("ENV_TEST_SECRET", "ENV_TEST_SHARED"):
        monkeypatch.delenv(key, raising=False)


def test_runtime_env_overrides_dotenv_for_a_shared_key(tmp_path, monkeypatch):
    (tmp_path / ".env").write_text("ENV_TEST_SHARED=from_dotenv\nENV_TEST_SECRET=shh\n")
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "runtime.env").write_text("ENV_TEST_SHARED=from_runtime\n")

    import src.env as env_module

    monkeypatch.setattr(env_module, "_ROOT", tmp_path)
    load_env()

    assert os.environ["ENV_TEST_SHARED"] == "from_runtime"
    assert os.environ["ENV_TEST_SECRET"] == "shh"


def test_runtime_env_does_not_affect_keys_it_does_not_define(tmp_path, monkeypatch):
    (tmp_path / ".env").write_text("ENV_TEST_SECRET=only_in_dotenv\n")
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "runtime.env").write_text("ENV_TEST_SHARED=from_runtime\n")

    import src.env as env_module

    monkeypatch.setattr(env_module, "_ROOT", tmp_path)
    load_env()

    assert os.environ["ENV_TEST_SECRET"] == "only_in_dotenv"


def test_missing_runtime_env_is_not_an_error(tmp_path, monkeypatch):
    (tmp_path / ".env").write_text("ENV_TEST_SECRET=still_works\n")

    import src.env as env_module

    monkeypatch.setattr(env_module, "_ROOT", tmp_path)
    load_env()

    assert os.environ["ENV_TEST_SECRET"] == "still_works"

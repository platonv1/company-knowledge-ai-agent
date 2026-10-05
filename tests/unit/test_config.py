"""Config is the one place retrieval tuning lives, so its defaults are load-bearing.

Every test here passes `_env_file=None` and clears the real environment, so a
developer's local .env can never make these pass or fail.
"""

import pytest
from pydantic import ValidationError

from app.core.config import Settings

BASE_ENV = {
    "DATABASE_URL": "postgresql+asyncpg://u:p@localhost:5433/db",
    "OPENAI_API_KEY": "sk-test",
    "ADMIN_API_KEY": "admin-test",
}

MANAGED_VARS = [
    "DATABASE_URL",
    "OPENAI_API_KEY",
    "ADMIN_API_KEY",
    "RELEVANCE_FLOOR",
    "SEARCH_K",
    "TOP_K",
    "CORS_ALLOWED_ORIGINS",
    "CHUNK_TARGET_TOKENS",
    "CHUNK_MAX_TOKENS",
]


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for var in MANAGED_VARS:
        monkeypatch.delenv(var, raising=False)


def make_settings(**overrides) -> Settings:
    return Settings(_env_file=None, **{**BASE_ENV, **overrides})


def test_relevance_floor_defaults_to_calibrated_value():
    # 0.70 (the value in CLAUDE.md s26) would refuse nearly every question with
    # text-embedding-3-small. The default must stay in the calibrated range.
    assert make_settings().relevance_floor == 0.35


def test_rejects_relevance_floor_above_one():
    with pytest.raises(ValidationError):
        make_settings(RELEVANCE_FLOOR=1.5)


def test_top_k_may_not_exceed_search_k():
    # Retrieving 8 then keeping 5 is intended; keeping more than we fetched is a config bug.
    with pytest.raises(ValidationError):
        make_settings(SEARCH_K=5, TOP_K=8)


def test_chunk_target_may_not_exceed_chunk_max():
    with pytest.raises(ValidationError):
        make_settings(CHUNK_TARGET_TOKENS=900, CHUNK_MAX_TOKENS=800)


def test_cors_origins_parsed_from_comma_separated_string():
    settings = make_settings(CORS_ALLOWED_ORIGINS="http://a.test, http://b.test")
    assert settings.cors_allowed_origins == ["http://a.test", "http://b.test"]


def test_overlap_tokens_derived_from_target_and_ratio():
    settings = make_settings(CHUNK_TARGET_TOKENS=600, CHUNK_OVERLAP_RATIO=0.1)
    assert settings.chunk_overlap_tokens == 60


def test_missing_database_url_is_an_error():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, OPENAI_API_KEY="sk-test", ADMIN_API_KEY="admin-test")

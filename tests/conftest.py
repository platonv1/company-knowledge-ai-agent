import os

import pytest

# Keep tests off any real provider even if a developer has keys exported.
os.environ.setdefault("APP_ENV", "test")
os.environ["OPENAI_API_KEY"] = "sk-test-not-a-real-key"
os.environ["ADMIN_API_KEY"] = "test-admin-key"
# A SEPARATE database from development. The integration fixtures truncate
# tables, so pointing tests at the dev database would wipe an ingested corpus
# every time the suite ran.
os.environ.setdefault(
    "DATABASE_URL", "postgresql+asyncpg://jarvis:jarvis@localhost:5433/jarvis_test"
)

# Offline embeddings, so the whole suite runs with no API key.
os.environ["EMBEDDING_PROVIDER"] = "hashing"
# Must match the live schema: pgvector fixes the dimension per column, and
# the migration set it to the local model's 384.
os.environ["EMBEDDING_DIMENSIONS"] = "384"
# The relevance floor is calibrated PER EMBEDDING MODEL against the golden set.
# For the hashing provider the sweep gives 0.20 the best page hit (70.5%) at the
# lowest over-refusal (13.1%); the answerer is the second refusal filter, so the
# gate favours recall. The OpenAI default of 0.35 would refuse almost everything
# here. See README, "Calibrating the floor".
os.environ["RELEVANCE_FLOOR"] = "0.20"


@pytest.fixture
def admin_headers() -> dict[str, str]:
    return {"X-Admin-Key": "test-admin-key"}


@pytest.fixture(autouse=True)
async def _dispose_engine_between_tests():
    """pytest-asyncio gives each test a fresh event loop, but the engine is a
    module-level singleton. Without this, the second test to touch the database
    reuses connections bound to a closed loop and fails with
    "Event loop is closed"."""
    yield
    from app.core.database import dispose_engine

    await dispose_engine()


@pytest.fixture(scope="session", autouse=True)
def migrate_test_database():
    """Bring the test database up to head once per session.

    Running the real migrations rather than metadata.create_all means the suite
    also proves the migration chain applies cleanly to an empty database.
    """
    from alembic.config import Config

    from alembic import command

    config = Config("alembic.ini")
    command.upgrade(config, "head")
    yield

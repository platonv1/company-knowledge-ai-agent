"""Health checks run against the real Docker Postgres -- a mocked DB probe would
prove nothing about whether we can actually reach the database."""

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import create_app

pytestmark = pytest.mark.integration


@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=create_app()), base_url="http://test") as c:
        yield c


async def test_health_reports_ok_when_database_reachable(client):
    response = await client.get("/api/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["checks"]["database"]["status"] == "ok"


async def test_health_reports_indexed_chunk_count(client):
    # An empty knowledge base is a valid state but a useful thing to surface:
    # "ok but zero chunks" is the signature of a forgotten ingestion step.
    body = (await client.get("/api/health")).json()

    assert body["checks"]["knowledge_base"]["chunk_count"] == 0
    assert body["checks"]["knowledge_base"]["document_count"] == 0


async def test_health_needs_no_admin_key(client):
    # Load balancers and uptime probes must reach it unauthenticated.
    assert (await client.get("/api/health")).status_code == 200


async def test_health_does_not_call_the_llm_provider(client):
    # The OpenAI key in tests is fake. If health made a real provider call this
    # would fail -- health must only report that a provider is *configured*.
    body = (await client.get("/api/health")).json()

    assert body["checks"]["llm"]["provider"] == "openai"
    assert body["checks"]["llm"]["configured"] is True


async def test_health_answers_head_requests(client):
    """Load balancers and uptime monitors commonly probe with HEAD.

    A GET-only route answers those with 405, which reads as an outage.
    """
    response = await client.head("/api/health")

    assert response.status_code == 200


async def test_the_chat_page_answers_head_requests(client):
    response = await client.head("/")

    assert response.status_code == 200

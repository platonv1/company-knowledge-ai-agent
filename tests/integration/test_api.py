"""HTTP surface tests.

The LLM is overridden with a scripted double; everything else -- database,
retrieval, ingestion -- is real. Embeddings use the offline hashing provider so
these run without an API key.
"""

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.deps import get_embedding_service, get_llm_service, get_rate_limiter
from app.core.rate_limit import TokenBucketLimiter
from app.llm.base import ScriptedLLMService
from app.main import create_app
from app.rag.embeddings import HashingEmbeddingService
from scripts.generate_corpus import generate_corpus

pytestmark = pytest.mark.integration

ADMIN = {"X-Admin-Key": "test-admin-key"}


@pytest.fixture(scope="module")
def corpus(tmp_path_factory):
    out = tmp_path_factory.mktemp("api_corpus")
    result = generate_corpus(out, facts_path=out / "facts.yaml")
    return {d.filename: d.path for d in result.documents}


@pytest.fixture
def llm() -> ScriptedLLMService:
    return ScriptedLLMService(responses=[])


@pytest.fixture
async def client(llm):
    app = create_app()
    app.dependency_overrides[get_llm_service] = lambda: llm
    app.dependency_overrides[get_embedding_service] = lambda: HashingEmbeddingService(
        dimensions=1536
    )
    # One limiter per test, shared across that test's requests. Returning a new
    # limiter per call would mean the bucket never depletes and nothing is limited.
    limiter = TokenBucketLimiter(per_minute=100)
    app.dependency_overrides[get_rate_limiter] = lambda: limiter

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


async def upload(client, path) -> dict:
    with open(path, "rb") as handle:
        response = await client.post(
            "/api/documents",
            headers=ADMIN,
            files={"file": (path.name, handle, "application/pdf")},
        )
    return response


# ---- chat ----


async def test_chat_answers_from_an_ingested_document(client, llm, corpus):
    await upload(client, corpus["Leave_Policy_v2.pdf"])
    llm.responses = ["Full-time employees receive 15 days of paid annual leave. [S1]"]

    response = await client.post(
        "/api/chat", json={"message": "How many annual leave days do employees get?"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["grounded"] is True
    assert "15 days" in body["answer"]
    assert body["sources"][0]["document"] == "Leave_Policy_v2.pdf"
    assert body["sources"][0]["page_label"]
    assert uuid.UUID(body["conversation_id"])


async def test_chat_refuses_when_the_knowledge_base_is_empty(client, llm):
    response = await client.post("/api/chat", json={"message": "What is the leave policy?"})

    assert response.status_code == 200
    body = response.json()
    assert body["grounded"] is False
    assert body["sources"] == []
    assert llm.call_count == 0


async def test_chat_rejects_an_empty_message(client):
    response = await client.post("/api/chat", json={"message": "   "})

    assert response.status_code == 422


async def test_chat_rejects_an_overlong_message(client):
    response = await client.post("/api/chat", json={"message": "x" * 2001})

    assert response.status_code == 422


async def test_chat_returns_404_for_an_unknown_conversation(client):
    response = await client.post(
        "/api/chat", json={"message": "hello", "conversation_id": str(uuid.uuid4())}
    )

    assert response.status_code == 404


async def test_chat_is_rate_limited(llm):
    # Builds its own app: the limit has to be in place before the first request.
    app = create_app()
    app.dependency_overrides[get_llm_service] = lambda: llm
    app.dependency_overrides[get_embedding_service] = lambda: HashingEmbeddingService(
        dimensions=1536
    )
    limiter = TokenBucketLimiter(per_minute=2)
    app.dependency_overrides[get_rate_limiter] = lambda: limiter

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        first = await c.post("/api/chat", json={"message": "one"})
        second = await c.post("/api/chat", json={"message": "two"})
        third = await c.post("/api/chat", json={"message": "three"})

    assert first.status_code == 200
    assert second.status_code == 200
    assert third.status_code == 429
    assert third.headers["Retry-After"]


# ---- documents ----


async def test_document_endpoints_require_the_admin_key(client):
    assert (await client.get("/api/documents")).status_code == 401
    assert (await client.post("/api/documents/x/archive")).status_code == 401
    assert (await client.delete("/api/documents/x")).status_code == 401


async def test_a_wrong_admin_key_is_rejected(client):
    response = await client.get("/api/documents", headers={"X-Admin-Key": "wrong"})

    assert response.status_code == 401


async def test_uploading_a_pdf_indexes_it(client, corpus):
    response = await upload(client, corpus["Code_of_Conduct.pdf"])

    assert response.status_code == 202
    body = response.json()
    assert body["ingest_status"] == "ready"

    listing = await client.get("/api/documents", headers=ADMIN)
    assert [d["filename"] for d in listing.json()] == ["Code_of_Conduct.pdf"]


async def test_uploading_a_scanned_pdf_reports_the_failure(client, corpus):
    response = await upload(client, corpus["Scanned_Notice.pdf"])

    assert response.status_code == 202
    assert response.json()["ingest_status"] == "failed"
    assert "scan" in response.json()["message"].lower()


async def test_uploading_a_non_pdf_is_rejected(client):
    response = await client.post(
        "/api/documents",
        headers=ADMIN,
        files={"file": ("notes.txt", b"just text, not a pdf", "text/plain")},
    )

    assert response.status_code == 400


async def test_uploading_the_same_file_twice_conflicts(client, corpus):
    await upload(client, corpus["Code_of_Conduct.pdf"])

    response = await upload(client, corpus["Code_of_Conduct.pdf"])

    assert response.status_code == 409


async def test_deleting_a_document_removes_it(client, corpus):
    uploaded = (await upload(client, corpus["Code_of_Conduct.pdf"])).json()

    response = await client.delete(f"/api/documents/{uploaded['id']}", headers=ADMIN)

    assert response.status_code == 204
    assert (await client.get("/api/documents", headers=ADMIN)).json() == []


async def test_archiving_a_document_removes_it_from_retrieval(client, llm, corpus):
    """Archiving is the mechanism that keeps a superseded policy out of answers."""
    uploaded = (await upload(client, corpus["Leave_Policy_v2.pdf"])).json()
    llm.responses = ["Employees receive 15 days. [S1]"]

    before = await client.post("/api/chat", json={"message": "How many annual leave days?"})
    assert before.json()["grounded"] is True

    archived = await client.post(f"/api/documents/{uploaded['id']}/archive", headers=ADMIN)
    assert archived.status_code == 200
    assert archived.json()["doc_status"] == "archived"

    after = await client.post("/api/chat", json={"message": "How many annual leave days?"})
    assert after.json()["grounded"] is False
    assert llm.call_count == 1  # no second answer call: nothing cleared the gate


async def test_health_reflects_ingested_content(client, corpus):
    await upload(client, corpus["Company_Profile.pdf"])

    body = (await client.get("/api/health")).json()

    assert body["status"] == "ok"
    assert body["checks"]["knowledge_base"]["document_count"] == 1
    assert body["checks"]["knowledge_base"]["chunk_count"] > 0


async def test_health_counts_only_documents_jarvis_can_answer_from(client, corpus):
    """A failed document must not be advertised as part of the knowledge base.

    The chat page shows this count as "answering from N controlled documents".
    Counting a scan that failed extraction would overstate what Jarvis can
    actually answer from.
    """
    await upload(client, corpus["Company_Profile.pdf"])
    await upload(client, corpus["Scanned_Notice.pdf"])  # fails extraction

    kb = (await client.get("/api/health")).json()["checks"]["knowledge_base"]

    assert kb["document_count"] == 1
    assert kb["failed_count"] == 1

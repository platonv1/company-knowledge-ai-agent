"""pgvector-backed retrieval, against the real database.

Mocking the store would test the mock. The behaviour that matters -- cosine
ordering, the active-version filter, and tenant isolation -- is all in SQL.
"""

import uuid

import pytest

from app.models.db import DocStatus, Organization
from app.rag.chunking import TextChunk
from app.rag.embeddings import HashingEmbeddingService
from app.repositories.vector_store import PgVectorStore, SearchFilters

pytestmark = pytest.mark.integration

DIMENSIONS = 1536


@pytest.fixture
def embedder() -> HashingEmbeddingService:
    return HashingEmbeddingService(dimensions=DIMENSIONS)


@pytest.fixture
def store(db_session) -> PgVectorStore:
    return PgVectorStore(db_session)


def chunk(index: int, content: str, page: int = 1, section: str | None = "1. Section") -> TextChunk:
    return TextChunk(
        chunk_index=index,
        content=content,
        token_count=len(content.split()),
        page_start=page,
        page_end=page,
        section_path=section,
        content_hash=uuid.uuid4().hex * 2,
    )


async def store_chunks(store, embedder, document, chunks):
    vectors = await embedder.embed_documents([c.content for c in chunks])
    await store.add_chunks(
        document_id=document.id,
        org_id=document.org_id,
        doc_status=document.doc_status,
        chunks=chunks,
        embeddings=vectors,
    )


async def test_search_returns_the_most_similar_chunk_first(
    store, embedder, make_document, organization
):
    document = await make_document("Leave_Policy_v2.pdf")
    await store_chunks(
        store,
        embedder,
        document,
        [
            chunk(0, "Full-time employees are entitled to 15 days of paid annual leave."),
            chunk(1, "A teller drawer must not hold more than 5,000 in cash."),
            chunk(2, "Passwords must be at least 14 characters long."),
        ],
    )

    query = await embedder.embed_query("how many paid annual leave days do employees get")
    results = await store.search(query, SearchFilters(org_id=organization.id), limit=3)

    assert len(results) == 3
    assert "15 days of paid annual leave" in results[0].content
    assert results[0].score >= results[1].score >= results[2].score


async def test_results_carry_the_metadata_a_citation_needs(
    store, embedder, make_document, organization
):
    document = await make_document(
        "Leave_Policy_v2.pdf", title="Annual Leave Policy", version="2.0"
    )
    await store_chunks(
        store, embedder, document, [chunk(0, "Employees are entitled to 15 days.", page=4)]
    )

    query = await embedder.embed_query("annual leave days")
    result = (await store.search(query, SearchFilters(org_id=organization.id), limit=1))[0]

    assert result.document_filename == "Leave_Policy_v2.pdf"
    assert result.document_title == "Annual Leave Policy"
    assert result.document_version == "2.0"
    assert result.page_start == 4
    assert result.section_path == "1. Section"


async def test_archived_documents_are_excluded_from_search(
    store, embedder, make_document, organization
):
    # The headline correctness case: both leave policies are indexed, only the
    # active one may ever be retrieved.
    active = await make_document("Leave_Policy_v2.pdf", version="2.0")
    archived = await make_document(
        "Leave_Policy_v1.pdf", version="1.0", doc_status=DocStatus.ARCHIVED
    )
    await store_chunks(
        store, embedder, active, [chunk(0, "Employees are entitled to 15 days of annual leave.")]
    )
    await store_chunks(
        store, embedder, archived, [chunk(0, "Employees are entitled to 12 days of annual leave.")]
    )

    query = await embedder.embed_query("how many days of annual leave")
    results = await store.search(query, SearchFilters(org_id=organization.id), limit=10)

    assert len(results) == 1
    assert "15 days" in results[0].content
    assert all(r.document_filename != "Leave_Policy_v1.pdf" for r in results)


async def test_archived_documents_can_be_included_explicitly(
    store, embedder, make_document, organization
):
    # An admin reviewing history needs to reach superseded documents; the default
    # just must never be to include them.
    archived = await make_document("Leave_Policy_v1.pdf", doc_status=DocStatus.ARCHIVED)
    await store_chunks(store, embedder, archived, [chunk(0, "Employees are entitled to 12 days.")])

    query = await embedder.embed_query("annual leave days")
    results = await store.search(
        query, SearchFilters(org_id=organization.id, include_archived=True), limit=10
    )

    assert len(results) == 1


async def test_search_is_isolated_per_organization(
    store, embedder, db_session, make_document, organization
):
    other = Organization(name="Other Bank", slug=f"other-{uuid.uuid4().hex[:8]}")
    db_session.add(other)
    await db_session.commit()

    mine = await make_document("Mine.pdf")
    theirs = await make_document("Theirs.pdf", org=other)
    await store_chunks(store, embedder, mine, [chunk(0, "Our annual leave is 15 days.")])
    await store_chunks(store, embedder, theirs, [chunk(0, "Our annual leave is 30 days.")])

    query = await embedder.embed_query("annual leave days")
    results = await store.search(query, SearchFilters(org_id=organization.id), limit=10)

    assert len(results) == 1
    assert "15 days" in results[0].content


async def test_limit_is_respected(store, embedder, make_document, organization):
    document = await make_document("Handbook.pdf")
    await store_chunks(
        store, embedder, document, [chunk(i, f"Clause number {i} about leave.") for i in range(8)]
    )

    query = await embedder.embed_query("leave clause")
    results = await store.search(query, SearchFilters(org_id=organization.id), limit=3)

    assert len(results) == 3


async def test_deleting_a_document_removes_its_chunks(store, embedder, make_document, organization):
    document = await make_document("Handbook.pdf")
    await store_chunks(store, embedder, document, [chunk(0, "Annual leave is 15 days.")])

    removed = await store.delete_document(document.id)

    assert removed == 1
    assert await store.count_chunks(organization.id) == 0


async def test_archiving_a_document_updates_its_chunk_status(
    store, embedder, make_document, organization
):
    # chunks.doc_status is denormalised, so archiving must propagate or the
    # active-version filter silently stops working.
    document = await make_document("Leave_Policy_v1.pdf")
    await store_chunks(store, embedder, document, [chunk(0, "Employees get 12 days.")])

    await store.set_document_status(document.id, DocStatus.ARCHIVED)

    query = await embedder.embed_query("annual leave days")
    assert await store.search(query, SearchFilters(org_id=organization.id), limit=5) == []


async def test_searching_an_empty_index_returns_nothing(store, embedder, organization):
    query = await embedder.embed_query("anything at all")

    assert await store.search(query, SearchFilters(org_id=organization.id), limit=5) == []


async def test_scores_are_cosine_similarities_in_the_unit_interval(
    store, embedder, make_document, organization
):
    document = await make_document("Handbook.pdf")
    await store_chunks(store, embedder, document, [chunk(0, "Annual leave is 15 days per year.")])

    query = await embedder.embed_query("annual leave 15 days per year")
    result = (await store.search(query, SearchFilters(org_id=organization.id), limit=1))[0]

    # Identical-ish text must score near 1, and the relevance floor depends on
    # these being similarities rather than distances.
    assert 0.0 <= result.score <= 1.0
    assert result.score > 0.8

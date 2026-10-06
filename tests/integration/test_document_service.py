"""End-to-end ingestion against the real database and real PDFs.

The offline hashing embedder is used so this runs without an API key; the
pipeline, status machine, and metadata handling are identical either way.
"""

import pytest

from app.core.config import get_settings
from app.models.db import DocStatus, IngestStatus
from app.rag.embeddings import HashingEmbeddingService
from app.repositories.vector_store import PgVectorStore, SearchFilters
from app.services.document_service import (
    DocumentService,
    DuplicateDocumentError,
    get_or_create_organization,
)
from scripts.generate_corpus import generate_corpus

pytestmark = pytest.mark.integration

DIMENSIONS = get_settings().embedding_dimensions


@pytest.fixture(scope="module")
def corpus(tmp_path_factory):
    out = tmp_path_factory.mktemp("ingest_corpus")
    result = generate_corpus(out, facts_path=out / "facts.yaml")
    return {d.filename: d.path for d in result.documents}


@pytest.fixture
async def service(db_session):
    return DocumentService(
        session=db_session,
        store=PgVectorStore(db_session),
        embedder=HashingEmbeddingService(dimensions=DIMENSIONS),
    )


@pytest.fixture
async def org(db_session):
    return await get_or_create_organization(db_session, name="Jarvis Financial Group", slug="jfg")


async def test_ingesting_a_pdf_reaches_ready_with_chunks(service, org, corpus):
    document = await service.ingest_file(corpus["Leave_Policy_v2.pdf"], org_id=org.id)

    assert document.ingest_status is IngestStatus.READY
    assert document.ingest_error is None
    assert document.page_count == 1
    assert await service.store.count_chunks(org.id) > 0


async def test_metadata_is_taken_from_the_document_header(service, org, corpus):
    document = await service.ingest_file(corpus["Leave_Policy_v2.pdf"], org_id=org.id)

    assert document.title == "Annual Leave Policy"
    assert document.version == "2.0"
    assert document.doc_type == "HR Policy"
    assert document.effective_date.isoformat() == "2026-01-01"
    assert document.doc_status is DocStatus.ACTIVE


async def test_a_superseded_document_is_ingested_as_archived(service, org, corpus):
    document = await service.ingest_file(corpus["Leave_Policy_v1.pdf"], org_id=org.id)

    assert document.doc_status is DocStatus.ARCHIVED
    assert document.ingest_status is IngestStatus.READY


async def test_a_scanned_document_fails_loudly_and_stores_nothing(service, org, corpus):
    document = await service.ingest_file(corpus["Scanned_Notice.pdf"], org_id=org.id)

    assert document.ingest_status is IngestStatus.FAILED
    assert "scan" in document.ingest_error.lower()
    assert await service.store.count_chunks(org.id) == 0


async def test_re_uploading_identical_bytes_is_rejected(service, org, corpus):
    await service.ingest_file(corpus["Code_of_Conduct.pdf"], org_id=org.id)

    with pytest.raises(DuplicateDocumentError):
        await service.ingest_file(corpus["Code_of_Conduct.pdf"], org_id=org.id)


async def test_deleting_a_document_removes_it_and_its_chunks(service, org, corpus):
    document = await service.ingest_file(corpus["Code_of_Conduct.pdf"], org_id=org.id)

    await service.delete_document(document.id)

    assert await service.store.count_chunks(org.id) == 0
    assert await service.list_documents(org.id) == []


async def test_overrides_win_over_the_document_header(service, org, corpus):
    # An admin correcting a mislabelled document must be able to.
    document = await service.ingest_file(
        corpus["Leave_Policy_v2.pdf"], org_id=org.id, doc_status=DocStatus.ARCHIVED
    )

    assert document.doc_status is DocStatus.ARCHIVED


async def test_ingesting_the_whole_corpus_answers_the_version_question_correctly(
    service, org, corpus
):
    """The milestone's headline check.

    Every document indexed, the scan rejected, and a leave query that reaches the
    active policy rather than the superseded one.
    """
    results = {}
    for filename, path in corpus.items():
        document = await service.ingest_file(path, org_id=org.id)
        results[filename] = document.ingest_status

    failed = {name: status for name, status in results.items() if status is IngestStatus.FAILED}
    assert set(failed) == {"Scanned_Notice.pdf"}

    documents = await service.list_documents(org.id)
    assert len(documents) == len(corpus)

    embedder = HashingEmbeddingService(dimensions=DIMENSIONS)
    query = await embedder.embed_query("how many days of paid annual leave do employees get")
    hits = await service.store.search(query, SearchFilters(org_id=org.id), limit=5)

    assert hits, "no chunks retrieved for a question the corpus answers"
    assert all(h.document_filename != "Leave_Policy_v1.pdf" for h in hits), (
        "retrieved the superseded leave policy"
    )
    top_text = " ".join(h.content for h in hits)
    assert "15 days" in top_text


async def test_the_archived_policy_outranks_the_active_one_on_raw_similarity(service, org, corpus):
    """Evidence that the doc_status filter is load-bearing, not decorative.

    Measured on this corpus: for "how many annual leave days", the superseded
    v1 policy scores HIGHER than the active v2 policy, because v1's text is
    shorter and so less diluted. A pipeline without the filter would answer
    "12 days" and cite a real document and a real page -- a wrong answer that
    looks perfectly sourced. This test pins the filter in place.
    """
    await service.ingest_file(corpus["Leave_Policy_v1.pdf"], org_id=org.id)
    await service.ingest_file(corpus["Leave_Policy_v2.pdf"], org_id=org.id)

    embedder = HashingEmbeddingService(dimensions=DIMENSIONS)
    query = await embedder.embed_query("how many annual leave days do employees get")

    unfiltered = await service.store.search(
        query, SearchFilters(org_id=org.id, include_archived=True), limit=10
    )
    filtered = await service.store.search(query, SearchFilters(org_id=org.id), limit=10)

    assert unfiltered[0].document_filename == "Leave_Policy_v1.pdf", (
        "precondition changed: v1 no longer outranks v2, so this test no longer "
        "demonstrates anything -- re-measure before weakening the filter"
    )
    assert all(r.document_filename == "Leave_Policy_v2.pdf" for r in filtered)
    assert "15 days" in " ".join(r.content for r in filtered)

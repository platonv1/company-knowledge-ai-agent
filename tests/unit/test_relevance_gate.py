"""The relevance gate decides when Jarvis refuses.

Tested against a stub store so score thresholds are exact. The real SQL
ordering is covered in tests/integration/test_vector_store.py.
"""

import uuid

import pytest

from app.rag.retriever import RetrievalConfig, Retriever
from app.repositories.vector_store import SearchFilters, SearchResult, VectorStore

ORG = uuid.uuid4()
CONFIG = RetrievalConfig(search_k=8, top_k=3, relevance_floor=0.35, relative_dropoff=0.75)


def result(score: float, content: str = "some policy text") -> SearchResult:
    return SearchResult(
        chunk_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        document_filename="Handbook.pdf",
        document_title="Employee Handbook",
        document_version="1.0",
        doc_type="HR Policy",
        effective_date=None,
        page_start=4,
        page_end=4,
        section_path="3. Leave",
        content=content,
        score=score,
    )


class StubStore(VectorStore):
    """Returns fixed results so the gate is the only thing under test."""

    def __init__(self, results: list[SearchResult]):
        self.results = results
        self.requested_limit: int | None = None

    async def search(self, query_embedding, filters: SearchFilters, limit: int):
        self.requested_limit = limit
        return sorted(self.results, key=lambda r: r.score, reverse=True)[:limit]

    async def add_chunks(self, **_):
        raise NotImplementedError

    async def delete_document(self, document_id):
        raise NotImplementedError

    async def set_document_status(self, document_id, status):
        raise NotImplementedError

    async def count_chunks(self, org_id):
        return len(self.results)


class StubEmbedder:
    dimensions = 8
    model_name = "stub"

    async def embed_query(self, text: str):
        return [0.1] * self.dimensions

    async def embed_documents(self, texts):
        return [[0.1] * self.dimensions for _ in texts]


def make_retriever(results: list[SearchResult]) -> tuple[Retriever, StubStore]:
    store = StubStore(results)
    return Retriever(store=store, embedder=StubEmbedder(), config=CONFIG), store


async def test_nothing_above_the_floor_means_not_grounded():
    retriever, _ = make_retriever([result(0.30), result(0.20), result(0.05)])

    retrieval = await retriever.retrieve("what is the pet insurance policy", ORG)

    assert retrieval.chunks == []
    assert retrieval.grounded is False


async def test_a_result_exactly_on_the_floor_is_kept():
    # Boundary behaviour must be defined, not incidental.
    retriever, _ = make_retriever([result(0.35)])

    retrieval = await retriever.retrieve("question", ORG)

    assert len(retrieval.chunks) == 1
    assert retrieval.grounded is True


async def test_results_below_the_floor_are_dropped_but_recorded():
    retriever, _ = make_retriever([result(0.80), result(0.20)])

    retrieval = await retriever.retrieve("question", ORG)

    assert len(retrieval.chunks) == 1
    # Kept for diagnostics: "why did it not use this chunk" is the first question
    # asked when tuning the floor.
    assert len(retrieval.rejected) == 1


async def test_no_more_than_top_k_chunks_are_kept():
    retriever, _ = make_retriever([result(0.9), result(0.88), result(0.86), result(0.84)])

    retrieval = await retriever.retrieve("question", ORG)

    assert len(retrieval.chunks) == CONFIG.top_k


async def test_weak_tail_is_dropped_when_the_best_match_is_strong():
    # 0.40 clears the floor but is far below 0.90: including it dilutes the
    # context with something the model may still cite.
    retriever, _ = make_retriever([result(0.90), result(0.85), result(0.40)])

    retrieval = await retriever.retrieve("question", ORG)

    scores = [c.score for c in retrieval.chunks]
    assert scores == [0.90, 0.85]


async def test_similar_scores_are_all_retained():
    retriever, _ = make_retriever([result(0.60), result(0.58), result(0.55)])

    retrieval = await retriever.retrieve("question", ORG)

    assert len(retrieval.chunks) == 3


async def test_chunks_are_ordered_by_descending_score():
    retriever, _ = make_retriever([result(0.55), result(0.90), result(0.70)])

    retrieval = await retriever.retrieve("question", ORG)

    scores = [c.score for c in retrieval.chunks]
    assert scores == sorted(scores, reverse=True)


async def test_search_fetches_search_k_before_gating():
    # Over-fetching then gating is the point: gating on 3 would hide candidates.
    retriever, store = make_retriever([result(0.9)])

    await retriever.retrieve("question", ORG)

    assert store.requested_limit == CONFIG.search_k


async def test_empty_index_is_not_grounded():
    retriever, _ = make_retriever([])

    retrieval = await retriever.retrieve("question", ORG)

    assert retrieval.grounded is False
    assert retrieval.chunks == []


async def test_blank_question_is_rejected():
    retriever, _ = make_retriever([result(0.9)])

    with pytest.raises(ValueError):
        await retriever.retrieve("   ", ORG)

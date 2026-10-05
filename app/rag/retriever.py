"""Retrieval and the relevance gate.

The gate is the mechanism behind "I could not find that". It has two parts:

* An **absolute floor**. Cosine scores are not comparable across embedding
  models, so this value is calibrated against the golden set rather than
  guessed. CLAUDE.md s26 suggests 0.70, which for text-embedding-3-small sits
  above where genuinely relevant passages score and would refuse nearly every
  question.
* A **relative drop-off**. When the best match is strong, a chunk that merely
  clears the floor is noise that the model may still cite. Keeping it produces
  confident answers assembled from loosely related passages.

Over-fetch (`search_k`) then gate down to `top_k`: gating on a short list would
discard candidates before they could be compared.
"""

import uuid
from dataclasses import dataclass

from app.core.config import Settings
from app.core.logging import get_logger, truncate
from app.rag.embeddings import EmbeddingService
from app.repositories.vector_store import SearchFilters, SearchResult, VectorStore

logger = get_logger(__name__)


@dataclass(frozen=True)
class RetrievalConfig:
    search_k: int = 8
    top_k: int = 5
    relevance_floor: float = 0.35
    relative_dropoff: float = 0.75

    @classmethod
    def from_settings(cls, settings: Settings) -> "RetrievalConfig":
        return cls(
            search_k=settings.search_k,
            top_k=settings.top_k,
            relevance_floor=settings.relevance_floor,
            relative_dropoff=settings.relative_dropoff,
        )


@dataclass(frozen=True)
class Retrieval:
    query: str
    chunks: list[SearchResult]
    rejected: list[SearchResult]

    @property
    def grounded(self) -> bool:
        """Whether there is any evidence to answer from."""
        return bool(self.chunks)

    @property
    def best_score(self) -> float | None:
        return self.chunks[0].score if self.chunks else None


def apply_relevance_gate(
    candidates: list[SearchResult], config: RetrievalConfig
) -> tuple[list[SearchResult], list[SearchResult]]:
    """Split candidates into kept and rejected.

    A pure function so the eval harness can sweep thresholds over one set of
    retrieved candidates instead of re-embedding the whole golden set for every
    combination -- which is what makes calibration cheap enough to actually do.
    """
    ordered = sorted(candidates, key=lambda r: r.score, reverse=True)

    above_floor = [r for r in ordered if r.score >= config.relevance_floor]
    below_floor = [r for r in ordered if r.score < config.relevance_floor]

    kept = above_floor[: config.top_k]
    dropped_by_limit = above_floor[config.top_k :]

    if len(kept) > 1:
        cutoff = kept[0].score * config.relative_dropoff
        weak = [r for r in kept[1:] if r.score < cutoff]
        kept = [kept[0]] + [r for r in kept[1:] if r.score >= cutoff]
    else:
        weak = []

    return kept, below_floor + dropped_by_limit + weak


class Retriever:
    def __init__(
        self,
        store: VectorStore,
        embedder: EmbeddingService,
        config: RetrievalConfig | None = None,
    ):
        self._store = store
        self._embedder = embedder
        self._config = config or RetrievalConfig()

    async def retrieve(
        self,
        question: str,
        org_id: uuid.UUID,
        *,
        include_archived: bool = False,
        doc_types: tuple[str, ...] | None = None,
    ) -> Retrieval:
        if not question or not question.strip():
            raise ValueError("Cannot retrieve for an empty question.")

        embedding = await self._embedder.embed_query(question)
        candidates = await self._store.search(
            embedding,
            SearchFilters(org_id=org_id, include_archived=include_archived, doc_types=doc_types),
            limit=self._config.search_k,
        )

        kept, rejected = self._apply_gate(candidates)

        logger.info(
            "Retrieval for %r: %d candidates, %d kept, best score %s",
            truncate(question, 60),
            len(candidates),
            len(kept),
            f"{kept[0].score:.3f}" if kept else "n/a",
        )
        return Retrieval(query=question, chunks=kept, rejected=rejected)

    def _apply_gate(
        self, candidates: list[SearchResult]
    ) -> tuple[list[SearchResult], list[SearchResult]]:
        return apply_relevance_gate(candidates, self._config)

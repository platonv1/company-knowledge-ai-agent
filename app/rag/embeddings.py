"""Embedding providers behind one interface (CLAUDE.md s10).

Two implementations ship:

* `OpenAIEmbeddingService` -- the real provider, batched.
* `HashingEmbeddingService` -- a deterministic offline provider. It exists so
  the application runs, and the retrieval tests exercise genuine similarity
  ordering, with no API key and no network. It is a hashing bag-of-words
  vectoriser: good enough for lexical overlap, materially worse than a real
  model at paraphrase and synonymy, and never appropriate for production.

Switching provider requires a full re-embed of the corpus: vectors from
different models are not comparable, so a mixed index silently returns nonsense.
"""

import hashlib
import math
import re
from abc import ABC, abstractmethod

from app.core.config import Settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# OpenAI accepts far more per request, but large batches make a single failure
# expensive to retry and make progress logging useless.
DEFAULT_BATCH_SIZE = 128

_WORD = re.compile(r"[a-z0-9]+")


class EmbeddingError(Exception):
    pass


class EmbeddingService(ABC):
    """Interface for turning text into vectors."""

    dimensions: int

    @abstractmethod
    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Embed many texts, preserving input order."""

    @abstractmethod
    async def embed_query(self, text: str) -> list[float]:
        """Embed a single query."""

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Identifier recorded alongside stored vectors."""

    @staticmethod
    def _require_text(text: str) -> str:
        if not text or not text.strip():
            # A blank chunk indicates an upstream extraction or chunking bug.
            # Embedding it would bury the bug behind a meaningless vector.
            raise ValueError("Cannot embed empty text.")
        return text


def _normalise(vector: list[float]) -> list[float]:
    magnitude = math.sqrt(sum(value * value for value in vector))
    if magnitude == 0:
        return vector
    return [value / magnitude for value in vector]


class HashingEmbeddingService(EmbeddingService):
    """Deterministic offline embeddings via feature hashing.

    Each token is hashed to a dimension and accumulated with a sub-linear
    frequency weight, then the vector is L2-normalised so a dot product is the
    cosine similarity. Lexical overlap therefore drives the score.
    """

    def __init__(self, dimensions: int = 1536):
        self.dimensions = dimensions

    @property
    def model_name(self) -> str:
        return f"hashing-{self.dimensions}"

    def _embed(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        counts: dict[str, int] = {}
        for token in _WORD.findall(text.lower()):
            counts[token] = counts.get(token, 0) + 1

        for token, count in counts.items():
            digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
            index = int.from_bytes(digest[:4], "big") % self.dimensions
            # Sign bit spreads tokens across the space instead of only adding.
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[index] += sign * (1.0 + math.log(count))

        return _normalise(vector)

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed(self._require_text(text)) for text in texts]

    async def embed_query(self, text: str) -> list[float]:
        return self._embed(self._require_text(text))


class OpenAIEmbeddingService(EmbeddingService):
    def __init__(
        self,
        client,
        model: str,
        dimensions: int,
        batch_size: int = DEFAULT_BATCH_SIZE,
    ):
        self._client = client
        self._model = model
        self.dimensions = dimensions
        self._batch_size = batch_size

    @property
    def model_name(self) -> str:
        return self._model

    async def _embed_batch(self, texts: list[str]) -> list[list[float]]:
        response = await self._client.embeddings.create(
            input=texts, model=self._model, dimensions=self.dimensions
        )
        vectors = [item.embedding for item in response.data]
        if len(vectors) != len(texts):
            raise EmbeddingError(
                f"Provider returned {len(vectors)} vectors for {len(texts)} inputs."
            )
        return vectors

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        cleaned = [self._require_text(text) for text in texts]
        vectors: list[list[float]] = []
        for start in range(0, len(cleaned), self._batch_size):
            batch = cleaned[start : start + self._batch_size]
            vectors.extend(await self._embed_batch(batch))
            logger.info("Embedded %d/%d chunks", len(vectors), len(cleaned))
        return vectors

    async def embed_query(self, text: str) -> list[float]:
        vectors = await self._embed_batch([self._require_text(text)])
        return vectors[0]


def build_embedding_service(settings: Settings) -> EmbeddingService:
    """Construct the configured provider."""
    provider = settings.embedding_provider.lower()

    if provider == "hashing":
        return HashingEmbeddingService(dimensions=settings.embedding_dimensions)

    if provider == "openai":
        from openai import AsyncOpenAI

        return OpenAIEmbeddingService(
            client=AsyncOpenAI(api_key=settings.openai_api_key),
            model=settings.embedding_model,
            dimensions=settings.embedding_dimensions,
        )

    raise EmbeddingError(
        f"Unknown EMBEDDING_PROVIDER {settings.embedding_provider!r}; "
        "expected 'openai' or 'hashing'."
    )

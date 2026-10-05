"""Vector store behind a repository interface (CLAUDE.md s9).

The active-version filter lives here rather than in calling code. Putting it in
the store means no caller can forget it, which matters because forgetting it
produces confident answers from superseded policies -- a wrong answer with a
valid-looking citation, which is the worst failure this system can have.
"""

import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.db import Chunk, DocStatus, Document
from app.rag.chunking import TextChunk

logger = get_logger(__name__)


@dataclass(frozen=True)
class SearchFilters:
    org_id: uuid.UUID
    # Archived documents are excluded unless explicitly requested. The default
    # is the safe one on purpose.
    include_archived: bool = False
    doc_types: tuple[str, ...] | None = None


@dataclass(frozen=True)
class SearchResult:
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    document_filename: str
    document_title: str
    document_version: str | None
    doc_type: str | None
    effective_date: date | None
    page_start: int
    page_end: int
    section_path: str | None
    content: str
    score: float


class VectorStore(ABC):
    @abstractmethod
    async def add_chunks(
        self,
        *,
        document_id: uuid.UUID,
        org_id: uuid.UUID,
        doc_status: DocStatus,
        chunks: list[TextChunk],
        embeddings: list[list[float]],
    ) -> int:
        """Store chunks with their vectors. Returns the number stored."""

    @abstractmethod
    async def search(
        self, query_embedding: list[float], filters: SearchFilters, limit: int
    ) -> list[SearchResult]:
        """Return the most similar chunks, highest score first."""

    @abstractmethod
    async def delete_document(self, document_id: uuid.UUID) -> int:
        """Delete a document's chunks. Returns the number removed."""

    @abstractmethod
    async def set_document_status(self, document_id: uuid.UUID, status: DocStatus) -> None:
        """Change a document's status, propagating it to its chunks."""

    @abstractmethod
    async def count_chunks(self, org_id: uuid.UUID) -> int:
        """Number of stored chunks for an organization."""


class PgVectorStore(VectorStore):
    def __init__(self, session: AsyncSession):
        self._session = session

    async def add_chunks(
        self,
        *,
        document_id: uuid.UUID,
        org_id: uuid.UUID,
        doc_status: DocStatus,
        chunks: list[TextChunk],
        embeddings: list[list[float]],
    ) -> int:
        if len(chunks) != len(embeddings):
            raise ValueError(
                f"Got {len(chunks)} chunks but {len(embeddings)} embeddings; refusing to "
                "store a misaligned index."
            )
        if not chunks:
            return 0

        self._session.add_all(
            [
                Chunk(
                    document_id=document_id,
                    org_id=org_id,
                    doc_status=doc_status,
                    chunk_index=chunk.chunk_index,
                    content=chunk.content,
                    token_count=chunk.token_count,
                    page_start=chunk.page_start,
                    page_end=chunk.page_end,
                    section_path=chunk.section_path,
                    content_hash=chunk.content_hash,
                    embedding=embedding,
                )
                for chunk, embedding in zip(chunks, embeddings, strict=True)
            ]
        )
        await self._session.commit()
        return len(chunks)

    async def search(
        self, query_embedding: list[float], filters: SearchFilters, limit: int
    ) -> list[SearchResult]:
        distance = Chunk.embedding.cosine_distance(query_embedding).label("distance")

        statement = (
            select(
                Chunk.id,
                Chunk.document_id,
                Chunk.page_start,
                Chunk.page_end,
                Chunk.section_path,
                Chunk.content,
                Document.filename,
                Document.title,
                Document.version,
                Document.doc_type,
                Document.effective_date,
                distance,
            )
            .join(Document, Document.id == Chunk.document_id)
            .where(Chunk.org_id == filters.org_id)
            .order_by(distance)
            .limit(limit)
        )

        if not filters.include_archived:
            statement = statement.where(Chunk.doc_status == DocStatus.ACTIVE)
        if filters.doc_types:
            statement = statement.where(Document.doc_type.in_(filters.doc_types))

        rows = (await self._session.execute(statement)).all()

        return [
            SearchResult(
                chunk_id=row.id,
                document_id=row.document_id,
                document_filename=row.filename,
                document_title=row.title,
                document_version=row.version,
                doc_type=row.doc_type,
                effective_date=row.effective_date,
                page_start=row.page_start,
                page_end=row.page_end,
                section_path=row.section_path,
                content=row.content,
                # pgvector returns cosine distance; the relevance floor is
                # expressed as a similarity, so convert once, here.
                score=1.0 - float(row.distance),
            )
            for row in rows
        ]

    async def delete_document(self, document_id: uuid.UUID) -> int:
        result = await self._session.execute(delete(Chunk).where(Chunk.document_id == document_id))
        await self._session.commit()
        return result.rowcount or 0

    async def set_document_status(self, document_id: uuid.UUID, status: DocStatus) -> None:
        await self._session.execute(
            update(Document).where(Document.id == document_id).values(doc_status=status)
        )
        # chunks.doc_status is denormalised for index-only filtering, so it must
        # be updated in the same transaction or the filter goes stale.
        await self._session.execute(
            update(Chunk).where(Chunk.document_id == document_id).values(doc_status=status)
        )
        await self._session.commit()
        logger.info("Document %s status set to %s", document_id, status.value)

    async def count_chunks(self, org_id: uuid.UUID) -> int:
        return (
            await self._session.scalar(
                select(func.count()).select_from(Chunk).where(Chunk.org_id == org_id)
            )
        ) or 0

"""Ingestion orchestration.

The status machine (pending -> extracting -> chunking -> embedding -> ready, or
failed with a recorded reason) exists so a failure is visible in the document
list rather than only in a log nobody reads. A document that fails extraction
must never reach `ready` with zero chunks: that is the silent failure where
Jarvis confidently reports it has no information about a handbook it was given.
"""

import hashlib
import uuid
from datetime import date
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.db import DocStatus, Document, IngestStatus, Organization
from app.rag.chunking import ChunkConfig, chunk_document, embedding_text
from app.rag.embeddings import EmbeddingService
from app.rag.extraction import ExtractionError, extract_document
from app.rag.metadata import parse_document_metadata
from app.repositories.vector_store import VectorStore

logger = get_logger(__name__)


class DocumentServiceError(Exception):
    pass


class DuplicateDocumentError(DocumentServiceError):
    """Identical bytes already exist for this organization."""


async def get_or_create_organization(
    session: AsyncSession, *, name: str, slug: str
) -> Organization:
    existing = await session.scalar(select(Organization).where(Organization.slug == slug))
    if existing:
        return existing

    organization = Organization(name=name, slug=slug)
    session.add(organization)
    await session.commit()
    logger.info("Created organization %s (%s)", name, slug)
    return organization


class DocumentService:
    def __init__(
        self,
        session: AsyncSession,
        store: VectorStore,
        embedder: EmbeddingService,
        chunk_config: ChunkConfig | None = None,
    ):
        self._session = session
        self.store = store
        self._embedder = embedder
        self._chunk_config = chunk_config or ChunkConfig()

    # ---- queries ----

    async def list_documents(self, org_id: uuid.UUID) -> list[Document]:
        result = await self._session.execute(
            select(Document).where(Document.org_id == org_id).order_by(Document.uploaded_at.desc())
        )
        return list(result.scalars())

    async def get_document(self, document_id: uuid.UUID) -> Document | None:
        return await self._session.get(Document, document_id)

    # ---- mutations ----

    async def delete_document(self, document_id: uuid.UUID) -> None:
        await self.store.delete_document(document_id)
        await self._session.execute(delete(Document).where(Document.id == document_id))
        await self._session.commit()
        logger.info("Deleted document %s", document_id)

    async def archive_document(self, document_id: uuid.UUID) -> None:
        await self.store.set_document_status(document_id, DocStatus.ARCHIVED)

    async def ingest_file(
        self,
        path: str | Path,
        *,
        org_id: uuid.UUID,
        title: str | None = None,
        doc_type: str | None = None,
        version: str | None = None,
        effective_date: date | None = None,
        doc_status: DocStatus | None = None,
    ) -> Document:
        """Ingest a PDF from disk.

        Metadata is read from the document's own header; any argument supplied
        here overrides it, so an admin can correct a mislabelled file.
        """
        path = Path(path)
        content = path.read_bytes()
        sha256 = hashlib.sha256(content).hexdigest()

        duplicate = await self._session.scalar(
            select(Document).where(Document.org_id == org_id, Document.sha256 == sha256)
        )
        if duplicate:
            raise DuplicateDocumentError(
                f"{path.name} is byte-identical to {duplicate.filename}, already ingested "
                f"on {duplicate.uploaded_at:%Y-%m-%d}."
            )

        document = Document(
            org_id=org_id,
            filename=path.name,
            title=title or path.stem.replace("_", " "),
            sha256=sha256,
            doc_type=doc_type,
            version=version,
            effective_date=effective_date,
            doc_status=doc_status or DocStatus.ACTIVE,
            ingest_status=IngestStatus.PENDING,
        )
        self._session.add(document)
        await self._session.commit()

        return await self.process_document(
            document,
            path,
            overrides={
                "title": title,
                "doc_type": doc_type,
                "version": version,
                "effective_date": effective_date,
                "doc_status": doc_status,
            },
        )

    async def process_document(
        self,
        document: Document,
        path: Path,
        overrides: dict | None = None,
    ) -> Document:
        """Run extraction, chunking, and embedding, recording progress."""
        overrides = {k: v for k, v in (overrides or {}).items() if v is not None}

        try:
            await self._set_status(document, IngestStatus.EXTRACTING)
            extracted = extract_document(path)

            metadata = parse_document_metadata(
                extracted.pages[0].combined_text, filename=document.filename
            )
            document.title = overrides.get("title") or metadata.title
            document.doc_type = overrides.get("doc_type") or metadata.doc_type
            document.version = overrides.get("version") or metadata.version
            document.effective_date = overrides.get("effective_date") or metadata.effective_date
            document.doc_status = overrides.get("doc_status") or metadata.doc_status
            document.page_count = extracted.page_count

            await self._set_status(document, IngestStatus.CHUNKING)
            chunks = chunk_document(extracted, document.title, self._chunk_config)
            if not chunks:
                raise ExtractionError(
                    f"{document.filename} produced no chunks; refusing to mark it ready."
                )

            await self._set_status(document, IngestStatus.EMBEDDING)
            vectors = await self._embedder.embed_documents(
                [embedding_text(chunk, document.title) for chunk in chunks]
            )

            await self.store.add_chunks(
                document_id=document.id,
                org_id=document.org_id,
                doc_status=document.doc_status,
                chunks=chunks,
                embeddings=vectors,
            )

            await self._set_status(document, IngestStatus.READY)
            logger.info(
                "Ingested %s: %d pages, %d chunks, status %s",
                document.filename,
                document.page_count,
                len(chunks),
                document.doc_status.value,
            )

        except Exception as exc:  # noqa: BLE001 - the reason is recorded and re-surfaced
            # Partial chunks from a failed run would be retrievable but
            # incomplete, which is worse than none.
            await self.store.delete_document(document.id)
            document.ingest_status = IngestStatus.FAILED
            document.ingest_error = str(exc)
            await self._session.commit()
            logger.error("Ingestion failed for %s: %s", document.filename, exc)

        return document

    async def _set_status(self, document: Document, status: IngestStatus) -> None:
        document.ingest_status = status
        await self._session.commit()

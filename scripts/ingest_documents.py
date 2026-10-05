"""Ingest PDFs into the knowledge base.

A thin shell over DocumentService -- all the logic it reports on is tested in
tests/integration/test_document_service.py.

Usage:
    python -m scripts.ingest_documents documents/
    python -m scripts.ingest_documents documents/Leave_Policy_v2.pdf --reset
"""

import argparse
import asyncio
from pathlib import Path

from sqlalchemy import text

from app.core.config import get_settings
from app.core.database import dispose_engine, get_session_factory
from app.core.logging import configure_logging
from app.models.db import IngestStatus
from app.rag.chunking import ChunkConfig
from app.rag.embeddings import build_embedding_service
from app.repositories.vector_store import PgVectorStore
from app.services.document_service import (
    DocumentService,
    DuplicateDocumentError,
    get_or_create_organization,
)

DEFAULT_ORG_SLUG = "jarvis-financial-group"


def collect_pdfs(targets: list[Path]) -> list[Path]:
    paths: list[Path] = []
    for target in targets:
        if target.is_dir():
            paths.extend(sorted(target.glob("*.pdf")))
        elif target.suffix.lower() == ".pdf":
            paths.append(target)
    return paths


async def run(targets: list[Path], *, org_slug: str, reset: bool) -> int:
    configure_logging()
    settings = get_settings()

    pdfs = collect_pdfs(targets)
    if not pdfs:
        print(f"No PDFs found in: {', '.join(str(t) for t in targets)}")
        print("Run `python -m scripts.generate_corpus` first.")
        return 1

    session_factory = get_session_factory()
    async with session_factory() as session:
        if reset:
            await session.execute(text("TRUNCATE chunks, documents CASCADE"))
            await session.commit()
            print("Cleared existing documents and chunks.\n")

        organization = await get_or_create_organization(
            session, name=settings.company_name, slug=org_slug
        )
        service = DocumentService(
            session=session,
            store=PgVectorStore(session),
            embedder=build_embedding_service(settings),
            chunk_config=ChunkConfig(
                target_tokens=settings.chunk_target_tokens,
                max_tokens=settings.chunk_max_tokens,
                overlap_ratio=settings.chunk_overlap_ratio,
            ),
        )

        print(f"Ingesting {len(pdfs)} documents with {settings.embedding_provider} embeddings\n")
        print(f"  {'Document':<40} {'Pages':>5} {'Status':<12} Notes")
        print(f"  {'-' * 40} {'-' * 5} {'-' * 12} {'-' * 30}")

        unexpected_failures = 0
        for path in pdfs:
            try:
                document = await service.ingest_file(path, org_id=organization.id)
            except DuplicateDocumentError as exc:
                print(f"  {path.name:<40} {'-':>5} {'skipped':<12} {exc}")
                continue

            note = ""
            if document.ingest_status is IngestStatus.FAILED:
                note = (document.ingest_error or "")[:60]
                unexpected_failures += 1
            elif document.doc_status.value != "active":
                note = f"doc_status={document.doc_status.value}"

            print(
                f"  {document.filename:<40} {document.page_count or 0:>5} "
                f"{document.ingest_status.value:<12} {note}"
            )

        total = await service.store.count_chunks(organization.id)
        print(f"\nIndexed {total} chunks for {organization.name}.")
        if unexpected_failures:
            print(
                f"{unexpected_failures} document(s) failed. A scanned document failing here "
                "is expected; anything else is not."
            )

    await dispose_engine()
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest PDFs into the knowledge base.")
    parser.add_argument("targets", nargs="*", default=[Path("documents")], type=Path)
    parser.add_argument("--org-slug", default=DEFAULT_ORG_SLUG)
    parser.add_argument(
        "--reset", action="store_true", help="Delete existing documents and chunks first."
    )
    args = parser.parse_args()

    raise SystemExit(asyncio.run(run(args.targets, org_slug=args.org_slug, reset=args.reset)))


if __name__ == "__main__":
    main()

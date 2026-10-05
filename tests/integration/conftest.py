"""Fixtures for tests that use the Docker Postgres."""

import uuid

import pytest
from sqlalchemy import text

from app.core.database import get_session_factory
from app.models.db import DocStatus, Document, IngestStatus, Organization

TABLES = ["messages", "conversations", "chunks", "documents", "organizations"]


@pytest.fixture
async def db_session():
    async with get_session_factory()() as session:
        yield session


@pytest.fixture(autouse=True)
async def clean_database():
    """Truncate before each test so ordering never matters."""
    async with get_session_factory()() as session:
        await session.execute(text(f"TRUNCATE {', '.join(TABLES)} CASCADE"))
        await session.commit()
    yield


@pytest.fixture
async def organization(db_session) -> Organization:
    org = Organization(name="Jarvis Financial Group", slug=f"jfg-{uuid.uuid4().hex[:8]}")
    db_session.add(org)
    await db_session.commit()
    return org


@pytest.fixture
async def make_document(db_session, organization):
    async def _make(
        filename: str,
        *,
        doc_status: DocStatus = DocStatus.ACTIVE,
        title: str | None = None,
        version: str | None = None,
        doc_type: str = "HR Policy",
        org: Organization | None = None,
    ) -> Document:
        document = Document(
            org_id=(org or organization).id,
            filename=filename,
            title=title or filename.replace(".pdf", "").replace("_", " "),
            doc_type=doc_type,
            version=version,
            doc_status=doc_status,
            sha256=uuid.uuid4().hex * 2,
            page_count=1,
            ingest_status=IngestStatus.READY,
        )
        db_session.add(document)
        await db_session.commit()
        return document

    return _make

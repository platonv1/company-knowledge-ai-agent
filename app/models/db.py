"""SQLAlchemy models.

Two deliberate shapes here, both from the Phase 1 plan:

1. `org_id` exists everywhere from the first migration. Only one organization
   exists today, but retrofitting tenant isolation later is a rewrite.
2. `doc_status` is denormalised onto `chunks` so the active-version filter on
   every query hits an index without a join. The cost is that archiving a
   document must also update its chunk rows -- see `DocumentService.archive`.
"""

import enum
import uuid
from datetime import date, datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    ARRAY,
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from app.core.config import get_settings

# The vector dimension is fixed per column in pgvector, so it comes from
# configuration and the database must agree with it. Changing it requires a
# migration AND a full re-embed: vectors from different models are not
# comparable, so a mismatched index returns nonsense rather than failing.
# app/api/health.py compares this against the live column and reports a mismatch.
EMBEDDING_DIM = get_settings().embedding_dimensions


def _pg_enum(python_enum: type[enum.Enum], name: str) -> Enum:
    """One shared type object per PG enum.

    Reusing the instance stops SQLAlchemy emitting CREATE TYPE twice when the
    same enum appears on two tables, and `values_callable` stores the lowercase
    values ("active") instead of the member names ("ACTIVE").
    """
    return Enum(
        python_enum,
        name=name,
        native_enum=True,
        values_callable=lambda e: [member.value for member in e],
    )


class Base(DeclarativeBase):
    pass


class DocStatus(enum.StrEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"


class IngestStatus(enum.StrEnum):
    PENDING = "pending"
    EXTRACTING = "extracting"
    CHUNKING = "chunking"
    EMBEDDING = "embedding"
    READY = "ready"
    FAILED = "failed"


class Role(enum.StrEnum):
    USER = "user"
    ASSISTANT = "assistant"


DOC_STATUS_TYPE = _pg_enum(DocStatus, "doc_status")
INGEST_STATUS_TYPE = _pg_enum(IngestStatus, "ingest_status")
MESSAGE_ROLE_TYPE = _pg_enum(Role, "message_role")


def _uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[uuid.UUID] = _uuid_pk()
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Document(Base):
    __tablename__ = "documents"
    __table_args__ = (
        # Re-uploading identical bytes is a mistake, not a new document.
        UniqueConstraint("org_id", "sha256", name="uq_documents_org_sha256"),
        Index("ix_documents_org_status", "org_id", "doc_status"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    org_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    filename: Mapped[str] = mapped_column(String(500), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    doc_type: Mapped[str | None] = mapped_column(String(100))
    version: Mapped[str | None] = mapped_column(String(50))
    effective_date: Mapped[date | None] = mapped_column(Date)
    doc_status: Mapped[DocStatus] = mapped_column(
        DOC_STATUS_TYPE,
        nullable=False,
        default=DocStatus.ACTIVE,
    )
    page_count: Mapped[int | None] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    ingest_status: Mapped[IngestStatus] = mapped_column(
        INGEST_STATUS_TYPE,
        nullable=False,
        default=IngestStatus.PENDING,
    )
    ingest_error: Mapped[str | None] = mapped_column(Text)
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    chunks: Mapped[list["Chunk"]] = relationship(
        back_populates="document", cascade="all, delete-orphan", passive_deletes=True
    )


class Chunk(Base):
    __tablename__ = "chunks"
    __table_args__ = (
        UniqueConstraint("document_id", "chunk_index", name="uq_chunks_document_index"),
        Index("ix_chunks_org_status", "org_id", "doc_status"),
        Index(
            "ix_chunks_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
        CheckConstraint("page_end >= page_start", name="ck_chunks_page_range"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    document_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    # Denormalised from documents -- see module docstring.
    org_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    doc_status: Mapped[DocStatus] = mapped_column(DOC_STATUS_TYPE, nullable=False)

    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    token_count: Mapped[int] = mapped_column(Integer, nullable=False)
    page_start: Mapped[int] = mapped_column(Integer, nullable=False)
    page_end: Mapped[int] = mapped_column(Integer, nullable=False)
    section_path: Mapped[str | None] = mapped_column(String(500))
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIM), nullable=False)

    document: Mapped[Document] = relationship(back_populates="chunks")


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[uuid.UUID] = _uuid_pk()
    org_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    last_active_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    messages: Mapped[list["Message"]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="Message.created_at",
    )


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (Index("ix_messages_conversation_created", "conversation_id", "created_at"),)

    id: Mapped[uuid.UUID] = _uuid_pk()
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[Role] = mapped_column(MESSAGE_ROLE_TYPE, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # Which chunks the answer actually cited -- the audit trail for grounding.
    cited_chunk_ids: Mapped[list[uuid.UUID] | None] = mapped_column(ARRAY(PGUUID(as_uuid=True)))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    conversation: Mapped[Conversation] = relationship(back_populates="messages")

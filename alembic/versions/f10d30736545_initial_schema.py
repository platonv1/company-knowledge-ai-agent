"""initial schema

Hand-finished from `alembic revision --autogenerate`. Three changes autogenerate
cannot make on its own:

1. `CREATE EXTENSION vector` must run before any vector column exists.
2. The enum types are created once, up front, with `create_type=False` on the
   columns -- otherwise `doc_status` (used by both documents and chunks) is
   emitted twice and the second CREATE TYPE fails.
3. The pgvector import autogenerate referenced but did not add.

Revision ID: f10d30736545
Revises:
Create Date: 2026-10-05
"""

from collections.abc import Sequence

import pgvector.sqlalchemy
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "f10d30736545"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

EMBEDDING_DIM = 1536

doc_status = postgresql.ENUM("active", "archived", name="doc_status", create_type=False)
ingest_status = postgresql.ENUM(
    "pending",
    "extracting",
    "chunking",
    "embedding",
    "ready",
    "failed",
    name="ingest_status",
    create_type=False,
)
message_role = postgresql.ENUM("user", "assistant", name="message_role", create_type=False)


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    bind = op.get_bind()
    doc_status.create(bind, checkfirst=True)
    ingest_status.create(bind, checkfirst=True)
    message_role.create(bind, checkfirst=True)

    op.create_table(
        "organizations",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("slug", sa.String(length=100), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
    )

    op.create_table(
        "conversations",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "last_active_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "documents",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("filename", sa.String(length=500), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("doc_type", sa.String(length=100), nullable=True),
        sa.Column("version", sa.String(length=50), nullable=True),
        sa.Column("effective_date", sa.Date(), nullable=True),
        sa.Column("doc_status", doc_status, nullable=False),
        sa.Column("page_count", sa.Integer(), nullable=True),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("ingest_status", ingest_status, nullable=False),
        sa.Column("ingest_error", sa.Text(), nullable=True),
        sa.Column(
            "uploaded_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("org_id", "sha256", name="uq_documents_org_sha256"),
    )
    op.create_index("ix_documents_org_status", "documents", ["org_id", "doc_status"], unique=False)

    op.create_table(
        "chunks",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("document_id", sa.UUID(), nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("doc_status", doc_status, nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=False),
        sa.Column("page_start", sa.Integer(), nullable=False),
        sa.Column("page_end", sa.Integer(), nullable=False),
        sa.Column("section_path", sa.String(length=500), nullable=True),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "embedding", pgvector.sqlalchemy.vector.VECTOR(dim=EMBEDDING_DIM), nullable=False
        ),
        sa.CheckConstraint("page_end >= page_start", name="ck_chunks_page_range"),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("document_id", "chunk_index", name="uq_chunks_document_index"),
    )
    op.create_index(
        "ix_chunks_embedding_hnsw",
        "chunks",
        ["embedding"],
        unique=False,
        postgresql_using="hnsw",
        postgresql_with={"m": 16, "ef_construction": 64},
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )
    op.create_index("ix_chunks_org_status", "chunks", ["org_id", "doc_status"], unique=False)

    op.create_table(
        "messages",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("conversation_id", sa.UUID(), nullable=False),
        sa.Column("role", message_role, nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("cited_chunk_ids", sa.ARRAY(sa.UUID()), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_messages_conversation_created", "messages", ["conversation_id", "created_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_messages_conversation_created", table_name="messages")
    op.drop_table("messages")
    op.drop_index("ix_chunks_org_status", table_name="chunks")
    op.drop_index("ix_chunks_embedding_hnsw", table_name="chunks")
    op.drop_table("chunks")
    op.drop_index("ix_documents_org_status", table_name="documents")
    op.drop_table("documents")
    op.drop_table("conversations")
    op.drop_table("organizations")

    bind = op.get_bind()
    message_role.drop(bind, checkfirst=True)
    ingest_status.drop(bind, checkfirst=True)
    doc_status.drop(bind, checkfirst=True)

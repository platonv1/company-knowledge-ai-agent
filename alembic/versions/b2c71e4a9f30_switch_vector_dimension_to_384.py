"""switch vector dimension to 384 for local embeddings

The original column was vector(1536) for OpenAI's text-embedding-3-small. The
local ONNX model (BAAI/bge-small-en-v1.5) produces 384 dimensions, and pgvector
fixes dimension per column, so the column type has to change.

Existing rows are deleted rather than converted. There is no conversion: a
vector from one model means nothing to another, and keeping them would leave an
index that returns confident nonsense. Re-ingest after upgrading:

    python -m scripts.ingest_documents documents/ --reset

To go back to a 1536-dimensional provider, downgrade this revision and re-ingest.

Revision ID: b2c71e4a9f30
Revises: f10d30736545
Create Date: 2026-10-06
"""

from collections.abc import Sequence

from alembic import op

revision: str = "b2c71e4a9f30"
down_revision: str | None = "f10d30736545"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OPENAI_DIM = 1536
LOCAL_DIM = 384

HNSW_INDEX = "ix_chunks_embedding_hnsw"


def _resize(dimension: int) -> None:
    # The HNSW index is built over the column's type and must be rebuilt, not
    # altered, so it is dropped first and recreated last.
    op.drop_index(HNSW_INDEX, table_name="chunks")

    # Vectors of the old dimension are unusable at the new one, and there is no
    # meaningful cast between them.
    op.execute("DELETE FROM chunks")

    op.execute(f"ALTER TABLE chunks ALTER COLUMN embedding TYPE vector({dimension})")

    op.create_index(
        HNSW_INDEX,
        "chunks",
        ["embedding"],
        unique=False,
        postgresql_using="hnsw",
        postgresql_with={"m": 16, "ef_construction": 64},
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )


def upgrade() -> None:
    _resize(LOCAL_DIM)


def downgrade() -> None:
    _resize(OPENAI_DIM)

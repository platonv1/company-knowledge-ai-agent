"""Document API schemas."""

import uuid
from datetime import date, datetime

from pydantic import BaseModel


class DocumentOut(BaseModel):
    id: uuid.UUID
    filename: str
    title: str
    doc_type: str | None = None
    version: str | None = None
    effective_date: date | None = None
    doc_status: str
    page_count: int | None = None
    ingest_status: str
    ingest_error: str | None = None
    uploaded_at: datetime
    chunk_count: int | None = None


class UploadAccepted(BaseModel):
    id: uuid.UUID
    filename: str
    ingest_status: str
    message: str

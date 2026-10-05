"""Document management endpoints.

All of these require the admin key: they change what Jarvis will say.
"""

import tempfile
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, UploadFile, status

from app.api.deps import DocumentServiceDep, OrgId
from app.core.logging import get_logger
from app.core.security import require_admin_key
from app.models.documents import DocumentOut, UploadAccepted
from app.services.document_service import DuplicateDocumentError

router = APIRouter(tags=["documents"], dependencies=[Depends(require_admin_key)])
logger = get_logger(__name__)

MAX_UPLOAD_BYTES = 25 * 1024 * 1024
PDF_MAGIC = b"%PDF-"


def to_out(document, chunk_count: int | None = None) -> DocumentOut:
    return DocumentOut(
        id=document.id,
        filename=document.filename,
        title=document.title,
        doc_type=document.doc_type,
        version=document.version,
        effective_date=document.effective_date,
        doc_status=document.doc_status.value,
        page_count=document.page_count,
        ingest_status=document.ingest_status.value,
        ingest_error=document.ingest_error,
        uploaded_at=document.uploaded_at,
        chunk_count=chunk_count,
    )


@router.get("/documents", response_model=list[DocumentOut])
async def list_documents(service: DocumentServiceDep, org_id: OrgId) -> list[DocumentOut]:
    return [to_out(d) for d in await service.list_documents(org_id)]


@router.get("/documents/{document_id}", response_model=DocumentOut)
async def get_document(document_id: str, service: DocumentServiceDep) -> DocumentOut:
    document = await service.get_document(document_id)
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No such document.")
    return to_out(document)


@router.post(
    "/documents",
    response_model=UploadAccepted,
    status_code=status.HTTP_202_ACCEPTED,
)
async def upload_document(
    background: BackgroundTasks,
    service: DocumentServiceDep,
    org_id: OrgId,
    file: UploadFile,
) -> UploadAccepted:
    content = await file.read()

    if not content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="File is empty.")
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds the {MAX_UPLOAD_BYTES // (1024 * 1024)} MB limit.",
        )
    # Check the magic bytes, not the extension: the extension is caller-supplied
    # and extraction will fail confusingly on a renamed file.
    if not content.startswith(PDF_MAGIC):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF documents are supported.",
        )

    filename = Path(file.filename or "upload.pdf").name
    temp_dir = Path(tempfile.mkdtemp(prefix="jarvis-upload-"))
    temp_path = temp_dir / filename
    temp_path.write_bytes(content)

    try:
        document = await service.ingest_file(temp_path, org_id=org_id)
    except DuplicateDocumentError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    finally:
        background.add_task(_cleanup, temp_path)

    return UploadAccepted(
        id=document.id,
        filename=document.filename,
        ingest_status=document.ingest_status.value,
        message=(
            f"Indexed {document.page_count or 0} pages."
            if document.ingest_status.value == "ready"
            else f"Ingestion failed: {document.ingest_error}"
        ),
    )


@router.delete("/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(document_id: str, service: DocumentServiceDep) -> None:
    document = await service.get_document(document_id)
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No such document.")
    await service.delete_document(document.id)


@router.post("/documents/{document_id}/archive", response_model=DocumentOut)
async def archive_document(document_id: str, service: DocumentServiceDep) -> DocumentOut:
    """Archive a superseded document.

    Archiving rather than deleting keeps the audit trail while removing the
    document from retrieval, which is what a replaced policy needs.
    """
    document = await service.get_document(document_id)
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No such document.")

    await service.archive_document(document.id)
    return to_out(await service.get_document(document_id))


def _cleanup(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
        path.parent.rmdir()
    except OSError as exc:
        logger.warning("Could not clean up %s: %s", path, exc)

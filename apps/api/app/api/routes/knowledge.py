import mimetypes
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.core.security import get_current_user_id
from app.database.session import get_db
from app.models.entities import Document
from app.schemas.document import DocumentOut
from app.services.permissions import get_membership, primary_workspace_id
from app.services.rag import RagError, RagPipeline
from app.services.storage import StorageError, get_storage_provider
from app.services.usage import record_usage

router = APIRouter(prefix="/knowledge", tags=["knowledge"])
rag = RagPipeline()
storage = get_storage_provider()


def _resolve_workspace(db: Session, user_id: str) -> str:
    """Knowledge base is workspace-scoped (see RagPipeline's docstring) — every call here
    needs a workspace, defaulting to the caller's primary one. Raises rather than silently
    falling back to something else if a user somehow has no workspace at all (shouldn't
    happen post-registration, but failing loudly beats writing into the wrong scope)."""
    workspace_id = primary_workspace_id(db, user_id)
    if not workspace_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No workspace found for this account.")
    return workspace_id


@router.post("/upload", response_model=DocumentOut, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> Document:
    """Persists the actual file (services/storage) AND indexes it for search (services/rag)
    — these were conflated before (upload meant "process and discard the bytes"); now the
    original file is real and downloadable, separate from its search index."""
    workspace_id = _resolve_workspace(db, user_id)
    content = await file.read()
    filename = file.filename or "document"
    content_type = file.content_type or mimetypes.guess_type(filename)[0] or "application/octet-stream"

    try:
        collection, usage_events = await rag.ingest(workspace_id, filename, content)
    except RagError as exc:
        # Covers both "unsupported/unparseable file" and "Qdrant/embeddings unreachable" —
        # both are real failures the caller needs to see, not a silently-empty success.
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    for event in usage_events:
        record_usage(db, event, owner_id=user_id)

    storage_key = f"{workspace_id}/{uuid.uuid4()}-{filename}"
    try:
        await storage.upload(storage_key, content, content_type)
    except StorageError as exc:
        # The file is already searchable (indexed above) even if raw storage failed — don't
        # roll that back over a storage hiccup, but the caller needs to know download won't
        # work for this one until it's re-uploaded.
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Indexed for search, but storing the original file failed: {exc}",
        ) from exc

    document = Document(
        workspace_id=workspace_id,
        uploaded_by=user_id,
        filename=filename,
        content_type=content_type,
        size_bytes=len(content),
        storage_key=storage_key,
        qdrant_collection=collection,
    )
    db.add(document)
    db.commit()
    return document


@router.get("/documents", response_model=list[DocumentOut])
async def list_documents(db: Session = Depends(get_db), user_id: str = Depends(get_current_user_id)) -> list[Document]:
    workspace_id = _resolve_workspace(db, user_id)
    return db.query(Document).filter(Document.workspace_id == workspace_id).order_by(Document.created_at.desc()).all()


@router.get("/documents/{document_id}/download-url")
async def get_document_download_url(
    document_id: str,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> dict:
    document = db.get(Document, document_id)
    if not document or not get_membership(db, document.workspace_id, user_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    try:
        url = await storage.get_signed_url(document.storage_key)
    except StorageError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    return {"url": url}


@router.delete("/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: str,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> None:
    """Deletes the stored file and the tracking row. Does NOT remove this document's vectors
    from Qdrant — RagPipeline has no per-document delete (it was never built to need one; see
    AUDIT.md). Stated here rather than silently leaving search results pointing at a deleted
    file: searching may still surface this document's text until that's built."""
    document = db.get(Document, document_id)
    if not document or not get_membership(db, document.workspace_id, user_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    try:
        await storage.delete(document.storage_key)
    except StorageError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    db.delete(document)
    db.commit()


@router.get("/search")
async def search(
    q: str,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> dict:
    workspace_id = _resolve_workspace(db, user_id)
    try:
        results, usage_events = await rag.search(workspace_id, q)
    except RagError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    for event in usage_events:
        record_usage(db, event, owner_id=user_id)
    return {"results": [result.__dict__ for result in results]}

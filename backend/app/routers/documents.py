import uuid
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from app.database import get_db
from app.models import Document, DocumentStatus, WorkspaceMember, Workspace
from app.auth import get_current_user, User
from app.services.storage import upload_file, get_local_path, delete_file
from app.tasks.process_document import process_document

router = APIRouter()

ALLOWED_TYPES = {"application/pdf"}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB


# ─────────────────────────────────────────────
# Response schemas
# ─────────────────────────────────────────────

class DocumentResponse(BaseModel):
    id: uuid.UUID
    filename: str
    status: DocumentStatus
    error_message: Optional[str]
    file_size_bytes: Optional[int]
    page_count: Optional[int]
    created_at: datetime
    summary: Optional[str]

    model_config = {"from_attributes": True}


# ─────────────────────────────────────────────
# Helper — get user's workspace
# ─────────────────────────────────────────────

async def get_user_workspace(user: User, db: AsyncSession) -> Workspace:
    result = await db.execute(
        select(WorkspaceMember)
        .where(WorkspaceMember.user_id == user.id)
        .limit(1)
    )
    member = result.scalar_one_or_none()
    if not member:
        raise HTTPException(status_code=404, detail="No workspace found for user")
    workspace = await db.get(Workspace, member.workspace_id)
    return workspace


# ─────────────────────────────────────────────
# POST /documents/upload
# ─────────────────────────────────────────────

@router.post("/upload", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Validate file type
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")

    # Validate file size
    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File too large. Max size is 50MB")

    # Reset file position after reading for size check
    import io
    file.file = io.BytesIO(contents)
    file.size = len(contents)

    # Get user's workspace
    workspace = await get_user_workspace(current_user, db)

    # Upload to storage (local or R2)
    storage_meta = await upload_file(file, str(workspace.id))

    # Save document record to DB
    doc = Document(
        workspace_id=workspace.id,
        uploaded_by=current_user.id,
        filename=file.filename,
        s3_key=storage_meta["s3_key"],
        file_size_bytes=storage_meta["file_size_bytes"],
        mime_type=file.content_type,
        status=DocumentStatus.pending,
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)

    # Trigger background processing
    process_document.delay(str(doc.id))

    return DocumentResponse.model_validate(doc)


# ─────────────────────────────────────────────
# GET /documents/
# ─────────────────────────────────────────────

@router.get("/", response_model=list[DocumentResponse])
async def list_documents(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    workspace = await get_user_workspace(current_user, db)
    result = await db.execute(
        select(Document)
        .where(Document.workspace_id == workspace.id)
        .order_by(Document.created_at.desc())
    )
    return [DocumentResponse.model_validate(doc) for doc in result.scalars().all()]


# ─────────────────────────────────────────────
# GET /documents/{document_id}
# ─────────────────────────────────────────────

@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    doc = await db.get(Document, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    workspace = await get_user_workspace(current_user, db)
    if doc.workspace_id != workspace.id:
        raise HTTPException(status_code=403, detail="Access denied")

    return DocumentResponse.model_validate(doc)


@router.post("/{document_id}/retry", response_model=DocumentResponse)
async def retry_document_processing(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    doc = await db.get(Document, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    workspace = await get_user_workspace(current_user, db)
    if doc.workspace_id != workspace.id:
        raise HTTPException(status_code=403, detail="Access denied")

    if doc.status not in {DocumentStatus.failed, DocumentStatus.pending}:
        raise HTTPException(status_code=400, detail=f"Cannot retry a {doc.status.value} document")

    doc.status = DocumentStatus.pending
    doc.error_message = None
    await db.commit()
    await db.refresh(doc)

    process_document.delay(str(doc.id))

    return DocumentResponse.model_validate(doc)


# ─────────────────────────────────────────────
# GET /documents/{document_id}/download
# ─────────────────────────────────────────────

@router.get("/{document_id}/download")
async def download_document(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    doc = await db.get(Document, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    workspace = await get_user_workspace(current_user, db)
    if doc.workspace_id != workspace.id:
        raise HTTPException(status_code=403, detail="Access denied")

    file_path = get_local_path(doc.s3_key)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found in storage")

    return FileResponse(
        path=str(file_path),
        filename=doc.filename,
        media_type="application/pdf",
    )


# ─────────────────────────────────────────────
# DELETE /documents/{document_id}
# ─────────────────────────────────────────────

@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    doc = await db.get(Document, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    workspace = await get_user_workspace(current_user, db)
    if doc.workspace_id != workspace.id:
        raise HTTPException(status_code=403, detail="Access denied")

    await delete_file(doc.s3_key)
    await db.delete(doc)
    await db.commit()

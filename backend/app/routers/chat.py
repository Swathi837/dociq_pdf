import uuid, json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text
from pydantic import BaseModel
from typing import Optional
from app.database import get_db
from app.models import Document, Chunk, WorkspaceMember
from app.auth import get_current_user, User
from app.services.ai import embed_text, answer_question

router = APIRouter()


class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    question: str
    history: Optional[list[ChatMessage]] = []

class ChatResponse(BaseModel):
    answer: str
    sources: list[dict]

class ExtractionResponse(BaseModel):
    document_id: uuid.UUID
    filename: str
    summary: Optional[str]
    extracted_data: Optional[dict]


async def get_workspace_id(user: User, db: AsyncSession) -> uuid.UUID:
    r = await db.execute(select(WorkspaceMember).where(WorkspaceMember.user_id == user.id).limit(1))
    m = r.scalar_one_or_none()
    if not m:
        raise HTTPException(404, "No workspace found")
    return m.workspace_id


@router.get("/{document_id}/extraction", response_model=ExtractionResponse)
async def get_extraction(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    doc = await db.get(Document, document_id)
    if not doc:
        raise HTTPException(404, "Document not found")
    wid = await get_workspace_id(current_user, db)
    if doc.workspace_id != wid:
        raise HTTPException(403, "Access denied")
    if doc.status != "processed":
        raise HTTPException(400, f"Not ready: {doc.status}")
    extracted = None
    if doc.extracted_data:
        try:
            extracted = json.loads(doc.extracted_data)
        except Exception:
            extracted = None
    return ExtractionResponse(
        document_id=doc.id,
        filename=doc.filename,
        summary=doc.summary,
        extracted_data=extracted
    )


@router.post("/{document_id}/ask", response_model=ChatResponse)
async def ask_question(
    document_id: uuid.UUID,
    body: ChatRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    doc = await db.get(Document, document_id)
    if not doc:
        raise HTTPException(404, "Document not found")
    wid = await get_workspace_id(current_user, db)
    if doc.workspace_id != wid:
        raise HTTPException(403, "Access denied")
    if doc.status != "processed":
        raise HTTPException(400, f"Not ready: {doc.status}")

    # Embed the question
    q_emb = await embed_text(body.question)
    emb_str = "[" + ",".join(str(x) for x in q_emb) + "]"

    # Vector similarity search using CAST syntax (asyncpg compatible)
    rows = (await db.execute(
        text("""
            SELECT content, page_num, chunk_index,
                   1 - (embedding <=> CAST(:emb AS vector)) AS similarity
            FROM chunks
            WHERE document_id = :did
              AND embedding IS NOT NULL
            ORDER BY embedding <=> CAST(:emb AS vector)
            LIMIT 5
        """),
        {"emb": emb_str, "did": str(document_id)}
    )).fetchall()

    if not rows:
        return ChatResponse(answer="No relevant content found in this document.", sources=[])

    chunks = [
        {
            "content": r.content,
            "page_num": r.page_num,
            "chunk_index": r.chunk_index,
            "similarity": float(r.similarity)
        }
        for r in rows
    ]

    history = [{"role": m.role, "content": m.content} for m in (body.history or [])]
    answer = await answer_question(body.question, chunks, history)

    sources = [
        {
            "page_num": c["page_num"] + 1,
            "snippet": c["content"][:200] + "..." if len(c["content"]) > 200 else c["content"],
            "similarity": round(c["similarity"], 3)
        }
        for c in chunks
    ]

    return ChatResponse(answer=answer, sources=sources)
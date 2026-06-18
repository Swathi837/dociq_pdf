from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from pydantic import BaseModel
from typing import Optional
from app.database import get_db
from app.models import Document, DocumentStatus, Alert, AlertStatus, Chunk, WorkspaceMember, User
from app.auth import get_current_user

router = APIRouter()


class DashboardStats(BaseModel):
    total_documents: int
    processed_documents: int
    pending_documents: int
    failed_documents: int
    total_chunks: int
    total_alerts: int
    active_alerts: int
    upcoming_alerts_7days: int
    upcoming_alerts_30days: int


class RecentDocument(BaseModel):
    id: str
    filename: str
    status: str
    created_at: datetime
    page_count: Optional[int]


class UpcomingDeadline(BaseModel):
    alert_id: str
    title: str
    document_name: str
    deadline_date: datetime
    days_until: int


class DashboardResponse(BaseModel):
    stats: DashboardStats
    recent_documents: list[RecentDocument]
    upcoming_deadlines: list[UpcomingDeadline]


async def get_workspace_id(user, db):
    r = await db.execute(select(WorkspaceMember).where(WorkspaceMember.user_id == user.id).limit(1))
    m = r.scalar_one_or_none()
    if not m:
        raise HTTPException(404, "No workspace found")
    return m.workspace_id


@router.get("/", response_model=DashboardResponse)
async def get_dashboard(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    wid = await get_workspace_id(current_user, db)

    docs_result = await db.execute(select(Document).where(Document.workspace_id == wid))
    all_docs = docs_result.scalars().all()
    total_docs = len(all_docs)
    processed = sum(1 for d in all_docs if d.status == DocumentStatus.processed)
    pending = sum(1 for d in all_docs if d.status in [DocumentStatus.pending, DocumentStatus.processing])
    failed = sum(1 for d in all_docs if d.status == DocumentStatus.failed)

    chunks_result = await db.execute(select(func.count(Chunk.id)).where(Chunk.workspace_id == wid))
    total_chunks = chunks_result.scalar() or 0

    alerts_result = await db.execute(select(Alert).where(Alert.workspace_id == wid))
    all_alerts = alerts_result.scalars().all()
    total_alerts = len(all_alerts)
    active_alerts = sum(1 for a in all_alerts if a.status == AlertStatus.active)

    now = datetime.utcnow()
    upcoming_7 = sum(1 for a in all_alerts if a.status == AlertStatus.active and a.deadline_date and now <= a.deadline_date <= now + timedelta(days=7))
    upcoming_30 = sum(1 for a in all_alerts if a.status == AlertStatus.active and a.deadline_date and now <= a.deadline_date <= now + timedelta(days=30))

    recent_docs = sorted(all_docs, key=lambda d: d.created_at, reverse=True)[:5]
    recent_list = [RecentDocument(id=str(d.id), filename=d.filename, status=d.status.value, created_at=d.created_at, page_count=d.page_count) for d in recent_docs]

    upcoming = sorted([a for a in all_alerts if a.status == AlertStatus.active and a.deadline_date and now <= a.deadline_date <= now + timedelta(days=30)], key=lambda a: a.deadline_date)[:10]
    doc_map = {str(d.id): d.filename for d in all_docs}
    deadline_list = [UpcomingDeadline(alert_id=str(a.id), title=a.title, document_name=doc_map.get(str(a.document_id), "Unknown"), deadline_date=a.deadline_date, days_until=max(0, (a.deadline_date - now).days)) for a in upcoming]

    return DashboardResponse(
        stats=DashboardStats(total_documents=total_docs, processed_documents=processed, pending_documents=pending, failed_documents=failed, total_chunks=total_chunks, total_alerts=total_alerts, active_alerts=active_alerts, upcoming_alerts_7days=upcoming_7, upcoming_alerts_30days=upcoming_30),
        recent_documents=recent_list,
        upcoming_deadlines=deadline_list,
    )
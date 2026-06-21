import uuid
import json
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional
from app.database import get_db
from app.models import Alert, AlertStatus, Document, WorkspaceMember, User
from app.auth import get_current_user
from app.services.email import send_deadline_alert

router = APIRouter()


class AlertCreate(BaseModel):
    document_id: uuid.UUID
    title: str
    description: Optional[str] = None
    deadline_date: datetime
    notify_days_before: int = 7
    notify_email: bool = True
    notify_slack: bool = False


class AlertUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    deadline_date: Optional[datetime] = None
    notify_days_before: Optional[int] = None
    notify_email: Optional[bool] = None
    status: Optional[AlertStatus] = None


class AlertResponse(BaseModel):
    id: uuid.UUID
    document_id: uuid.UUID
    title: str
    description: Optional[str]
    deadline_date: datetime
    notify_days_before: int
    notify_email: bool
    notify_slack: bool
    status: AlertStatus
    days_until_deadline: Optional[int] = None
    created_at: datetime
    model_config = {"from_attributes": True}


class TestEmailResponse(BaseModel):
    sent: bool
    to_email: str
    message: str


async def get_workspace_id(user, db):
    r = await db.execute(select(WorkspaceMember).where(WorkspaceMember.user_id == user.id).limit(1))
    m = r.scalar_one_or_none()
    if not m:
        raise HTTPException(404, "No workspace found")
    return m.workspace_id


def enrich_alert(alert):
    days = None
    if alert.deadline_date:
        delta = alert.deadline_date - datetime.utcnow()
        days = max(0, delta.days)
    return {
        "id": alert.id, "document_id": alert.document_id,
        "title": alert.title, "description": alert.description,
        "deadline_date": alert.deadline_date, "notify_days_before": alert.notify_days_before,
        "notify_email": alert.notify_email, "notify_slack": alert.notify_slack,
        "status": alert.status, "created_at": alert.created_at, "days_until_deadline": days,
    }


@router.post("/", response_model=AlertResponse, status_code=201)
async def create_alert(body: AlertCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    wid = await get_workspace_id(current_user, db)
    doc = await db.get(Document, body.document_id)
    if not doc or doc.workspace_id != wid:
        raise HTTPException(404, "Document not found")
    alert = Alert(workspace_id=wid, document_id=body.document_id, created_by=current_user.id,
                  title=body.title, description=body.description, deadline_date=body.deadline_date.replace(tzinfo=None),
                  notify_days_before=body.notify_days_before, notify_email=body.notify_email, notify_slack=body.notify_slack)
    db.add(alert)
    await db.commit()
    await db.refresh(alert)
    return AlertResponse(**enrich_alert(alert))


@router.get("/", response_model=list[AlertResponse])
async def list_alerts(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    wid = await get_workspace_id(current_user, db)
    result = await db.execute(select(Alert).where(Alert.workspace_id == wid).order_by(Alert.deadline_date.asc()))
    return [AlertResponse(**enrich_alert(a)) for a in result.scalars().all()]


@router.get("/upcoming", response_model=list[AlertResponse])
async def upcoming_alerts(days: int = 30, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    wid = await get_workspace_id(current_user, db)
    cutoff = datetime.utcnow() + timedelta(days=days)
    result = await db.execute(
        select(Alert).where(Alert.workspace_id == wid, Alert.deadline_date <= cutoff,
                            Alert.deadline_date >= datetime.utcnow(), Alert.status == AlertStatus.active)
        .order_by(Alert.deadline_date.asc())
    )
    return [AlertResponse(**enrich_alert(a)) for a in result.scalars().all()]


@router.post("/test-email", response_model=TestEmailResponse)
async def send_test_email(current_user: User = Depends(get_current_user)):
    sent = send_deadline_alert(
        to_email=current_user.email,
        document_name="DocIQ test document",
        alert_title="Email configuration test",
        deadline_date=datetime.utcnow(),
        days_until=0,
    )
    return TestEmailResponse(
        sent=sent,
        to_email=current_user.email,
        message="Test email sent" if sent else "Email send failed. Check backend logs.",
    )


@router.put("/{alert_id}", response_model=AlertResponse)
async def update_alert(alert_id: uuid.UUID, body: AlertUpdate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    wid = await get_workspace_id(current_user, db)
    alert = await db.get(Alert, alert_id)
    if not alert or alert.workspace_id != wid:
        raise HTTPException(404, "Alert not found")
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(alert, field, value)
    await db.commit()
    await db.refresh(alert)
    return AlertResponse(**enrich_alert(alert))


@router.delete("/{alert_id}", status_code=204)
async def delete_alert(alert_id: uuid.UUID, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    wid = await get_workspace_id(current_user, db)
    alert = await db.get(Alert, alert_id)
    if not alert or alert.workspace_id != wid:
        raise HTTPException(404, "Alert not found")
    await db.delete(alert)
    await db.commit()


@router.post("/{document_id}/auto-detect", response_model=list[AlertResponse])
async def auto_detect_alerts(document_id: uuid.UUID, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    wid = await get_workspace_id(current_user, db)
    doc = await db.get(Document, document_id)
    if not doc or doc.workspace_id != wid:
        raise HTTPException(404, "Document not found")
    if not doc.extracted_data:
        raise HTTPException(400, "No extracted data")
    extracted = json.loads(doc.extracted_data)
    created = []
    expiry = extracted.get("expiry_date")
    if expiry:
        try:
            dl = datetime.fromisoformat(expiry)
            if dl > datetime.utcnow():
                a = Alert(workspace_id=wid, document_id=document_id, created_by=current_user.id,
                          title="Document Expiry", description=f"'{doc.filename}' expires",
                          deadline_date=dl, notify_days_before=30, notify_email=True)
                db.add(a); created.append(a)
        except (ValueError, TypeError):
            pass
    for kd in extracted.get("key_dates", [])[:5]:
        try:
            dl = datetime.fromisoformat(kd.get("date", ""))
            if dl > datetime.utcnow():
                a = Alert(workspace_id=wid, document_id=document_id, created_by=current_user.id,
                          title=kd.get("label", "Key Date"), description=f"Date from '{doc.filename}'",
                          deadline_date=dl, notify_days_before=7, notify_email=True)
                db.add(a); created.append(a)
        except (ValueError, TypeError):
            pass
    if not created:
        return []
    await db.commit()
    for a in created:
        await db.refresh(a)
    return [AlertResponse(**enrich_alert(a)) for a in created]

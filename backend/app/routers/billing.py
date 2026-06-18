from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional
from app.database import get_db
from app.models import Document, WorkspaceMember, User, Workspace
from app.auth import get_current_user

router = APIRouter()

PLANS = {
    "free":  {"name": "Free",  "max_documents": 5,   "max_members": 1,  "price": 0,   "features": ["5 documents", "Basic extraction", "Q&A chat"]},
    "pro":   {"name": "Pro",   "max_documents": 100,  "max_members": 3,  "price": 29,  "features": ["100 documents", "Advanced extraction", "Q&A chat", "Deadline alerts", "Email notifications"]},
    "team":  {"name": "Team",  "max_documents": 9999, "max_members": 20, "price": 99,  "features": ["Unlimited documents", "All features", "Team collaboration", "Priority support"]},
}


class PlanResponse(BaseModel):
    current_plan: str
    plan_name: str
    price_per_month: int
    max_documents: int
    max_members: int
    features: list[str]
    documents_used: int
    members_used: int
    documents_remaining: int


class UsageResponse(BaseModel):
    documents_used: int
    documents_limit: int
    members_used: int
    members_limit: int
    plan: str


class PlanUpgradeRequest(BaseModel):
    plan: str


async def get_workspace_id(user, db):
    r = await db.execute(select(WorkspaceMember).where(WorkspaceMember.user_id == user.id).limit(1))
    m = r.scalar_one_or_none()
    if not m:
        raise HTTPException(404, "No workspace found")
    return m.workspace_id


@router.get("/plan", response_model=PlanResponse)
async def get_plan(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    wid = await get_workspace_id(current_user, db)

    # Count documents and members
    docs = await db.execute(select(Document).where(Document.workspace_id == wid))
    doc_count = len(docs.scalars().all())
    members = await db.execute(select(WorkspaceMember).where(WorkspaceMember.workspace_id == wid))
    member_count = len(members.scalars().all())

    # Determine plan based on usage (simple logic — no DB storage needed)
    if doc_count > 100 or member_count > 3:
        plan_key = "team"
    elif doc_count > 5 or member_count > 1:
        plan_key = "pro"
    else:
        plan_key = "free"

    plan = PLANS[plan_key]
    remaining = max(0, plan["max_documents"] - doc_count) if plan["max_documents"] != 9999 else 9999

    return PlanResponse(
        current_plan=plan_key,
        plan_name=plan["name"],
        price_per_month=plan["price"],
        max_documents=plan["max_documents"],
        max_members=plan["max_members"],
        features=plan["features"],
        documents_used=doc_count,
        members_used=member_count,
        documents_remaining=remaining,
    )


@router.get("/usage", response_model=UsageResponse)
async def get_usage(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    wid = await get_workspace_id(current_user, db)
    docs = await db.execute(select(Document).where(Document.workspace_id == wid))
    doc_count = len(docs.scalars().all())
    members = await db.execute(select(WorkspaceMember).where(WorkspaceMember.workspace_id == wid))
    member_count = len(members.scalars().all())

    if doc_count > 100 or member_count > 3:
        plan_key = "team"
    elif doc_count > 5 or member_count > 1:
        plan_key = "pro"
    else:
        plan_key = "free"

    plan = PLANS[plan_key]
    return UsageResponse(documents_used=doc_count, documents_limit=plan["max_documents"], members_used=member_count, members_limit=plan["max_members"], plan=plan_key)


@router.get("/plans")
async def list_plans():
    return {"plans": PLANS}
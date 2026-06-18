import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime
from app.database import get_db
from app.models import User, Workspace, WorkspaceMember, MemberRole
from app.auth import get_current_user, hash_password

router = APIRouter()


class MemberResponse(BaseModel):
    user_id: uuid.UUID
    email: str
    full_name: Optional[str]
    role: MemberRole
    joined_at: datetime


class InviteRequest(BaseModel):
    email: EmailStr
    role: MemberRole = MemberRole.viewer


class RoleUpdateRequest(BaseModel):
    role: MemberRole


class WorkspaceResponse(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    owner_id: uuid.UUID
    created_at: datetime
    member_count: int = 0


async def get_user_workspace(user, db):
    r = await db.execute(select(WorkspaceMember).where(WorkspaceMember.user_id == user.id).limit(1))
    m = r.scalar_one_or_none()
    if not m:
        raise HTTPException(404, "No workspace found")
    ws = await db.get(Workspace, m.workspace_id)
    return ws, m.role


@router.get("/", response_model=WorkspaceResponse)
async def get_workspace(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    ws, _ = await get_user_workspace(current_user, db)
    members = await db.execute(select(WorkspaceMember).where(WorkspaceMember.workspace_id == ws.id))
    count = len(members.scalars().all())
    return WorkspaceResponse(id=ws.id, name=ws.name, slug=ws.slug, owner_id=ws.owner_id, created_at=ws.created_at, member_count=count)


@router.get("/members", response_model=list[MemberResponse])
async def list_members(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    ws, _ = await get_user_workspace(current_user, db)
    result = await db.execute(select(WorkspaceMember).where(WorkspaceMember.workspace_id == ws.id))
    members = result.scalars().all()
    response = []
    for m in members:
        user = await db.get(User, m.user_id)
        if user:
            response.append(MemberResponse(user_id=m.user_id, email=user.email, full_name=user.full_name, role=m.role, joined_at=m.joined_at))
    return response


@router.post("/invite", response_model=MemberResponse, status_code=201)
async def invite_member(body: InviteRequest, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    ws, role = await get_user_workspace(current_user, db)
    if role not in [MemberRole.owner]:
        raise HTTPException(403, "Only workspace owners can invite members")

    # Find or create user
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()
    if not user:
        user = User(email=body.email, hashed_password=hash_password("ChangeMe123!"), full_name=body.email.split("@")[0])
        db.add(user)
        await db.flush()

    # Check if already a member
    existing = await db.execute(select(WorkspaceMember).where(WorkspaceMember.workspace_id == ws.id, WorkspaceMember.user_id == user.id))
    if existing.scalar_one_or_none():
        raise HTTPException(400, "User is already a member")

    member = WorkspaceMember(workspace_id=ws.id, user_id=user.id, role=body.role)
    db.add(member)
    await db.commit()
    await db.refresh(member)
    return MemberResponse(user_id=user.id, email=user.email, full_name=user.full_name, role=member.role, joined_at=member.joined_at)


@router.put("/members/{user_id}/role", response_model=MemberResponse)
async def update_member_role(user_id: uuid.UUID, body: RoleUpdateRequest, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    ws, role = await get_user_workspace(current_user, db)
    if role != MemberRole.owner:
        raise HTTPException(403, "Only owners can change roles")
    result = await db.execute(select(WorkspaceMember).where(WorkspaceMember.workspace_id == ws.id, WorkspaceMember.user_id == user_id))
    member = result.scalar_one_or_none()
    if not member:
        raise HTTPException(404, "Member not found")
    member.role = body.role
    await db.commit()
    user = await db.get(User, user_id)
    return MemberResponse(user_id=user.id, email=user.email, full_name=user.full_name, role=member.role, joined_at=member.joined_at)


@router.delete("/members/{user_id}", status_code=204)
async def remove_member(user_id: uuid.UUID, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    ws, role = await get_user_workspace(current_user, db)
    if role != MemberRole.owner:
        raise HTTPException(403, "Only owners can remove members")
    if user_id == current_user.id:
        raise HTTPException(400, "Cannot remove yourself")
    result = await db.execute(select(WorkspaceMember).where(WorkspaceMember.workspace_id == ws.id, WorkspaceMember.user_id == user_id))
    member = result.scalar_one_or_none()
    if not member:
        raise HTTPException(404, "Member not found")
    await db.delete(member)
    await db.commit()
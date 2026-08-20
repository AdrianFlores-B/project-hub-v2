from collections import defaultdict
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.concurrency import run_in_threadpool
from pydantic import EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import mailer
from app.config import settings
from app.database import get_db
from app.deps import ProjectAccess, get_current_user, get_owned_project, get_project_access
from app.models import Document, Project, ProjectMember, Role, User
from app.schemas import (
    DocumentOut,
    MemberOut,
    ProjectCreate,
    ProjectOut,
    ProjectUpdate,
    ProjectWithDocuments,
)
from app.security import create_share_token, decode_share_token
from app.storage import S3Storage, get_storage

router = APIRouter(tags=["projects"])


@router.post("/projects", response_model=ProjectOut, status_code=status.HTTP_201_CREATED)
async def create_project(
    data: ProjectCreate,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Project:
    project = Project(name=data.name, description=data.description)
    db.add(project)
    await db.flush()  # assigns project.id, needed for the membership row
    db.add(ProjectMember(project_id=project.id, user_id=user.id, role=Role.OWNER))
    await db.commit()
    await db.refresh(project)
    return project


@router.get("/projects", response_model=list[ProjectWithDocuments])
async def list_projects(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[ProjectWithDocuments]:
    projects = list(
        await db.scalars(
            select(Project)
            .join(ProjectMember, ProjectMember.project_id == Project.id)
            .where(ProjectMember.user_id == user.id)
            .order_by(Project.id)
        )
    )

    # one extra query for all documents beats one query per project
    documents_by_project: dict[int, list[Document]] = defaultdict(list)
    if projects:
        documents = await db.scalars(
            select(Document)
            .where(Document.project_id.in_([p.id for p in projects]))
            .order_by(Document.id)
        )
        for document in documents:
            documents_by_project[document.project_id].append(document)

    result = []
    for project in projects:
        item = ProjectWithDocuments.model_validate(project)
        item.documents = [DocumentOut.model_validate(d) for d in documents_by_project[project.id]]
        result.append(item)
    return result


@router.get("/project/{project_id}/info", response_model=ProjectOut)
async def get_project_info(
    access: Annotated[ProjectAccess, Depends(get_project_access)],
) -> Project:
    return access.project


@router.put("/project/{project_id}/info", response_model=ProjectOut)
async def update_project_info(
    data: ProjectUpdate,
    access: Annotated[ProjectAccess, Depends(get_project_access)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Project:
    project = access.project
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(project, field, value)
    await db.commit()
    await db.refresh(project)
    return project


@router.delete("/project/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project: Annotated[Project, Depends(get_owned_project)],
    db: Annotated[AsyncSession, Depends(get_db)],
    storage: Annotated[S3Storage, Depends(get_storage)],
) -> None:
    # membership and document rows go away via ON DELETE CASCADE; the files
    # in the bucket need an explicit cleanup
    prefix = f"projects/{project.id}/"
    await db.delete(project)
    await db.commit()
    await run_in_threadpool(storage.delete_prefix, prefix)


@router.post(
    "/project/{project_id}/invite",
    response_model=MemberOut,
    status_code=status.HTTP_201_CREATED,
)
async def invite_user(
    project: Annotated[Project, Depends(get_owned_project)],
    login: Annotated[str, Query(alias="user", description="Login of the user to invite")],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MemberOut:
    invited = await db.scalar(select(User).where(User.login == login))
    if invited is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")

    already_member = await db.get(ProjectMember, (project.id, invited.id))
    if already_member is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "User already has access to this project")

    db.add(ProjectMember(project_id=project.id, user_id=invited.id, role=Role.PARTICIPANT))
    await db.commit()
    return MemberOut(login=invited.login, role=Role.PARTICIPANT)


@router.get("/project/{project_id}/share")
async def share_project(
    project: Annotated[Project, Depends(get_owned_project)],
    email: Annotated[EmailStr, Query(alias="with")],
) -> dict[str, str]:
    token = create_share_token(project.id)
    join_url = f"{settings.app_base_url}/join?token={token}"
    await run_in_threadpool(mailer.send_share_email, email, project.name, join_url)
    return {"detail": f"Share link sent to {email}"}


@router.get("/join", response_model=ProjectOut)
async def join_project(
    token: str,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Project:
    project_id = decode_share_token(token)
    if project_id is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid or expired share link")

    project = await db.get(Project, project_id)
    if project is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found")

    membership = await db.get(ProjectMember, (project.id, user.id))
    if membership is None:
        db.add(ProjectMember(project_id=project.id, user_id=user.id, role=Role.PARTICIPANT))
        await db.commit()
    # clicking the link twice is fine, joining is idempotent
    return project

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import ProjectAccess, get_current_user, get_owned_project, get_project_access
from app.models import Project, ProjectMember, Role, User
from app.schemas import MemberOut, ProjectCreate, ProjectOut, ProjectUpdate

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


@router.get("/projects", response_model=list[ProjectOut])
async def list_projects(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[Project]:
    result = await db.scalars(
        select(Project)
        .join(ProjectMember, ProjectMember.project_id == Project.id)
        .where(ProjectMember.user_id == user.id)
        .order_by(Project.id)
    )
    return list(result)


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
) -> None:
    # membership rows go away via ON DELETE CASCADE
    await db.delete(project)
    await db.commit()


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

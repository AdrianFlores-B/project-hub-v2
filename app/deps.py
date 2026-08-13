from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Project, ProjectMember, Role, User
from app.security import decode_access_token

bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    if credentials is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")

    user_id = decode_access_token(credentials.credentials)
    if user_id is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token")

    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User no longer exists")

    return user


@dataclass
class ProjectAccess:
    project: Project
    role: Role


async def get_project_access(
    project_id: int,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ProjectAccess:
    project = await db.get(Project, project_id)
    if project is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found")
    membership = await db.get(ProjectMember, (project_id, user.id))
    if membership is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "No access to this project")
    return ProjectAccess(project=project, role=membership.role)


async def get_owned_project(
    access: Annotated[ProjectAccess, Depends(get_project_access)],
) -> Project:
    if access.role != Role.OWNER:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the project owner can do this")
    return access.project

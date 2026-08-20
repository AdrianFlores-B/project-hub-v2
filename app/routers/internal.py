from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models import Project
from app.schemas import ProjectSizeUpdate

# not part of the public API: only the size-calculator lambda calls this,
# so it stays out of the OpenAPI docs
router = APIRouter(include_in_schema=False)


@router.post("/internal/projects/{project_id}/size", status_code=status.HTTP_204_NO_CONTENT)
async def set_project_size(
    project_id: int,
    data: ProjectSizeUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    x_internal_token: Annotated[str | None, Header()] = None,
) -> None:
    if x_internal_token != settings.internal_token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid internal token")

    project = await db.get(Project, project_id)
    if project is None:
        # the project may have been deleted while the S3 event was in flight
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found")

    project.total_size_bytes = data.total_size_bytes
    await db.commit()

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import ProjectAccess, get_accessible_document, get_project_access
from app.models import Document
from app.schemas import DocumentOut
from app.storage import S3Storage, get_storage

router = APIRouter(tags=["documents"])

# content type is derived from the extension instead of trusting the
# client-provided header
CONTENT_TYPES = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


def _validate_filename(raw: str | None) -> tuple[str, str]:
    """Return (clean filename, content type), or raise 415 for unsupported files."""
    # strip any path the client may have sent along with the name
    filename = (raw or "").replace("\\", "/").rsplit("/", 1)[-1]
    suffix = filename[filename.rfind(".") :].lower() if "." in filename else ""
    if not filename or suffix not in CONTENT_TYPES:
        allowed = ", ".join(sorted(CONTENT_TYPES))
        raise HTTPException(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, f"Unsupported file type, allowed: {allowed}"
        )
    return filename, CONTENT_TYPES[suffix]


@router.get("/project/{project_id}/documents", response_model=list[DocumentOut])
async def list_documents(
    access: Annotated[ProjectAccess, Depends(get_project_access)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[Document]:
    result = await db.scalars(
        select(Document).where(Document.project_id == access.project.id).order_by(Document.id)
    )
    return list(result)


@router.post(
    "/project/{project_id}/documents",
    response_model=list[DocumentOut],
    status_code=status.HTTP_201_CREATED,
)
async def upload_documents(
    files: list[UploadFile],
    access: Annotated[ProjectAccess, Depends(get_project_access)],
    db: Annotated[AsyncSession, Depends(get_db)],
    storage: Annotated[S3Storage, Depends(get_storage)],
) -> list[Document]:
    # validate every file before storing anything, so a bad file rejects the whole batch
    validated = [_validate_filename(f.filename) for f in files]

    documents = []
    for upload, (filename, content_type) in zip(files, validated, strict=True):
        data = await upload.read()
        document = Document(
            project_id=access.project.id,
            filename=filename,
            s3_key="",
            content_type=content_type,
            size_bytes=len(data),
        )
        db.add(document)
        await db.flush()  # assigns document.id, which is part of the key
        document.s3_key = f"projects/{access.project.id}/{document.id}/{filename}"
        await run_in_threadpool(storage.save, document.s3_key, data, content_type)
        documents.append(document)

    await db.commit()
    for document in documents:
        await db.refresh(document)
    return documents


@router.get("/document/{document_id}")
async def download_document(
    document: Annotated[Document, Depends(get_accessible_document)],
    storage: Annotated[S3Storage, Depends(get_storage)],
) -> StreamingResponse:
    chunks = await run_in_threadpool(storage.open, document.s3_key)
    return StreamingResponse(
        chunks,
        media_type=document.content_type,
        headers={
            "Content-Disposition": f'attachment; filename="{document.filename}"',
            "Content-Length": str(document.size_bytes),
        },
    )


@router.put("/document/{document_id}", response_model=DocumentOut)
async def update_document(
    file: UploadFile,
    document: Annotated[Document, Depends(get_accessible_document)],
    db: Annotated[AsyncSession, Depends(get_db)],
    storage: Annotated[S3Storage, Depends(get_storage)],
) -> Document:
    filename, content_type = _validate_filename(file.filename)
    data = await file.read()

    old_key = document.s3_key
    document.filename = filename
    document.content_type = content_type
    document.size_bytes = len(data)
    document.s3_key = f"projects/{document.project_id}/{document.id}/{filename}"

    await run_in_threadpool(storage.save, document.s3_key, data, content_type)
    if old_key != document.s3_key:
        await run_in_threadpool(storage.delete, old_key)
    await db.commit()
    await db.refresh(document)
    return document


@router.delete("/document/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document: Annotated[Document, Depends(get_accessible_document)],
    db: Annotated[AsyncSession, Depends(get_db)],
    storage: Annotated[S3Storage, Depends(get_storage)],
) -> None:
    key = document.s3_key
    await db.delete(document)
    await db.commit()
    # if this fails we are left with an orphan object in the bucket, which is
    # preferable to a document row whose file is already gone
    await run_in_threadpool(storage.delete, key)

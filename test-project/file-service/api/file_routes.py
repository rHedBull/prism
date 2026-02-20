from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query, UploadFile
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from file_service.services.file_service import FileService
from file_service.storage.s3_storage import S3Storage

router = APIRouter(prefix="/files", tags=["files"])

# Wired during startup
_get_db = None
_s3_storage: S3Storage | None = None


def set_dependencies(get_db: Any, s3_storage: S3Storage) -> None:
    global _get_db, _s3_storage
    _get_db = get_db
    _s3_storage = s3_storage


def _get_file_service(db: AsyncSession) -> FileService:
    assert _s3_storage is not None
    return FileService(db, _s3_storage)


@router.post("/upload", status_code=201)
async def upload_file(
    file: UploadFile,
    workspace_id: uuid.UUID = Query(...),
    x_tenant_id: str = Header(...),
    x_user_id: str = Header(...),
    db: AsyncSession = Depends(lambda: _get_db()),
) -> dict[str, Any]:
    if file.filename is None:
        raise HTTPException(status_code=422, detail="Filename is required")

    # Read file to determine size
    contents = await file.read()
    size_bytes = len(contents)
    await file.seek(0)

    service = _get_file_service(db)
    try:
        file_meta = await service.upload_file(
            tenant_id=uuid.UUID(x_tenant_id),
            workspace_id=workspace_id,
            filename=file.filename,
            file_data=file.file,
            content_type=file.content_type,
            size_bytes=size_bytes,
            uploaded_by=uuid.UUID(x_user_id),
        )
        return file_meta.to_dict()
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.get("/")
async def list_files(
    workspace_id: uuid.UUID = Query(...),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(lambda: _get_db()),
) -> list[dict[str, Any]]:
    service = _get_file_service(db)
    files = await service.list_files(
        workspace_id=workspace_id, offset=offset, limit=limit
    )
    return [f.to_dict() for f in files]


@router.get("/{file_id}")
async def get_file(
    file_id: uuid.UUID,
    db: AsyncSession = Depends(lambda: _get_db()),
) -> dict[str, Any]:
    service = _get_file_service(db)
    file_meta = await service.get_file(file_id)
    if file_meta is None:
        raise HTTPException(status_code=404, detail="File not found")
    return file_meta.to_dict()


@router.get("/{file_id}/download")
async def download_file(
    file_id: uuid.UUID,
    presigned: bool = Query(False),
    db: AsyncSession = Depends(lambda: _get_db()),
) -> Any:
    service = _get_file_service(db)

    if presigned:
        url = await service.generate_presigned_url(file_id)
        if url is None:
            raise HTTPException(status_code=404, detail="File not found")
        return {"download_url": url}

    result = await service.download_file(file_id)
    if result is None:
        raise HTTPException(status_code=404, detail="File not found")

    data, file_meta = result
    return Response(
        content=data,
        media_type=file_meta.content_type,
        headers={
            "Content-Disposition": f'attachment; filename="{file_meta.filename}"',
            "Content-Length": str(file_meta.size_bytes),
        },
    )


@router.delete("/{file_id}", status_code=204)
async def delete_file(
    file_id: uuid.UUID,
    db: AsyncSession = Depends(lambda: _get_db()),
) -> None:
    service = _get_file_service(db)
    deleted = await service.delete_file(file_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="File not found")

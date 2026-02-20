from __future__ import annotations

import logging
import mimetypes
import os
import uuid
from datetime import datetime, timezone
from typing import Any, BinaryIO

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from file_service.config.settings import settings
from file_service.models.file_metadata import FileMetadata
from file_service.storage.s3_storage import S3Storage

logger = logging.getLogger(__name__)


class FileService:
    """Manages file upload, download, listing, and deletion."""

    def __init__(self, db: AsyncSession, storage: S3Storage) -> None:
        self._db = db
        self._storage = storage

    async def upload_file(
        self,
        tenant_id: uuid.UUID,
        workspace_id: uuid.UUID,
        filename: str,
        file_data: BinaryIO,
        content_type: str | None,
        size_bytes: int,
        uploaded_by: uuid.UUID,
    ) -> FileMetadata:
        # Validate file extension
        _, ext = os.path.splitext(filename)
        ext_lower = ext.lower()
        if ext_lower and ext_lower not in settings.allowed_extensions:
            raise ValueError(
                f"File extension '{ext_lower}' is not allowed. "
                f"Allowed: {', '.join(settings.allowed_extensions)}"
            )

        # Validate file size
        if size_bytes > settings.max_file_size:
            max_mb = settings.max_file_size / (1024 * 1024)
            raise ValueError(f"File size exceeds maximum allowed size of {max_mb:.0f} MB")

        # Determine content type
        if content_type is None:
            content_type, _ = mimetypes.guess_type(filename)
            content_type = content_type or "application/octet-stream"

        # Generate S3 key and upload
        s3_key = S3Storage.generate_s3_key(tenant_id, workspace_id, filename)

        await self._storage.upload(
            s3_key=s3_key,
            file_data=file_data,
            content_type=content_type,
            metadata={
                "tenant_id": str(tenant_id),
                "workspace_id": str(workspace_id),
                "uploaded_by": str(uploaded_by),
            },
        )

        # Create metadata record
        file_meta = FileMetadata(
            tenant_id=tenant_id,
            workspace_id=workspace_id,
            filename=filename,
            content_type=content_type,
            size_bytes=size_bytes,
            s3_key=s3_key,
            uploaded_by=uploaded_by,
        )
        self._db.add(file_meta)
        await self._db.flush()

        logger.info(
            "Uploaded file %s (%s, %d bytes) for workspace %s",
            filename, content_type, size_bytes, workspace_id,
        )
        return file_meta

    async def get_file(self, file_id: uuid.UUID) -> FileMetadata | None:
        result = await self._db.execute(
            select(FileMetadata).where(
                FileMetadata.id == file_id,
                FileMetadata.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def list_files(
        self,
        workspace_id: uuid.UUID,
        offset: int = 0,
        limit: int = 50,
    ) -> list[FileMetadata]:
        result = await self._db.execute(
            select(FileMetadata)
            .where(
                FileMetadata.workspace_id == workspace_id,
                FileMetadata.deleted_at.is_(None),
            )
            .order_by(FileMetadata.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def delete_file(self, file_id: uuid.UUID) -> bool:
        file_meta = await self.get_file(file_id)
        if file_meta is None:
            return False

        # Soft delete in database
        file_meta.deleted_at = datetime.now(timezone.utc)
        await self._db.flush()

        # Delete from S3 (could be deferred to a background job)
        try:
            await self._storage.delete(file_meta.s3_key)
        except Exception as exc:
            logger.error(
                "Failed to delete S3 object %s (will retry later): %s",
                file_meta.s3_key, exc,
            )

        logger.info("Deleted file %s (id: %s)", file_meta.filename, file_id)
        return True

    async def generate_presigned_url(
        self, file_id: uuid.UUID, expiry: int | None = None
    ) -> str | None:
        file_meta = await self.get_file(file_id)
        if file_meta is None:
            return None

        url = await self._storage.generate_presigned_url(
            s3_key=file_meta.s3_key, expiry=expiry
        )
        return url

    async def download_file(self, file_id: uuid.UUID) -> tuple[bytes, FileMetadata] | None:
        file_meta = await self.get_file(file_id)
        if file_meta is None:
            return None

        data = await self._storage.download(file_meta.s3_key)
        return data, file_meta

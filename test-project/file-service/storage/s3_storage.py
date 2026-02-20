from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any, BinaryIO

import boto3
from botocore.config import Config as BotoConfig
from botocore.exceptions import ClientError

from file_service.config.settings import settings

logger = logging.getLogger(__name__)


class S3Storage:
    """Manages file storage operations against S3-compatible object stores."""

    def __init__(self) -> None:
        session_kwargs: dict[str, Any] = {
            "aws_access_key_id": settings.s3_access_key,
            "aws_secret_access_key": settings.s3_secret_key,
            "region_name": settings.s3_region,
        }
        client_kwargs: dict[str, Any] = {
            "config": BotoConfig(
                signature_version="s3v4",
                retries={"max_attempts": 3, "mode": "adaptive"},
            ),
        }

        if settings.s3_endpoint_url:
            client_kwargs["endpoint_url"] = settings.s3_endpoint_url

        self._s3 = boto3.client("s3", **session_kwargs, **client_kwargs)
        self._bucket = settings.s3_bucket

    async def upload(
        self,
        s3_key: str,
        file_data: BinaryIO,
        content_type: str,
        metadata: dict[str, str] | None = None,
    ) -> str:
        extra_args: dict[str, Any] = {
            "ContentType": content_type,
        }
        if metadata:
            extra_args["Metadata"] = metadata

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            lambda: self._s3.upload_fileobj(
                file_data,
                self._bucket,
                s3_key,
                ExtraArgs=extra_args,
            ),
        )

        logger.info("Uploaded %s to s3://%s/%s", s3_key, self._bucket, s3_key)
        return s3_key

    async def download(self, s3_key: str) -> bytes:
        loop = asyncio.get_event_loop()
        try:
            response = await loop.run_in_executor(
                None,
                lambda: self._s3.get_object(Bucket=self._bucket, Key=s3_key),
            )
            body = await loop.run_in_executor(None, response["Body"].read)
            return body
        except ClientError as exc:
            if exc.response["Error"]["Code"] == "NoSuchKey":
                raise FileNotFoundError(f"File not found: {s3_key}") from exc
            raise

    async def delete(self, s3_key: str) -> None:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            lambda: self._s3.delete_object(Bucket=self._bucket, Key=s3_key),
        )
        logger.info("Deleted s3://%s/%s", self._bucket, s3_key)

    async def generate_presigned_url(
        self,
        s3_key: str,
        expiry: int | None = None,
        method: str = "get_object",
    ) -> str:
        if expiry is None:
            expiry = settings.presigned_url_expiry

        params: dict[str, Any] = {
            "Bucket": self._bucket,
            "Key": s3_key,
        }

        loop = asyncio.get_event_loop()
        url = await loop.run_in_executor(
            None,
            lambda: self._s3.generate_presigned_url(
                ClientMethod=method,
                Params=params,
                ExpiresIn=expiry,
            ),
        )
        return url

    async def head_object(self, s3_key: str) -> dict[str, Any]:
        loop = asyncio.get_event_loop()
        try:
            response = await loop.run_in_executor(
                None,
                lambda: self._s3.head_object(Bucket=self._bucket, Key=s3_key),
            )
            return {
                "content_type": response.get("ContentType"),
                "content_length": response.get("ContentLength"),
                "last_modified": response.get("LastModified"),
                "etag": response.get("ETag"),
            }
        except ClientError as exc:
            if exc.response["Error"]["Code"] == "404":
                raise FileNotFoundError(f"File not found: {s3_key}") from exc
            raise

    @staticmethod
    def generate_s3_key(
        tenant_id: uuid.UUID, workspace_id: uuid.UUID, filename: str
    ) -> str:
        file_uuid = uuid.uuid4().hex
        return f"tenants/{tenant_id}/workspaces/{workspace_id}/files/{file_uuid}/{filename}"

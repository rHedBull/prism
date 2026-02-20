from __future__ import annotations

from pydantic_settings import BaseSettings


class FileSettings(BaseSettings):
    """Configuration for the file service."""

    model_config = {"env_prefix": "FILE_"}

    postgres_url: str = "postgresql+asyncpg://prism:prism@localhost:5432/prism_files"

    s3_bucket: str = "prism-file-uploads"
    s3_region: str = "us-east-1"
    s3_access_key: str = ""
    s3_secret_key: str = ""
    s3_endpoint_url: str | None = None  # For MinIO / localstack

    max_file_size: int = 100 * 1024 * 1024  # 100 MB
    allowed_extensions: list[str] = [
        ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".csv",
        ".png", ".jpg", ".jpeg", ".gif", ".svg",
        ".zip", ".tar", ".gz",
        ".txt", ".md", ".json", ".yaml", ".yml",
    ]

    presigned_url_expiry: int = 3600  # 1 hour

    service_name: str = "file-service"
    log_level: str = "INFO"


settings = FileSettings()

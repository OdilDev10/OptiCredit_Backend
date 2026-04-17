"""Storage service for file uploads - local and cloud (Cloudflare R2)."""

import os
import uuid
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path

import aiofiles

from app.config import settings
from app.core.exceptions import AppException, NotFoundException


def _get_r2_session():
    from aioboto3 import Session

    return Session()


class StorageService(ABC):
    """Abstract base class for storage providers."""

    @abstractmethod
    async def upload(self, file_content: bytes, file_name: str, folder: str) -> str:
        """Upload file and return the access URL or path."""
        pass

    @abstractmethod
    async def download(self, file_path: str) -> bytes:
        """Download file content."""
        pass

    @abstractmethod
    async def delete(self, file_path: str) -> None:
        """Delete file."""
        pass

    @abstractmethod
    async def generate_url(self, file_path: str, expires_in: int = 3600) -> str:
        """Generate download URL with optional expiration."""
        pass


class LocalStorageService(StorageService):
    """Store files locally on the filesystem."""

    def __init__(self, base_path: str | None = None):
        self.base_path = Path(base_path or settings.local_storage_path)
        self.base_path.mkdir(parents=True, exist_ok=True)

    def _get_file_path(self, folder: str, file_name: str) -> Path:
        """Build full file path with date-based folder structure."""
        year_month = datetime.now().strftime("%Y-%m")
        folder_path = self.base_path / folder / year_month
        folder_path.mkdir(parents=True, exist_ok=True)
        return folder_path / file_name

    async def upload(self, file_content: bytes, file_name: str, folder: str) -> str:
        """Upload file locally and return relative path."""
        try:
            file_path = self._get_file_path(folder, file_name)
            async with aiofiles.open(file_path, "wb") as f:
                await f.write(file_content)
            return str(file_path.relative_to(self.base_path))
        except IOError as e:
            raise AppException(f"Failed to save file: {str(e)}", code="STORAGE_ERROR")

    async def download(self, file_path: str) -> bytes:
        """Download file from local storage."""
        try:
            full_path = self.base_path / file_path
            if not full_path.exists():
                raise NotFoundException(
                    f"File not found: {file_path}", code="FILE_NOT_FOUND"
                )
            async with aiofiles.open(full_path, "rb") as f:
                return await f.read()
        except IOError as e:
            raise AppException(f"Failed to read file: {str(e)}", code="STORAGE_ERROR")

    async def delete(self, file_path: str) -> None:
        """Delete file from local storage."""
        try:
            full_path = self.base_path / file_path
            if full_path.exists():
                os.remove(full_path)
        except IOError as e:
            raise AppException(f"Failed to delete file: {str(e)}", code="STORAGE_ERROR")

    async def generate_url(self, file_path: str, expires_in: int = 3600) -> str:
        """Generate URL for local file (static serving URL)."""
        # For local storage, return the relative path
        # In production, this would be served by a CDN or static file server
        return f"/api/v1/files/{file_path}"


class R2StorageService(StorageService):
    """Store files on Cloudflare R2."""

    def __init__(self):
        self._session = None
        self.bucket_name = settings.r2_bucket_name

        if not all(
            [
                settings.r2_endpoint_url,
                settings.r2_access_key_id,
                settings.r2_secret_access_key,
                self.bucket_name,
            ]
        ):
            raise AppException("R2 configuration is incomplete", code="CONFIG_ERROR")

    @property
    def session(self):
        if self._session is None:
            self._session = _get_r2_session()
        return self._session

    def _build_object_key(self, folder: str, file_name: str) -> str:
        """Build S3 object key with folder structure."""
        year_month = datetime.now().strftime("%Y-%m")
        return f"{folder}/{year_month}/{file_name}"

    async def upload(self, file_content: bytes, file_name: str, folder: str) -> str:
        """Upload file to R2 and return the object key."""
        try:
            object_key = self._build_object_key(folder, file_name)

            async with self.session.client(
                "s3",
                endpoint_url=settings.r2_endpoint_url,
                aws_access_key_id=settings.r2_access_key_id,
                aws_secret_access_key=settings.r2_secret_access_key,
                region_name="us-east-1",
            ) as client:
                await client.put_object(
                    Bucket=self.bucket_name,
                    Key=object_key,
                    Body=file_content,
                )

            return object_key
        except Exception as e:
            raise AppException(f"R2 upload failed: {str(e)}", code="STORAGE_ERROR")

    async def download(self, file_path: str) -> bytes:
        """Download file from R2."""
        try:
            async with self.session.client(
                "s3",
                endpoint_url=settings.r2_endpoint_url,
                aws_access_key_id=settings.r2_access_key_id,
                aws_secret_access_key=settings.r2_secret_access_key,
                region_name="us-east-1",
            ) as client:
                response = await client.get_object(
                    Bucket=self.bucket_name, Key=file_path
                )
                return await response["Body"].read()
        except Exception as e:
            raise AppException(f"R2 download failed: {str(e)}", code="STORAGE_ERROR")

    async def delete(self, file_path: str) -> None:
        """Delete file from R2."""
        try:
            async with self.session.client(
                "s3",
                endpoint_url=settings.r2_endpoint_url,
                aws_access_key_id=settings.r2_access_key_id,
                aws_secret_access_key=settings.r2_secret_access_key,
                region_name="us-east-1",
            ) as client:
                await client.delete_object(Bucket=self.bucket_name, Key=file_path)
        except Exception as e:
            raise AppException(f"R2 delete failed: {str(e)}", code="STORAGE_ERROR")

    async def generate_url(self, file_path: str, expires_in: int = 3600) -> str:
        """Generate pre-signed URL for R2 object."""
        try:
            async with self.session.client(
                "s3",
                endpoint_url=settings.r2_endpoint_url,
                aws_access_key_id=settings.r2_access_key_id,
                aws_secret_access_key=settings.r2_secret_access_key,
                region_name="us-east-1",
            ) as client:
                url = await client.generate_presigned_url(
                    "get_object",
                    Params={"Bucket": self.bucket_name, "Key": file_path},
                    ExpiresIn=expires_in,
                )
                return url
        except Exception as e:
            raise AppException(
                f"Failed to generate presigned URL: {str(e)}", code="STORAGE_ERROR"
            )


def get_storage_service() -> StorageService:
    """Factory function to get the configured storage service."""
    if settings.storage_backend == "r2":
        return R2StorageService()
    return LocalStorageService()


# Singleton instance
storage_service = get_storage_service()

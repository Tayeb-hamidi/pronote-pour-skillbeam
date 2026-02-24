"""S3-compatible object storage client."""

from __future__ import annotations

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError

from shared.config import get_settings


class ObjectStorage:
    """Wrapper around boto3 S3 client for MinIO/S3."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self.client = boto3.client(
            "s3",
            endpoint_url=self.settings.s3_endpoint_url,
            aws_access_key_id=self.settings.s3_access_key_id,
            aws_secret_access_key=self.settings.s3_secret_access_key,
            region_name=self.settings.s3_region,
            use_ssl=self.settings.s3_secure,
            config=Config(signature_version="s3v4"),
        )
        public_endpoint = self.settings.s3_public_endpoint_url or self.settings.s3_endpoint_url
        self.presign_client = boto3.client(
            "s3",
            endpoint_url=public_endpoint,
            aws_access_key_id=self.settings.s3_access_key_id,
            aws_secret_access_key=self.settings.s3_secret_access_key,
            region_name=self.settings.s3_region,
            use_ssl=self.settings.s3_secure,
            config=Config(signature_version="s3v4"),
        )

    def ensure_bucket(self) -> None:
        """Create bucket if absent."""

        try:
            self.client.head_bucket(Bucket=self.settings.s3_bucket)
        except ClientError:
            self.client.create_bucket(Bucket=self.settings.s3_bucket)

    def generate_upload_url(self, object_key: str) -> str:
        """Generate pre-signed URL for uploading an object."""

        return self.presign_client.generate_presigned_url(
            ClientMethod="put_object",
            Params={"Bucket": self.settings.s3_bucket, "Key": object_key},
            ExpiresIn=self.settings.presigned_expiration_seconds,
        )

    def generate_download_url(
        self, object_key: str, *, filename: str | None = None, mime_type: str | None = None
    ) -> str:
        """Generate pre-signed URL for downloading an object."""

        params = {"Bucket": self.settings.s3_bucket, "Key": object_key}
        if filename:
            safe_filename = filename.replace("\\", "_").replace('"', "'")
            params["ResponseContentDisposition"] = f'attachment; filename="{safe_filename}"'
        if mime_type:
            params["ResponseContentType"] = mime_type

        return self.presign_client.generate_presigned_url(
            ClientMethod="get_object",
            Params=params,
            ExpiresIn=self.settings.presigned_expiration_seconds,
        )

    def put_bytes(self, object_key: str, data: bytes, content_type: str) -> None:
        """Upload raw bytes."""

        self.client.put_object(
            Bucket=self.settings.s3_bucket,
            Key=object_key,
            Body=data,
            ContentType=content_type,
        )

    def get_bytes(self, object_key: str) -> bytes:
        """Download object as bytes."""

        response = self.client.get_object(Bucket=self.settings.s3_bucket, Key=object_key)
        return response["Body"].read()

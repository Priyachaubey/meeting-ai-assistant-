from app.core.config import settings
from app.services.storage.base import StorageError, StorageProvider


class S3CompatibleStorageProvider(StorageProvider):
    """One implementation genuinely covers AWS S3, Cloudflare R2, and MinIO — all three speak
    the S3 API, and boto3's S3 client accepts a configurable endpoint_url for the latter two
    (AWS S3 itself just omits it). NOT separately implemented for Azure Blob or GCS: those use
    a different API entirely, not just a different endpoint — a real second implementation if
    one of those is actually chosen, not a few extra lines on this one.

    NOTE: written against boto3's documented S3 client API from training knowledge — not
    exercised against a live bucket (no network access in this sandbox, and no AWS/R2/MinIO
    credentials would help with that constraint anyway). Verify `generate_presigned_url` and
    the basic put/get/delete_object calls against your actual boto3 version before relying on
    this in production, same as every other "real but sandbox-unverified" provider in this
    codebase (Deepgram, Stripe — see their respective files for the same caveat).
    """

    name = "s3"

    def __init__(self) -> None:
        if not settings.storage_s3_bucket:
            raise StorageError("STORAGE_S3_BUCKET is not set — configure it in .env before using this provider.")
        import boto3

        client_kwargs: dict = {}
        if settings.storage_s3_endpoint_url:  # set for R2/MinIO; omitted for real AWS S3
            client_kwargs["endpoint_url"] = settings.storage_s3_endpoint_url
        if settings.storage_s3_access_key_id:
            client_kwargs["aws_access_key_id"] = settings.storage_s3_access_key_id
            client_kwargs["aws_secret_access_key"] = settings.storage_s3_secret_access_key
        if settings.storage_s3_region:
            client_kwargs["region_name"] = settings.storage_s3_region

        self._client = boto3.client("s3", **client_kwargs)
        self._bucket = settings.storage_s3_bucket

    async def upload(self, key: str, content: bytes, content_type: str) -> None:
        try:
            self._client.put_object(Bucket=self._bucket, Key=key, Body=content, ContentType=content_type)
        except Exception as exc:
            raise StorageError(f"S3 upload failed for {key}: {exc}") from exc

    async def download(self, key: str) -> bytes:
        try:
            response = self._client.get_object(Bucket=self._bucket, Key=key)
            return response["Body"].read()
        except Exception as exc:
            raise StorageError(f"S3 download failed for {key}: {exc}") from exc

    async def delete(self, key: str) -> None:
        try:
            self._client.delete_object(Bucket=self._bucket, Key=key)  # idempotent by S3's own semantics
        except Exception as exc:
            raise StorageError(f"S3 delete failed for {key}: {exc}") from exc

    async def get_signed_url(self, key: str, *, expires_in_seconds: int = 3600) -> str:
        try:
            return self._client.generate_presigned_url(
                "get_object", Params={"Bucket": self._bucket, "Key": key}, ExpiresIn=expires_in_seconds
            )
        except Exception as exc:
            raise StorageError(f"Could not generate signed URL for {key}: {exc}") from exc

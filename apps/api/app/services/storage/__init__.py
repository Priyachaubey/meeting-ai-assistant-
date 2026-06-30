from app.core.config import settings
from app.services.storage.base import StorageError, StorageProvider
from app.services.storage.local import LocalStorageProvider

_provider_instance: StorageProvider | None = None


def get_storage_provider() -> StorageProvider:
    global _provider_instance
    if _provider_instance is not None:
        return _provider_instance

    if settings.storage_provider == "s3":
        from app.services.storage.s3_compatible import S3CompatibleStorageProvider

        _provider_instance = S3CompatibleStorageProvider()
    else:
        _provider_instance = LocalStorageProvider()
    return _provider_instance


__all__ = ["StorageProvider", "StorageError", "get_storage_provider"]

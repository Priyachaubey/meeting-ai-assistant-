from abc import ABC, abstractmethod


class StorageError(Exception):
    """Upload/download/delete/signed-URL failure — same error-visibility principle as every
    other provider in this codebase: a failed upload should be a visible error, not a
    silent no-op that looks like it worked."""


class StorageProvider(ABC):
    name: str

    @abstractmethod
    async def upload(self, key: str, content: bytes, content_type: str) -> None:
        """Raises StorageError on failure."""

    @abstractmethod
    async def download(self, key: str) -> bytes:
        """Raises StorageError if the key doesn't exist or can't be read."""

    @abstractmethod
    async def delete(self, key: str) -> None:
        """Raises StorageError on failure. Deleting a key that doesn't exist is NOT an
        error — deletion is idempotent by design, same convention real cloud storage APIs use."""

    @abstractmethod
    async def get_signed_url(self, key: str, *, expires_in_seconds: int = 3600) -> str:
        """A time-limited URL the caller can hand to a browser for direct download, without
        proxying the file's bytes through the API process. Raises StorageError if the key
        doesn't exist."""

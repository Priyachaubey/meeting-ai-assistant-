import hashlib
import hmac
import time
from pathlib import Path

from app.core.config import settings
from app.services.storage.base import StorageError, StorageProvider


def _sign(key: str, expires_at: int) -> str:
    message = f"{key}:{expires_at}".encode()
    return hmac.new(settings.jwt_secret.encode(), message, hashlib.sha256).hexdigest()


def verify_local_signed_url(key: str, expires_at: int, signature: str) -> bool:
    """Used by the download route to check a signed URL before streaming a file — real HMAC
    verification (constant-time compare via hmac.compare_digest, not ==, to avoid a timing
    side-channel), not a no-op. Reuses settings.jwt_secret as the signing key rather than a
    dedicated one: this app already treats that as the one signing secret, and introducing a
    second secret for a second purpose is marginal separation-of-concerns benefit for real
    config-sprawl cost."""
    if time.time() > expires_at:
        return False
    expected = _sign(key, expires_at)
    return hmac.compare_digest(expected, signature)


class LocalStorageProvider(StorageProvider):
    """Real file I/O against a directory on disk — the only storage provider in this codebase
    that can actually be exercised end-to-end without any external credentials, which is why
    it's the default (settings.storage_provider == "local") rather than S3. Fine for local
    dev and single-instance deployments; doesn't survive a redeploy on most PaaS platforms
    with ephemeral filesystems, and doesn't work at all across multiple API instances — that's
    exactly what S3CompatibleStorageProvider is for once real deployment needs it."""

    name = "local"

    def __init__(self, base_dir: str | None = None) -> None:
        self._base_dir = Path(base_dir or settings.storage_local_dir).resolve()
        self._base_dir.mkdir(parents=True, exist_ok=True)

    def _resolve(self, key: str) -> Path:
        # Block path traversal — a key like "../../etc/passwd" must never resolve outside
        # base_dir. Resolve first, then verify the result is still a descendant.
        candidate = (self._base_dir / key).resolve()
        if self._base_dir not in candidate.parents and candidate != self._base_dir:
            raise StorageError(f"Invalid storage key (path traversal attempt): {key!r}")
        return candidate

    async def upload(self, key: str, content: bytes, content_type: str) -> None:
        path = self._resolve(key)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        except OSError as exc:
            raise StorageError(f"Could not write {key}: {exc}") from exc

    async def download(self, key: str) -> bytes:
        path = self._resolve(key)
        if not path.is_file():
            raise StorageError(f"No such file: {key}")
        try:
            return path.read_bytes()
        except OSError as exc:
            raise StorageError(f"Could not read {key}: {exc}") from exc

    async def delete(self, key: str) -> None:
        path = self._resolve(key)
        try:
            path.unlink(missing_ok=True)  # idempotent — deleting a missing key is not an error
        except OSError as exc:
            raise StorageError(f"Could not delete {key}: {exc}") from exc

    async def get_signed_url(self, key: str, *, expires_in_seconds: int = 3600) -> str:
        path = self._resolve(key)
        if not path.is_file():
            raise StorageError(f"No such file: {key}")
        expires_at = int(time.time()) + expires_in_seconds
        signature = _sign(key, expires_at)
        return f"{settings.api_url}/api/storage/local/{key}?exp={expires_at}&sig={signature}"

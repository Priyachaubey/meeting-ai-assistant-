import time

import pytest

from app.services.storage.base import StorageError
from app.services.storage.local import LocalStorageProvider, verify_local_signed_url, _sign


@pytest.fixture()
def provider(tmp_path):
    return LocalStorageProvider(base_dir=str(tmp_path))


@pytest.mark.asyncio
async def test_upload_then_download_round_trip(provider):
    content = b"this is real file content, not a mock"
    await provider.upload("workspace-abc/contract.pdf", content, "application/pdf")
    assert await provider.download("workspace-abc/contract.pdf") == content


@pytest.mark.asyncio
async def test_delete_is_idempotent(provider):
    await provider.upload("a.txt", b"data", "text/plain")
    await provider.delete("a.txt")
    with pytest.raises(StorageError):
        await provider.download("a.txt")
    await provider.delete("a.txt")  # second delete must not raise


@pytest.mark.asyncio
async def test_path_traversal_is_blocked(provider):
    with pytest.raises(StorageError, match="path traversal"):
        await provider.upload("../../../etc/passwd", b"pwned", "text/plain")


@pytest.mark.asyncio
async def test_download_missing_key_raises(provider):
    with pytest.raises(StorageError):
        await provider.download("does/not/exist.txt")


def test_signed_url_verifies_with_correct_signature():
    exp = int(time.time()) + 3600
    sig = _sign("workspace-abc/contract.pdf", exp)
    assert verify_local_signed_url("workspace-abc/contract.pdf", exp, sig) is True


def test_signed_url_rejects_signature_for_a_different_key():
    exp = int(time.time()) + 3600
    sig = _sign("workspace-abc/contract.pdf", exp)
    assert verify_local_signed_url("workspace-abc/other-file.pdf", exp, sig) is False


def test_signed_url_rejects_expired_timestamp():
    expired = int(time.time()) - 10
    sig = _sign("workspace-abc/contract.pdf", expired)
    assert verify_local_signed_url("workspace-abc/contract.pdf", expired, sig) is False

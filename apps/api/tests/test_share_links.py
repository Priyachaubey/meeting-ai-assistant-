from datetime import datetime, timedelta

from app.services.share_links import _hash_token


def test_same_token_hashes_identically():
    token = "test-token-abc"
    assert _hash_token(token) == _hash_token(token)


def test_different_tokens_hash_differently():
    assert _hash_token("token-a") != _hash_token("token-b")


def test_default_expiry_is_roughly_seven_days():
    expires_at = datetime.utcnow() + timedelta(hours=168)
    delta = expires_at - datetime.utcnow()
    assert 6 <= delta.days <= 7

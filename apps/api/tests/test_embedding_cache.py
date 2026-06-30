import json

from app.services.rag.embedding_cache import _cache_key


def test_identical_model_and_text_produce_identical_key():
    assert _cache_key("text-embedding-3-small", "hello") == _cache_key("text-embedding-3-small", "hello")


def test_different_text_produces_different_key():
    assert _cache_key("text-embedding-3-small", "hello") != _cache_key("text-embedding-3-small", "world")


def test_different_model_produces_different_key_for_identical_text():
    assert _cache_key("text-embedding-3-small", "hello") != _cache_key("text-embedding-3-large", "hello")


def test_embedding_round_trips_through_json():
    embedding = [0.123, -0.456, 0.789] * 512
    assert json.loads(json.dumps(embedding)) == embedding

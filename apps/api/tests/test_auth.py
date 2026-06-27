import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database.session import get_db
from app.main import app
from app.models import entities  # noqa: F401 - registers models on Base.metadata
from app.models.base import Base


@pytest.fixture()
def client():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_register_then_login(client):
    register_response = client.post(
        "/api/auth/register", json={"email": "founder@microtechniqueit.com", "password": "correct-horse-battery"}
    )
    assert register_response.status_code == 201
    assert register_response.json()["access_token"]

    login_response = client.post(
        "/api/auth/login", json={"email": "founder@microtechniqueit.com", "password": "correct-horse-battery"}
    )
    assert login_response.status_code == 200
    assert login_response.json()["access_token"]


def test_login_with_wrong_password_is_rejected(client):
    client.post("/api/auth/register", json={"email": "second@microtechniqueit.com", "password": "right-password"})
    response = client.post("/api/auth/login", json={"email": "second@microtechniqueit.com", "password": "wrong"})
    assert response.status_code == 401


def test_duplicate_registration_is_rejected(client):
    body = {"email": "dupe@microtechniqueit.com", "password": "whatever-12345"}
    first = client.post("/api/auth/register", json=body)
    second = client.post("/api/auth/register", json=body)
    assert first.status_code == 201
    assert second.status_code == 409

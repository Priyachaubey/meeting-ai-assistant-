"""Security utilities – JWT verification for inter-service auth."""

from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from app.core.config import settings

_bearer = HTTPBearer(auto_error=False)


def decode_access_token(token: str) -> dict:
    """Decode and validate a JWT. Returns the payload dict."""
    try:
        payload = jwt.decode(
            token, settings.jwt_secret, algorithms=[settings.jwt_algorithm]
        )
        return payload
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        ) from exc


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> dict:
    """FastAPI dependency – extract current user from JWT."""
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated"
        )
    return decode_access_token(credentials.credentials)


def create_internal_token(sub: str, role: str = "service") -> str:
    """Create a short-lived token for inter-service calls."""
    import datetime

    payload = {
        "sub": sub,
        "role": role,
        "exp": datetime.datetime.now(datetime.timezone.utc)
        + datetime.timedelta(minutes=5),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)

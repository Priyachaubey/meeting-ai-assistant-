"""Security utilities for Meeting Server."""

from __future__ import annotations

import datetime

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from app.core.config import settings

_bearer = HTTPBearer(auto_error=False)


def decode_access_token(token: str) -> dict:
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
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated"
        )
    return decode_access_token(credentials.credentials)


def create_access_token(sub: str, role: str = "member") -> str:
    payload = {
        "sub": sub,
        "role": role,
        "exp": datetime.datetime.now(datetime.timezone.utc)
        + datetime.timedelta(hours=24),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)

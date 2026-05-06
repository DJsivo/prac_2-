from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import os
from pathlib import Path
from typing import Callable

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer


@dataclass
class UserPrincipal:
    user_id: int
    email: str
    role: str


_bearer = HTTPBearer(auto_error=False)


def _read_jwt_secret() -> str:
    secret_file = os.getenv("JWT_SECRET_FILE")
    if secret_file and Path(secret_file).exists():
        return Path(secret_file).read_text(encoding="utf-8").strip()

    secret = os.getenv("JWT_SECRET", "dev-jwt-secret")
    if not secret:
        raise RuntimeError("JWT secret is not configured")
    return secret


def _jwt_issuer() -> str:
    return os.getenv("JWT_ISSUER", "lab2-auth")


def _jwt_audience() -> str:
    return os.getenv("JWT_AUDIENCE", "lab2-services")


def create_access_token(user_id: int, email: str, role: str, expires_minutes: int = 60) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "email": email,
        "role": role,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=expires_minutes)).timestamp()),
        "iss": _jwt_issuer(),
        "aud": _jwt_audience(),
    }
    return jwt.encode(payload, _read_jwt_secret(), algorithm="HS256")


def decode_access_token(token: str) -> UserPrincipal:
    try:
        payload = jwt.decode(
            token,
            _read_jwt_secret(),
            algorithms=["HS256"],
            issuer=_jwt_issuer(),
            audience=_jwt_audience(),
        )
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from exc

    try:
        return UserPrincipal(
            user_id=int(payload["sub"]),
            email=str(payload["email"]),
            role=str(payload["role"]),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload") from exc


def get_current_principal(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> UserPrincipal:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")
    return decode_access_token(credentials.credentials)


def require_roles(*allowed_roles: str) -> Callable[[UserPrincipal], UserPrincipal]:
    def dependency(principal: UserPrincipal = Depends(get_current_principal)) -> UserPrincipal:
        if principal.role not in allowed_roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
        return principal

    return dependency

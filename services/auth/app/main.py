from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
import hashlib
import os
import secrets
from urllib.parse import urlencode

from fastapi import Depends, FastAPI, HTTPException, Query, Response, status
import grpc
import httpx
import msgpack
from sqlalchemy import text
from sqlalchemy.orm import Session

from common.common.auth import create_access_token, get_current_principal
from common.common.auth import UserPrincipal
from common.grpc_generated import auth_pb2, auth_pb2_grpc
from . import database, models, schemas

app = FastAPI(title="Auth Service", version="2.0.0")

AUTH_GRPC_PORT = os.getenv("AUTH_GRPC_PORT", "50052")
JWT_EXPIRES_MINUTES = int(os.getenv("JWT_EXPIRES_MINUTES", "60"))
GITHUB_CLIENT_ID = os.getenv("GITHUB_CLIENT_ID", "")
GITHUB_CLIENT_SECRET = os.getenv("GITHUB_CLIENT_SECRET", "")
GITHUB_CALLBACK_URL = os.getenv(
    "GITHUB_CALLBACK_URL",
    "http://localhost:8000/auth/oauth/github/callback",
)
DEFAULT_ADMIN_EMAIL = os.getenv("DEFAULT_ADMIN_EMAIL", "admin@example.com")
DEFAULT_ADMIN_PASSWORD = os.getenv("DEFAULT_ADMIN_PASSWORD", "strongpass123")

grpc_server: grpc.aio.Server | None = None
grpc_task: asyncio.Task | None = None

models.Base.metadata.create_all(bind=database.engine)


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    iterations = 120000
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), iterations)
    return f"pbkdf2_sha256${iterations}${salt}${digest.hex()}"


def verify_password(password: str, password_hash: str) -> bool:
    try:
        algorithm, iterations_raw, salt, expected = password_hash.split("$", 3)
    except ValueError:
        return False
    if algorithm != "pbkdf2_sha256":
        return False

    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        int(iterations_raw),
    )
    return secrets.compare_digest(digest.hex(), expected)


def _safe_username_from_email(email: str, db: Session) -> str:
    base = email.split("@", 1)[0].replace(".", "_").replace("-", "_")
    candidate = base[:50] or "user"
    suffix = 1

    while db.query(models.User).filter(models.User.username == candidate).first():
        tail = f"_{suffix}"
        candidate = f"{base[: max(1, 50 - len(tail))]}{tail}"
        suffix += 1

    return candidate


def _user_to_dict(user: models.User) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "role": user.role,
    }


def _issue_token(user: models.User) -> schemas.TokenResponse:
    return schemas.TokenResponse(
        access_token=create_access_token(
            user_id=user.id,
            email=user.email,
            role=user.role,
            expires_minutes=JWT_EXPIRES_MINUTES,
        )
    )


def _ensure_auth_schema() -> None:
    statements = [
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS role VARCHAR(20) NOT NULL DEFAULT 'user'",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS oauth_provider VARCHAR(50)",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS oauth_subject VARCHAR(255)",
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_users_oauth_subject ON users(oauth_subject)",
        """
        CREATE TABLE IF NOT EXISTS oauth_states (
            id SERIAL PRIMARY KEY,
            provider VARCHAR(50) NOT NULL,
            state VARCHAR(255) UNIQUE NOT NULL,
            expires_at TIMESTAMP NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """,
    ]
    with database.engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))


def _ensure_default_admin() -> None:
    db = database.SessionLocal()
    try:
        admin = db.query(models.User).filter(models.User.email == DEFAULT_ADMIN_EMAIL).first()
        if admin:
            admin.role = "admin"
            if not admin.password_hash.startswith("pbkdf2_sha256$"):
                admin.password_hash = hash_password(DEFAULT_ADMIN_PASSWORD)
        else:
            admin = models.User(
                username="admin",
                email=DEFAULT_ADMIN_EMAIL,
                password_hash=hash_password(DEFAULT_ADMIN_PASSWORD),
                role="admin",
            )
            db.add(admin)
        db.commit()
    finally:
        db.close()


async def _grpc_get_user(payload: dict) -> dict:
    try:
        user_id = int(payload.get("user_id", 0))
    except Exception:
        return {"found": False, "id": 0, "username": "", "email": ""}

    if user_id <= 0:
        return {"found": False, "id": 0, "username": "", "email": ""}

    db = database.SessionLocal()
    try:
        user = db.query(models.User).filter(models.User.id == user_id).first()
        if not user:
            return {"found": False, "id": 0, "username": "", "email": ""}
        return {"found": True, **_user_to_dict(user)}
    finally:
        db.close()


async def _start_grpc_server() -> None:
    global grpc_server

    class AuthServicer(auth_pb2_grpc.AuthServiceServicer):
        async def GetUser(self, request: auth_pb2.GetUserRequest, context: grpc.aio.ServicerContext):
            payload = {"user_id": request.user_id}
            data = await _grpc_get_user(payload)
            return auth_pb2.GetUserReply(
                found=data["found"],
                id=data["id"],
                username=data["username"],
                email=data["email"],
            )

    grpc_server = grpc.aio.server()
    auth_pb2_grpc.add_AuthServiceServicer_to_server(AuthServicer(), grpc_server)
    grpc_server.add_insecure_port(f"[::]:{AUTH_GRPC_PORT}")
    await grpc_server.start()
    await grpc_server.wait_for_termination()


def _cleanup_expired_states(db: Session) -> None:
    db.query(models.OAuthState).filter(models.OAuthState.expires_at < datetime.now(UTC)).delete()
    db.commit()


@app.get("/")
async def root():
    return {"status": "ok", "service": "auth"}


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.on_event("startup")
async def on_startup() -> None:
    global grpc_task
    _ensure_auth_schema()
    _ensure_default_admin()
    grpc_task = asyncio.create_task(_start_grpc_server())


@app.on_event("shutdown")
async def on_shutdown() -> None:
    global grpc_server, grpc_task
    if grpc_server is not None:
        await grpc_server.stop(grace=1)
    if grpc_task is not None:
        grpc_task.cancel()


@app.post("/register", response_model=schemas.TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(payload: schemas.RegisterRequest, db: Session = Depends(database.get_db)):
    existing = db.query(models.User).filter(models.User.email == payload.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="User already exists")

    db_user = models.User(
        username=_safe_username_from_email(payload.email, db),
        email=payload.email,
        password_hash=hash_password(payload.password),
        role="user",
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return _issue_token(db_user)


@app.post("/login", response_model=schemas.TokenResponse)
async def login(credentials: schemas.LoginRequest, db: Session = Depends(database.get_db)):
    user = db.query(models.User).filter(models.User.email == credentials.email).first()
    if not user or not verify_password(credentials.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return _issue_token(user)


@app.get("/me", response_model=schemas.MeResponse)
async def me(principal: UserPrincipal = Depends(get_current_principal)):
    return schemas.MeResponse(user_id=principal.user_id, email=principal.email, role=principal.role)


@app.get("/oauth/github/login")
async def oauth_github_login(db: Session = Depends(database.get_db)):
    if not GITHUB_CLIENT_ID or not GITHUB_CLIENT_SECRET:
        raise HTTPException(status_code=503, detail="GitHub OAuth is not configured")

    _cleanup_expired_states(db)
    state_value = secrets.token_urlsafe(24)
    oauth_state = models.OAuthState(
        provider="github",
        state=state_value,
        expires_at=datetime.now(UTC) + timedelta(minutes=10),
    )
    db.add(oauth_state)
    db.commit()

    params = urlencode(
        {
            "client_id": GITHUB_CLIENT_ID,
            "redirect_uri": GITHUB_CALLBACK_URL,
            "scope": "read:user user:email",
            "state": state_value,
        }
    )
    return Response(
        status_code=status.HTTP_307_TEMPORARY_REDIRECT,
        headers={"Location": f"https://github.com/login/oauth/authorize?{params}"},
    )


@app.get("/oauth/github/callback")
async def oauth_github_callback(
    code: str = Query(...),
    state: str = Query(...),
    db: Session = Depends(database.get_db),
):
    if not GITHUB_CLIENT_ID or not GITHUB_CLIENT_SECRET:
        raise HTTPException(status_code=503, detail="GitHub OAuth is not configured")

    _cleanup_expired_states(db)
    db_state = db.query(models.OAuthState).filter(models.OAuthState.state == state).first()
    if not db_state:
        raise HTTPException(status_code=400, detail="Invalid OAuth state")

    db.delete(db_state)
    db.commit()

    async with httpx.AsyncClient(timeout=10.0, trust_env=False) as client:
        token_resp = await client.post(
            "https://github.com/login/oauth/access_token",
            headers={"Accept": "application/json"},
            data={
                "client_id": GITHUB_CLIENT_ID,
                "client_secret": GITHUB_CLIENT_SECRET,
                "code": code,
                "redirect_uri": GITHUB_CALLBACK_URL,
                "state": state,
            },
        )
        token_resp.raise_for_status()
        access_token = token_resp.json().get("access_token")
        if not access_token:
            raise HTTPException(status_code=400, detail="GitHub access token was not returned")

        auth_headers = {"Authorization": f"Bearer {access_token}", "Accept": "application/json"}
        profile_resp = await client.get("https://api.github.com/user", headers=auth_headers)
        emails_resp = await client.get("https://api.github.com/user/emails", headers=auth_headers)
        profile_resp.raise_for_status()
        emails_resp.raise_for_status()

    profile = profile_resp.json()
    emails = emails_resp.json()
    primary_email = next((item["email"] for item in emails if item.get("primary")), None)
    if not primary_email:
        primary_email = profile.get("email")
    if not primary_email:
        raise HTTPException(status_code=400, detail="GitHub email was not returned")

    oauth_subject = f"github:{profile['id']}"
    user = db.query(models.User).filter(models.User.oauth_subject == oauth_subject).first()
    if not user:
        user = db.query(models.User).filter(models.User.email == primary_email).first()

    if not user:
        user = models.User(
            username=_safe_username_from_email(primary_email, db),
            email=primary_email,
            password_hash=hash_password(secrets.token_urlsafe(32)),
            role="user",
        )
        db.add(user)
        db.flush()

    user.oauth_provider = "github"
    user.oauth_subject = oauth_subject
    db.commit()
    db.refresh(user)
    token = _issue_token(user)
    return {"access_token": token.access_token, "token_type": token.token_type}


@app.get("/users/{user_id}", response_model=schemas.UserResponse)
async def get_user(user_id: int, db: Session = Depends(database.get_db)):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@app.get("/internal/users/{user_id}/http", response_model=schemas.UserResponse)
async def get_user_http(user_id: int, db: Session = Depends(database.get_db)):
    return await get_user(user_id, db)


@app.get("/internal/users/{user_id}/msgpack")
async def get_user_msgpack(user_id: int, db: Session = Depends(database.get_db)):
    user = await get_user(user_id, db)
    packed = msgpack.packb(_user_to_dict(user), use_bin_type=True)
    return Response(content=packed, media_type="application/msgpack")

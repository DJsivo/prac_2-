import asyncio
import os

from fastapi import Depends, FastAPI, HTTPException, Response, status
import grpc
import msgpack
from sqlalchemy.orm import Session
import hashlib

from common.grpc_generated import auth_pb2, auth_pb2_grpc
from . import models, schemas, database

app = FastAPI(title="Auth Service", version="1.0.0")
AUTH_GRPC_PORT = os.getenv("AUTH_GRPC_PORT", "50052")
grpc_server: grpc.aio.Server | None = None
grpc_task: asyncio.Task | None = None

# Создаём таблицы при старте
models.Base.metadata.create_all(bind=database.engine)


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def _user_to_dict(user: models.User) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
    }


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


@app.get("/")
async def root():
    return {"status": "ok", "service": "auth"}


@app.get("/health")
async def health():
    return {"alive": True}


@app.on_event("startup")
async def on_startup() -> None:
    global grpc_task
    grpc_task = asyncio.create_task(_start_grpc_server())


@app.on_event("shutdown")
async def on_shutdown() -> None:
    global grpc_server, grpc_task
    if grpc_server is not None:
        await grpc_server.stop(grace=1)
    if grpc_task is not None:
        grpc_task.cancel()


@app.post("/register", response_model=schemas.UserResponse, status_code=status.HTTP_201_CREATED)
async def register(user: schemas.UserCreate, db: Session = Depends(database.get_db)):
    existing = db.query(models.User).filter(
        (models.User.username == user.username) | 
        (models.User.email == user.email)
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="User already exists")
    
    db_user = models.User(
        username=user.username,
        email=user.email,
        password_hash=hash_password(user.password)
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


@app.post("/login", response_model=schemas.TokenResponse)
async def login(credentials: schemas.LoginRequest, db: Session = Depends(database.get_db)):
    user = db.query(models.User).filter(models.User.username == credentials.username).first()
    if not user or user.password_hash != hash_password(credentials.password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    # Простой токен 
    token = hashlib.sha256(f"{user.id}:{credentials.username}".encode()).hexdigest()
    return {"access_token": token, "token_type": "bearer"}


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
    packed = msgpack.packb(
        _user_to_dict(user),
        use_bin_type=True,
    )
    return Response(content=packed, media_type="application/msgpack")



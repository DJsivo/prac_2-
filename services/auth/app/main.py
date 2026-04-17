from fastapi import FastAPI, HTTPException, Depends, status
from sqlalchemy.orm import Session
import hashlib

from . import models, schemas, database

app = FastAPI(title="Auth Service", version="1.0.0")

# Создаём таблицы при старте (для лабы ок)
models.Base.metadata.create_all(bind=database.engine)


def hash_password(password: str) -> str:
    """Простое хеширование (для лабы; в продакшене использовать bcrypt)"""
    return hashlib.sha256(password.encode()).hexdigest()


@app.get("/")
async def root():
    return {"status": "ok", "service": "auth"}


@app.get("/health")
async def health():
    return {"alive": True}


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


@app.get("/internal/users/{user_id}/msgpack", response_model=schemas.UserResponse)
async def get_user_msgpack(user_id: int, db: Session = Depends(database.get_db)):
    return await get_user(user_id, db)


@app.get("/internal/users/{user_id}/grpc", response_model=schemas.UserResponse)
async def get_user_grpc(user_id: int, db: Session = Depends(database.get_db)):
    return await get_user(user_id, db)

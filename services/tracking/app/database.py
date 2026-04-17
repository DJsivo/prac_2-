from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os


def _read_password() -> str:
    password_file = os.getenv("DB_PASSWORD_FILE")
    if not password_file:
        return "postgres123"

    with open(password_file, "r", encoding="utf-8") as file:
        return file.read().strip()


DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = _read_password()
DB_HOST = os.getenv("DB_HOST", "postgres")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "logistics")

DATABASE_URL = f"postgresql+psycopg://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


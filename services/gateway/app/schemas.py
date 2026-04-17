# services/gateway/app/schemas.py
from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str
    service: str


class ErrorResponse(BaseModel):
    detail: str


class ProxyResponse(BaseModel):
    """Универсальный ответ от прокси"""
    data: dict | list | None = None
    error: str | None = None
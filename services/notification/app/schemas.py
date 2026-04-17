from datetime import datetime

from pydantic import BaseModel, Field


class NotificationCreate(BaseModel):
    user_id: int = Field(..., ge=1)
    order_id: int | None = Field(default=None, ge=1)
    message: str = Field(..., min_length=1)


class NotificationReadUpdate(BaseModel):
    is_read: bool = True


class NotificationResponse(BaseModel):
    id: int
    user_id: int
    order_id: int | None
    message: str
    is_read: bool
    created_at: datetime

    class Config:
        from_attributes = True

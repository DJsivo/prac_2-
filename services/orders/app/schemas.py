from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field


class OrderCreate(BaseModel):
    user_id: int = Field(..., ge=1)
    total_amount: Decimal = Field(..., ge=0)
    notify_method: Literal["msgpack"] = "msgpack"


class OrderStatusUpdate(BaseModel):
    status: Literal["pending", "processing", "shipped", "delivered", "cancelled"]


class OrderResponse(BaseModel):
    id: int
    user_id: int
    status: str
    total_amount: Decimal
    created_at: datetime

    class Config:
        from_attributes = True

from datetime import datetime

from pydantic import BaseModel, Field


class TrackingCreate(BaseModel):
    location: str = Field(..., min_length=2, max_length=100)
    status: str = Field(..., min_length=2, max_length=50)


class TrackingInitRequest(BaseModel):
    order_id: int = Field(..., ge=1)


class TrackingResponse(BaseModel):
    id: int
    order_id: int
    location: str
    status: str
    updated_at: datetime

    class Config:
        from_attributes = True

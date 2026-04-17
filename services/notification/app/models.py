from sqlalchemy import Boolean, Column, DateTime, Integer, Text, func
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    order_id = Column(Integer, nullable=True, index=True)
    message = Column(Text, nullable=False)
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

from fastapi import Depends, FastAPI, HTTPException, status
from sqlalchemy.orm import Session

from . import database, models, schemas

app = FastAPI(title="Notification Service", version="1.0.0")

models.Base.metadata.create_all(bind=database.engine)


@app.get("/")
async def root():
    return {"status": "ok", "service": "notification"}


@app.get("/health")
async def health():
    return {"alive": True}


def _create_notification(payload: schemas.NotificationCreate, db: Session) -> models.Notification:
    db_notification = models.Notification(
        user_id=payload.user_id,
        order_id=payload.order_id,
        message=payload.message,
        is_read=False,
    )
    db.add(db_notification)
    db.commit()
    db.refresh(db_notification)
    return db_notification


@app.post("/notifications", response_model=schemas.NotificationResponse, status_code=status.HTTP_201_CREATED)
async def create_notification(payload: schemas.NotificationCreate, db: Session = Depends(database.get_db)):
    return _create_notification(payload, db)


@app.get("/notifications", response_model=list[schemas.NotificationResponse])
async def list_notifications(user_id: int | None = None, db: Session = Depends(database.get_db)):
    query = db.query(models.Notification)
    if user_id is not None:
        query = query.filter(models.Notification.user_id == user_id)
    return query.order_by(models.Notification.created_at.desc()).all()


@app.patch("/notifications/{notification_id}/read", response_model=schemas.NotificationResponse)
async def mark_as_read(
    notification_id: int,
    payload: schemas.NotificationReadUpdate,
    db: Session = Depends(database.get_db),
):
    notification = db.query(models.Notification).filter(models.Notification.id == notification_id).first()
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")

    notification.is_read = payload.is_read
    db.commit()
    db.refresh(notification)
    return notification


@app.post("/internal/order-created/http", status_code=status.HTTP_201_CREATED)
async def internal_order_created_http(payload: schemas.NotificationCreate, db: Session = Depends(database.get_db)):
    notification = _create_notification(payload, db)
    return {"ok": True, "channel": "http", "notification_id": notification.id}

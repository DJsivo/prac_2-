import asyncio
import json
import os

from fastapi import Depends, FastAPI, HTTPException, Request, status
import grpc
import msgpack
from sqlalchemy.orm import Session

from common.grpc_generated import notification_pb2, notification_pb2_grpc
from . import database, models, schemas

app = FastAPI(title="Notification Service", version="1.0.0")

models.Base.metadata.create_all(bind=database.engine)
GRPC_PORT = os.getenv("GRPC_PORT", "50051")
grpc_server: grpc.aio.Server | None = None
grpc_task: asyncio.Task | None = None


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


def _decode_notification_payload_from_request(request: Request, body: bytes) -> schemas.NotificationCreate:
    content_type = request.headers.get("content-type", "").lower()
    if "application/msgpack" in content_type:
        data = msgpack.unpackb(body, raw=False)
    else:
        data = json.loads(body.decode("utf-8"))
    return schemas.NotificationCreate(**data)


async def _grpc_create_order_notification(payload: dict) -> dict:
    db = database.SessionLocal()
    try:
        notification = _create_notification(schemas.NotificationCreate(**payload), db)
        return {"ok": True, "channel": "grpc", "notification_id": notification.id}
    finally:
        db.close()


async def _start_grpc_server() -> None:
    global grpc_server
    
    class NotificationServicer(notification_pb2_grpc.NotificationServiceServicer):
        async def CreateOrderNotification(
            self,
            request: notification_pb2.NotificationRequest,
            context: grpc.aio.ServicerContext,
        ):
            payload = {
                "user_id": request.user_id,
                "order_id": request.order_id,
                "message": request.message,
            }
            data = await _grpc_create_order_notification(payload)
            return notification_pb2.NotificationReply(
                ok=data["ok"],
                channel=data["channel"],
                notification_id=data["notification_id"],
            )

    grpc_server = grpc.aio.server()
    notification_pb2_grpc.add_NotificationServiceServicer_to_server(NotificationServicer(), grpc_server)
    grpc_server.add_insecure_port(f"[::]:{GRPC_PORT}")
    await grpc_server.start()
    await grpc_server.wait_for_termination()


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


@app.post("/internal/order-created/msgpack", status_code=status.HTTP_201_CREATED)
async def internal_order_created_msgpack(request: Request, db: Session = Depends(database.get_db)):
    body = await request.body()
    payload = _decode_notification_payload_from_request(request, body)
    notification = _create_notification(payload, db)
    return {"ok": True, "channel": "msgpack", "notification_id": notification.id}

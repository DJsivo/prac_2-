import asyncio
import json
import os

from fastapi import Depends, FastAPI, Request, status
import grpc
import msgpack
from sqlalchemy.orm import Session

from . import database, models, schemas

app = FastAPI(title="Tracking Service", version="1.0.0")
TRACKING_GRPC_PORT = os.getenv("TRACKING_GRPC_PORT", "50053")
grpc_server: grpc.aio.Server | None = None
grpc_task: asyncio.Task | None = None

models.Base.metadata.create_all(bind=database.engine)


@app.get("/")
async def root():
    return {"status": "ok", "service": "tracking"}


@app.get("/health")
async def health():
    return {"alive": True}


def _init_tracking_for_order_by_id(order_id: int, db: Session) -> dict:
    existing = (
        db.query(models.TrackingEvent)
        .filter(models.TrackingEvent.order_id == order_id)
        .first()
    )
    if existing:
        return {"ok": True, "tracking_id": existing.id, "message": "Tracking already initialized"}

    event = models.TrackingEvent(
        order_id=order_id,
        location="Warehouse",
        status="processing",
    )
    db.add(event)
    db.commit()
    db.refresh(event)

    return {"ok": True, "tracking_id": event.id, "message": "Tracking initialized"}


async def _grpc_init_tracking(payload: dict) -> dict:
    try:
        request = schemas.TrackingInitRequest(order_id=int(payload.get("order_id", 0)))
    except Exception:
        return {"ok": False, "tracking_id": 0, "message": "Invalid order_id"}

    db = database.SessionLocal()
    try:
        return _init_tracking_for_order_by_id(request.order_id, db)
    finally:
        db.close()


async def _start_grpc_server() -> None:
    global grpc_server

    async def grpc_handler(payload: dict, context: grpc.aio.ServicerContext) -> dict:
        return await _grpc_init_tracking(payload)

    handler = grpc.unary_unary_rpc_method_handler(
        grpc_handler,
        request_deserializer=lambda raw: json.loads(raw.decode("utf-8")),
        response_serializer=lambda data: json.dumps(data).encode("utf-8"),
    )
    service = grpc.method_handlers_generic_handler(
        "tracking.TrackingService",
        {"InitTrackingForOrder": handler},
    )

    grpc_server = grpc.aio.server()
    grpc_server.add_generic_rpc_handlers((service,))
    grpc_server.add_insecure_port(f"[::]:{TRACKING_GRPC_PORT}")
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


@app.get("/tracking/order/{order_id}", response_model=list[schemas.TrackingResponse])
async def get_order_tracking(order_id: int, db: Session = Depends(database.get_db)):
    return (
        db.query(models.TrackingEvent)
        .filter(models.TrackingEvent.order_id == order_id)
        .order_by(models.TrackingEvent.updated_at.desc())
        .all()
    )


@app.post("/tracking/order/{order_id}/events", response_model=schemas.TrackingResponse, status_code=status.HTTP_201_CREATED)
async def create_tracking_event(
    order_id: int,
    payload: schemas.TrackingCreate,
    db: Session = Depends(database.get_db),
):
    event = models.TrackingEvent(
        order_id=order_id,
        location=payload.location,
        status=payload.status,
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


@app.post("/tracking/internal/order-created/http", status_code=status.HTTP_201_CREATED)
async def init_tracking_for_order_http(payload: schemas.TrackingInitRequest, db: Session = Depends(database.get_db)):
    return _init_tracking_for_order_by_id(payload.order_id, db)


@app.post("/tracking/internal/order-created/msgpack", status_code=status.HTTP_201_CREATED)
async def init_tracking_for_order_msgpack(request: Request, db: Session = Depends(database.get_db)):
    body = await request.body()
    content_type = request.headers.get("content-type", "").lower()
    if "application/msgpack" in content_type:
        data = msgpack.unpackb(body, raw=False)
    else:
        data = json.loads(body.decode("utf-8"))
    payload = schemas.TrackingInitRequest(**data)
    return _init_tracking_for_order_by_id(payload.order_id, db)



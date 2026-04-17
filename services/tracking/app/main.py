from fastapi import Depends, FastAPI, status
from sqlalchemy.orm import Session

from . import database, models, schemas

app = FastAPI(title="Tracking Service", version="1.0.0")

models.Base.metadata.create_all(bind=database.engine)


@app.get("/")
async def root():
    return {"status": "ok", "service": "tracking"}


@app.get("/health")
async def health():
    return {"alive": True}


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


@app.post("/tracking/internal/order-created", status_code=status.HTTP_201_CREATED)
async def init_tracking_for_order(payload: schemas.TrackingInitRequest, db: Session = Depends(database.get_db)):
    existing = (
        db.query(models.TrackingEvent)
        .filter(models.TrackingEvent.order_id == payload.order_id)
        .first()
    )
    if existing:
        return {"ok": True, "message": "Tracking already initialized"}

    event = models.TrackingEvent(
        order_id=payload.order_id,
        location="Warehouse",
        status="processing",
    )
    db.add(event)
    db.commit()
    db.refresh(event)

    return {"ok": True, "tracking_id": event.id}


@app.post("/tracking/internal/order-created/grpc", status_code=status.HTTP_201_CREATED)
async def init_tracking_for_order_transport(payload: schemas.TrackingInitRequest, db: Session = Depends(database.get_db)):
    return await init_tracking_for_order(payload, db)

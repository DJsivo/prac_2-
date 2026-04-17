from fastapi import Depends, FastAPI, HTTPException, status
from sqlalchemy.orm import Session
import httpx
import os

from . import database, models, schemas

app = FastAPI(title="Order Service", version="1.0.0")

AUTH_URL = os.getenv("AUTH_SERVICE_URL", "http://auth:8001")
NOTIFICATION_URL = os.getenv("NOTIFICATION_SERVICE_URL", "http://notification:8004")
TRACKING_URL = os.getenv("TRACKING_SERVICE_URL", "http://tracking:8003")

models.Base.metadata.create_all(bind=database.engine)


@app.get("/")
async def root():
    return {"status": "ok", "service": "orders"}


@app.get("/health")
async def health():
    return {"alive": True}


async def _ensure_user_exists(user_id: int) -> None:
    async with httpx.AsyncClient(timeout=5.0) as client:
        try:
            response = await client.get(f"{AUTH_URL}/internal/users/{user_id}/grpc")
        except httpx.TimeoutException as exc:
            raise HTTPException(status_code=504, detail=f"Auth service timeout: {exc}") from exc
        except httpx.RequestError as exc:
            raise HTTPException(status_code=503, detail=f"Auth service unavailable: {exc}") from exc

    if response.status_code == 404:
        raise HTTPException(status_code=404, detail="User not found")
    if response.status_code >= 500:
        raise HTTPException(status_code=503, detail="Auth service internal error")
    if response.status_code >= 400:
        raise HTTPException(status_code=400, detail="Cannot validate user")


async def _notify_about_order(order: models.Order) -> None:
    payload = {
        "user_id": order.user_id,
        "order_id": order.id,
        "message": f"Order #{order.id} created with status '{order.status}'",
    }

    async with httpx.AsyncClient(timeout=5.0) as client:
        try:
            await client.post(f"{NOTIFICATION_URL}/internal/order-created/grpc", json=payload)
            await client.post(
                f"{TRACKING_URL}/tracking/internal/order-created/grpc",
                json={"order_id": order.id},
            )
        except (httpx.RequestError, httpx.TimeoutException):
            return


async def _create_order(order: schemas.OrderCreate, db: Session) -> models.Order:
    await _ensure_user_exists(order.user_id)

    db_order = models.Order(
        user_id=order.user_id,
        status="pending",
        total_amount=order.total_amount,
    )
    db.add(db_order)
    db.commit()
    db.refresh(db_order)

    await _notify_about_order(db_order)
    return db_order


@app.post("/orders", response_model=schemas.OrderResponse, status_code=status.HTTP_201_CREATED)
async def create_order(order: schemas.OrderCreate, db: Session = Depends(database.get_db)):
    return await _create_order(order, db)


@app.post("/orders/grpc", response_model=schemas.OrderResponse, status_code=status.HTTP_201_CREATED)
async def create_order_transport(order: schemas.OrderCreate, db: Session = Depends(database.get_db)):
    return await _create_order(order.model_copy(update={"notify_method": "grpc"}), db)


@app.get("/orders", response_model=list[schemas.OrderResponse])
async def list_orders(db: Session = Depends(database.get_db)):
    return db.query(models.Order).order_by(models.Order.id.desc()).all()


@app.get("/orders/{order_id}", response_model=schemas.OrderResponse)
async def get_order(order_id: int, db: Session = Depends(database.get_db)):
    order = db.query(models.Order).filter(models.Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order


@app.patch("/orders/{order_id}/status", response_model=schemas.OrderResponse)
async def update_order_status(
    order_id: int,
    update: schemas.OrderStatusUpdate,
    db: Session = Depends(database.get_db),
):
    order = db.query(models.Order).filter(models.Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    order.status = update.status
    db.commit()
    db.refresh(order)
    return order

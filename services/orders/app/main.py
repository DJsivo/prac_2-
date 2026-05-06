from fastapi import Depends, FastAPI, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func
import httpx
import grpc
import msgpack
import os

from common.common.auth import get_current_principal, require_roles, UserPrincipal
from common.grpc_generated import auth_pb2, auth_pb2_grpc, notification_pb2, notification_pb2_grpc, tracking_pb2, tracking_pb2_grpc
from . import database, models, schemas

app = FastAPI(title="Order Service", version="1.0.0")

AUTH_URL = os.getenv("AUTH_SERVICE_URL", "http://auth:8001")
AUTH_GRPC_URL = os.getenv("AUTH_GRPC_URL", "auth:50052")
NOTIFICATION_URL = os.getenv("NOTIFICATION_SERVICE_URL", "http://notification:8004")
NOTIFICATION_GRPC_URL = os.getenv("NOTIFICATION_GRPC_URL", "notification:50051")
TRACKING_URL = os.getenv("TRACKING_SERVICE_URL", "http://tracking:8003")
TRACKING_GRPC_URL = os.getenv("TRACKING_GRPC_URL", "tracking:50053")

models.Base.metadata.create_all(bind=database.engine)


@app.get("/")
async def root():
    return {"status": "ok", "service": "orders"}


@app.get("/health")
async def health():
    return {"alive": True}


async def _ensure_user_exists(user_id: int, method: str) -> None:
    try:
        if method == "grpc":
            async with grpc.aio.insecure_channel(AUTH_GRPC_URL) as channel:
                stub = auth_pb2_grpc.AuthServiceStub(channel)
                result = await stub.GetUser(auth_pb2.GetUserRequest(user_id=user_id), timeout=5.0)
                if not result.found:
                    raise HTTPException(status_code=404, detail="User not found")
                return

        auth_endpoint = f"/internal/users/{user_id}/http"
        headers: dict[str, str] | None = None

        if method == "msgpack":
            auth_endpoint = f"/internal/users/{user_id}/msgpack"
            headers = {"accept": "application/msgpack"}

        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{AUTH_URL}{auth_endpoint}", headers=headers)

        if response.status_code == 404:
            raise HTTPException(status_code=404, detail="User not found")
        if response.status_code >= 500:
            raise HTTPException(status_code=503, detail="Auth service internal error")
        if response.status_code >= 400:
            raise HTTPException(status_code=400, detail="Cannot validate user")

        if method == "msgpack":
            msgpack.unpackb(response.content, raw=False)
    except httpx.TimeoutException as exc:
        raise HTTPException(status_code=504, detail=f"Auth service timeout: {exc}") from exc
    except httpx.RequestError as exc:
        raise HTTPException(status_code=503, detail=f"Auth service unavailable: {exc}") from exc
    except grpc.RpcError as exc:
        raise HTTPException(status_code=503, detail=f"Auth gRPC unavailable: {exc}") from exc
    except (msgpack.ExtraData, msgpack.FormatError, msgpack.StackError, ValueError) as exc:
        raise HTTPException(status_code=503, detail=f"Auth msgpack invalid response: {exc}") from exc


async def _notify_about_order(order: models.Order, method: str) -> None:
    payload = {
        "user_id": order.user_id,
        "order_id": order.id,
        "message": f"Order #{order.id} created with status '{order.status}'",
    }

    tracking_endpoint_by_method = {
        "http": "/tracking/internal/order-created/http",
        "msgpack": "/tracking/internal/order-created/msgpack",
    }
    tracking_endpoint = tracking_endpoint_by_method.get(method, "/tracking/internal/order-created/http")

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            if method == "msgpack":
                raw_notification = msgpack.packb(payload, use_bin_type=True)
                await client.post(
                    f"{NOTIFICATION_URL}/internal/order-created/msgpack",
                    content=raw_notification,
                    headers={"content-type": "application/msgpack"},
                )

                raw_tracking = msgpack.packb({"order_id": order.id}, use_bin_type=True)
                await client.post(
                    f"{TRACKING_URL}{tracking_endpoint}",
                    content=raw_tracking,
                    headers={"content-type": "application/msgpack"},
                )
            elif method == "grpc":
                async with grpc.aio.insecure_channel(NOTIFICATION_GRPC_URL) as channel:
                    stub = notification_pb2_grpc.NotificationServiceStub(channel)
                    await stub.CreateOrderNotification(
                        notification_pb2.NotificationRequest(
                            user_id=payload["user_id"],
                            order_id=payload["order_id"],
                            message=payload["message"],
                        ),
                        timeout=5.0,
                    )

                async with grpc.aio.insecure_channel(TRACKING_GRPC_URL) as tracking_channel:
                    tracking_stub = tracking_pb2_grpc.TrackingServiceStub(tracking_channel)
                    await tracking_stub.InitTrackingForOrder(
                        tracking_pb2.InitTrackingRequest(order_id=order.id),
                        timeout=5.0,
                    )
            else:
                await client.post(f"{NOTIFICATION_URL}/internal/order-created/http", json=payload)
                await client.post(
                    f"{TRACKING_URL}{tracking_endpoint}",
                    json={"order_id": order.id},
                )
    except (httpx.RequestError, httpx.TimeoutException, grpc.RpcError):
        # For lab work we keep order creation successful even if side effects fail.
        return


async def _create_order(order: schemas.OrderCreate, db: Session) -> models.Order:
    await _ensure_user_exists(order.user_id, order.notify_method)

    db_order = models.Order(
        user_id=order.user_id,
        status="pending",
        total_amount=order.total_amount,
    )
    db.add(db_order)
    db.commit()
    db.refresh(db_order)

    await _notify_about_order(db_order, order.notify_method)
    return db_order


def _get_order_or_404(order_id: int, db: Session) -> models.Order:
    order = db.query(models.Order).filter(models.Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order


def _ensure_order_access(order: models.Order, principal: UserPrincipal) -> None:
    if principal.role == "admin":
        return
    if order.user_id != principal.user_id:
        raise HTTPException(status_code=403, detail="Insufficient permissions")


@app.post("/orders", response_model=schemas.OrderResponse, status_code=status.HTTP_201_CREATED)
async def create_order(
    order: schemas.OrderCreate,
    db: Session = Depends(database.get_db),
    principal: UserPrincipal = Depends(require_roles("user", "admin")),
):
    if principal.role != "admin" and order.user_id != principal.user_id:
        raise HTTPException(status_code=403, detail="Users can create orders only for themselves")
    return await _create_order(order, db)


@app.post("/orders/http", response_model=schemas.OrderResponse, status_code=status.HTTP_201_CREATED)
async def create_order_http(
    order: schemas.OrderCreate,
    db: Session = Depends(database.get_db),
    principal: UserPrincipal = Depends(require_roles("user", "admin")),
):
    if principal.role != "admin" and order.user_id != principal.user_id:
        raise HTTPException(status_code=403, detail="Users can create orders only for themselves")
    return await _create_order(order.model_copy(update={"notify_method": "http"}), db)


@app.post("/orders/msgpack", response_model=schemas.OrderResponse, status_code=status.HTTP_201_CREATED)
async def create_order_msgpack(
    order: schemas.OrderCreate,
    db: Session = Depends(database.get_db),
    principal: UserPrincipal = Depends(require_roles("user", "admin")),
):
    if principal.role != "admin" and order.user_id != principal.user_id:
        raise HTTPException(status_code=403, detail="Users can create orders only for themselves")
    return await _create_order(order.model_copy(update={"notify_method": "msgpack"}), db)


@app.post("/orders/grpc", response_model=schemas.OrderResponse, status_code=status.HTTP_201_CREATED)
async def create_order_grpc(
    order: schemas.OrderCreate,
    db: Session = Depends(database.get_db),
    principal: UserPrincipal = Depends(require_roles("user", "admin")),
):
    if principal.role != "admin" and order.user_id != principal.user_id:
        raise HTTPException(status_code=403, detail="Users can create orders only for themselves")
    return await _create_order(order.model_copy(update={"notify_method": "grpc"}), db)


@app.get("/orders", response_model=list[schemas.OrderResponse])
async def list_orders(
    db: Session = Depends(database.get_db),
    principal: UserPrincipal = Depends(get_current_principal),
):
    query = db.query(models.Order)
    if principal.role != "admin":
        query = query.filter(models.Order.user_id == principal.user_id)
    return query.order_by(models.Order.id.desc()).all()


@app.get("/orders/{order_id}", response_model=schemas.OrderResponse)
async def get_order(
    order_id: int,
    db: Session = Depends(database.get_db),
    principal: UserPrincipal = Depends(get_current_principal),
):
    order = _get_order_or_404(order_id, db)
    _ensure_order_access(order, principal)
    return order


@app.patch("/orders/{order_id}/status", response_model=schemas.OrderResponse)
async def update_order_status(
    order_id: int,
    update: schemas.OrderStatusUpdate,
    db: Session = Depends(database.get_db),
    principal: UserPrincipal = Depends(require_roles("admin")),
):
    order = _get_order_or_404(order_id, db)

    order.status = update.status
    db.commit()
    db.refresh(order)
    return order


@app.get("/metrics")
async def get_metrics(
    db: Session = Depends(database.get_db),
    principal: UserPrincipal = Depends(require_roles("admin")),
):
    total_orders = db.query(func.count(models.Order.id)).scalar() or 0
    total_revenue = db.query(func.coalesce(func.sum(models.Order.total_amount), 0)).scalar() or 0
    status_rows = (
        db.query(models.Order.status, func.count(models.Order.id))
        .group_by(models.Order.status)
        .order_by(models.Order.status.asc())
        .all()
    )
    return {
        "total_orders": int(total_orders),
        "total_revenue": float(total_revenue),
        "orders_by_status": {status_name: int(count) for status_name, count in status_rows},
    }

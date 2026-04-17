from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import JSONResponse
import httpx
import os

app = FastAPI(title="Logistics Gateway", version="1.0.0")

AUTH_URL = os.getenv("AUTH_SERVICE_URL", "http://auth:8001")
ORDER_URL = os.getenv("ORDER_SERVICE_URL", "http://orders:8002")
TRACKING_URL = os.getenv("TRACKING_SERVICE_URL", "http://tracking:8003")
NOTIFY_URL = os.getenv("NOTIFICATION_SERVICE_URL", "http://notification:8004")


@app.get("/")
async def root():
    return {"status": "ok", "service": "gateway"}


@app.get("/internal/ping/msgpack")
async def ping_transport():
    return {"ok": True, "transport": "msgpack", "service": "gateway"}


def _forward_headers(request: Request) -> dict:
    return {
        key: value
        for key, value in request.headers.items()
        if key.lower() not in {"host", "content-length"}
    }


async def proxy_request(base_url: str, endpoint: str, request: Request, service_name: str):
    target = f"{base_url}/{endpoint}".rstrip("/")
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.request(
                method=request.method,
                url=target,
                params=request.query_params,
                headers=_forward_headers(request),
                content=await request.body(),
            )
        except httpx.TimeoutException as exc:
            raise HTTPException(status_code=504, detail=f"{service_name} timeout: {exc}") from exc
        except httpx.RequestError as exc:
            raise HTTPException(status_code=503, detail=f"{service_name} unavailable: {exc}") from exc

    content_type = resp.headers.get("content-type", "")
    if "application/json" in content_type:
        try:
            return JSONResponse(status_code=resp.status_code, content=resp.json())
        except ValueError:
            return Response(
                status_code=resp.status_code,
                content=resp.text,
                media_type="text/plain",
            )

    return Response(
        status_code=resp.status_code,
        content=resp.content,
        media_type=content_type or None,
    )


@app.api_route("/api/auth/{endpoint:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def auth_proxy(endpoint: str, request: Request):
    return await proxy_request(AUTH_URL, endpoint, request, "Auth service")


@app.api_route("/api/orders/{endpoint:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def orders_proxy(endpoint: str, request: Request):
    return await proxy_request(ORDER_URL, endpoint, request, "Order service")


@app.api_route("/api/tracking/{endpoint:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def tracking_proxy(endpoint: str, request: Request):
    return await proxy_request(TRACKING_URL, endpoint, request, "Tracking service")


@app.api_route("/api/notifications/{endpoint:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def notify_proxy(endpoint: str, request: Request):
    return await proxy_request(NOTIFY_URL, endpoint, request, "Notification service")

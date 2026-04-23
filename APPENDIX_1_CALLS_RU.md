# Приложение 1. Вызовы микросервисов (методы и внешние вызовы)

## Сервис `gateway`

| Метод сервиса | Внешние вызовы |
|---|---|
| `GET /` | Нет |
| `GET /internal/ping/http` | Нет |
| `ANY /api/auth/{endpoint:path}` | HTTP -> `auth` (`{AUTH_URL}/{endpoint}`) |
| `ANY /api/orders/{endpoint:path}` | HTTP -> `orders` (`{ORDER_URL}/{endpoint}`) |
| `ANY /api/tracking/{endpoint:path}` | HTTP -> `tracking` (`{TRACKING_URL}/{endpoint}`) |
| `ANY /api/notifications/{endpoint:path}` | HTTP -> `notification` (`{NOTIFY_URL}/{endpoint}`) |

## Сервис `orders`

| Метод сервиса | Внешние вызовы |
|---|---|
| `GET /` | Нет |
| `GET /health` | Нет |
| `GET /orders` | Нет (чтение своей БД) |
| `GET /orders/{order_id}` | Нет (чтение своей БД) |
| `PATCH /orders/{order_id}/status` | Нет (запись в свою БД) |
| `POST /orders` (`notify_method=http`) | 1) HTTP -> `auth`: `GET /internal/users/{id}/http` 2) HTTP -> `notification`: `POST /internal/order-created/http` 3) HTTP -> `tracking`: `POST /tracking/internal/order-created/http` |
| `POST /orders` (`notify_method=msgpack`) | 1) HTTP -> `auth`: `GET /internal/users/{id}/msgpack` 2) HTTP + MessagePack -> `notification`: `POST /internal/order-created/msgpack` 3) HTTP + MessagePack -> `tracking`: `POST /tracking/internal/order-created/msgpack` |
| `POST /orders` (`notify_method=grpc`) | 1) gRPC -> `auth.AuthService/GetUser` 2) gRPC -> `notification.NotificationService/CreateOrderNotification` 3) gRPC -> `tracking.TrackingService/InitTrackingForOrder` |
| `POST /orders/http` | То же, что `POST /orders` с `notify_method=http` |
| `POST /orders/msgpack` | То же, что `POST /orders` с `notify_method=msgpack` |
| `POST /orders/grpc` | То же, что `POST /orders` с `notify_method=grpc` |

## Сервис `auth`

| Метод сервиса | Внешние вызовы |
|---|---|
| `GET /` | Нет |
| `GET /health` | Нет |
| `POST /register` | Нет (запись в свою БД) |
| `POST /login` | Нет (чтение своей БД) |
| `GET /users/{user_id}` | Нет (чтение своей БД) |
| `GET /internal/users/{user_id}/http` | Нет (чтение своей БД) |
| `GET /internal/users/{user_id}/msgpack` | Нет (чтение своей БД) |
| gRPC `auth.AuthService/GetUser` | Нет (чтение своей БД) |

## Сервис `tracking`

| Метод сервиса | Внешние вызовы |
|---|---|
| `GET /` | Нет |
| `GET /health` | Нет |
| `GET /tracking/order/{order_id}` | Нет (чтение своей БД) |
| `POST /tracking/order/{order_id}/events` | Нет (запись в свою БД) |
| `POST /tracking/internal/order-created/http` | Нет (запись в свою БД) |
| `POST /tracking/internal/order-created/msgpack` | Нет (запись в свою БД) |
| gRPC `tracking.TrackingService/InitTrackingForOrder` | Нет (запись/чтение своей БД) |

## Сервис `notification`

| Метод сервиса | Внешние вызовы |
|---|---|
| `GET /` | Нет |
| `GET /health` | Нет |
| `POST /notifications` | Нет (запись в свою БД) |
| `GET /notifications` | Нет (чтение своей БД) |
| `PATCH /notifications/{notification_id}/read` | Нет (запись в свою БД) |
| `POST /internal/order-created/http` | Нет (запись в свою БД) |
| `POST /internal/order-created/msgpack` | Нет (запись в свою БД) |
| gRPC `notification.NotificationService/CreateOrderNotification` | Нет (запись в свою БД) |



# Lab 2: Logistics Microservices

Учебный проект по микросервисной архитектуре для темы "Логистика".

## Сервисы

- `gateway` (порт `8000`) - единая точка входа.
- `auth` (порт `8001`) - регистрация и логин пользователей.
- `orders` (порт `8002`) - создание и управление заказами.
- `tracking` (порт `8003`) - события отслеживания заказов.
- `notification` (порт `8004`) - уведомления пользователю.
- `postgres` (порт `5432`) - общая БД.

## Быстрый запуск

```bash
docker compose up --build
```

Проверка:

- `GET http://localhost:8000/`
- `GET http://localhost:8000/api/auth/health`
- `GET http://localhost:8000/api/orders/health`
- `GET http://localhost:8000/api/tracking/health`
- `GET http://localhost:8000/api/notifications/health`

## Основные API

Регистрация:

```http
POST /api/auth/register
{
  "username": "anna",
  "email": "anna@example.com",
  "password": "strongpass"
}
```

Логин:

```http
POST /api/auth/login
{
  "username": "anna",
  "password": "strongpass"
}
```

Создание заказа (универсальный эндпоинт):

```http
POST /api/orders/orders
{
  "user_id": 1,
  "total_amount": 2500.00,
  "notify_method": "http"
}
```

Создание заказа по отдельным эндпоинтам методов взаимодействия:

- `POST /api/orders/orders/http`
- `POST /api/orders/orders/msgpack`
- `POST /api/orders/orders/grpc`

`notify_method` будет выбран автоматически по эндпоинту.

Внутренние endpoint'ы с тремя методами в сервисах:

- `auth`:  
  `GET /api/auth/internal/users/{user_id}/http`  
  `GET /api/auth/internal/users/{user_id}/msgpack`  
  `GET /api/auth/internal/users/{user_id}/grpc`
- `tracking`:  
  `POST /api/tracking/tracking/internal/order-created/http`  
  `POST /api/tracking/tracking/internal/order-created/msgpack`  
  `POST /api/tracking/tracking/internal/order-created/grpc`
- `notification`:  
  `POST /api/notifications/internal/order-created/http`  
  `POST /api/notifications/internal/order-created/msgpack`  
  `POST /api/notifications/internal/order-created/grpc`
- `gateway` (технические ping-ручки для демонстрации трех каналов):  
  `GET /internal/ping/http`  
  `GET /internal/ping/msgpack`  
  `GET /internal/ping/grpc`

## Кто с кем общается

- Клиент -> `gateway` (HTTP).
- `gateway` -> `auth`, `orders`, `tracking`, `notification` (проксирование HTTP).
- `orders` -> `auth` (проверка пользователя) через внутренние endpoint'ы `http/msgpack/grpc`.
- `orders` -> `notification` (создание уведомления) через внутренние endpoint'ы `http/msgpack/grpc`.
- `orders` -> `tracking` (инициализация трекинга) через внутренние endpoint'ы `http/msgpack/grpc`.

## Нагрузочная проверка

```bash
python tests/performance_test.py --base-url http://localhost:8000 --path /api/orders/orders --requests 200 --concurrency 20
```

## Что упрощено для учебной задачи

- Авторизация пока базовая (username/password + простой токен).
- Внутренние интеграции (`http`, `msgpack`, `grpc`) показаны через отдельные API-контракты без полноценного брокера/настоящего gRPC-сервера.


## Branch profile

This branch keeps only HTTP transport endpoints for inter-service communication.

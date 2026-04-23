# Lab 2: Logistics Microservices

Учебный проект по микросервисной архитектуре для темы "Логистика".

## Сервисы

- `gateway` (`8000`) — единая точка входа
- `auth` (`8001`) — регистрация/логин, проверка пользователя
- `orders` (`8002`) — создание и управление заказами
- `tracking` (`8003`) — события отслеживания заказов
- `notification` (`8004`) — уведомления
- `postgres` (`5432`) — общая БД

## Транспорты межсервисного обмена

- `HTTP`
- `MessagePack` (по HTTP с `application/msgpack`)
- `gRPC` (RPC-методы для `auth`, `tracking`, `notification`)

Proto-файлы:
- `infra/grpc/auth.proto`
- `infra/grpc/tracking.proto`
- `infra/grpc/notification.proto`

## Пошаговая проверка

### 1) Запуск

```powershell
docker compose up -d --build
docker compose ps
```

### 2) Проверка доступности

```powershell
curl http://localhost:8000/
curl http://localhost:8000/api/auth/health
curl http://localhost:8000/api/orders/health
curl http://localhost:8000/api/tracking/health
curl http://localhost:8000/api/notifications/health
```

### 3) Создать пользователя

```powershell
$body = @{ username="demo_show"; email="demo_show@example.com"; password="strongpass123" } | ConvertTo-Json
$u = Invoke-RestMethod -Uri "http://localhost:8000/api/auth/register" -Method Post -ContentType "application/json" -Body $body
$uid = $u.id
$uid
```

### 4) Проверить 3 метода обмена

```powershell
$oHttp = Invoke-RestMethod -Uri "http://localhost:8000/api/orders/orders/http" -Method Post -ContentType "application/json" -Body (@{ user_id=$uid; total_amount=1000.00; notify_method="http" } | ConvertTo-Json)
$oMsg  = Invoke-RestMethod -Uri "http://localhost:8000/api/orders/orders/msgpack" -Method Post -ContentType "application/json" -Body (@{ user_id=$uid; total_amount=2000.00; notify_method="msgpack" } | ConvertTo-Json)
$oGrpc = Invoke-RestMethod -Uri "http://localhost:8000/api/orders/orders/grpc" -Method Post -ContentType "application/json" -Body (@{ user_id=$uid; total_amount=3000.00; notify_method="grpc" } | ConvertTo-Json)

$oHttp
$oMsg
$oGrpc
```

### 5) Проверить побочные эффекты

```powershell
Invoke-RestMethod -Uri ("http://localhost:8000/api/notifications/notifications?user_id=" + $uid) -Method Get
Invoke-RestMethod -Uri ("http://localhost:8000/api/tracking/tracking/order/" + $oGrpc.id) -Method Get
```

### 6) Замер "одно сообщение"

```powershell
powershell -ExecutionPolicy Bypass -File tests/run_one_message_benchmark.ps1
```

Показать последний отчёт:

```powershell
$last = Get-ChildItem reports/benchmarks | Sort-Object LastWriteTime -Descending | Select-Object -First 1
$last.FullName
Get-Content $last.FullName
```

### 7) Остановка

```powershell
docker compose down
```

## Дополнительные материалы

- Таблица вызовов по сервисам: `APPENDIX_1_CALLS_RU.md`
- Чек-лист демонстрации: `DEMO_CHECKLIST_RU.md`
- Последние замеры: `reports/benchmarks/`

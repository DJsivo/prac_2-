# Чек-лист

## Кто и как общается

- Клиент -> gateway: HTTP.
- gateway -> auth/orders/tracking/notification: HTTP-проксирование.
- orders -> notification:
  - `http`: HTTP + JSON (`/internal/order-created/http`)
  - `msgpack`: HTTP + `application/msgpack` (`/internal/order-created/msgpack`)
  - `grpc`: gRPC вызов `CreateOrderNotification` на `notification:50051` — 
- orders -> tracking:
  - `http`: HTTP + JSON
  - `msgpack`: HTTP + `application/msgpack` 
  - `grpc`: gRPC вызов `InitTrackingForOrder` на `tracking:50053` 
- orders -> auth:
  - `http`: HTTP + JSON
  - `msgpack`: HTTP + `application/msgpack` (бинарный ответ пользователя)
  - `grpc`: gRPC вызов `GetUser` на `auth:50052` 


## Быстрая проверка работоспособности

### Поднять проект

```powershell
docker compose up -d --build
docker compose ps
```

Ожидаемо: все контейнеры в `Up`.

### Проверить health

```powershell
curl http://localhost:8000/
curl http://localhost:8000/api/auth/health
curl http://localhost:8000/api/orders/health
curl http://localhost:8000/api/tracking/health
curl http://localhost:8000/api/notifications/health
```

### Создать пользователя

```powershell
$body = @{ username="demo_show"; email="demo_show@example.com"; password="strongpass123" } | ConvertTo-Json
$u = Invoke-RestMethod -Uri "http://localhost:8000/api/auth/register" -Method Post -ContentType "application/json" -Body $body
$u
```

### Прогнать 3 метода создания заказа

```powershell
$uid = $u.id

Invoke-RestMethod -Uri "http://localhost:8000/api/orders/orders/http" -Method Post -ContentType "application/json" -Body (@{ user_id=$uid; total_amount=1111.11; notify_method="http" } | ConvertTo-Json)
Invoke-RestMethod -Uri "http://localhost:8000/api/orders/orders/msgpack" -Method Post -ContentType "application/json" -Body (@{ user_id=$uid; total_amount=2222.22; notify_method="msgpack" } | ConvertTo-Json)
$g = Invoke-RestMethod -Uri "http://localhost:8000/api/orders/orders/grpc" -Method Post -ContentType "application/json" -Body (@{ user_id=$uid; total_amount=3333.33; notify_method="grpc" } | ConvertTo-Json)
$g
```

### Проверить побочные эффекты

```powershell
Invoke-RestMethod -Uri ("http://localhost:8000/api/notifications/notifications?user_id=" + $uid) -Method Get
Invoke-RestMethod -Uri ("http://localhost:8000/api/tracking/tracking/order/" + $g.id) -Method Get
```

Ожидаемо: есть уведомления и запись трекинга.

### Замер «одно сообщение»

```powershell
powershell -ExecutionPolicy Bypass -File tests/run_one_message_benchmark.ps1
```

Результат сохранится в:
- `reports/benchmarks/one_message_YYYYMMDD_HHMMSS.txt`

Показать последний:

```powershell
$last = Get-ChildItem reports/benchmarks | Sort-Object LastWriteTime -Descending | Select-Object -First 1
$last.FullName
Get-Content $last.FullName
```

### Остановить

```powershell
docker compose down
```

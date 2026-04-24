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

### Получить пользователя для теста (без ошибок)

Этот блок работает и для нового, и для уже существующего пользователя.

```powershell
$baseUrl = "http://localhost:8000"
$username = "demo_show"
$password = "strongpass123"
$email = "demo_show@example.com"

$registerBody = @{ username=$username; email=$email; password=$password } | ConvertTo-Json
$uid = $null

try {
    $u = Invoke-RestMethod -Uri "$baseUrl/api/auth/register" -Method Post -ContentType "application/json" -Body $registerBody -ErrorAction Stop
    $uid = [int]$u.id
} catch {
    $loginBody = @{ username=$username; password=$password } | ConvertTo-Json
    Invoke-RestMethod -Uri "$baseUrl/api/auth/login" -Method Post -ContentType "application/json" -Body $loginBody -ErrorAction Stop | Out-Null
}

if (-not $uid) {
    for ($i = 1; $i -le 1000; $i++) {
        try {
            $candidate = Invoke-RestMethod -Uri "$baseUrl/api/auth/users/$i" -Method Get -ErrorAction Stop
            if ($candidate.username -eq $username) {
                $uid = [int]$candidate.id
                break
            }
        } catch {}
    }
}

if (-not $uid) { throw "Не удалось определить uid для пользователя $username" }
$uid
```

### Прогнать 3 метода создания заказа

```powershell
if (-not $uid) { throw "uid пустой — сначала выполни шаг получения пользователя" }
$oHttp = Invoke-RestMethod -Uri "http://localhost:8000/api/orders/orders/http" -Method Post -ContentType "application/json" -Body (@{ user_id=$uid; total_amount=1111.11; notify_method="http" } | ConvertTo-Json)
$oHttp
```

```powershell
$oMsg = Invoke-RestMethod -Uri "http://localhost:8000/api/orders/orders/msgpack" -Method Post -ContentType "application/json" -Body (@{ user_id=$uid; total_amount=2222.22; notify_method="msgpack" } | ConvertTo-Json)
$oMsg
```

```powershell
$g = Invoke-RestMethod -Uri "http://localhost:8000/api/orders/orders/grpc" -Method Post -ContentType "application/json" -Body (@{ user_id=$uid; total_amount=3333.33; notify_method="grpc" } | ConvertTo-Json)
$g
```

### Проверить побочные эффекты

```powershell
if (-not $uid) { throw "uid пустой — сначала выполни шаг получения пользователя" }
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

### Формальный замер для ЛР (100+ вызовов, средняя/дисперсия/график)

```powershell
powershell -ExecutionPolicy Bypass -File tests/run_full_chain_benchmark.ps1
```

Проверить, что созданы 3 файла:

```powershell
Get-ChildItem reports/performance_fullchain | Sort-Object LastWriteTime -Descending | Select-Object -First 3 Name,LastWriteTime,Length
```

### Остановить

```powershell
docker compose down
```

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

### 3) Получить пользователя для теста (без ошибок)

Этот блок работает и для нового, и для уже существующего пользователя.
Он:
1. пытается зарегистрировать пользователя;
2. если пользователь уже есть, делает логин;
3. получает `uid` (если не вернулся при регистрации, ищет по username).

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
    # Пользователь уже есть -> логинимся
    $loginBody = @{ username=$username; password=$password } | ConvertTo-Json
    Invoke-RestMethod -Uri "$baseUrl/api/auth/login" -Method Post -ContentType "application/json" -Body $loginBody -ErrorAction Stop | Out-Null
}

if (-not $uid) {
    # Поиск uid существующего пользователя (для учебного демо)
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

### 4) Проверить 3 метода обмена

```powershell
$oHttp = Invoke-RestMethod -Uri "http://localhost:8000/api/orders/orders/http" -Method Post -ContentType "application/json" -Body (@{ user_id=$uid; total_amount=1000.00; notify_method="http" } | ConvertTo-Json)
$oHttp
```

```powershell
$oMsg  = Invoke-RestMethod -Uri "http://localhost:8000/api/orders/orders/msgpack" -Method Post -ContentType "application/json" -Body (@{ user_id=$uid; total_amount=2000.00; notify_method="msgpack" } | ConvertTo-Json)
$oMsg
```

```powershell
$oGrpc = Invoke-RestMethod -Uri "http://localhost:8000/api/orders/orders/grpc" -Method Post -ContentType "application/json" -Body (@{ user_id=$uid; total_amount=3000.00; notify_method="grpc" } | ConvertTo-Json)
$oGrpc
```

### 5) Проверить побочные эффекты

```powershell
if (-not $uid) { throw "uid пустой — сначала выполни шаг 3" }
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
- Чек-лист демонстрации: `CHECKLIST.md`
- Последние замеры: `reports/benchmarks/`

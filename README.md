# Logistics Microservices

## Что нужно для запуска

1. Docker Desktop
2. Файл `secrets/jwt_secret.txt`
3. Файл `.env`



`В .env должны содержаться`:

```text
GATEWAY_PORT
AUTH_GRPC_PORT
TRACKING_GRPC_PORT
NOTIFICATION_GRPC_PORT
JWT_ISSUER
JWT_AUDIENCE
JWT_EXPIRES_MINUTES
DEFAULT_ADMIN_EMAIL
DEFAULT_ADMIN_PASSWORD
GITHUB_CALLBACK_URL=http://localhost:8000/auth/oauth/github/callback
GITHUB_CLIENT_ID
GITHUB_CLIENT_SECRET
```

## Запуск

```powershell
docker compose up -d --build
docker compose ps
```

Ожидаемый результат:
- контейнеры `lab2_postgres`, `lab2_gateway`, `lab2_auth`, `lab2_orders`, `lab2_tracking`, `lab2_notification` в статусе `Up`

## GitHub OAuth App

Путь:
- `GitHub -> Settings -> Developer settings -> OAuth Apps -> New OAuth App`

Поля:
- `Application name`: `название какое-то`
- `Homepage URL`: `http://localhost:8000`
- `Application description`: `Какой-то дискрипшн`
- `Authorization callback URL`: `http://localhost:8000/auth/oauth/github/callback`
- `Enable Device Flow`: выключено

## Проверка работоспособности

### 1. Health

```powershell
curl http://localhost:8000/auth/health
curl http://localhost:8000/api/orders/health
curl http://localhost:8000/api/tracking/health
curl http://localhost:8000/api/notifications/health
```

Ожидаемый результат:
- `auth`: `{"status":"ok"}`
- `orders`, `tracking`, `notification`: ответ `200 OK`

### 2. Регистрация

```powershell
$email = "demo_show@example.com"
$password = "strongpass123"
$register = @{ email=$email; password=$password } | ConvertTo-Json
$reg = Invoke-RestMethod -Uri "http://localhost:8000/api/auth/register" -Method Post -ContentType "application/json" -Body $register
$reg
```

Ожидаемый результат:
- JSON с `access_token`
- `token_type = bearer`

### 3. Логин и `/me`

```powershell
$login = @{ email=$email; password=$password } | ConvertTo-Json
$auth = Invoke-RestMethod -Uri "http://localhost:8000/api/auth/login" -Method Post -ContentType "application/json" -Body $login
$token = $auth.access_token
$headers = @{ Authorization = "Bearer $token" }
Invoke-RestMethod -Uri "http://localhost:8000/api/auth/me" -Method Get -Headers $headers
```

Ожидаемый результат:
- логин возвращает `access_token`
- `/me` возвращает `user_id`, `email`, `role`

### 4. Создание заказа тремя способами

```powershell
$me = Invoke-RestMethod -Uri "http://localhost:8000/api/auth/me" -Method Get -Headers $headers
$uid = [int]$me.user_id
```

HTTP:

```powershell
Invoke-RestMethod -Uri "http://localhost:8000/api/orders/orders/http" -Method Post -Headers $headers -ContentType "application/json" -Body (@{ user_id=$uid; total_amount=1000.00; notify_method="http" } | ConvertTo-Json)
```

MessagePack:

```powershell
Invoke-RestMethod -Uri "http://localhost:8000/api/orders/orders/msgpack" -Method Post -Headers $headers -ContentType "application/json" -Body (@{ user_id=$uid; total_amount=2000.00; notify_method="msgpack" } | ConvertTo-Json)
```

gRPC:

```powershell
$oGrpc = Invoke-RestMethod -Uri "http://localhost:8000/api/orders/orders/grpc" -Method Post -Headers $headers -ContentType "application/json" -Body (@{ user_id=$uid; total_amount=3000.00; notify_method="grpc" } | ConvertTo-Json)
$oGrpc
```

Ожидаемый результат:
- каждый запрос возвращает созданный заказ
- есть `id`, `user_id`, `status`, `total_amount`

### 5. Уведомления и трекинг

```powershell
Invoke-RestMethod -Uri ("http://localhost:8000/api/notifications/notifications?user_id=" + $uid) -Method Get -Headers $headers
Invoke-RestMethod -Uri ("http://localhost:8000/api/tracking/tracking/order/" + $oGrpc.id) -Method Get -Headers $headers
```

Ожидаемый результат:
- по уведомлениям приходит непустой список
- по трекингу для `grpc`-заказа приходит хотя бы одна запись

### 6. GitHub OAuth

Открыть в браузере:

```text
http://localhost:8000/auth/oauth/github/login
```

Ожидаемый результат:
- redirect на GitHub
- после авторизации callback возвращает JSON:

```json
{"access_token":"...","token_type":"bearer"}
```

### 7. RBAC

Без токена:

```powershell
curl http://localhost:8000/api/orders/orders
```

Ожидаемый результат:
- `401`

Admin metrics:

```powershell
$adminLogin = @{ email="admin@example.com"; password="strongpass123" } | ConvertTo-Json
$adminToken = (Invoke-RestMethod -Uri "http://localhost:8000/api/auth/login" -Method Post -ContentType "application/json" -Body $adminLogin).access_token
$adminHeaders = @{ Authorization = "Bearer $adminToken" }
Invoke-RestMethod -Uri "http://localhost:8000/api/orders/metrics" -Method Get -Headers $adminHeaders
```

Ожидаемый результат:
- `200 OK`
- JSON с `total_orders`, `total_revenue`, `orders_by_status`

User на admin endpoint:

```powershell
Invoke-WebRequest -Uri "http://localhost:8000/api/orders/metrics" -Headers $headers -UseBasicParsing
```

Ожидаемый результат:
- `403`

## Остановка

```powershell
docker compose down
```

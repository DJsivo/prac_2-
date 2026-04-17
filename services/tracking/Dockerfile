# services/gateway/Dockerfile
FROM python:3.11-slim

# Переменные окружения для оптимизации
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Копируем зависимости и устанавливаем их
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем исходный код сервиса
COPY services/tracking/app ./app
COPY common ./common

# Создаём пользователя для безопасности (не запускаем от root)
RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

# Запускаем сервис
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8003"]
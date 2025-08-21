# syntax=docker/dockerfile:1
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app:/app/libs/odin_core \
    PORT=8080

WORKDIR /app

# Install Python deps
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -U pip && \
    pip install --no-cache-dir -r /app/requirements.txt

# Copy source
COPY . /app

EXPOSE 8080

# Start FastAPI via uvicorn; Cloud Run sets $PORT
ENTRYPOINT ["sh","-c","uvicorn apps.gateway.api:app --host 0.0.0.0 --port ${PORT:-8080}"]

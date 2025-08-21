# syntax=docker/dockerfile:1
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app:/app/libs/odin_core \
    PORT=8080

WORKDIR /app

# Install deps first for caching
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -U pip && \
    pip install --no-cache-dir -r /app/requirements.txt

# Copy only what relay needs
COPY services/relay /app/services/relay
COPY libs/odin_core /app/libs/odin_core

EXPOSE 8080

# Start Relay via uvicorn; Cloud Run honors $PORT
ENTRYPOINT ["sh","-c","uvicorn services.relay.api:app --host 0.0.0.0 --port ${PORT:-8080}"]

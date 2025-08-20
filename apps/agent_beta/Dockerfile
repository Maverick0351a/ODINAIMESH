FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# (Optional) build deps; keep minimal—cryptography usually has wheels, but this is safe.
RUN apt-get update && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy only what we need to build/install the package and run apps/*
COPY pyproject.toml README.md /app/
COPY libs /app/libs
COPY apps /app/apps

# Install the project (with optional [gcp] extras so Firestore/GCS libs are available if needed)
RUN python -m pip install --upgrade pip && \
    python -m pip install ./libs/odin_core && \
    python -m pip install ".[gcp]"

# Cloud Run provides PORT; default to 8080 locally.
ENV PORT=8080
EXPOSE 8080

# Start Agent Beta
# NOTE: env substitution requires sh -c
CMD ["sh","-c","python -m uvicorn apps.agent_beta.api:app --host 0.0.0.0 --port ${PORT:-8080}"]

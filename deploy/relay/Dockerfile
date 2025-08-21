# ODIN Relay - Hardened Egress Service for Google Cloud Run

FROM python:3.11-slim as builder

# Install build dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Production stage
FROM python:3.11-slim

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && useradd -m -u 1000 odin

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Set working directory
WORKDIR /app

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p /app/logs /app/tmp && \
    chown -R odin:odin /app

# Switch to non-root user
USER odin

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# Environment variables
ENV PYTHONPATH=/app
ENV ODIN_RELAY_PORT=8080
ENV ODIN_LOG_LEVEL=INFO
ENV ODIN_STREAM_ENABLED=false
ENV ODIN_EGRESS_HARDENED=true

# Expose port
EXPOSE 8080

# Start relay service
CMD ["python", "-m", "uvicorn", "apps.relay.api:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "1"]

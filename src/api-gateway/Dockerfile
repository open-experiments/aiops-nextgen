# API Gateway Service Dockerfile
# Spec Reference: specs/09-deployment.md

FROM python:3.11-slim AS base

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Build stage
FROM base AS builder

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install dependencies to /opt (OpenShift-friendly)
COPY src/api-gateway/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir --prefix=/opt/python -r /app/requirements.txt

# Final stage
FROM base AS final

# Copy installed packages from builder
COPY --from=builder /opt/python /opt/python
ENV PATH=/opt/python/bin:$PATH \
    PYTHONPATH=/app/src:/opt/python/lib/python3.11/site-packages

# Copy source code
COPY src/shared /app/src/shared
COPY src/api-gateway /app/src/api-gateway

# Set working directory to the service
WORKDIR /app/src/api-gateway

# Create non-root user for OpenShift compatibility
RUN chgrp -R 0 /app && chmod -R g=u /app

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# Expose port
EXPOSE 8080

# Run the application
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]

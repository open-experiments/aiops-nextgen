# Observability Collector Service Dockerfile
#
# Spec Reference: specs/09-deployment.md
#
# Multi-stage build for minimal image size

# Stage 1: Build dependencies
FROM python:3.11-slim AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY src/observability-collector/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir --prefix=/opt/python -r /app/requirements.txt

# Stage 2: Runtime
FROM python:3.11-slim AS base

WORKDIR /app

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Stage 3: Final image
FROM base AS final

# Copy installed packages from builder
COPY --from=builder /opt/python /opt/python

# Add Python packages to path
ENV PYTHONPATH="/opt/python/lib/python3.11/site-packages:/app/src"
ENV PATH="/opt/python/bin:$PATH"

# Copy shared package
COPY src/shared /app/src/shared

# Copy application
COPY src/observability-collector /app/src/observability-collector

# Set working directory
WORKDIR /app/src/observability-collector

# OpenShift compatibility: run as non-root
RUN chgrp -R 0 /app && chmod -R g=u /app

# Expose port
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# Run the application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]

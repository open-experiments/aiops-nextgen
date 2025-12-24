# Intelligence Engine Service Dockerfile
# Spec Reference: specs/04-intelligence-engine.md

FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy shared package first
COPY src/shared /app/shared
RUN pip install --no-cache-dir -e /app/shared

# Copy service requirements and install
COPY src/intelligence-engine/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy service code
COPY src/intelligence-engine/app /app/app

# Fix permissions for OpenShift (runs with random UID)
RUN chmod -R g+rwX /app && \
    chown -R 1001:0 /app

# Set Python path
ENV PYTHONPATH=/app

# Run as non-root user
USER 1001

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# Run the service
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]

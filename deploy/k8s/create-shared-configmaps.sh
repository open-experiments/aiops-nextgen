#!/bin/bash
# Create ConfigMaps for each shared module
# Run from project root: ./deploy/k8s/create-shared-configmaps.sh

set -e

echo "Creating ConfigMaps for src/shared/ modules..."

# Models module
oc create configmap shared-models \
  --from-file=__init__.py=src/shared/models/__init__.py \
  --from-file=base.py=src/shared/models/base.py \
  --from-file=common.py=src/shared/models/common.py \
  --from-file=cluster.py=src/shared/models/cluster.py \
  --from-file=observability.py=src/shared/models/observability.py \
  --from-file=gpu.py=src/shared/models/gpu.py \
  --from-file=intelligence.py=src/shared/models/intelligence.py \
  --from-file=events.py=src/shared/models/events.py \
  --from-file=reports.py=src/shared/models/reports.py \
  --dry-run=client -o yaml | oc apply -f -

# Database module
oc create configmap shared-database \
  --from-file=__init__.py=src/shared/database/__init__.py \
  --from-file=base.py=src/shared/database/base.py \
  --from-file=models.py=src/shared/database/models.py \
  --dry-run=client -o yaml | oc apply -f -

# Redis client module
oc create configmap shared-redis-client \
  --from-file=__init__.py=src/shared/redis_client/__init__.py \
  --from-file=client.py=src/shared/redis_client/client.py \
  --dry-run=client -o yaml | oc apply -f -

# Config module
oc create configmap shared-config \
  --from-file=__init__.py=src/shared/config/__init__.py \
  --from-file=settings.py=src/shared/config/settings.py \
  --dry-run=client -o yaml | oc apply -f -

# Observability module
oc create configmap shared-observability \
  --from-file=__init__.py=src/shared/observability/__init__.py \
  --from-file=logging.py=src/shared/observability/logging.py \
  --dry-run=client -o yaml | oc apply -f -

# Shared root init
oc create configmap shared-root \
  --from-file=__init__.py=src/shared/__init__.py \
  --dry-run=client -o yaml | oc apply -f -

echo "ConfigMaps created successfully!"

# 09 - OpenShift Deployment Specification

## Document Info
| Field | Value |
|-------|-------|
| Version | 0.1.0 |
| Status | Draft |
| Last Updated | 2024-12-24 |

---

## 1. Purpose

This document specifies the deployment architecture for AIOps NextGen on OpenShift, including:

- Namespace structure
- Resource requirements
- Helm chart organization
- Configuration management
- Security policies
- Scaling strategies

---

## 2. Target Platform

| Requirement | Value |
|-------------|-------|
| Platform | OpenShift Container Platform |
| Version | 4.16+ |
| Architecture | x86_64, ARM64 |
| Cluster Type | Hub cluster (dedicated or shared) |

---

## 3. Namespace Structure

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            aiops-nextgen                                    │
│                         (Main Application)                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│  Deployments:                                                               │
│  • api-gateway                                                              │
│  • cluster-registry                                                         │
│  • observability-collector                                                  │
│  • intelligence-engine                                                      │
│  • realtime-streaming                                                       │
│  • frontend                                                                 │
│                                                                             │
│  StatefulSets:                                                              │
│  • postgresql                                                               │
│  • redis                                                                    │
│                                                                             │
│  Services, ConfigMaps, Secrets, Routes                                      │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                         aiops-nextgen-llm                                   │
│                        (Optional: Local LLM)                                │
├─────────────────────────────────────────────────────────────────────────────┤
│  Deployments:                                                               │
│  • vllm-inference                                                           │
│                                                                             │
│  InferenceService (if using KServe)                                         │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                      aiops-nextgen-storage                                  │
│                       (Object Storage)                                      │
├─────────────────────────────────────────────────────────────────────────────┤
│  Deployments:                                                               │
│  • minio (if not using ODF)                                                 │
│                                                                             │
│  ObjectBucketClaim (if using ODF)                                           │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 4. Resource Requirements

### 4.1 Minimum Requirements (Development)

| Component | Replicas | CPU | Memory | Storage |
|-----------|----------|-----|--------|---------|
| api-gateway | 1 | 250m | 256Mi | - |
| cluster-registry | 1 | 250m | 512Mi | - |
| observability-collector | 1 | 500m | 1Gi | - |
| intelligence-engine | 1 | 500m | 1Gi | - |
| realtime-streaming | 1 | 250m | 256Mi | - |
| frontend | 1 | 100m | 128Mi | - |
| postgresql | 1 | 500m | 1Gi | 10Gi |
| redis | 1 | 250m | 256Mi | 1Gi |
| **Total** | **8** | **2.6 cores** | **4.4Gi** | **11Gi** |

### 4.2 Production Requirements

| Component | Replicas | CPU | Memory | Storage |
|-----------|----------|-----|--------|---------|
| api-gateway | 3 | 500m | 512Mi | - |
| cluster-registry | 2 | 500m | 1Gi | - |
| observability-collector | 3 | 1 | 2Gi | - |
| intelligence-engine | 2 | 1 | 2Gi | - |
| realtime-streaming | 3 | 500m | 512Mi | - |
| frontend | 2 | 200m | 256Mi | - |
| postgresql | 2 | 1 | 2Gi | 50Gi |
| redis | 3 | 500m | 1Gi | 5Gi |
| **Total** | **20** | **8.2 cores** | **14.5Gi** | **55Gi** |

### 4.3 LLM Requirements (Optional)

| Component | GPU | CPU | Memory | Storage |
|-----------|-----|-----|--------|---------|
| vLLM (3B model) | 1x A10 | 4 | 16Gi | 50Gi |
| vLLM (8B model) | 1x A100-40GB | 8 | 32Gi | 100Gi |
| vLLM (70B model) | 2x A100-80GB | 16 | 128Gi | 200Gi |

---

## 5. Helm Chart Structure

```
deploy/helm/
├── aiops-nextgen/                    # Umbrella chart
│   ├── Chart.yaml
│   ├── values.yaml
│   ├── values-dev.yaml
│   ├── values-prod.yaml
│   └── charts/
│       ├── api-gateway/
│       ├── cluster-registry/
│       ├── observability-collector/
│       ├── intelligence-engine/
│       ├── realtime-streaming/
│       ├── frontend/
│       ├── postgresql/
│       └── redis/
│
├── aiops-llm/                        # LLM deployment (optional)
│   ├── Chart.yaml
│   ├── values.yaml
│   └── templates/
│       ├── deployment.yaml
│       └── service.yaml
│
└── aiops-storage/                    # Storage (optional)
    ├── Chart.yaml
    ├── values.yaml
    └── templates/
        ├── minio-deployment.yaml
        └── pvc.yaml
```

### 5.1 Umbrella Chart Values

```yaml
# values.yaml
global:
  namespace: aiops-nextgen
  imageRegistry: quay.io/ecosystem-appeng
  imageTag: "1.0.0"

  # Shared configuration
  postgresql:
    host: postgresql
    port: 5432
    database: aiops
    secretName: postgresql-credentials

  redis:
    host: redis
    port: 6379

  oauth:
    issuer: ""  # Set during install
    clientId: aiops-nextgen

# Component configurations
api-gateway:
  enabled: true
  replicas: 2
  resources:
    requests:
      cpu: 250m
      memory: 256Mi
    limits:
      cpu: 500m
      memory: 512Mi

cluster-registry:
  enabled: true
  replicas: 2
  resources:
    requests:
      cpu: 250m
      memory: 512Mi

observability-collector:
  enabled: true
  replicas: 2
  resources:
    requests:
      cpu: 500m
      memory: 1Gi

intelligence-engine:
  enabled: true
  replicas: 2
  llm:
    provider: local  # local, anthropic, openai, google
    localUrl: http://vllm:8080/v1
    model: meta-llama/Llama-3.2-3B-Instruct
  resources:
    requests:
      cpu: 500m
      memory: 1Gi

realtime-streaming:
  enabled: true
  replicas: 2
  resources:
    requests:
      cpu: 250m
      memory: 256Mi

frontend:
  enabled: true
  replicas: 2
  resources:
    requests:
      cpu: 100m
      memory: 128Mi

postgresql:
  enabled: true
  persistence:
    size: 20Gi
    storageClass: ""  # Use cluster default

redis:
  enabled: true
  persistence:
    size: 5Gi
    storageClass: ""
```

---

## 6. Deployment Templates

### 6.1 Deployment Template (Example: API Gateway)

```yaml
# templates/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{ include "api-gateway.fullname" . }}
  labels:
    {{- include "api-gateway.labels" . | nindent 4 }}
spec:
  replicas: {{ .Values.replicas }}
  selector:
    matchLabels:
      {{- include "api-gateway.selectorLabels" . | nindent 6 }}
  template:
    metadata:
      labels:
        {{- include "api-gateway.selectorLabels" . | nindent 8 }}
        app.kubernetes.io/part-of: aiops-nextgen
        app.kubernetes.io/component: gateway
      annotations:
        prometheus.io/scrape: "true"
        prometheus.io/port: "8080"
        prometheus.io/path: "/metrics"
    spec:
      serviceAccountName: {{ include "api-gateway.serviceAccountName" . }}
      securityContext:
        runAsNonRoot: true
        seccompProfile:
          type: RuntimeDefault
      containers:
        - name: api-gateway
          image: "{{ .Values.global.imageRegistry }}/aiops-api-gateway:{{ .Values.global.imageTag }}"
          imagePullPolicy: IfNotPresent
          securityContext:
            allowPrivilegeEscalation: false
            capabilities:
              drop:
                - ALL
            readOnlyRootFilesystem: true
          ports:
            - name: http
              containerPort: 8080
              protocol: TCP
          env:
            - name: REDIS_URL
              value: "redis://{{ .Values.global.redis.host }}:{{ .Values.global.redis.port }}"
            - name: CLUSTER_REGISTRY_URL
              value: "http://cluster-registry:8080"
            - name: OBSERVABILITY_COLLECTOR_URL
              value: "http://observability-collector:8080"
            - name: INTELLIGENCE_ENGINE_URL
              value: "http://intelligence-engine:8080"
            - name: REALTIME_STREAMING_URL
              value: "http://realtime-streaming:8080"
            - name: OAUTH_ISSUER
              value: "{{ .Values.global.oauth.issuer }}"
            - name: OAUTH_CLIENT_ID
              value: "{{ .Values.global.oauth.clientId }}"
          envFrom:
            - secretRef:
                name: oauth-client-secret
          livenessProbe:
            httpGet:
              path: /health
              port: http
            initialDelaySeconds: 10
            periodSeconds: 10
          readinessProbe:
            httpGet:
              path: /ready
              port: http
            initialDelaySeconds: 5
            periodSeconds: 5
          resources:
            {{- toYaml .Values.resources | nindent 12 }}
      affinity:
        podAntiAffinity:
          preferredDuringSchedulingIgnoredDuringExecution:
            - weight: 100
              podAffinityTerm:
                labelSelector:
                  matchLabels:
                    {{- include "api-gateway.selectorLabels" . | nindent 20 }}
                topologyKey: kubernetes.io/hostname
```

### 6.2 Service Template

```yaml
# templates/service.yaml
apiVersion: v1
kind: Service
metadata:
  name: {{ include "api-gateway.fullname" . }}
  labels:
    {{- include "api-gateway.labels" . | nindent 4 }}
spec:
  type: ClusterIP
  ports:
    - port: 8080
      targetPort: http
      protocol: TCP
      name: http
  selector:
    {{- include "api-gateway.selectorLabels" . | nindent 4 }}
```

### 6.3 Route Template

```yaml
# templates/route.yaml
{{- if .Values.route.enabled }}
apiVersion: route.openshift.io/v1
kind: Route
metadata:
  name: {{ include "api-gateway.fullname" . }}
  labels:
    {{- include "api-gateway.labels" . | nindent 4 }}
spec:
  host: {{ .Values.route.host }}
  to:
    kind: Service
    name: {{ include "api-gateway.fullname" . }}
    weight: 100
  port:
    targetPort: http
  tls:
    termination: edge
    insecureEdgeTerminationPolicy: Redirect
{{- end }}
```

---

## 7. Security Configuration

### 7.1 Service Accounts

```yaml
# templates/serviceaccount.yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: {{ include "api-gateway.serviceAccountName" . }}
  labels:
    {{- include "api-gateway.labels" . | nindent 4 }}
  annotations:
    # For token projection
    kubernetes.io/enforce-mountable-secrets: "true"
```

### 7.2 RBAC for Cluster Registry

```yaml
# Cluster Registry needs to access Kubernetes Secrets
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: cluster-registry
  namespace: {{ .Release.Namespace }}
rules:
  - apiGroups: [""]
    resources: ["secrets"]
    verbs: ["get", "create", "update", "delete"]
    resourceNames: []  # Scoped to cluster-creds-* prefix via code

---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: cluster-registry
  namespace: {{ .Release.Namespace }}
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: Role
  name: cluster-registry
subjects:
  - kind: ServiceAccount
    name: cluster-registry
    namespace: {{ .Release.Namespace }}
```

### 7.3 RBAC for Observability Collector (Spoke Cluster Access)

```yaml
# Applied on each spoke cluster
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: aiops-observability-reader
rules:
  - apiGroups: [""]
    resources: ["pods", "pods/exec"]
    verbs: ["get", "list"]
  - apiGroups: [""]
    resources: ["namespaces"]
    verbs: ["get", "list"]

---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: aiops-observability-reader
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: ClusterRole
  name: aiops-observability-reader
subjects:
  - kind: ServiceAccount
    name: aiops-collector
    namespace: aiops-spoke
```

### 7.4 Network Policies

```yaml
# Allow ingress only from API Gateway
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-from-gateway
  namespace: {{ .Release.Namespace }}
spec:
  podSelector:
    matchLabels:
      app.kubernetes.io/part-of: aiops-nextgen
      app.kubernetes.io/component: backend
  policyTypes:
    - Ingress
  ingress:
    - from:
        - podSelector:
            matchLabels:
              app.kubernetes.io/name: api-gateway
      ports:
        - protocol: TCP
          port: 8080

# Note: Backend deployments must include these labels:
#   app.kubernetes.io/part-of: aiops-nextgen
#   app.kubernetes.io/component: backend

---
# Allow ingress from OpenShift Router for frontend
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-from-router
  namespace: {{ .Release.Namespace }}
spec:
  podSelector:
    matchLabels:
      app.kubernetes.io/name: frontend
  policyTypes:
    - Ingress
  ingress:
    - from:
        - namespaceSelector:
            matchLabels:
              network.openshift.io/policy-group: ingress
```

---

## 8. Configuration Management

### 8.1 ConfigMaps

```yaml
# Shared configuration
apiVersion: v1
kind: ConfigMap
metadata:
  name: aiops-config
  namespace: {{ .Release.Namespace }}
data:
  LOG_LEVEL: "INFO"
  LOG_FORMAT: "json"
  METRICS_ENABLED: "true"
  TRACING_ENABLED: "true"
  OTEL_EXPORTER_OTLP_ENDPOINT: "http://otel-collector:4317"
```

### 8.2 Secrets

```yaml
# PostgreSQL credentials
apiVersion: v1
kind: Secret
metadata:
  name: postgresql-credentials
  namespace: {{ .Release.Namespace }}
type: Opaque
stringData:
  POSTGRES_USER: aiops
  POSTGRES_PASSWORD: {{ .Values.postgresql.password | default (randAlphaNum 32) }}
  POSTGRES_DB: aiops
  DATABASE_URL: postgresql://aiops:{{ .Values.postgresql.password }}@postgresql:5432/aiops

---
# OAuth client secret
apiVersion: v1
kind: Secret
metadata:
  name: oauth-client-secret
  namespace: {{ .Release.Namespace }}
type: Opaque
stringData:
  OAUTH_CLIENT_SECRET: {{ .Values.oauth.clientSecret }}
```

---

## 9. Scaling Configuration

### 9.1 Horizontal Pod Autoscaler

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: api-gateway
  namespace: {{ .Release.Namespace }}
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: api-gateway
  minReplicas: {{ .Values.apiGateway.minReplicas | default 2 }}
  maxReplicas: {{ .Values.apiGateway.maxReplicas | default 10 }}
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 70
    - type: Resource
      resource:
        name: memory
        target:
          type: Utilization
          averageUtilization: 80
```

### 9.2 Pod Disruption Budget

```yaml
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: api-gateway
  namespace: {{ .Release.Namespace }}
spec:
  minAvailable: 1
  selector:
    matchLabels:
      app.kubernetes.io/name: api-gateway
```

---

## 10. Observability

### 10.1 ServiceMonitor

```yaml
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: aiops-nextgen
  namespace: {{ .Release.Namespace }}
  labels:
    app.kubernetes.io/part-of: aiops-nextgen
spec:
  selector:
    matchLabels:
      app.kubernetes.io/part-of: aiops-nextgen
  endpoints:
    - port: http
      path: /metrics
      interval: 30s
```

### 10.2 PrometheusRule (Alerts)

```yaml
apiVersion: monitoring.coreos.com/v1
kind: PrometheusRule
metadata:
  name: aiops-nextgen-alerts
  namespace: {{ .Release.Namespace }}
spec:
  groups:
    - name: aiops-nextgen
      rules:
        - alert: AIOpsHighErrorRate
          expr: |
            sum(rate(http_requests_total{job="aiops-nextgen",status=~"5.."}[5m]))
            /
            sum(rate(http_requests_total{job="aiops-nextgen"}[5m]))
            > 0.05
          for: 5m
          labels:
            severity: warning
          annotations:
            summary: "High error rate in AIOps NextGen"
            description: "Error rate is {{ $value | humanizePercentage }}"

        - alert: AIOpsServiceDown
          expr: up{job="aiops-nextgen"} == 0
          for: 1m
          labels:
            severity: critical
          annotations:
            summary: "AIOps service is down"
            description: "{{ $labels.instance }} is down"
```

---

## 11. Installation Commands

### 11.1 Full Installation

```bash
# Create namespace
oc new-project aiops-nextgen

# Add Helm repo (if published)
helm repo add aiops https://charts.example.com/aiops
helm repo update

# Install with custom values
helm install aiops-nextgen aiops/aiops-nextgen \
  --namespace aiops-nextgen \
  --values values-prod.yaml \
  --set global.oauth.issuer="https://oauth-openshift.apps.example.com" \
  --set global.imageTag="1.0.0"

# Or install from local chart
helm install aiops-nextgen ./deploy/helm/aiops-nextgen \
  --namespace aiops-nextgen \
  --values ./deploy/helm/aiops-nextgen/values-prod.yaml
```

### 11.2 Upgrade

```bash
helm upgrade aiops-nextgen aiops/aiops-nextgen \
  --namespace aiops-nextgen \
  --values values-prod.yaml \
  --set global.imageTag="1.1.0"
```

### 11.3 Uninstall

```bash
helm uninstall aiops-nextgen --namespace aiops-nextgen

# Clean up PVCs if needed
oc delete pvc -l app.kubernetes.io/instance=aiops-nextgen -n aiops-nextgen
```

---

## 12. Post-Installation

### 12.1 Verify Deployment

```bash
# Check pods
oc get pods -n aiops-nextgen

# Check services
oc get svc -n aiops-nextgen

# Check routes
oc get routes -n aiops-nextgen

# Check health
curl https://aiops.example.com/health
```

### 12.2 Configure OAuth

```bash
# Create OAuth client
oc create -f - <<EOF
apiVersion: oauth.openshift.io/v1
kind: OAuthClient
metadata:
  name: aiops-nextgen
grantMethod: auto
redirectURIs:
  - https://aiops.example.com/oauth/callback
secret: <generated-secret>
EOF
```

### 12.3 Register First Cluster

```bash
# Using CLI tool (to be developed)
aiops cluster add \
  --name prod-east-1 \
  --api-server https://api.prod-east-1.example.com:6443 \
  --kubeconfig ~/.kube/prod-east-1
```

---

## 13. Backup and Recovery

### 13.1 Backup

```bash
# PostgreSQL backup
oc exec -n aiops-nextgen postgresql-0 -- \
  pg_dump -U aiops aiops > aiops-backup-$(date +%Y%m%d).sql

# Secrets backup
oc get secrets -n aiops-nextgen -o yaml > secrets-backup.yaml
```

### 13.2 Recovery

```bash
# Restore PostgreSQL
oc exec -i -n aiops-nextgen postgresql-0 -- \
  psql -U aiops aiops < aiops-backup-20241224.sql
```

---

## 14. Open Questions

1. **Multi-Hub**: Support for federated hub clusters?
2. **Disaster Recovery**: Active-passive or active-active DR?
3. **Air-Gapped**: Support for disconnected installations?
4. **Operators**: Should we create an Operator for lifecycle management?
5. **GitOps**: ArgoCD application manifests?

---

## End of Specification Documents

Review all specs (00-09) and provide feedback before implementation begins.

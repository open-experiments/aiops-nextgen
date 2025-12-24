# 07 - Frontend Application

## Document Info
| Field | Value |
|-------|-------|
| Version | 0.1.0 |
| Status | Draft |
| Last Updated | 2024-12-24 |

---

## 1. Purpose

The Frontend Application provides a web-based user interface for interacting with AIOps NextGen platform. It delivers:

- Fleet overview dashboard
- Real-time GPU monitoring
- AI chat interface with personas
- Observability exploration (metrics, traces, logs)
- Report generation and viewing
- Cluster management

---

## 2. Technology Stack

| Component | Technology | Version |
|-----------|------------|---------|
| Framework | React | 18.x |
| Language | TypeScript | 5.x |
| Build Tool | Vite | 5.x |
| State Management | Zustand | 4.x |
| Styling | Tailwind CSS | 3.x |
| Charts | Chart.js / Recharts | Latest |
| Icons | Heroicons | 2.x |
| HTTP Client | Axios | 1.x |
| WebSocket | Native + reconnecting-websocket | Latest |
| Testing | Vitest + React Testing Library | Latest |

---

## 3. Application Structure

```
frontend/
├── public/
│   ├── favicon.ico
│   └── manifest.json
├── src/
│   ├── main.tsx                 # Entry point
│   ├── App.tsx                  # Root component
│   ├── routes.tsx               # Route definitions
│   │
│   ├── components/              # Reusable UI components
│   │   ├── common/              # Shared components
│   │   │   ├── Button/
│   │   │   ├── Card/
│   │   │   ├── Modal/
│   │   │   ├── Table/
│   │   │   ├── Spinner/
│   │   │   └── ErrorBoundary/
│   │   ├── charts/              # Chart components
│   │   │   ├── LineChart/
│   │   │   ├── GaugeChart/
│   │   │   ├── HeatMap/
│   │   │   └── TimeSeriesChart/
│   │   ├── layout/              # Layout components
│   │   │   ├── Header/
│   │   │   ├── Sidebar/
│   │   │   ├── Footer/
│   │   │   └── MainLayout/
│   │   └── domain/              # Domain-specific components
│   │       ├── ClusterCard/
│   │       ├── GPUCard/
│   │       ├── AlertBadge/
│   │       ├── MetricPanel/
│   │       └── ChatMessage/
│   │
│   ├── pages/                   # Page components
│   │   ├── Dashboard/           # Fleet overview
│   │   ├── Clusters/            # Cluster management
│   │   ├── GPU/                 # GPU monitoring
│   │   ├── Observability/       # Metrics/Traces/Logs
│   │   ├── Alerts/              # Alert management
│   │   ├── Chat/                # AI chat interface
│   │   ├── Reports/             # Report generation
│   │   └── Settings/            # User settings
│   │
│   ├── hooks/                   # Custom React hooks
│   │   ├── useAuth.ts
│   │   ├── useWebSocket.ts
│   │   ├── useClusters.ts
│   │   ├── useMetrics.ts
│   │   ├── useGPU.ts
│   │   ├── useAlerts.ts
│   │   ├── useChat.ts
│   │   └── useLocalStorage.ts
│   │
│   ├── services/                # API services
│   │   ├── api.ts               # Base API client
│   │   ├── clusterService.ts
│   │   ├── metricsService.ts
│   │   ├── tracesService.ts
│   │   ├── logsService.ts
│   │   ├── alertsService.ts
│   │   ├── gpuService.ts
│   │   ├── chatService.ts
│   │   └── reportService.ts
│   │
│   ├── store/                   # Zustand stores
│   │   ├── authStore.ts
│   │   ├── clusterStore.ts
│   │   ├── alertStore.ts
│   │   ├── gpuStore.ts
│   │   └── chatStore.ts
│   │
│   ├── types/                   # TypeScript types
│   │   ├── cluster.ts
│   │   ├── metrics.ts
│   │   ├── traces.ts
│   │   ├── alerts.ts
│   │   ├── gpu.ts
│   │   ├── chat.ts
│   │   └── api.ts
│   │
│   ├── utils/                   # Utility functions
│   │   ├── formatters.ts
│   │   ├── validators.ts
│   │   ├── dateUtils.ts
│   │   └── constants.ts
│   │
│   └── styles/                  # Global styles
│       ├── globals.css
│       └── tailwind.css
│
├── .env.example
├── index.html
├── package.json
├── tailwind.config.js
├── tsconfig.json
└── vite.config.ts
```

---

## 4. Pages and Features

### 4.1 Dashboard (Fleet Overview)

**Route:** `/`

**Features:**
- Fleet summary cards (total clusters, GPU count, active alerts)
- Cluster status grid (mini cards with health indicators)
- Recent alerts timeline
- GPU utilization heatmap
- Quick actions (add cluster, create report)

```
┌─────────────────────────────────────────────────────────────────────┐
│  AIOps NextGen                                    [User] [Settings] │
├─────────────────────────────────────────────────────────────────────┤
│ ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌───────────┐            │
│ │ Clusters  │ │ GPUs      │ │ Alerts    │ │ Health    │            │
│ │    25     │ │   128     │ │    7      │ │   87%     │            │
│ │ 22 Online │ │ 78% Util  │ │ 2 Critical│ │           │            │
│ └───────────┘ └───────────┘ └───────────┘ └───────────┘            │
│                                                                      │
│ ┌─────────────────────────────┐ ┌────────────────────────────────┐ │
│ │      Cluster Status         │ │       GPU Utilization          │ │
│ │                             │ │                                 │ │
│ │ ●prod-east ●prod-west      │ │  [████████░░] 78%              │ │
│ │ ●staging   ○dev-01         │ │  [██████░░░░] 62%              │ │
│ │ ●edge-01   ●edge-02        │ │  [█████████░] 91%              │ │
│ │                             │ │                                 │ │
│ └─────────────────────────────┘ └────────────────────────────────┘ │
│                                                                      │
│ ┌────────────────────────────────────────────────────────────────┐ │
│ │                     Recent Alerts                               │ │
│ │ ⚠ HighCPUUsage    prod-east-1   production   2m ago            │ │
│ │ 🔴 MemoryPressure  staging-01   default      15m ago            │ │
│ │ ⚠ GPUTempHigh     prod-west-1   ml-training  1h ago            │ │
│ └────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
```

### 4.2 Clusters

**Route:** `/clusters`

**Features:**
- Cluster list with filtering and search
- Cluster detail view with health metrics
- Add/edit/delete clusters
- Credential management

### 4.3 GPU Monitoring

**Route:** `/gpu`

**Features:**
- Real-time GPU metrics (utilization, memory, temperature)
- Multi-GPU node view
- Process list with memory consumption
- Historical charts
- Alert thresholds

```
┌─────────────────────────────────────────────────────────────────────┐
│  GPU Monitoring                        [Cluster: prod-east-1 ▼]     │
├─────────────────────────────────────────────────────────────────────┤
│ ┌─────────────────────────────────────────────────────────────────┐ │
│ │  worker-gpu-01                                                   │ │
│ │ ┌───────────────────┐ ┌───────────────────┐                     │ │
│ │ │ GPU 0: A100       │ │ GPU 1: A100       │                     │ │
│ │ │ Util: [████████░░]│ │ Util: [██████░░░░]│                     │ │
│ │ │        78%        │ │        62%        │                     │ │
│ │ │ Mem:  55GB/80GB   │ │ Mem:  42GB/80GB   │                     │ │
│ │ │ Temp: 62°C 🟢     │ │ Temp: 58°C 🟢     │                     │ │
│ │ │ Power: 285W/400W  │ │ Power: 245W/400W  │                     │ │
│ │ └───────────────────┘ └───────────────────┘                     │ │
│ │ Processes:                                                       │ │
│ │ • python (PID 12345) - 42GB - vLLM Inference                    │ │
│ │ • python (PID 12346) - 38GB - Model Training                    │ │
│ └─────────────────────────────────────────────────────────────────┘ │
│                                                                      │
│ ┌─────────────────────────────────────────────────────────────────┐ │
│ │  GPU Utilization History (Last 1 Hour)                          │ │
│ │  100% ┤                    ╭─╮                                  │ │
│ │   80% ┤      ╭────────────╯  ╰──────────                        │ │
│ │   60% ┤─────╯                                                   │ │
│ │   40% ┤                                                          │ │
│ │   20% ┤                                                          │ │
│ │    0% ┼────────────────────────────────────────────             │ │
│ │       10:00    10:15    10:30    10:45    11:00                 │ │
│ └─────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
```

### 4.4 Observability

**Routes:**
- `/observability/metrics` - PromQL queries
- `/observability/traces` - Trace exploration
- `/observability/logs` - Log queries

**Features:**
- Interactive query builders
- Time range selection
- Multi-cluster selection
- Result visualization
- Query history

### 4.5 Alerts

**Route:** `/alerts`

**Features:**
- Active alerts list with filtering
- Alert history
- Severity indicators
- Cluster/namespace grouping
- Link to related metrics/logs

### 4.6 AI Chat

**Route:** `/chat`

**Features:**
- Chat interface with streaming responses
- Persona selection
- Cluster context selection
- Session management
- Tool call visualization
- Markdown rendering

```
┌─────────────────────────────────────────────────────────────────────┐
│  AI Assistant                         [Persona: GPU Expert ▼]       │
├─────────────────────────────────────────────────────────────────────┤
│ ┌───────────────────────────────────────────────────────────────┐   │
│ │                                                                │   │
│ │  User: What's the current GPU utilization?                    │   │
│ │                                                                │   │
│ │  ────────────────────────────────────────────────────────     │   │
│ │                                                                │   │
│ │  🤖 Assistant: I'll check the GPU metrics for you.            │   │
│ │                                                                │   │
│ │  [Tool: get_gpu_nodes] ✓                                      │   │
│ │                                                                │   │
│ │  Based on the current metrics from prod-east-1:               │   │
│ │                                                                │   │
│ │  | Node          | GPU    | Util | Memory | Temp |            │   │
│ │  |---------------|--------|------|--------|------|            │   │
│ │  | worker-gpu-01 | A100#0 | 78%  | 55%    | 62°C |            │   │
│ │  | worker-gpu-01 | A100#1 | 65%  | 48%    | 58°C |            │   │
│ │                                                                │   │
│ │  **Observation**: GPU utilization is healthy. No thermal      │   │
│ │  throttling detected.                                         │   │
│ │                                                                │   │
│ └───────────────────────────────────────────────────────────────┘   │
│ ┌───────────────────────────────────────────────────────────────┐   │
│ │ Ask a question about your infrastructure...                   │   │
│ │                                                    [Send ▶]   │   │
│ └───────────────────────────────────────────────────────────────┘   │
│ Sessions: [New] [GPU Analysis (2h ago)] [Alert Investigation]      │
└─────────────────────────────────────────────────────────────────────┘
```

### 4.7 Reports

**Route:** `/reports`

**Features:**
- Report generation wizard
- Template selection
- Cluster/time range selection
- Format selection (HTML, PDF, Markdown)
- Report history
- Download/view reports

### 4.8 Settings

**Route:** `/settings`

**Features:**
- User preferences
- Theme selection (light/dark)
- Notification settings
- API token management

---

## 5. State Management

### 5.1 Zustand Stores

```typescript
// authStore.ts
interface AuthState {
  user: User | null;
  token: string | null;
  isAuthenticated: boolean;
  login: (token: string) => void;
  logout: () => void;
}

// clusterStore.ts
interface ClusterState {
  clusters: Cluster[];
  selectedCluster: Cluster | null;
  loading: boolean;
  error: string | null;
  fetchClusters: () => Promise<void>;
  selectCluster: (id: string) => void;
}

// alertStore.ts
interface AlertState {
  alerts: Alert[];
  unreadCount: number;
  loading: boolean;
  fetchAlerts: () => Promise<void>;
  markAsRead: (id: string) => void;
  addAlert: (alert: Alert) => void;  // For real-time updates
}

// gpuStore.ts
interface GPUState {
  nodes: GPUNode[];
  selectedNode: GPUNode | null;
  loading: boolean;
  fetchNodes: (clusterId: string) => Promise<void>;
  updateNode: (node: GPUNode) => void;  // For real-time updates
}

// chatStore.ts
interface ChatState {
  sessions: ChatSession[];
  currentSession: ChatSession | null;
  messages: ChatMessage[];
  persona: Persona;
  streaming: boolean;
  createSession: () => Promise<ChatSession>;
  sendMessage: (content: string) => Promise<void>;
  setPersona: (persona: Persona) => void;
}
```

---

## 6. API Integration

### 6.1 Base API Client

```typescript
// services/api.ts
import axios from 'axios';

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || '/api/v1',
  timeout: 30000,
});

// Request interceptor for auth
api.interceptors.request.use((config) => {
  const token = useAuthStore.getState().token;
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Response interceptor for error handling
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      useAuthStore.getState().logout();
    }
    return Promise.reject(error);
  }
);

export default api;
```

### 6.2 Service Example

```typescript
// services/gpuService.ts
import api from './api';
import { GPUNode, GPUSummary } from '../types/gpu';

export const gpuService = {
  async getNodes(clusterIds?: string[]): Promise<GPUNode[]> {
    const params = clusterIds ? { cluster_ids: clusterIds.join(',') } : {};
    const response = await api.get('/gpu/nodes', { params });
    return response.data.nodes;
  },

  async getSummary(): Promise<GPUSummary> {
    const response = await api.get('/gpu/summary');
    return response.data;
  },

  async getNodeDetails(clusterId: string, nodeName: string): Promise<GPUNode> {
    const response = await api.get(`/gpu/nodes/${clusterId}/${nodeName}`);
    return response.data;
  },
};
```

---

## 7. WebSocket Integration

### 7.1 WebSocket Hook

```typescript
// hooks/useWebSocket.ts
import { useEffect, useCallback, useRef } from 'react';
import ReconnectingWebSocket from 'reconnecting-websocket';
import { useAuthStore } from '../store/authStore';

interface UseWebSocketOptions {
  onMessage: (event: MessageEvent) => void;
  onConnect?: () => void;
  onDisconnect?: () => void;
  eventTypes?: string[];
  clusterFilter?: string[];
}

export function useWebSocket(options: UseWebSocketOptions) {
  const wsRef = useRef<ReconnectingWebSocket | null>(null);
  const token = useAuthStore((state) => state.token);

  useEffect(() => {
    const wsUrl = `${import.meta.env.VITE_WS_URL || 'wss://localhost:8080'}/ws`;
    const ws = new ReconnectingWebSocket(wsUrl);

    ws.onopen = () => {
      // Authenticate
      ws.send(JSON.stringify({ type: 'auth', token }));

      // Subscribe to events
      if (options.eventTypes) {
        ws.send(JSON.stringify({
          type: 'subscribe',
          subscription: {
            event_types: options.eventTypes,
            cluster_filter: options.clusterFilter || [],
          },
        }));
      }

      options.onConnect?.();
    };

    ws.onmessage = options.onMessage;
    ws.onclose = () => options.onDisconnect?.();

    wsRef.current = ws;

    return () => {
      ws.close();
    };
  }, [token, options.eventTypes, options.clusterFilter]);

  const send = useCallback((message: object) => {
    wsRef.current?.send(JSON.stringify(message));
  }, []);

  return { send };
}
```

### 7.2 Real-Time Alert Updates

```typescript
// hooks/useAlerts.ts
import { useEffect } from 'react';
import { useAlertStore } from '../store/alertStore';
import { useWebSocket } from './useWebSocket';

export function useAlerts() {
  const { alerts, addAlert, fetchAlerts } = useAlertStore();

  useWebSocket({
    eventTypes: ['ALERT_FIRED', 'ALERT_RESOLVED'],
    onMessage: (event) => {
      const data = JSON.parse(event.data);
      if (data.type === 'event') {
        addAlert(data.payload);
      }
    },
  });

  useEffect(() => {
    fetchAlerts();
  }, []);

  return { alerts };
}
```

---

## 8. Theming

### 8.1 Tailwind Configuration

```javascript
// tailwind.config.js
module.exports = {
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        primary: {
          50: '#eff6ff',
          500: '#3b82f6',
          600: '#2563eb',
          700: '#1d4ed8',
        },
        severity: {
          critical: '#ef4444',
          warning: '#f59e0b',
          info: '#3b82f6',
        },
        status: {
          online: '#22c55e',
          offline: '#ef4444',
          degraded: '#f59e0b',
          unknown: '#6b7280',
        },
      },
    },
  },
};
```

### 8.2 Dark Mode Toggle

```typescript
// hooks/useTheme.ts
import { create } from 'zustand';
import { persist } from 'zustand/middleware';

interface ThemeState {
  isDark: boolean;
  toggle: () => void;
}

export const useTheme = create<ThemeState>()(
  persist(
    (set) => ({
      isDark: false,
      toggle: () => set((state) => {
        const newDark = !state.isDark;
        document.documentElement.classList.toggle('dark', newDark);
        return { isDark: newDark };
      }),
    }),
    { name: 'theme' }
  )
);
```

---

## 9. Build and Deployment

### 9.1 Environment Variables

```bash
# .env.example
VITE_API_URL=https://aiops.example.com/api/v1
VITE_WS_URL=wss://aiops.example.com
VITE_OAUTH_CLIENT_ID=aiops-frontend
VITE_OAUTH_ISSUER=https://oauth-openshift.apps.example.com
```

### 9.2 Docker Build

```dockerfile
# Dockerfile
FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/nginx.conf
EXPOSE 8080
CMD ["nginx", "-g", "daemon off;"]
```

### 9.3 Nginx Configuration

```nginx
# nginx.conf
server {
    listen 8080;
    root /usr/share/nginx/html;
    index index.html;

    # SPA routing
    location / {
        try_files $uri $uri/ /index.html;
    }

    # API proxy (optional, if not using external gateway)
    location /api/ {
        proxy_pass http://api-gateway:8080;
    }

    location /ws {
        proxy_pass http://realtime-streaming:8080;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }

    # Cache static assets
    location /assets/ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
}
```

---

## 10. Testing

### 10.1 Unit Tests

```typescript
// components/ClusterCard.test.tsx
import { render, screen } from '@testing-library/react';
import { ClusterCard } from './ClusterCard';

describe('ClusterCard', () => {
  it('renders cluster name', () => {
    render(<ClusterCard cluster={mockCluster} />);
    expect(screen.getByText('prod-east-1')).toBeInTheDocument();
  });

  it('shows online status indicator', () => {
    render(<ClusterCard cluster={{ ...mockCluster, status: { state: 'ONLINE' } }} />);
    expect(screen.getByTestId('status-indicator')).toHaveClass('bg-green-500');
  });
});
```

### 10.2 E2E Tests (Playwright)

```typescript
// e2e/dashboard.spec.ts
import { test, expect } from '@playwright/test';

test('dashboard loads clusters', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByText('Fleet Overview')).toBeVisible();
  await expect(page.getByTestId('cluster-grid')).toBeVisible();
});
```

---

## 11. Accessibility

- WCAG 2.1 AA compliance
- Keyboard navigation
- Screen reader support
- Color contrast ratios
- Focus indicators
- ARIA labels

---

## 12. Open Questions

1. **Offline Support**: Should we add service worker for offline capability?
2. **Mobile Responsive**: Full mobile support or desktop-focused?
3. **Internationalization**: Support for multiple languages?
4. **Custom Dashboards**: Allow users to create custom dashboard layouts?
5. **Embeddable Widgets**: Support embedding components in external pages?

---

## Next: [08-integration-matrix.md](./08-integration-matrix.md)

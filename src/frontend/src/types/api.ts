export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface ApiError {
  detail: string;
  status_code: number;
}

export interface HealthStatus {
  status: 'healthy' | 'unhealthy' | 'degraded';
  service: string;
  version?: string;
  uptime_seconds?: number;
}

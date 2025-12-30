import api from './api';
import type { Alert, AlertSummary } from '../types/alerts';

export interface AlertFilters {
  cluster_ids?: string[];
  severity?: string;
  state?: string;
  limit?: number;
}

export const alertService = {
  async list(filters?: AlertFilters): Promise<Alert[]> {
    const params: Record<string, string> = {};
    if (filters?.cluster_ids?.length) {
      params.cluster_ids = filters.cluster_ids.join(',');
    }
    if (filters?.severity) params.severity = filters.severity;
    if (filters?.state) params.state = filters.state;
    if (filters?.limit) params.limit = String(filters.limit);

    const response = await api.get('/alerts', { params });
    return response.data.alerts || response.data;
  },

  async getSummary(): Promise<AlertSummary> {
    const response = await api.get('/alerts/summary');
    return response.data;
  },

  async acknowledge(id: string): Promise<void> {
    await api.post(`/alerts/${id}/acknowledge`);
  },
};

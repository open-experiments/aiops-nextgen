import api from './api';
import type { Cluster, FleetSummary } from '../types/cluster';
import type { PaginatedResponse } from '../types/api';

export interface ClusterFilters {
  environment?: string;
  cluster_type?: string;
  state?: string;
  search?: string;
  page?: number;
  page_size?: number;
}

export const clusterService = {
  async list(filters?: ClusterFilters): Promise<PaginatedResponse<Cluster>> {
    const response = await api.get('/clusters', { params: filters });
    return response.data;
  },

  async get(id: string): Promise<Cluster> {
    const response = await api.get(`/clusters/${id}`);
    return response.data;
  },

  async create(data: Partial<Cluster>): Promise<Cluster> {
    const response = await api.post('/clusters', data);
    return response.data;
  },

  async update(id: string, data: Partial<Cluster>): Promise<Cluster> {
    const response = await api.put(`/clusters/${id}`, data);
    return response.data;
  },

  async delete(id: string): Promise<void> {
    await api.delete(`/clusters/${id}`);
  },

  async getStatus(id: string): Promise<Cluster['status']> {
    const response = await api.get(`/clusters/${id}/status`);
    return response.data;
  },

  async getFleetSummary(): Promise<FleetSummary> {
    const response = await api.get('/fleet/summary');
    return response.data;
  },

  async refresh(id: string): Promise<Cluster> {
    const response = await api.post(`/clusters/${id}/refresh`);
    return response.data;
  },
};

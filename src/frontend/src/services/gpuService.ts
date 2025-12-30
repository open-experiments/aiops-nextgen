import api from './api';
import type { GPUNode, GPUSummary } from '../types/gpu';

export const gpuService = {
  async getNodes(clusterIds?: string[]): Promise<GPUNode[]> {
    const params = clusterIds?.length ? { cluster_ids: clusterIds.join(',') } : {};
    const response = await api.get('/gpu/nodes', { params });
    return response.data.nodes || response.data;
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

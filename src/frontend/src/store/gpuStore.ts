import { create } from 'zustand';
import type { GPUNode, GPUSummary } from '../types/gpu';
import { gpuService } from '../services/gpuService';

interface GPUState {
  nodes: GPUNode[];
  summary: GPUSummary | null;
  selectedNode: GPUNode | null;
  loading: boolean;
  error: string | null;
  fetchNodes: (clusterIds?: string[]) => Promise<void>;
  fetchSummary: () => Promise<void>;
  selectNode: (clusterId: string, nodeName: string) => void;
  updateNode: (node: GPUNode) => void;
}

export const useGPUStore = create<GPUState>((set, get) => ({
  nodes: [],
  summary: null,
  selectedNode: null,
  loading: false,
  error: null,

  fetchNodes: async (clusterIds?: string[]) => {
    set({ loading: true, error: null });
    try {
      const nodes = await gpuService.getNodes(clusterIds);
      set({ nodes, loading: false });
    } catch (error) {
      set({ error: (error as Error).message, loading: false });
    }
  },

  fetchSummary: async () => {
    try {
      const summary = await gpuService.getSummary();
      set({ summary });
    } catch (error) {
      console.error('Failed to fetch GPU summary:', error);
    }
  },

  selectNode: (clusterId: string, nodeName: string) => {
    const node = get().nodes.find(
      (n) => n.cluster_id === clusterId && n.node_name === nodeName
    );
    set({ selectedNode: node || null });
  },

  updateNode: (node: GPUNode) => {
    set((state) => ({
      nodes: state.nodes.map((n) =>
        n.cluster_id === node.cluster_id && n.node_name === node.node_name ? node : n
      ),
      selectedNode:
        state.selectedNode?.cluster_id === node.cluster_id &&
        state.selectedNode?.node_name === node.node_name
          ? node
          : state.selectedNode,
    }));
  },
}));

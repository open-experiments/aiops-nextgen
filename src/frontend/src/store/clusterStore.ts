import { create } from 'zustand';
import type { Cluster, FleetSummary } from '../types/cluster';
import { clusterService } from '../services/clusterService';

interface ClusterState {
  clusters: Cluster[];
  selectedCluster: Cluster | null;
  fleetSummary: FleetSummary | null;
  loading: boolean;
  error: string | null;
  fetchClusters: () => Promise<void>;
  fetchFleetSummary: () => Promise<void>;
  selectCluster: (id: string | null) => void;
  updateCluster: (cluster: Cluster) => void;
  addCluster: (cluster: Cluster) => void;
  removeCluster: (id: string) => void;
}

export const useClusterStore = create<ClusterState>((set, get) => ({
  clusters: [],
  selectedCluster: null,
  fleetSummary: null,
  loading: false,
  error: null,

  fetchClusters: async () => {
    set({ loading: true, error: null });
    try {
      const response = await clusterService.list();
      set({ clusters: response.items, loading: false });
    } catch (error) {
      set({ error: (error as Error).message, loading: false });
    }
  },

  fetchFleetSummary: async () => {
    try {
      const summary = await clusterService.getFleetSummary();
      set({ fleetSummary: summary });
    } catch (error) {
      console.error('Failed to fetch fleet summary:', error);
    }
  },

  selectCluster: (id: string | null) => {
    if (!id) {
      set({ selectedCluster: null });
      return;
    }
    const cluster = get().clusters.find((c) => c.id === id);
    set({ selectedCluster: cluster || null });
  },

  updateCluster: (cluster: Cluster) => {
    set((state) => ({
      clusters: state.clusters.map((c) => (c.id === cluster.id ? cluster : c)),
      selectedCluster:
        state.selectedCluster?.id === cluster.id ? cluster : state.selectedCluster,
    }));
  },

  addCluster: (cluster: Cluster) => {
    set((state) => ({
      clusters: [...state.clusters, cluster],
    }));
  },

  removeCluster: (id: string) => {
    set((state) => ({
      clusters: state.clusters.filter((c) => c.id !== id),
      selectedCluster: state.selectedCluster?.id === id ? null : state.selectedCluster,
    }));
  },
}));

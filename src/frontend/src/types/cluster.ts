export type ClusterType = 'HUB' | 'SPOKE' | 'EDGE' | 'FAR_EDGE';
export type ClusterState = 'ONLINE' | 'OFFLINE' | 'DEGRADED' | 'UNKNOWN';
export type Environment = 'PRODUCTION' | 'STAGING' | 'DEVELOPMENT' | 'LAB';

export interface ClusterCapabilities {
  has_gpu_nodes: boolean;
  gpu_count: number;
  gpu_types: string[];
  has_cnf_workloads: boolean;
  cnf_types: string[];
  has_prometheus: boolean;
  has_loki: boolean;
  has_tempo: boolean;
  has_alertmanager: boolean;
  openshift_version: string | null;
  kubernetes_version: string | null;
}

export interface ClusterStatus {
  state: ClusterState;
  health_score: number;
  connectivity: string;
  last_check_at: string | null;
  error_message: string | null;
  prometheus_healthy: boolean | null;
  tempo_healthy: boolean | null;
  loki_healthy: boolean | null;
  node_count?: number;
  ready_nodes?: number;
  cpu_usage_percent?: number | null;
  memory_usage_percent?: number | null;
  pod_count?: number;
  alert_count?: number;
}

export interface ClusterEndpoints {
  prometheus_url: string | null;
  thanos_url: string | null;
  tempo_url: string | null;
  loki_url: string | null;
  alertmanager_url: string | null;
}

export interface Cluster {
  id: string;
  name: string;
  display_name: string;
  cluster_type: ClusterType;
  platform: string;
  platform_version: string | null;
  environment: Environment;
  api_server_url: string;
  region: string | null;
  labels: Record<string, string>;
  capabilities: ClusterCapabilities | null;
  endpoints: ClusterEndpoints;
  status: ClusterStatus;
  created_at: string;
  updated_at: string;
  last_seen_at: string;
}

export interface FleetSummary {
  total_clusters: number;
  by_type: Record<ClusterType, number>;
  by_state: Record<ClusterState, number>;
  by_environment: Record<Environment, number>;
  total_gpu_count: number;
  total_node_count: number;
  total_pod_count: number;
  average_cpu_usage: number;
  average_memory_usage: number;
}

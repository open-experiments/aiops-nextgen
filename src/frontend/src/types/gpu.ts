export interface GPUMetrics {
  utilization_percent: number;
  memory_used_bytes: number;
  memory_total_bytes: number;
  temperature_celsius: number;
  power_usage_watts: number;
  power_limit_watts: number;
  clock_speed_mhz: number;
  memory_clock_mhz: number;
}

export interface GPUProcess {
  pid: number;
  name: string;
  memory_used_bytes: number;
  gpu_utilization_percent: number;
}

export interface GPU {
  index: number;
  uuid: string;
  name: string;
  serial: string | null;
  pci_bus_id: string;
  metrics: GPUMetrics;
  processes: GPUProcess[];
}

export interface GPUNode {
  cluster_id: string;
  cluster_name: string;
  node_name: string;
  gpus: GPU[];
  driver_version: string;
  cuda_version: string;
  collected_at: string;
}

export interface GPUSummary {
  total_nodes: number;
  total_gpus: number;
  total_memory_gb: number;
  used_memory_gb: number;
  avg_utilization_percent: number;
  gpu_types: Record<string, number>;
  clusters_with_gpu: number;
}

import { useEffect, useState } from 'react';
import { Card } from '../../components/common/Card';
import { ProgressBar } from '../../components/common/ProgressBar';
import { Spinner } from '../../components/common/Spinner';
import { useGPUStore } from '../../store/gpuStore';
import { useClusterStore } from '../../store/clusterStore';
import type { GPUNode, GPU } from '../../types/gpu';

export function GPUMonitoring() {
  const { nodes, summary, loading, fetchNodes, fetchSummary } = useGPUStore();
  const { clusters, fetchClusters } = useClusterStore();
  const [selectedCluster, setSelectedCluster] = useState<string>('all');

  useEffect(() => {
    fetchClusters();
    fetchSummary();
  }, []);

  useEffect(() => {
    if (selectedCluster === 'all') {
      fetchNodes();
    } else {
      fetchNodes([selectedCluster]);
    }
  }, [selectedCluster]);

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <Spinner size="lg" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
          GPU Monitoring
        </h1>
        <select
          value={selectedCluster}
          onChange={(e) => setSelectedCluster(e.target.value)}
          className="input w-48"
        >
          <option value="all">All Clusters</option>
          {clusters
            .filter((c) => c.capabilities?.has_gpu_nodes)
            .map((cluster) => (
              <option key={cluster.id} value={cluster.id}>
                {cluster.name}
              </option>
            ))}
        </select>
      </div>

      {/* Summary Cards */}
      {summary && (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <Card>
            <div className="text-center">
              <p className="text-3xl font-bold text-gray-900 dark:text-white">
                {summary.total_gpus}
              </p>
              <p className="text-sm text-gray-500 dark:text-gray-400">Total GPUs</p>
            </div>
          </Card>
          <Card>
            <div className="text-center">
              <p className="text-3xl font-bold text-gray-900 dark:text-white">
                {summary.avg_utilization_percent.toFixed(0)}%
              </p>
              <p className="text-sm text-gray-500 dark:text-gray-400">Avg Utilization</p>
            </div>
          </Card>
          <Card>
            <div className="text-center">
              <p className="text-3xl font-bold text-gray-900 dark:text-white">
                {summary.used_memory_gb.toFixed(1)} GB
              </p>
              <p className="text-sm text-gray-500 dark:text-gray-400">Memory Used</p>
            </div>
          </Card>
          <Card>
            <div className="text-center">
              <p className="text-3xl font-bold text-gray-900 dark:text-white">
                {summary.total_nodes}
              </p>
              <p className="text-sm text-gray-500 dark:text-gray-400">GPU Nodes</p>
            </div>
          </Card>
        </div>
      )}

      {/* GPU Nodes */}
      {nodes.length === 0 ? (
        <Card>
          <p className="text-center text-gray-500 dark:text-gray-400">
            No GPU nodes found
          </p>
        </Card>
      ) : (
        <div className="space-y-4">
          {nodes.map((node) => (
            <GPUNodeCard key={`${node.cluster_id}-${node.node_name}`} node={node} />
          ))}
        </div>
      )}
    </div>
  );
}

function GPUNodeCard({ node }: { node: GPUNode }) {
  return (
    <Card
      title={node.node_name}
      subtitle={`${node.cluster_name} · Driver ${node.driver_version} · CUDA ${node.cuda_version}`}
    >
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-4">
        {node.gpus.map((gpu) => (
          <GPUCard key={gpu.uuid} gpu={gpu} />
        ))}
      </div>
    </Card>
  );
}

function GPUCard({ gpu }: { gpu: GPU }) {
  const memoryUsedGB = gpu.metrics.memory_used_bytes / 1024 / 1024 / 1024;
  const memoryTotalGB = gpu.metrics.memory_total_bytes / 1024 / 1024 / 1024;
  const memoryPercent = (memoryUsedGB / memoryTotalGB) * 100;

  const tempColor =
    gpu.metrics.temperature_celsius >= 80
      ? 'text-red-500'
      : gpu.metrics.temperature_celsius >= 70
        ? 'text-yellow-500'
        : 'text-green-500';

  return (
    <div className="rounded-lg border border-gray-200 p-4 dark:border-gray-700">
      <div className="mb-3 flex items-center justify-between">
        <div>
          <p className="font-medium text-gray-900 dark:text-white">
            GPU {gpu.index}
          </p>
          <p className="text-xs text-gray-500 dark:text-gray-400">{gpu.name}</p>
        </div>
        <span className={`text-lg font-bold ${tempColor}`}>
          {gpu.metrics.temperature_celsius}°C
        </span>
      </div>

      <div className="space-y-3">
        <ProgressBar
          label="Utilization"
          value={gpu.metrics.utilization_percent}
          size="sm"
        />

        <ProgressBar
          label="Memory"
          value={memoryPercent}
          size="sm"
        />

        <div className="flex justify-between text-xs text-gray-500 dark:text-gray-400">
          <span>Power</span>
          <span>
            {gpu.metrics.power_usage_watts}W / {gpu.metrics.power_limit_watts}W
          </span>
        </div>
      </div>

      {gpu.processes.length > 0 && (
        <div className="mt-3 border-t border-gray-200 pt-3 dark:border-gray-700">
          <p className="mb-2 text-xs font-medium text-gray-500 dark:text-gray-400">
            Processes
          </p>
          <div className="space-y-1">
            {gpu.processes.slice(0, 3).map((proc) => (
              <div
                key={proc.pid}
                className="flex justify-between text-xs text-gray-600 dark:text-gray-300"
              >
                <span className="truncate">{proc.name}</span>
                <span>{(proc.memory_used_bytes / 1024 / 1024 / 1024).toFixed(1)} GB</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

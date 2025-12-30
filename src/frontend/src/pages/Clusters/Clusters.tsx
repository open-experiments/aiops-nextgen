import { useEffect, useState } from 'react';
import { PlusIcon, MagnifyingGlassIcon } from '@heroicons/react/24/outline';
import { Card } from '../../components/common/Card';
import { StatusBadge } from '../../components/common/StatusBadge';
import { Spinner } from '../../components/common/Spinner';
import { useClusterStore } from '../../store/clusterStore';
import type { Cluster, ClusterState } from '../../types/cluster';

export function Clusters() {
  const { clusters, loading, fetchClusters } = useClusterStore();
  const [search, setSearch] = useState('');
  const [filter, setFilter] = useState<string>('all');

  useEffect(() => {
    fetchClusters();
  }, []);

  const filteredClusters = clusters.filter((cluster) => {
    const matchesSearch =
      cluster.name.toLowerCase().includes(search.toLowerCase()) ||
      cluster.display_name.toLowerCase().includes(search.toLowerCase());
    const matchesFilter =
      filter === 'all' || cluster.status.state.toLowerCase() === filter;
    return matchesSearch && matchesFilter;
  });

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
          Clusters
        </h1>
        <button className="btn-primary">
          <PlusIcon className="mr-2 h-4 w-4" />
          Add Cluster
        </button>
      </div>

      {/* Filters */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center">
        <div className="relative flex-1">
          <MagnifyingGlassIcon className="absolute left-3 top-1/2 h-5 w-5 -translate-y-1/2 text-gray-400" />
          <input
            type="text"
            placeholder="Search clusters..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="input pl-10"
          />
        </div>
        <div className="flex gap-2">
          {['all', 'online', 'offline', 'degraded'].map((status) => (
            <button
              key={status}
              onClick={() => setFilter(status)}
              className={`rounded-lg px-4 py-2 text-sm font-medium transition-colors ${
                filter === status
                  ? 'bg-primary-600 text-white'
                  : 'bg-gray-100 text-gray-700 hover:bg-gray-200 dark:bg-gray-700 dark:text-gray-300 dark:hover:bg-gray-600'
              }`}
            >
              {status.charAt(0).toUpperCase() + status.slice(1)}
            </button>
          ))}
        </div>
      </div>

      {/* Cluster Grid */}
      {filteredClusters.length === 0 ? (
        <Card>
          <p className="text-center text-gray-500 dark:text-gray-400">
            No clusters found
          </p>
        </Card>
      ) : (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
          {filteredClusters.map((cluster) => (
            <ClusterCard key={cluster.id} cluster={cluster} />
          ))}
        </div>
      )}
    </div>
  );
}

function ClusterCard({ cluster }: { cluster: Cluster }) {
  const stateColors: Record<ClusterState, 'online' | 'offline' | 'degraded' | 'unknown'> = {
    ONLINE: 'online',
    OFFLINE: 'offline',
    DEGRADED: 'degraded',
    UNKNOWN: 'unknown',
  };

  return (
    <Card className="hover:shadow-md transition-shadow">
      <div className="flex items-start justify-between">
        <div>
          <h3 className="font-semibold text-gray-900 dark:text-white">
            {cluster.display_name || cluster.name}
          </h3>
          <p className="text-sm text-gray-500 dark:text-gray-400">
            {cluster.cluster_type} · {cluster.environment}
          </p>
        </div>
        <StatusBadge
          status={stateColors[cluster.status.state]}
          label={cluster.status.state}
        />
      </div>

      <div className="mt-4 space-y-3">
        <div className="flex justify-between text-sm">
          <span className="text-gray-500 dark:text-gray-400">Health</span>
          <span className="font-medium text-gray-900 dark:text-white">
            {cluster.status.health_score}%
          </span>
        </div>

        <div className="flex justify-between text-sm">
          <span className="text-gray-500 dark:text-gray-400">Platform</span>
          <span className="font-medium text-gray-900 dark:text-white">
            {cluster.platform} {cluster.platform_version || ''}
          </span>
        </div>

        <div className="flex justify-between text-sm">
          <span className="text-gray-500 dark:text-gray-400">Region</span>
          <span className="font-medium text-gray-900 dark:text-white">
            {cluster.region || 'N/A'}
          </span>
        </div>
      </div>

      <div className="mt-4 flex flex-wrap gap-1">
        {cluster.capabilities?.has_gpu_nodes && (
          <span className="rounded-full bg-purple-100 px-2 py-0.5 text-xs font-medium text-purple-700 dark:bg-purple-900/30 dark:text-purple-300">
            GPU: {cluster.capabilities.gpu_count}
          </span>
        )}
        {cluster.capabilities?.has_cnf_workloads && (
          <span className="rounded-full bg-blue-100 px-2 py-0.5 text-xs font-medium text-blue-700 dark:bg-blue-900/30 dark:text-blue-300">
            CNF
          </span>
        )}
        {cluster.capabilities?.has_prometheus && (
          <span className="rounded-full bg-green-100 px-2 py-0.5 text-xs font-medium text-green-700 dark:bg-green-900/30 dark:text-green-300">
            Prometheus
          </span>
        )}
      </div>
    </Card>
  );
}

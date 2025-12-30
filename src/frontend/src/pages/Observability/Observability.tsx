import { useEffect } from 'react';
import { Card } from '../../components/common/Card';
import { StatusBadge } from '../../components/common/StatusBadge';
import { Spinner } from '../../components/common/Spinner';
import { useClusterStore } from '../../store/clusterStore';
import type { Cluster } from '../../types/cluster';
import {
  ChartBarIcon,
  DocumentTextIcon,
  ClockIcon,
  BellAlertIcon,
} from '@heroicons/react/24/outline';

export function Observability() {
  const { clusters, loading, fetchClusters } = useClusterStore();

  useEffect(() => {
    fetchClusters();
  }, []);

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <Spinner size="lg" />
      </div>
    );
  }

  // Calculate observability stack statistics
  const stats = {
    prometheusHealthy: clusters.filter((c) => c.status.prometheus_healthy).length,
    lokiHealthy: clusters.filter((c) => c.status.loki_healthy).length,
    tempoHealthy: clusters.filter((c) => c.status.tempo_healthy).length,
    hasPrometheus: clusters.filter((c) => c.capabilities?.has_prometheus).length,
    hasLoki: clusters.filter((c) => c.capabilities?.has_loki).length,
    hasTempo: clusters.filter((c) => c.capabilities?.has_tempo).length,
    hasAlertmanager: clusters.filter((c) => c.capabilities?.has_alertmanager).length,
  };

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
        Observability Stack
      </h1>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <ObservabilityCard
          title="Prometheus"
          icon={ChartBarIcon}
          healthy={stats.prometheusHealthy}
          total={stats.hasPrometheus}
          color="orange"
        />
        <ObservabilityCard
          title="Loki"
          icon={DocumentTextIcon}
          healthy={stats.lokiHealthy}
          total={stats.hasLoki}
          color="yellow"
        />
        <ObservabilityCard
          title="Tempo"
          icon={ClockIcon}
          healthy={stats.tempoHealthy}
          total={stats.hasTempo}
          color="blue"
        />
        <ObservabilityCard
          title="Alertmanager"
          icon={BellAlertIcon}
          healthy={stats.hasAlertmanager}
          total={stats.hasAlertmanager}
          color="red"
        />
      </div>

      {/* Cluster Observability Status */}
      <Card title="Cluster Observability Status" subtitle="Per-cluster observability stack health">
        {clusters.length === 0 ? (
          <p className="text-center text-gray-500 dark:text-gray-400">
            No clusters found
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
              <thead>
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500 dark:text-gray-400">
                    Cluster
                  </th>
                  <th className="px-4 py-3 text-center text-xs font-medium uppercase tracking-wider text-gray-500 dark:text-gray-400">
                    Prometheus
                  </th>
                  <th className="px-4 py-3 text-center text-xs font-medium uppercase tracking-wider text-gray-500 dark:text-gray-400">
                    Loki
                  </th>
                  <th className="px-4 py-3 text-center text-xs font-medium uppercase tracking-wider text-gray-500 dark:text-gray-400">
                    Tempo
                  </th>
                  <th className="px-4 py-3 text-center text-xs font-medium uppercase tracking-wider text-gray-500 dark:text-gray-400">
                    Alertmanager
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500 dark:text-gray-400">
                    Endpoints
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
                {clusters.map((cluster) => (
                  <ClusterObservabilityRow key={cluster.id} cluster={cluster} />
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}

interface ObservabilityCardProps {
  title: string;
  icon: React.ComponentType<{ className?: string }>;
  healthy: number;
  total: number;
  color: 'orange' | 'yellow' | 'blue' | 'red';
}

function ObservabilityCard({ title, icon: Icon, healthy, total, color }: ObservabilityCardProps) {
  const colorClasses = {
    orange: 'bg-orange-100 text-orange-600 dark:bg-orange-900/30 dark:text-orange-400',
    yellow: 'bg-yellow-100 text-yellow-600 dark:bg-yellow-900/30 dark:text-yellow-400',
    blue: 'bg-blue-100 text-blue-600 dark:bg-blue-900/30 dark:text-blue-400',
    red: 'bg-red-100 text-red-600 dark:bg-red-900/30 dark:text-red-400',
  };

  const healthPercent = total > 0 ? Math.round((healthy / total) * 100) : 0;
  const healthStatus = healthPercent === 100 ? 'online' : healthPercent >= 50 ? 'degraded' : total === 0 ? 'unknown' : 'offline';

  return (
    <Card>
      <div className="flex items-center gap-4">
        <div className={`rounded-lg p-3 ${colorClasses[color]}`}>
          <Icon className="h-6 w-6" />
        </div>
        <div className="flex-1">
          <p className="text-sm font-medium text-gray-500 dark:text-gray-400">{title}</p>
          <div className="flex items-center gap-2">
            <p className="text-2xl font-bold text-gray-900 dark:text-white">
              {healthy}/{total}
            </p>
            <StatusBadge status={healthStatus} label={`${healthPercent}%`} />
          </div>
        </div>
      </div>
    </Card>
  );
}

function ClusterObservabilityRow({ cluster }: { cluster: Cluster }) {
  const renderHealthStatus = (hasCapability: boolean | undefined, isHealthy: boolean | null | undefined) => {
    if (!hasCapability) {
      return <span className="text-gray-400 dark:text-gray-500">N/A</span>;
    }
    return (
      <StatusBadge
        status={isHealthy ? 'online' : isHealthy === false ? 'offline' : 'unknown'}
      />
    );
  };

  const renderEndpointLink = (url: string | null, label: string) => {
    if (!url) return null;
    return (
      <a
        href={url}
        target="_blank"
        rel="noopener noreferrer"
        className="text-xs text-primary-600 hover:text-primary-700 hover:underline"
      >
        {label}
      </a>
    );
  };

  return (
    <tr className="hover:bg-gray-50 dark:hover:bg-gray-800/50">
      <td className="whitespace-nowrap px-4 py-3">
        <div>
          <p className="font-medium text-gray-900 dark:text-white">
            {cluster.display_name || cluster.name}
          </p>
          <p className="text-xs text-gray-500 dark:text-gray-400">
            {cluster.cluster_type} · {cluster.environment}
          </p>
        </div>
      </td>
      <td className="whitespace-nowrap px-4 py-3 text-center">
        {renderHealthStatus(cluster.capabilities?.has_prometheus, cluster.status.prometheus_healthy)}
      </td>
      <td className="whitespace-nowrap px-4 py-3 text-center">
        {renderHealthStatus(cluster.capabilities?.has_loki, cluster.status.loki_healthy)}
      </td>
      <td className="whitespace-nowrap px-4 py-3 text-center">
        {renderHealthStatus(cluster.capabilities?.has_tempo, cluster.status.tempo_healthy)}
      </td>
      <td className="whitespace-nowrap px-4 py-3 text-center">
        {cluster.capabilities?.has_alertmanager ? (
          <StatusBadge status="online" />
        ) : (
          <span className="text-gray-400 dark:text-gray-500">N/A</span>
        )}
      </td>
      <td className="px-4 py-3">
        <div className="flex flex-wrap gap-2">
          {renderEndpointLink(cluster.endpoints.prometheus_url, 'Prometheus')}
          {renderEndpointLink(cluster.endpoints.loki_url, 'Loki')}
          {renderEndpointLink(cluster.endpoints.tempo_url, 'Tempo')}
          {renderEndpointLink(cluster.endpoints.alertmanager_url, 'Alertmanager')}
        </div>
      </td>
    </tr>
  );
}

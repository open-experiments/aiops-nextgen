import { useEffect } from 'react';
import { Link } from 'react-router-dom';
import {
  ServerStackIcon,
  CpuChipIcon,
  BellAlertIcon,
  HeartIcon,
} from '@heroicons/react/24/outline';
import { Card } from '../../components/common/Card';
import { StatusBadge } from '../../components/common/StatusBadge';
import { ProgressBar } from '../../components/common/ProgressBar';
import { Spinner } from '../../components/common/Spinner';
import { useClusterStore } from '../../store/clusterStore';
import { useAlertStore } from '../../store/alertStore';
import { useGPUStore } from '../../store/gpuStore';
import type { ClusterState } from '../../types/cluster';

export function Dashboard() {
  const { clusters, fleetSummary, loading, fetchClusters, fetchFleetSummary } =
    useClusterStore();
  const { alerts, fetchAlerts } = useAlertStore();
  const { summary: gpuSummary, fetchSummary: fetchGPUSummary } = useGPUStore();

  useEffect(() => {
    fetchClusters();
    fetchFleetSummary();
    fetchAlerts();
    fetchGPUSummary();
  }, []);

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <Spinner size="lg" />
      </div>
    );
  }

  const criticalAlerts = alerts.filter((a) => a.severity === 'CRITICAL').length;
  const warningAlerts = alerts.filter((a) => a.severity === 'WARNING').length;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
        Fleet Overview
      </h1>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-4">
        <SummaryCard
          title="Clusters"
          value={fleetSummary?.total_clusters || clusters.length}
          subtitle={`${fleetSummary?.by_state?.ONLINE || 0} Online`}
          icon={ServerStackIcon}
          color="blue"
        />
        <SummaryCard
          title="GPUs"
          value={gpuSummary?.total_gpus || fleetSummary?.total_gpu_count || 0}
          subtitle={`${gpuSummary?.avg_utilization_percent?.toFixed(0) || 0}% Utilization`}
          icon={CpuChipIcon}
          color="purple"
        />
        <SummaryCard
          title="Alerts"
          value={alerts.length}
          subtitle={`${criticalAlerts} Critical, ${warningAlerts} Warning`}
          icon={BellAlertIcon}
          color={criticalAlerts > 0 ? 'red' : warningAlerts > 0 ? 'yellow' : 'green'}
        />
        <SummaryCard
          title="Fleet Health"
          value={`${fleetSummary?.average_cpu_usage?.toFixed(0) || 0}%`}
          subtitle="Avg CPU Usage"
          icon={HeartIcon}
          color="green"
        />
      </div>

      {/* Cluster Status Grid */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Card title="Cluster Status" subtitle="Quick overview of all clusters">
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
            {clusters.slice(0, 6).map((cluster) => (
              <Link
                key={cluster.id}
                to={`/clusters/${cluster.id}`}
                className="flex items-center gap-2 rounded-lg bg-gray-50 p-3 hover:bg-gray-100 dark:bg-gray-700/50 dark:hover:bg-gray-700"
              >
                <StatusBadge
                  status={cluster.status.state.toLowerCase() as Lowercase<ClusterState>}
                />
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium text-gray-900 dark:text-white">
                    {cluster.name}
                  </p>
                  <p className="text-xs text-gray-500 dark:text-gray-400">
                    {cluster.cluster_type}
                  </p>
                </div>
              </Link>
            ))}
          </div>
          {clusters.length > 6 && (
            <Link
              to="/clusters"
              className="mt-4 block text-center text-sm text-primary-600 hover:text-primary-700"
            >
              View all {clusters.length} clusters
            </Link>
          )}
        </Card>

        <Card title="GPU Utilization" subtitle="Fleet-wide GPU metrics">
          <div className="space-y-4">
            <ProgressBar
              label="Average Utilization"
              value={gpuSummary?.avg_utilization_percent || 0}
            />
            <ProgressBar
              label="Memory Usage"
              value={
                gpuSummary && gpuSummary.total_memory_gb > 0
                  ? (gpuSummary.used_memory_gb / gpuSummary.total_memory_gb) * 100
                  : 0
              }
            />
            <div className="flex justify-between text-sm">
              <span className="text-gray-500 dark:text-gray-400">Total GPUs</span>
              <span className="font-medium text-gray-900 dark:text-white">
                {gpuSummary?.total_gpus || 0}
              </span>
            </div>
          </div>
        </Card>
      </div>

      {/* Recent Alerts */}
      <Card title="Recent Alerts" action={<Link to="/alerts" className="text-sm text-primary-600 hover:text-primary-700">View all</Link>}>
        {alerts.length === 0 ? (
          <p className="text-center text-gray-500 dark:text-gray-400">
            No active alerts
          </p>
        ) : (
          <div className="divide-y divide-gray-200 dark:divide-gray-700">
            {alerts.slice(0, 5).map((alert) => (
              <div
                key={alert.id}
                className="flex items-center justify-between py-3"
              >
                <div className="flex items-center gap-3">
                  <StatusBadge
                    status={alert.severity.toLowerCase() as 'critical' | 'warning' | 'info'}
                  />
                  <div>
                    <p className="font-medium text-gray-900 dark:text-white">
                      {alert.name}
                    </p>
                    <p className="text-sm text-gray-500 dark:text-gray-400">
                      {alert.cluster_name} · {alert.labels.namespace || 'cluster'}
                    </p>
                  </div>
                </div>
                <span className="text-sm text-gray-500 dark:text-gray-400">
                  {new Date(alert.starts_at).toLocaleTimeString()}
                </span>
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  );
}

interface SummaryCardProps {
  title: string;
  value: number | string;
  subtitle: string;
  icon: React.ComponentType<{ className?: string }>;
  color: 'blue' | 'purple' | 'green' | 'red' | 'yellow';
}

function SummaryCard({ title, value, subtitle, icon: Icon, color }: SummaryCardProps) {
  const colorClasses = {
    blue: 'bg-blue-100 text-blue-600 dark:bg-blue-900/30 dark:text-blue-400',
    purple: 'bg-purple-100 text-purple-600 dark:bg-purple-900/30 dark:text-purple-400',
    green: 'bg-green-100 text-green-600 dark:bg-green-900/30 dark:text-green-400',
    red: 'bg-red-100 text-red-600 dark:bg-red-900/30 dark:text-red-400',
    yellow: 'bg-yellow-100 text-yellow-600 dark:bg-yellow-900/30 dark:text-yellow-400',
  };

  return (
    <Card>
      <div className="flex items-center gap-4">
        <div className={`rounded-lg p-3 ${colorClasses[color]}`}>
          <Icon className="h-6 w-6" />
        </div>
        <div>
          <p className="text-2xl font-bold text-gray-900 dark:text-white">{value}</p>
          <p className="text-sm text-gray-500 dark:text-gray-400">{title}</p>
          <p className="text-xs text-gray-400 dark:text-gray-500">{subtitle}</p>
        </div>
      </div>
    </Card>
  );
}

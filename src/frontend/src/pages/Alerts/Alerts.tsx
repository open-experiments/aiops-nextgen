import { useEffect, useState } from 'react';
import { MagnifyingGlassIcon, FunnelIcon } from '@heroicons/react/24/outline';
import { Card } from '../../components/common/Card';
import { StatusBadge } from '../../components/common/StatusBadge';
import { Spinner } from '../../components/common/Spinner';
import { useAlertStore } from '../../store/alertStore';
import { useClusterStore } from '../../store/clusterStore';
import type { Alert, AlertSeverity, AlertState } from '../../types/alerts';

export function Alerts() {
  const { alerts, loading, fetchAlerts } = useAlertStore();
  const { clusters, fetchClusters } = useClusterStore();
  const [search, setSearch] = useState('');
  const [severityFilter, setSeverityFilter] = useState<AlertSeverity | 'all'>('all');
  const [stateFilter, setStateFilter] = useState<AlertState | 'all'>('FIRING');
  const [clusterFilter, setClusterFilter] = useState<string>('all');

  useEffect(() => {
    fetchAlerts();
    fetchClusters();
  }, []);

  const filteredAlerts = alerts.filter((alert) => {
    const matchesSearch =
      alert.name.toLowerCase().includes(search.toLowerCase()) ||
      alert.message.toLowerCase().includes(search.toLowerCase()) ||
      alert.cluster_name.toLowerCase().includes(search.toLowerCase());
    const matchesSeverity = severityFilter === 'all' || alert.severity === severityFilter;
    const matchesState = stateFilter === 'all' || alert.state === stateFilter;
    const matchesCluster = clusterFilter === 'all' || alert.cluster_id === clusterFilter;
    return matchesSearch && matchesSeverity && matchesState && matchesCluster;
  });

  // Summary stats
  const criticalCount = alerts.filter((a) => a.severity === 'CRITICAL' && a.state === 'FIRING').length;
  const warningCount = alerts.filter((a) => a.severity === 'WARNING' && a.state === 'FIRING').length;
  const infoCount = alerts.filter((a) => a.severity === 'INFO' && a.state === 'FIRING').length;

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
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Alerts</h1>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <SummaryCard
          label="Critical"
          count={criticalCount}
          color="red"
          onClick={() => setSeverityFilter('CRITICAL')}
          isActive={severityFilter === 'CRITICAL'}
        />
        <SummaryCard
          label="Warning"
          count={warningCount}
          color="yellow"
          onClick={() => setSeverityFilter('WARNING')}
          isActive={severityFilter === 'WARNING'}
        />
        <SummaryCard
          label="Info"
          count={infoCount}
          color="blue"
          onClick={() => setSeverityFilter('INFO')}
          isActive={severityFilter === 'INFO'}
        />
      </div>

      {/* Filters */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center">
        <div className="relative flex-1">
          <MagnifyingGlassIcon className="absolute left-3 top-1/2 h-5 w-5 -translate-y-1/2 text-gray-400" />
          <input
            type="text"
            placeholder="Search alerts..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="input pl-10"
          />
        </div>
        <div className="flex gap-2">
          <select
            value={stateFilter}
            onChange={(e) => setStateFilter(e.target.value as AlertState | 'all')}
            className="input w-32"
          >
            <option value="all">All States</option>
            <option value="FIRING">Firing</option>
            <option value="RESOLVED">Resolved</option>
            <option value="PENDING">Pending</option>
          </select>
          <select
            value={clusterFilter}
            onChange={(e) => setClusterFilter(e.target.value)}
            className="input w-40"
          >
            <option value="all">All Clusters</option>
            {clusters.map((cluster) => (
              <option key={cluster.id} value={cluster.id}>
                {cluster.name}
              </option>
            ))}
          </select>
          {severityFilter !== 'all' && (
            <button
              onClick={() => setSeverityFilter('all')}
              className="btn-secondary text-sm"
            >
              <FunnelIcon className="mr-1 h-4 w-4" />
              Clear
            </button>
          )}
        </div>
      </div>

      {/* Alert List */}
      {filteredAlerts.length === 0 ? (
        <Card>
          <p className="text-center text-gray-500 dark:text-gray-400">
            No alerts found
          </p>
        </Card>
      ) : (
        <div className="space-y-3">
          {filteredAlerts.map((alert) => (
            <AlertCard key={alert.id} alert={alert} />
          ))}
        </div>
      )}
    </div>
  );
}

function SummaryCard({
  label,
  count,
  color,
  onClick,
  isActive,
}: {
  label: string;
  count: number;
  color: 'red' | 'yellow' | 'blue';
  onClick: () => void;
  isActive: boolean;
}) {
  const colorClasses = {
    red: 'border-red-500 bg-red-50 dark:bg-red-900/20',
    yellow: 'border-yellow-500 bg-yellow-50 dark:bg-yellow-900/20',
    blue: 'border-blue-500 bg-blue-50 dark:bg-blue-900/20',
  };

  const textClasses = {
    red: 'text-red-600 dark:text-red-400',
    yellow: 'text-yellow-600 dark:text-yellow-400',
    blue: 'text-blue-600 dark:text-blue-400',
  };

  return (
    <button
      onClick={onClick}
      className={`rounded-lg border-l-4 p-4 text-left transition-all ${colorClasses[color]} ${
        isActive ? 'ring-2 ring-primary-500' : ''
      }`}
    >
      <p className={`text-3xl font-bold ${textClasses[color]}`}>{count}</p>
      <p className="text-sm text-gray-600 dark:text-gray-400">{label}</p>
    </button>
  );
}

function AlertCard({ alert }: { alert: Alert }) {
  const [expanded, setExpanded] = useState(false);

  const severityColors: Record<AlertSeverity, 'critical' | 'warning' | 'info'> = {
    CRITICAL: 'critical',
    WARNING: 'warning',
    INFO: 'info',
  };

  const stateColors: Record<AlertState, string> = {
    FIRING: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400',
    RESOLVED: 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400',
    PENDING: 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400',
  };

  const timeAgo = (dateString: string) => {
    const date = new Date(dateString);
    const now = new Date();
    const seconds = Math.floor((now.getTime() - date.getTime()) / 1000);

    if (seconds < 60) return `${seconds}s ago`;
    const minutes = Math.floor(seconds / 60);
    if (minutes < 60) return `${minutes}m ago`;
    const hours = Math.floor(minutes / 60);
    if (hours < 24) return `${hours}h ago`;
    const days = Math.floor(hours / 24);
    return `${days}d ago`;
  };

  return (
    <Card className="cursor-pointer" onClick={() => setExpanded(!expanded)}>
      <div className="flex items-start justify-between">
        <div className="flex items-start gap-3">
          <StatusBadge status={severityColors[alert.severity]} />
          <div>
            <h3 className="font-semibold text-gray-900 dark:text-white">
              {alert.name}
            </h3>
            <p className="text-sm text-gray-500 dark:text-gray-400">
              {alert.cluster_name}
              {alert.labels.namespace && ` / ${alert.labels.namespace}`}
              {alert.labels.pod && ` / ${alert.labels.pod}`}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${stateColors[alert.state]}`}>
            {alert.state}
          </span>
          <span className="text-sm text-gray-500 dark:text-gray-400">
            {timeAgo(alert.starts_at)}
          </span>
        </div>
      </div>

      {expanded && (
        <div className="mt-4 border-t border-gray-200 pt-4 dark:border-gray-700">
          <div className="space-y-3">
            <div>
              <p className="text-sm font-medium text-gray-700 dark:text-gray-300">
                Message
              </p>
              <p className="mt-1 text-sm text-gray-600 dark:text-gray-400">
                {alert.message}
              </p>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <p className="text-sm font-medium text-gray-700 dark:text-gray-300">
                  Started At
                </p>
                <p className="mt-1 text-sm text-gray-600 dark:text-gray-400">
                  {new Date(alert.starts_at).toLocaleString()}
                </p>
              </div>
              {alert.ends_at && (
                <div>
                  <p className="text-sm font-medium text-gray-700 dark:text-gray-300">
                    Ended At
                  </p>
                  <p className="mt-1 text-sm text-gray-600 dark:text-gray-400">
                    {new Date(alert.ends_at).toLocaleString()}
                  </p>
                </div>
              )}
            </div>

            <div>
              <p className="text-sm font-medium text-gray-700 dark:text-gray-300">
                Labels
              </p>
              <div className="mt-1 flex flex-wrap gap-1">
                {Object.entries(alert.labels).map(([key, value]) => (
                  <span
                    key={key}
                    className="rounded-full bg-gray-100 px-2 py-0.5 text-xs text-gray-600 dark:bg-gray-700 dark:text-gray-300"
                  >
                    {key}: {value}
                  </span>
                ))}
              </div>
            </div>

            {alert.generator_url && (
              <a
                href={alert.generator_url}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-block text-sm text-primary-600 hover:text-primary-700"
                onClick={(e) => e.stopPropagation()}
              >
                View in Alertmanager
              </a>
            )}
          </div>
        </div>
      )}
    </Card>
  );
}

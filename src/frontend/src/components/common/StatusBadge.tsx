import clsx from 'clsx';

type Status = 'online' | 'offline' | 'degraded' | 'unknown';
type Severity = 'critical' | 'warning' | 'info';

interface StatusBadgeProps {
  status: Status | Severity;
  label?: string;
  size?: 'sm' | 'md' | 'lg';
}

const statusColors: Record<Status | Severity, string> = {
  online: 'bg-status-online',
  offline: 'bg-status-offline',
  degraded: 'bg-status-degraded',
  unknown: 'bg-status-unknown',
  critical: 'bg-severity-critical',
  warning: 'bg-severity-warning',
  info: 'bg-severity-info',
};

const sizeClasses = {
  sm: 'h-2 w-2',
  md: 'h-3 w-3',
  lg: 'h-4 w-4',
};

export function StatusBadge({ status, label, size = 'md' }: StatusBadgeProps) {
  const colorClass = statusColors[status.toLowerCase() as Status | Severity] || statusColors.unknown;

  return (
    <div className="flex items-center gap-2">
      <span
        className={clsx(
          'rounded-full',
          sizeClasses[size],
          colorClass
        )}
      />
      {label && (
        <span className="text-sm font-medium text-gray-700 dark:text-gray-300">
          {label}
        </span>
      )}
    </div>
  );
}

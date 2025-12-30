import clsx from 'clsx';

interface ProgressBarProps {
  value: number;
  max?: number;
  label?: string;
  showValue?: boolean;
  color?: 'primary' | 'success' | 'warning' | 'danger';
  size?: 'sm' | 'md' | 'lg';
}

const colorClasses = {
  primary: 'bg-primary-600',
  success: 'bg-green-500',
  warning: 'bg-yellow-500',
  danger: 'bg-red-500',
};

const sizeClasses = {
  sm: 'h-1',
  md: 'h-2',
  lg: 'h-3',
};

export function ProgressBar({
  value,
  max = 100,
  label,
  showValue = true,
  color = 'primary',
  size = 'md',
}: ProgressBarProps) {
  const percentage = Math.min(Math.max((value / max) * 100, 0), 100);

  // Auto-determine color based on value
  const autoColor =
    percentage >= 90 ? 'danger' : percentage >= 75 ? 'warning' : color;

  return (
    <div>
      {(label || showValue) && (
        <div className="mb-1 flex items-center justify-between text-sm">
          {label && (
            <span className="font-medium text-gray-700 dark:text-gray-300">
              {label}
            </span>
          )}
          {showValue && (
            <span className="text-gray-500 dark:text-gray-400">
              {percentage.toFixed(0)}%
            </span>
          )}
        </div>
      )}
      <div
        className={clsx(
          'w-full rounded-full bg-gray-200 dark:bg-gray-700',
          sizeClasses[size]
        )}
      >
        <div
          className={clsx(
            'rounded-full transition-all duration-300',
            colorClasses[autoColor],
            sizeClasses[size]
          )}
          style={{ width: `${percentage}%` }}
        />
      </div>
    </div>
  );
}

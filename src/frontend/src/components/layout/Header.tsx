import { BellIcon, MoonIcon, SunIcon } from '@heroicons/react/24/outline';
import { useThemeStore } from '../../store/themeStore';
import { useAlertStore } from '../../store/alertStore';
import { useAuthStore } from '../../store/authStore';

export function Header() {
  const { isDark, toggle } = useThemeStore();
  const unreadCount = useAlertStore((state) => state.unreadCount);
  const user = useAuthStore((state) => state.user);

  return (
    <header className="sticky top-0 z-10 flex h-16 items-center justify-between border-b border-gray-200 bg-white px-6 dark:border-gray-700 dark:bg-gray-800">
      <div className="flex items-center gap-4">
        <h1 className="text-lg font-semibold text-gray-900 dark:text-white">
          Fleet Operations
        </h1>
      </div>

      <div className="flex items-center gap-4">
        {/* Alert Bell */}
        <button
          className="relative rounded-lg p-2 text-gray-500 hover:bg-gray-100 dark:text-gray-400 dark:hover:bg-gray-700"
          aria-label="View alerts"
        >
          <BellIcon className="h-5 w-5" />
          {unreadCount > 0 && (
            <span className="absolute -right-1 -top-1 flex h-5 w-5 items-center justify-center rounded-full bg-red-500 text-xs font-medium text-white">
              {unreadCount > 99 ? '99+' : unreadCount}
            </span>
          )}
        </button>

        {/* Theme Toggle */}
        <button
          onClick={toggle}
          className="rounded-lg p-2 text-gray-500 hover:bg-gray-100 dark:text-gray-400 dark:hover:bg-gray-700"
          aria-label="Toggle theme"
        >
          {isDark ? (
            <SunIcon className="h-5 w-5" />
          ) : (
            <MoonIcon className="h-5 w-5" />
          )}
        </button>

        {/* User Menu */}
        <div className="flex items-center gap-2">
          <div className="h-8 w-8 rounded-full bg-primary-600 flex items-center justify-center">
            <span className="text-sm font-medium text-white">
              {user?.name?.[0]?.toUpperCase() || 'U'}
            </span>
          </div>
          <span className="text-sm font-medium text-gray-700 dark:text-gray-300">
            {user?.name || 'User'}
          </span>
        </div>
      </div>
    </header>
  );
}

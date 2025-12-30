import { NavLink } from 'react-router-dom';
import {
  HomeIcon,
  ServerStackIcon,
  CpuChipIcon,
  BellAlertIcon,
  ChatBubbleLeftRightIcon,
  ChartBarIcon,
  Cog6ToothIcon,
} from '@heroicons/react/24/outline';
import clsx from 'clsx';

const navigation = [
  { name: 'Dashboard', href: '/', icon: HomeIcon },
  { name: 'Clusters', href: '/clusters', icon: ServerStackIcon },
  { name: 'GPU Monitoring', href: '/gpu', icon: CpuChipIcon },
  { name: 'Alerts', href: '/alerts', icon: BellAlertIcon },
  { name: 'AI Chat', href: '/chat', icon: ChatBubbleLeftRightIcon },
  { name: 'Observability', href: '/observability', icon: ChartBarIcon },
];

export function Sidebar() {
  return (
    <aside className="fixed inset-y-0 left-0 w-64 bg-gray-900 dark:bg-gray-950">
      <div className="flex h-16 items-center px-6">
        <span className="text-xl font-bold text-white">AIOps NextGen</span>
      </div>

      <nav className="mt-6 px-3">
        <ul className="space-y-1">
          {navigation.map((item) => (
            <li key={item.name}>
              <NavLink
                to={item.href}
                className={({ isActive }) =>
                  clsx(
                    'flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors',
                    isActive
                      ? 'bg-primary-600 text-white'
                      : 'text-gray-300 hover:bg-gray-800 hover:text-white'
                  )
                }
              >
                <item.icon className="h-5 w-5" />
                {item.name}
              </NavLink>
            </li>
          ))}
        </ul>
      </nav>

      <div className="absolute bottom-0 left-0 right-0 p-3">
        <NavLink
          to="/settings"
          className={({ isActive }) =>
            clsx(
              'flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors',
              isActive
                ? 'bg-primary-600 text-white'
                : 'text-gray-300 hover:bg-gray-800 hover:text-white'
            )
          }
        >
          <Cog6ToothIcon className="h-5 w-5" />
          Settings
        </NavLink>
      </div>
    </aside>
  );
}

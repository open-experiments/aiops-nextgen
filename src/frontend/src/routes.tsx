import { RouteObject } from 'react-router-dom';
import { MainLayout } from './components/layout/MainLayout';
import { Dashboard } from './pages/Dashboard/Dashboard';
import { Clusters } from './pages/Clusters/Clusters';
import { GPUMonitoring } from './pages/GPU/GPU';
import { Chat } from './pages/Chat/Chat';
import { Alerts } from './pages/Alerts/Alerts';
import { Observability } from './pages/Observability/Observability';

export const routes: RouteObject[] = [
  {
    path: '/',
    element: <MainLayout />,
    children: [
      {
        index: true,
        element: <Dashboard />,
      },
      {
        path: 'clusters',
        element: <Clusters />,
      },
      {
        path: 'clusters/:clusterId',
        element: <Clusters />, // TODO: Cluster detail page
      },
      {
        path: 'gpu',
        element: <GPUMonitoring />,
      },
      {
        path: 'alerts',
        element: <Alerts />,
      },
      {
        path: 'chat',
        element: <Chat />,
      },
      {
        path: 'observability',
        element: <Observability />,
      },
    ],
  },
];

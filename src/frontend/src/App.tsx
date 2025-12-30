import { useRoutes } from 'react-router-dom';
import { routes } from './routes';
import { useWebSocket } from './hooks/useWebSocket';
import { useAlertStore } from './store/alertStore';

function App() {
  const element = useRoutes(routes);
  const { addAlert, updateAlert } = useAlertStore();

  // WebSocket for real-time alerts
  useWebSocket({
    eventTypes: ['ALERT_FIRED', 'ALERT_RESOLVED'],
    onMessage: (data) => {
      if (data.event_type === 'ALERT_FIRED' && data.payload) {
        addAlert(data.payload as Parameters<typeof addAlert>[0]);
      } else if (data.event_type === 'ALERT_RESOLVED' && data.payload) {
        updateAlert(data.payload as Parameters<typeof updateAlert>[0]);
      }
    },
  });

  return element;
}

export default App;

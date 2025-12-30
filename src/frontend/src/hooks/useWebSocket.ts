import { useEffect, useCallback, useRef, useState } from 'react';
import ReconnectingWebSocket from 'reconnecting-websocket';
import { useAuthStore } from '../store/authStore';

export type EventType =
  | 'CLUSTER_STATUS_CHANGED'
  | 'ALERT_FIRED'
  | 'ALERT_RESOLVED'
  | 'GPU_UPDATE'
  | 'ANOMALY_DETECTED';

interface WebSocketMessage {
  type: string;
  event_type?: EventType;
  payload?: unknown;
  subscription_id?: string;
}

interface UseWebSocketOptions {
  onMessage?: (event: WebSocketMessage) => void;
  onConnect?: () => void;
  onDisconnect?: () => void;
  eventTypes?: EventType[];
  clusterFilter?: string[];
  autoConnect?: boolean;
}

interface UseWebSocketReturn {
  send: (message: object) => void;
  subscribe: (eventTypes: EventType[], clusterFilter?: string[]) => void;
  unsubscribe: (subscriptionId: string) => void;
  isConnected: boolean;
}

export function useWebSocket(options: UseWebSocketOptions = {}): UseWebSocketReturn {
  const wsRef = useRef<ReconnectingWebSocket | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const token = useAuthStore((state) => state.token);

  const {
    onMessage,
    onConnect,
    onDisconnect,
    eventTypes,
    clusterFilter,
    autoConnect = true,
  } = options;

  useEffect(() => {
    if (!autoConnect) return;

    const wsUrl = import.meta.env.VITE_WS_URL || 'ws://localhost:8080';
    const ws = new ReconnectingWebSocket(`${wsUrl}/ws`);

    ws.onopen = () => {
      setIsConnected(true);

      // Authenticate
      if (token) {
        ws.send(JSON.stringify({ type: 'auth', token }));
      }

      // Subscribe to events if specified
      if (eventTypes?.length) {
        ws.send(
          JSON.stringify({
            type: 'subscribe',
            subscription: {
              event_types: eventTypes,
              cluster_filter: clusterFilter || [],
            },
          })
        );
      }

      onConnect?.();
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data) as WebSocketMessage;
        onMessage?.(data);
      } catch (e) {
        console.error('Failed to parse WebSocket message:', e);
      }
    };

    ws.onclose = () => {
      setIsConnected(false);
      onDisconnect?.();
    };

    ws.onerror = (error) => {
      console.error('WebSocket error:', error);
    };

    wsRef.current = ws;

    return () => {
      ws.close();
    };
  }, [token, autoConnect, JSON.stringify(eventTypes), JSON.stringify(clusterFilter)]);

  const send = useCallback((message: object) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(message));
    }
  }, []);

  const subscribe = useCallback(
    (types: EventType[], clusters?: string[]) => {
      send({
        type: 'subscribe',
        subscription: {
          event_types: types,
          cluster_filter: clusters || [],
        },
      });
    },
    [send]
  );

  const unsubscribe = useCallback(
    (subscriptionId: string) => {
      send({
        type: 'unsubscribe',
        subscription_id: subscriptionId,
      });
    },
    [send]
  );

  return { send, subscribe, unsubscribe, isConnected };
}

import { create } from 'zustand';
import type { Alert } from '../types/alerts';
import { alertService } from '../services/alertService';

interface AlertState {
  alerts: Alert[];
  loading: boolean;
  error: string | null;
  unreadCount: number;
  fetchAlerts: () => Promise<void>;
  addAlert: (alert: Alert) => void;
  updateAlert: (alert: Alert) => void;
  removeAlert: (id: string) => void;
  markAsRead: (id: string) => void;
}

export const useAlertStore = create<AlertState>((set, get) => ({
  alerts: [],
  loading: false,
  error: null,
  unreadCount: 0,

  fetchAlerts: async () => {
    set({ loading: true, error: null });
    try {
      const alerts = await alertService.list({ state: 'FIRING' });
      set({
        alerts,
        loading: false,
        unreadCount: alerts.filter((a) => a.state === 'FIRING').length,
      });
    } catch (error) {
      set({ error: (error as Error).message, loading: false });
    }
  },

  addAlert: (alert: Alert) => {
    set((state) => {
      const exists = state.alerts.some((a) => a.id === alert.id);
      if (exists) return state;
      return {
        alerts: [alert, ...state.alerts],
        unreadCount: state.unreadCount + 1,
      };
    });
  },

  updateAlert: (alert: Alert) => {
    set((state) => ({
      alerts: state.alerts.map((a) => (a.id === alert.id ? alert : a)),
    }));
  },

  removeAlert: (id: string) => {
    set((state) => ({
      alerts: state.alerts.filter((a) => a.id !== id),
    }));
  },

  markAsRead: (id: string) => {
    const alert = get().alerts.find((a) => a.id === id);
    if (alert && alert.state === 'FIRING') {
      set((state) => ({ unreadCount: Math.max(0, state.unreadCount - 1) }));
    }
  },
}));

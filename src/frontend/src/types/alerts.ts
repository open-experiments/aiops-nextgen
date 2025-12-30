export type AlertSeverity = 'CRITICAL' | 'WARNING' | 'INFO';
export type AlertState = 'FIRING' | 'RESOLVED' | 'PENDING';

export interface AlertLabels {
  alertname: string;
  severity: string;
  namespace?: string;
  pod?: string;
  node?: string;
  [key: string]: string | undefined;
}

export interface Alert {
  id: string;
  cluster_id: string;
  cluster_name: string;
  fingerprint: string;
  state: AlertState;
  severity: AlertSeverity;
  name: string;
  message: string;
  labels: AlertLabels;
  annotations: Record<string, string>;
  starts_at: string;
  ends_at: string | null;
  generator_url: string | null;
}

export interface AlertSummary {
  total: number;
  by_severity: Record<AlertSeverity, number>;
  by_state: Record<AlertState, number>;
  by_cluster: Record<string, number>;
}

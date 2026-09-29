export interface Alert {
  id: number; alert_uid: string; src_ip: string; dst_ip: string; attack_type: string;
  risk_score: number; confidence: number; severity: string; status: string; assignee: string;
  signals: Record<string, number>; explanation: string;
  top_features: { feature: string; contribution: number }[];
  threat_intel: Record<string, unknown>; flow_ref: number | null;
  created_at: string; updated_at: string;
}
export interface Flow {
  id: number; ts: string; src_ip: string; dst_ip: string; src_port: number; dst_port: number;
  protocol: string; prediction: string; risk_score: number; severity: string; source: string;
}
export type Mode = 'dataset' | 'live' | 'demo';

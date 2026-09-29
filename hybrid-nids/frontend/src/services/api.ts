const BASE = '/api';

async function req(path: string, init?: RequestInit) {
  const r = await fetch(BASE + path, { headers: { 'Content-Type': 'application/json' }, ...init });
  if (!r.ok) throw new Error(`${r.status} ${await r.text()}`);
  return r.json();
}

export const api = {
  health: () => req('/health'),
  system: () => req('/system/status'),
  alerts: (p: Record<string, string | number> = {}) => {
    const q = new URLSearchParams(Object.entries(p).map(([k, v]) => [k, String(v)]));
    return req('/alerts?' + q.toString());
  },
  alert: (uid: string) => req(`/alerts/${uid}`),
  patchAlert: (uid: string, body: object) => req(`/alerts/${uid}`, { method: 'PATCH', body: JSON.stringify(body) }),
  traffic: (p: Record<string, string | number> = {}) => {
    const q = new URLSearchParams(Object.entries(p).map(([k, v]) => [k, String(v)]));
    return req('/traffic?' + q.toString());
  },
  trafficSummary: () => req('/traffic/summary'),
  trafficByDay: (days = 14) => req(`/traffic/by-day?days=${days}`),
  predict: (body: object) => req('/predict', { method: 'POST', body: JSON.stringify(body) }),
  models: () => req('/models'),
  performance: () => req('/models/performance'),
  drift: () => req('/drift'),
  driftFeatures: () => req('/drift/features'),
  driftCompute: (body: object) => req('/drift/compute', { method: 'POST', body: JSON.stringify(body) }),
  driftDist: (feature: string) => req('/drift/distributions?feature=' + encodeURIComponent(feature)),
  intel: (ip: string) => req(`/threat-intel/${ip}`),
  reports: (kind = 'summary', date?: string) => req(`/reports?kind=${kind}${date ? `&date=${date}` : ''}`),
  proposeThreshold: (body: object) => req('/system/threshold-proposal', { method: 'POST', body: JSON.stringify(body) }),
};

export function wsUrl(): string {
  const proto = location.protocol === 'https:' ? 'wss' : 'ws';
  // In dev, vite proxies /api but not ws; connect directly to backend.
  if (location.port === '5173') return 'ws://localhost:8000/ws/events';
  return `${proto}://${location.host}/ws/events`;
}

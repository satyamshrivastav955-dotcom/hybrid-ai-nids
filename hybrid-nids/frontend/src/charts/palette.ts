/** Single shared palette: severity + chart series. Light enterprise theme. */
export const SEV: Record<string, string> = {
  CRITICAL: '#c93a3a',
  HIGH: '#d97a1f',
  MEDIUM: '#b7950b',
  LOW: '#2e7d4f',
};

export const SERIES = ['#2456a6', '#c93a3a', '#2e7d4f', '#d97a1f', '#6b4fa0', '#0e7c7b', '#b7950b', '#5b6575'];

export const MODELS: Record<string, string> = {
  random_forest: '#2456a6',
  autoencoder: '#d97a1f',
  isolation_forest: '#6b4fa0',
  lstm: '#0e7c7b',
  ensemble: '#1a2332',
};

export const GRID = '#e3e6eb';
export const TICK = { fontSize: 11, fill: '#5b6575' };

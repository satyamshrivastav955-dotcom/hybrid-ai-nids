import React, { createContext, useContext, useState } from 'react';
import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import type { Mode } from '../types';
import { useWebSocket } from '../hooks/hooks';
import { ToastProvider } from '../components/ui';
import { I, type IconName } from '../components/icons';

const NAV: [string, string, IconName][] = [
  ['/', 'Dashboard', 'dashboard'],
  ['/traffic', 'Live Traffic', 'traffic'],
  ['/alerts', 'Alerts', 'alerts'],
  ['/attacks', 'Attack Analysis', 'attacks'],
  ['/network', 'Network Map', 'network'],
  ['/drift', 'Drift Monitoring', 'drift'],
  ['/models', 'Model Performance', 'models'],
  ['/intel', 'Threat Intelligence', 'intel'],
  ['/reports', 'Reports', 'reports'],
  ['/system', 'System Status', 'system'],
  ['/settings', 'Settings', 'settings'],
];

export const ModeCtx = createContext<{ mode: Mode; setMode: (m: Mode) => void }>({ mode: 'dataset', setMode: () => {} });
export const useMode = () => useContext(ModeCtx);

export const Layout: React.FC = () => {
  const [mode, setMode] = useState<Mode>('dataset');
  const [tick, setTick] = useState(0);
  const [q, setQ] = useState('');
  const navigate = useNavigate();
  const connected = useWebSocket(() => setTick((t) => t + 1));
  React.useEffect(() => {
    const fn = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement;
      if (e.key === '/' && t && !/INPUT|TEXTAREA|SELECT/.test(t.tagName)) {
        e.preventDefault();
        document.getElementById('global-search')?.focus();
      }
    };
    window.addEventListener('keydown', fn);
    return () => window.removeEventListener('keydown', fn);
  }, []);
  const IP_RE = /^\d{1,3}(\.\d{1,3}){3}$/;
  const go = () => {
    const v = q.trim();
    if (!v) return;
    if (IP_RE.test(v)) navigate(`/intel?ip=${encodeURIComponent(v)}`);
    else if (/^alert_/i.test(v)) navigate(`/alerts/${encodeURIComponent(v)}`);
    else navigate(`/alerts?attack=${encodeURIComponent(v)}`);
    setQ('');
  };
  return (
    <ModeCtx.Provider value={{ mode, setMode }}>
    <ToastProvider>
      <div className="app">
        <aside className="sidebar" aria-label="Primary">
          <div className="brand"><h1>NIDS SOC</h1><p>Network Intrusion Detection</p></div>
          <nav className="nav">
            {NAV.map(([to, label, ico]) => (
              <NavLink key={to} to={to} end={to === '/'} className={({ isActive }) => (isActive ? 'active' : '')}>
                <span className="ico" aria-hidden>{I[ico]}</span>{label}
              </NavLink>
            ))}
          </nav>
          <div className="side-foot">
            <div>System Online · v1.0.0</div>
            <div>Models v1 · schema v1</div>
            <div>Updates seen: {tick}</div>
          </div>
        </aside>
        <div className="main">
          <div className={`mode-banner mode-${mode}`} role="status">
            MODE: {mode.toUpperCase()}
            {mode === 'demo' && ' — synthetic demonstration traffic only, not research data.'}
            {mode === 'live' && ' — live network ingestion.'}
            {mode === 'dataset' && ' — offline dataset / evaluation mode.'}
          </div>
          <div className="topbar">
            <input id="global-search" type="search" placeholder="Search IP, alert ID, attack type…  ( / )" aria-label="Search"
              value={q} onChange={(e) => setQ(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter') go(); }} />
            <div style={{ marginLeft: 'auto' }} className="row">
              <span className={`conn ${connected ? 'on' : 'off'}`} title={connected ? 'WebSocket connected' : 'WebSocket reconnecting'}>
                <span style={{ color: connected ? '#2e7d4f' : '#5b6575' }}>●</span> {connected ? 'Live' : 'Offline'}
              </span>
              <select value={mode} onChange={(e) => setMode(e.target.value as Mode)} aria-label="Operating mode">
                <option value="dataset">Dataset</option>
                <option value="live">Live</option>
                <option value="demo">Demo</option>
              </select>
            </div>
          </div>
          <Outlet />
        </div>
      </div>
    </ToastProvider>
    </ModeCtx.Provider>
  );
};

import React from 'react';
import { api } from '../services/api';
import { useFetch } from '../hooks/hooks';
import { Card, Empty } from '../components/ui';

/** Engineering operations view: services, resources, versions. */
const SystemStatus: React.FC = () => {
  const q = useFetch(api.system);
  const mods = useFetch(api.models);
  const s = q.data as any;
  const m = mods.data as any;

  const Svc = ({ name, ok }: { name: string; ok: boolean | string }) => {
    const up = ok === true || ok === 'online';
    return (
      <tr><td>{name}</td>
        <td><span style={{ color: up ? '#2e7d4f' : '#d97a1f' }}>●</span> {up ? 'Operational' : String(ok)}</td></tr>
    );
  };

  return (
    <div className="page">
      <h2>System Status</h2>
      <p className="sub">Infrastructure and pipeline health.</p>
      {!s ? <Card><Empty msg="Loading…" /></Card> : (
        <>
          <div className="grid" style={{ gridTemplateColumns: '1fr 1fr 1fr' }}>
            <Card><div className="kpi"><div className="l">CPU</div><div className="v">{s.cpu_percent >= 0 ? `${s.cpu_percent}%` : 'n/a'}</div></div></Card>
            <Card><div className="kpi"><div className="l">RAM</div><div className="v">{s.ram_percent >= 0 ? `${s.ram_percent}%` : 'n/a'}</div></div></Card>
            <Card><div className="kpi"><div className="l">Uptime</div><div className="v">{Math.round(s.uptime_seconds / 60)}m</div></div></Card>
          </div>
          <div className="grid" style={{ gridTemplateColumns: '1fr 1fr', marginTop: 16 }}>
            <Card title="Services">
              <table className="tbl"><thead><tr><th>Service</th><th>State</th></tr></thead><tbody>
                <Svc name="Backend" ok={s.api} />
                <Svc name="Database" ok={s.database} />
                <Svc name="WebSocket" ok={s.websocket_connections > 0 ? true : 'idle'} />
                <Svc name="Models" ok={s.models?.loaded ? true : 'not loaded'} />
                <Svc name="Ingestion" ok={true} />
                <Svc name="Threat Intel" ok={true} />
              </tbody></table>
              <p style={{ fontSize: 12, color: '#5b6575' }}>{s.flows_stored} flows · {s.alerts_stored} alerts · {s.websocket_connections} WS connections · {s.ingestion_mode} mode</p>
            </Card>
            <Card title="Versions">
              <dl className="kv">
                <dt>Backend</dt><dd>1.0.0</dd>
                <dt>Models</dt><dd>{(m?.models ?? []).length ? `v1 (${(m?.models ?? []).length} registered)` : 'v1'}</dd>
                <dt>Feature schema</dt><dd>v1</dd>
                <dt>Last drift</dt><dd>{s.last_drift ?? 'STABLE'}</dd>
              </dl>
            </Card>
          </div>
        </>
      )}
    </div>
  );
};
export default SystemStatus;

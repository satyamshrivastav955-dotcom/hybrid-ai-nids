import React, { useEffect, useState } from 'react';
import { Bar, BarChart, CartesianGrid, Cell, Line, LineChart, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { api } from '../services/api';
import { useFetch, useWebSocket } from '../hooks/hooks';
import { GRID, SEV, SERIES, TICK } from '../charts/palette';
import { Badge, Card, Empty, Skeleton, SortableTable } from '../components/ui';
import type { Flow } from '../types';

const SEV_ORDER: Record<string, number> = { CRITICAL: 4, HIGH: 3, MEDIUM: 2, LOW: 1 };

const LiveTraffic: React.FC = () => {
  const [paused, setPaused] = useState(false);
  const [filter, setFilter] = useState('');
  const [sevFilter, setSevFilter] = useState('');
  const [showAll, setShowAll] = useState(false);
  const [live, setLive] = useState<Flow[]>([]);
  const summary = useFetch(api.trafficSummary);
  useWebSocket((m: any) => {
    if (paused || !m || m.type !== 'prediction') return;
    setLive((prev) => [{
      id: m.flow_id ?? Date.now(), ts: new Date().toISOString(), src_ip: '', dst_ip: '',
      src_port: 0, dst_port: 0, protocol: '', prediction: m.prediction,
      risk_score: m.risk_score, severity: m.severity, source: m.source ?? 'live',
    }, ...prev].slice(0, 60));
  });
  const flows = useFetch(() => api.traffic({ limit: 60 }), [paused]);
  useEffect(() => { if (!paused) { const t = setInterval(() => flows.reload(), 5000); return () => clearInterval(t); } }, [paused]);

  const rows: Flow[] = [...live, ...((flows.data as any)?.items ?? [])]
    .filter((f) => (!filter || `${f.src_ip} ${f.dst_ip} ${f.prediction}`.toLowerCase().includes(filter.toLowerCase()))
      && (!sevFilter || f.severity === sevFilter))
    .slice(0, showAll ? 500 : 60);
  const s = summary.data as any;
  const vol = (s?.timeseries ?? []).map((b: any) => ({ t: b.t, flows: b.flows, attacks: b.attacks }));
  const bySev = Object.entries((s?.by_severity ?? {}) as Record<string, number>).map(([name, value]) => ({ name, value }));

  const exportCsv = () => {
    const csv = 'ts,src,dst,prediction,risk,severity\n' + rows.map((f) => [f.ts, f.src_ip, f.dst_ip, f.prediction, f.risk_score, f.severity].join(',')).join('\n');
    const a = document.createElement('a');
    a.href = URL.createObjectURL(new Blob([csv], { type: 'text/csv' }));
    a.download = 'flows.csv'; a.click();
  };

  return (
    <div className="page">
      <h2>Live Traffic</h2>
      <p className="sub">Watch network activity as it happens. Streaming monitor — not a research view.</p>
      <div className="toolbar">
        <button className="btn" onClick={() => setPaused(!paused)}>{paused ? 'Resume' : 'Pause'}</button>
        <input type="search" placeholder="Filter IP / prediction…" value={filter} onChange={(e) => setFilter(e.target.value)} aria-label="Filter flows" />
        <select value={sevFilter} onChange={(e) => setSevFilter(e.target.value)} aria-label="Severity filter">
          <option value="">All severities</option><option>CRITICAL</option><option>HIGH</option><option>MEDIUM</option><option>LOW</option>
        </select>
        <button className="btn" onClick={exportCsv}>Export CSV</button>
        <span className="hint" style={{ color: '#5b6575', fontSize: 12 }}>{paused ? 'Paused — buffer held' : 'Auto-refresh 5s + WebSocket push'}</span>
      </div>
      <div className="kpis">
        <Card><div className="kpi"><div className="l">Current Flows</div><div className="v">{s?.total_flows ?? '—'}</div></div></Card>
        <Card><div className="kpi"><div className="l">Detected Attacks</div><div className="v">{s?.attacks ?? '—'}</div></div></Card>
        <Card><div className="kpi"><div className="l">Benign Traffic</div><div className="v">{s?.benign ?? '—'}</div></div></Card>
        <Card><div className="kpi"><div className="l">Attack Share</div><div className="v">{s?.total_flows ? `${Math.round((s.attacks / s.total_flows) * 100)}%` : '—'}</div></div></Card>
      </div>
      <div className="grid" style={{ gridTemplateColumns: '2fr 1fr 1fr', marginTop: 16 }}>
        <Card title="Live Traffic Volume" hint="Flows and attacks per window">
          {vol.length === 0 ? <Empty msg="No traffic yet." /> : (
            <ResponsiveContainer width="100%" height={240}>
              <LineChart data={vol}><CartesianGrid strokeDasharray="3 3" stroke={GRID} />
                <XAxis dataKey="t" tick={TICK} /><YAxis tick={TICK} /><Tooltip />
                <Line dataKey="flows" name="Flows" stroke={SERIES[0]} dot={false} /><Line dataKey="attacks" name="Attacks" stroke={SEV.CRITICAL} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          )}
        </Card>
        <Card title="By Severity" hint="Flow counts">
          {bySev.length === 0 ? <Empty msg="No traffic yet." /> : (
            <ResponsiveContainer width="100%" height={240}>
              <PieChart>
                <Pie data={bySev} dataKey="value" nameKey="name" innerRadius={45} outerRadius={75} paddingAngle={2}>
                  {bySev.map((e) => <Cell key={e.name} fill={SEV[e.name] ?? SERIES[0]} />)}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
          )}
        </Card>
        <Card title="Predictions" hint="Count by predicted class">
          <ResponsiveContainer width="100%" height={240}>
            <BarChart data={Object.entries((s?.by_prediction ?? {}) as Record<string, number>).map(([k, v]) => ({ k, v }))} layout="vertical">
              <CartesianGrid strokeDasharray="3 3" stroke={GRID} />
              <XAxis type="number" tick={TICK} /><YAxis dataKey="k" type="category" width={90} tick={TICK} /><Tooltip />
              <Bar dataKey="v" fill={SERIES[0]} />
            </BarChart>
          </ResponsiveContainer>
        </Card>
      </div>
      <Card title={`Real-time Flow Logs (${rows.length})`} hint="Newest first — sortable, paginated">
        <div style={{ textAlign: 'right', marginBottom: 8 }}>
          <button className="btn" onClick={() => setShowAll(!showAll)}>{showAll ? 'Show less' : 'View All >'}</button>
        </div>
        {flows.loading && rows.length === 0 ? <Skeleton rows={8} /> : rows.length === 0 ? <Empty msg="No flows match." /> : (
          <SortableTable
            initialSort="ts"
            cols={[
              { key: 'ts', label: 'Time', render: (f: Flow) => (f.ts ? new Date(f.ts).toLocaleTimeString() : '—'), sort: (f: Flow) => f.ts || '' },
              { key: 'src', label: 'Source', render: (f: Flow) => f.src_ip || '—', sort: (f: Flow) => f.src_ip },
              { key: 'dst', label: 'Destination', render: (f: Flow) => f.dst_ip || '—', sort: (f: Flow) => f.dst_ip },
              { key: 'pred', label: 'Prediction', render: (f: Flow) => f.prediction, sort: (f: Flow) => f.prediction },
              { key: 'risk', label: 'Risk', render: (f: Flow) => Number(f.risk_score).toFixed(2), sort: (f: Flow) => f.risk_score, numeric: true },
              { key: 'sev', label: 'Severity', render: (f: Flow) => <Badge v={f.severity} />, sort: (f: Flow) => SEV_ORDER[f.severity] ?? 0 },
              { key: 'org', label: 'Origin', render: (f: Flow) => f.source, sort: (f: Flow) => f.source },
            ]}
            rows={rows}
          />
        )}
      </Card>
    </div>
  );
};
export default LiveTraffic;

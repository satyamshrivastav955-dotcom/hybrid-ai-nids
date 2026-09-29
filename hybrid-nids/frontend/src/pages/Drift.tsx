import React, { useState } from 'react';
import { Bar, BarChart, CartesianGrid, Cell, Legend, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { api } from '../services/api';
import { useFetch } from '../hooks/hooks';
import { Badge, Card, Empty, driftLabel, fmt, Skeleton } from '../components/ui';
import { GRID, SERIES, TICK } from '../charts/palette';

/** Overlaid reference vs current histogram: the SHAPE of the shift. */
const DistOverlay: React.FC<{ feature: string }> = ({ feature }) => {
  const q = useFetch(() => api.driftDist(feature), [feature]);
  const d = q.data as any;
  if (q.loading) return <div style={{ marginTop: 12 }}><Skeleton rows={3} /></div>;
  if (!d) return null;
  const rows = (d.centers as number[]).map((c: number, i: number) => ({ c, ref: d.reference[i], cur: d.current[i] }));
  return (
    <div style={{ marginTop: 12 }}>
      <h4 style={{ margin: '8px 0 4px' }}>{d.feature}: reference (n={d.n_reference}) vs current (n={d.n_current})</h4>
      <ResponsiveContainer width="100%" height={200}>
        <BarChart data={rows} barCategoryGap="0%">
          <CartesianGrid strokeDasharray="3 3" stroke="#e3e6eb" />
          <XAxis dataKey="c" tick={{ fontSize: 10 }} />
          <YAxis tick={{ fontSize: 11 }} /><Tooltip />
          <Bar dataKey="ref" name="reference" fill={SERIES[0]} opacity={0.55} />
          <Bar dataKey="cur" name="current" fill={SERIES[1]} opacity={0.75} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
};

/** Statistics console: PSI timeline, feature heatmap, reference vs current, event history. */
const Drift: React.FC = () => {
  const events = useFetch(api.drift);
  const feats = useFetch(api.driftFeatures);
  const [sel, setSel] = useState<any | null>(null);
  const items: any[] = (events.data as any)?.items ?? [];
  const frows: any[] = (feats.data as any)?.features ?? [];

  const timeline = [...items].reverse().map((e) => ({
    d: new Date(e.ts).toLocaleDateString(undefined, { month: 'short', day: 'numeric' }),
    psi: e.aggregate_psi, status: e.status,
  }));
  const top = [...frows].sort((a, b) => b.psi - a.psi).slice(0, 5);

  const compute = async () => {
    await api.driftCompute({ reference_version: 'baseline-v1', current_window_rows: 500 });
    events.reload(); feats.reload();
  };

  return (
    <div className="page">
      <h2>Drift Monitoring</h2>
      <p className="sub">PSI-based distribution comparison. Advisory only — adaptation is an explicit audited action.</p>
      <div className="toolbar"><button className="btn primary" onClick={compute}>Compute drift on current window</button></div>
      <div className="grid" style={{ gridTemplateColumns: '3fr 2fr' }}>
        <Card title="PSI Timeline (Aggregate)" hint="Bands: Stable < 0.10 ≤ Moderate < 0.25 ≤ Severe">
          {timeline.length === 0 ? <Empty msg="No drift computations yet." /> : (
            <ResponsiveContainer width="100%" height={220}>
              <LineChart data={timeline} margin={{ top: 8 }}>
                <CartesianGrid strokeDasharray="3 3" stroke={GRID} />
                <XAxis dataKey="d" tick={TICK} /><YAxis tick={TICK} /><Tooltip />
                <Legend wrapperStyle={{ fontSize: 12 }} />
                <ReferenceLine y={0.1} stroke="#d97a1f" strokeDasharray="4 3" label={{ value: 'Moderate', fontSize: 10, fill: '#d97a1f' }} />
                <ReferenceLine y={0.25} stroke="#c93a3a" strokeDasharray="4 3" label={{ value: 'Severe', fontSize: 10, fill: '#c93a3a' }} />
                <Line dataKey="psi" name="Aggregate PSI" stroke={SERIES[0]} dot />
              </LineChart>
            </ResponsiveContainer>
          )}
        </Card>
        <Card title="Drift event details" hint="Latest computation">
          {items.length === 0 ? <Empty msg="Nothing computed." /> : (
            <dl className="kv">
              <dt>Aggregate PSI</dt><dd>{fmt(items[0].aggregate_psi)}</dd>
              <dt>Status</dt><dd><Badge v={driftLabel(items[0].status)} /></dd>
              <dt>Reference</dt><dd>{items[0].reference_version}</dd>
              <dt>Adaptation</dt><dd>{items[0].adaptation_status}</dd>
              <dt>Computed</dt><dd>{new Date(items[0].ts).toLocaleString()}</dd>
            </dl>
          )}
        </Card>
      </div>
      <Card title="Feature drift (top 5)" hint="Click a feature for interpretation and distributions">
        {top.length === 0 ? <Empty msg="Feature-level PSI unavailable." /> : (
          <table className="tbl"><thead><tr><th>Feature</th><th>PSI</th><th>Status</th></tr></thead>
            <tbody>{top.map((f) => (
              <tr key={f.feature} onClick={() => setSel(f)} style={{ cursor: 'pointer' }}>
                <td>{f.feature}</td>
                <td>{fmt(f.psi, 3)}</td>
                <td><Badge v={driftLabel(f.status)} /></td>
              </tr>))}</tbody></table>
        )}
        {sel && (
          <div style={{ marginTop: 12, fontSize: 13 }}>
            <strong>{sel.feature}</strong>: PSI {fmt(sel.psi, 3)} ({sel.status}).{' '}
            {sel.status === 'STABLE' ? 'Reference and current distributions match; no action.' :
              sel.status === 'MODERATE' ? 'Noticeable shift — monitor and consider recalibration review.' :
                'Strong shift — investigate traffic mix change before trusting thresholds.'}
          </div>
        )}
        {sel && <DistOverlay feature={sel.feature} />}
      </Card>
      <Card title="Reference vs current (top drifting features)">
        {top.length === 0 ? <Empty msg="Nothing to compare." /> : (
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={top.slice(0, 8)}><CartesianGrid strokeDasharray="3 3" stroke={GRID} />
              <XAxis dataKey="feature" tick={{ fontSize: 10 }} interval={0} angle={-18} height={64} />
              <YAxis tick={TICK} /><Tooltip />
              <Bar dataKey="psi">{top.slice(0, 8).map((f, i) => <Cell key={i} fill={f.psi >= 0.25 ? '#c93a3a' : f.psi >= 0.1 ? '#d97a1f' : '#2e7d4f'} />)}</Bar>
            </BarChart>
          </ResponsiveContainer>
        )}
      </Card>
      <Card title="Drift event history">
        {items.length === 0 ? <Empty msg="No events." /> : (
          <table className="tbl"><thead><tr><th>Time</th><th>PSI</th><th>Status</th><th>Adaptation</th></tr></thead>
            <tbody>{items.map((e) => <tr key={e.id}><td>{new Date(e.ts).toLocaleString()}</td><td>{fmt(e.aggregate_psi)}</td><td><Badge v={driftLabel(e.status)} /></td><td>{e.adaptation_status}</td></tr>)}</tbody></table>
        )}
      </Card>
    </div>
  );
};
export default Drift;

import React, { useState } from 'react';
import { Bar, BarChart, CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { api } from '../services/api';
import { useFetch } from '../hooks/hooks';
import { GRID, SERIES, TICK } from '../charts/palette';
import { Card, Empty, fmt } from '../components/ui';

/** Research/analytics view: frequency, mix, and per-class quality. Findings computed, not narrated. */
const AttackAnalysis: React.FC = () => {
  const [attack, setAttack] = useState('');
  const [range, setRange] = useState('14');
  const [model, setModel] = useState('Ensemble');
  const summary = useFetch(api.trafficSummary);
  const perf = useFetch(api.performance);
  const byDay = useFetch(() => api.trafficByDay(Number(range)), [range]);
  const s = summary.data as any;
  const std = (perf.data as any)?.standard_metrics?.metrics;
  const perClass = (perf.data as any)?.standard_metrics?.per_class ?? null;
  const days: any[] = (byDay.data as any)?.days ?? [];
  const classes: string[] = (byDay.data as any)?.classes ?? [];

  const focus = attack || 'All';
  const freqRows = days.map((d) => {
    const row: any = { day: String(d.day).slice(5) };
    for (const c of classes) {
      if (c === 'BENIGN') continue;
      if (focus !== 'All' && c !== focus) continue;
      row[c] = d[c] ?? 0;
    }
    return row;
  });
  const focusClasses = classes.filter((c) => c !== 'BENIGN' && (focus === 'All' || c === focus));
  const dist = Object.entries((s?.by_prediction ?? {}) as Record<string, number>)
    .map(([k, v]) => ({ k, v })).filter((d) => d.k !== 'BENIGN' && (!attack || d.k === attack));

  const classRows = perClass ? Object.entries(perClass)
    .filter(([k]) => !attack || k === attack)
    .map(([k, v]: [string, any]) => ({ k, ...v })) : [];
  const ens = std?.ensemble;

  return (
    <div className="page">
      <h2>Attack Analysis</h2>
      <p className="sub">Class distributions and detection quality. Findings are computed, not narrated.</p>
      <div className="toolbar">
        <label>Attack type <select value={attack} onChange={(e) => setAttack(e.target.value)}>
          <option value="">All</option>
          {Object.keys((s?.by_prediction ?? {}) as object).filter((k) => k !== 'BENIGN').map((k) => <option key={k} value={k}>{k}</option>)}
        </select></label>
        <label>Time range <select value={range} onChange={(e) => setRange(e.target.value)}>
          <option value="1">Last 24 hours</option>
          <option value="7">Last 7 days</option>
          <option value="14">Last 14 days</option>
        </select></label>
        <label>Model <select value={model} onChange={(e) => setModel(e.target.value)}>
          <option>Ensemble</option><option>Random Forest</option>
        </select></label>
      </div>
      <div className="grid" style={{ gridTemplateColumns: '3fr 2fr' }}>
        <Card title="Attack Frequency Over Time" hint="Stored flows per day by predicted class">
          {freqRows.length === 0 ? <Empty msg="No stored flow history yet." /> : (
            <ResponsiveContainer width="100%" height={240}>
              <LineChart data={freqRows}>
                <CartesianGrid strokeDasharray="3 3" stroke={GRID} />
                <XAxis dataKey="day" tick={TICK} />
                <YAxis tick={TICK} /><Tooltip /><Legend wrapperStyle={{ fontSize: 12 }} />
                {focusClasses.slice(0, 6).map((c, i) => (
                  <Line key={c} dataKey={c} stroke={SERIES[i % SERIES.length]} dot={false} strokeWidth={1.5} />
                ))}
              </LineChart>
            </ResponsiveContainer>
          )}
        </Card>
        <Card title="Attack Type Distribution" hint="Observed predictions in the database">
          {dist.length === 0 ? <Empty msg="No data yet." /> : (
            <ResponsiveContainer width="100%" height={240}>
              <BarChart data={dist}><CartesianGrid strokeDasharray="3 3" stroke={GRID} />
                <XAxis dataKey="k" tick={TICK} interval={0} angle={-20} height={60} />
                <YAxis tick={TICK} /><Tooltip /><Bar dataKey="v" fill={SERIES[0]} /></BarChart>
            </ResponsiveContainer>
          )}
        </Card>
      </div>
      <Card title={`Detection Metrics by Attack Type (${model === 'Ensemble' ? 'supervised head, RF' : 'Random Forest'})`}
        hint="Per-class quality from the standard-protocol evaluation">
        {!perClass ? <Empty msg="No evaluation run yet — metrics will appear after scripts/evaluate_all.py." /> : (
          <table className="tbl"><thead><tr><th>Attack Type</th><th>Precision</th><th>Recall</th><th>F1</th><th>Support</th></tr></thead>
            <tbody>{classRows.map((r: any) => (
              <tr key={r.k}><td>{r.k}</td><td>{fmt(r.precision)}</td><td>{fmt(r.recall)}</td><td>{fmt(r['f1-score'])}</td><td>{r.support}</td></tr>))}</tbody></table>
        )}
        {ens && model === 'Ensemble' && (
          <p style={{ fontSize: 12, color: '#5b6575' }}>Ensemble binary roll-up: precision {fmt(ens.precision)}, recall {fmt(ens.recall)}, F1 {fmt(ens.f1)}, FPR {fmt(ens.fpr)}.</p>
        )}
      </Card>
    </div>
  );
};
export default AttackAnalysis;

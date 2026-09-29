import React from 'react';
import { Link } from 'react-router-dom';
import { Area, AreaChart, CartesianGrid, Cell, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { api } from '../services/api';
import { useFetch } from '../hooks/hooks';
import { GRID, SEV, SERIES, TICK } from '../charts/palette';
import { age, Badge, Card, Empty, fmt, Skeleton, SortableTable } from '../components/ui';

const Dashboard: React.FC = () => {
  const sum = useFetch(api.trafficSummary);
  const alerts = useFetch(() => api.alerts({ limit: 8 }));
  const drift = useFetch(api.drift);

  const s = sum.data as any;
  const ts = (s?.timeseries ?? []) as { t: string; flows: number; attacks: number }[];
  const byPred = Object.entries((s?.by_prediction ?? {}) as Record<string, number>).map(([name, value]) => ({ name, value }));
  const predTotal = byPred.reduce((x, e) => x + e.value, 0);
  const driftItem = (drift.data as any)?.items?.[0];
  const latestPsi = driftItem?.aggregate_psi;
  const driftStatus = driftItem?.status === 'SEVERE' ? 'Severe' : driftItem?.status === 'MODERATE' ? 'Moderate' : driftItem ? 'Stable' : null;

  const recent: any[] = (alerts.data as any)?.items ?? [];

  return (
    <div className="page">
      <h2>Security Overview</h2>
      <p className="sub">Real-time network intrusion detection and monitoring.</p>
      {sum.error && <div className="err">API error: {sum.error}. Is the backend running?</div>}
      <div className="kpis">
        <Card><div className="kpi"><div className="l">Total Network Flows</div><div className="v">{s?.total_flows ?? '—'}</div></div></Card>
        <Card><div className="kpi"><div className="l">Detected Attacks</div><div className="v">{s?.attacks ?? '—'}</div></div></Card>
        <Card><div className="kpi"><div className="l">Critical Alerts</div><div className="v">{(s?.by_severity?.CRITICAL ?? 0)}</div></div></Card>
        <Card><div className="kpi"><div className="l">Current Drift (PSI)</div>
          <div className="v">{latestPsi ?? '—'} {driftStatus && <Badge v={driftStatus} />}</div></div></Card>
      </div>
      <div className="grid" style={{ gridTemplateColumns: '2fr 1fr', marginTop: 16 }}>
        <Card title="Network Activity & Detections" hint="Flows vs attacks over recent windows">
          {ts.length === 0 ? <Empty msg="No traffic recorded yet." /> : (
            <ResponsiveContainer width="100%" height={260}>
              <AreaChart data={ts}>
                <CartesianGrid strokeDasharray="3 3" stroke={GRID} />
                <XAxis dataKey="t" tick={TICK} />
                <YAxis tick={TICK} />
                <Tooltip />
                <Area dataKey="flows" name="Flows" fill="#dbe5f5" stroke={SERIES[0]} />
                <Area dataKey="attacks" name="Attacks" fill="#f6d9d9" stroke={SEV.CRITICAL} />
              </AreaChart>
            </ResponsiveContainer>
          )}
        </Card>
        <Card title="Attack Type Distribution" hint="Share of non-benign predictions">
          {byPred.length === 0 ? <Empty msg="No attacks observed yet." /> : (
            <div className="donut-wrap">
              <ResponsiveContainer width="100%" height={260}>
                <PieChart>
                  <Pie data={byPred} dataKey="value" nameKey="name" innerRadius={55} outerRadius={90} paddingAngle={2}>
                    {byPred.map((e, i) => <Cell key={i} fill={SERIES[i % SERIES.length]} />)}
                  </Pie>
                  <Tooltip formatter={(v: any, n: any) => [`${v} (${predTotal ? Math.round((v / predTotal) * 100) : 0}%)`, n]} />
                </PieChart>
              </ResponsiveContainer>
              <div className="donut-center"><span className="n">{predTotal}</span><span className="t">attacks</span></div>
            </div>
          )}
        </Card>
      </div>
      <div className="grid" style={{ gridTemplateColumns: '1fr', marginTop: 16 }}>
        <Card title="Recent Alerts" hint="Latest triage queue entries">
          <div style={{ textAlign: 'right', marginBottom: 8 }}><Link to="/alerts">View All &gt;</Link></div>
          {alerts.loading ? <Skeleton rows={6} /> : recent.length === 0 ? <Empty msg="No alerts." /> : (
            <SortableTable
              pageSize={8}
              initialSort="time"
              cols={[
                { key: 'time', label: 'Time', render: (a: any) => <span title={new Date(a.created_at).toLocaleString()}>{age(a.created_at).text}</span>, sort: (a: any) => a.created_at },
                { key: 'sev', label: 'Severity', render: (a: any) => <Badge v={a.severity} />, sort: (a: any) => a.risk_score },
                { key: 'src', label: 'Source IP', render: (a: any) => a.src_ip, sort: (a: any) => a.src_ip },
                { key: 'dst', label: 'Destination IP', render: (a: any) => a.dst_ip, sort: (a: any) => a.dst_ip },
                { key: 'type', label: 'Attack Type', render: (a: any) => <Link to={`/alerts/${a.alert_uid}`}>{a.attack_type}</Link>, sort: (a: any) => a.attack_type },
                { key: 'risk', label: 'Risk', render: (a: any) => fmt(a.risk_score), sort: (a: any) => a.risk_score, numeric: true },
                { key: 'st', label: 'Status', render: (a: any) => <Badge v={a.status} />, sort: (a: any) => a.status },
              ]}
              rows={recent}
            />
          )}
        </Card>
      </div>
    </div>
  );
};
export default Dashboard;

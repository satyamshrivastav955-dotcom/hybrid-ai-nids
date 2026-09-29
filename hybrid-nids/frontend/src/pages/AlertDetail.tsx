import React, { useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { Bar, BarChart, CartesianGrid, Cell, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { api } from '../services/api';
import { useFetch } from '../hooks/hooks';
import { Badge, Card, Empty, RiskBar, Skeleton, fmt, useToast } from '../components/ui';
import { GRID, MODELS, SERIES, TICK } from '../charts/palette';

const AlertDetail: React.FC = () => {
  const { uid } = useParams();
  const [note, setNote] = useState('');
  const toast = useToast();
  const q = useFetch(() => api.alert(uid!), [uid]);
  const d = q.data as any;
  const a = d?.alert;
  const peers = useFetch(() => api.alerts({ limit: 100 }), []);

  const act = async (status: string) => {
    try {
      await api.patchAlert(uid!, { status, note, actor: 'analyst' });
      toast(`Alert → ${status}`, 'ok');
    } catch (e) { toast(`Action failed: ${e}`, 'err'); }
    setNote(''); q.reload();
  };

  if (q.loading) return <div className="page"><Skeleton rows={8} /></div>;
  if (!a) return <div className="page"><div className="err">Alert not found.</div></div>;

  const signals = Object.entries((a.signals ?? {}) as Record<string, number>).map(([k, v]) => ({ k, v }));
  const intel = (a.threat_intel ?? {}) as Record<string, any>;
  const related = ((peers.data as any)?.items ?? []).filter((x: any) =>
    x.alert_uid !== a.alert_uid && (x.src_ip === a.src_ip || x.dst_ip === a.dst_ip)).slice(0, 8);

  return (
    <div className="page">
      <h2>Alert {a.alert_uid.slice(0, 18)}…</h2>
      <p className="sub">Investigation workspace — why did the system raise this alert?</p>
      <div className="toolbar">
        <Badge v={a.severity} /><Badge v={a.status} />
        <span style={{ flex: 1 }} />
        <button className="btn" onClick={() => act('investigating')}>Investigate</button>
        <button className="btn" onClick={() => act('acknowledged')}>Acknowledge</button>
        <button className="btn" onClick={() => act('resolved')}>Resolve</button>
        <button className="btn" onClick={() => act('dismissed')}>Dismiss</button>
      </div>
      <div className="grid" style={{ gridTemplateColumns: '1fr 1fr' }}>
        <Card title="Endpoint & Flow Metadata">
          <dl className="kv">
            <dt>Source IP</dt><dd>{a.src_ip}</dd>
            <dt>Destination IP</dt><dd>{a.dst_ip}</dd>
            <dt>Attack type</dt><dd>{a.attack_type}</dd>
            <dt>Created</dt><dd>{new Date(a.created_at).toLocaleString()}</dd>
            <dt>Assignee</dt><dd>{a.assignee || '—'}</dd>
            <dt>Reputation</dt><dd>{String(intel.reputation ?? '—')} ({String(intel.provider ?? '')})</dd>
          </dl>
        </Card>
        <Card title="Model Analysis" hint="Per-model evidence (0–1) — dashed line marks the 0.5 operating point">
          <ResponsiveContainer width="100%" height={180}>
            <BarChart data={signals} layout="vertical">
              <CartesianGrid strokeDasharray="3 3" stroke={GRID} />
              <XAxis type="number" domain={[0, 1]} tick={TICK} />
              <YAxis dataKey="k" type="category" width={110} tick={TICK} />
              <Tooltip formatter={(v: any) => [Number(v).toFixed(3), 'score']} />
              <ReferenceLine x={0.5} stroke="#5b6575" strokeDasharray="4 3" label={{ value: '0.5', fontSize: 10, fill: '#5b6575' }} />
              <Bar dataKey="v">
                {signals.map((s) => <Cell key={s.k} fill={s.v >= 0.5 ? (MODELS[s.k] ?? SERIES[0]) : '#c9cfd8'} />)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
          <p style={{ fontSize: 12.5 }}>{a.explanation}</p>
          <div className="row"><span style={{ fontSize: 12 }}>Risk {fmt(a.risk_score)}</span><div style={{ flex: 1 }}><RiskBar v={a.risk_score} /></div></div>
        </Card>
      </div>
      <div className="grid" style={{ gridTemplateColumns: '1fr 1fr', marginTop: 16 }}>
        <Card title="Top Contributing Features" hint="Computed attribution, not narrative">
          {(a.top_features ?? []).length === 0 ? <Empty msg="No attribution available." /> : (
            <table className="tbl"><thead><tr><th>Feature</th><th>Contribution</th></tr></thead>
              <tbody>{a.top_features.map((f: any) => <tr key={f.feature}><td>{f.feature}</td><td>{fmt(f.contribution, 4)}</td></tr>)}</tbody></table>
          )}
        </Card>
        <Card title="Threat Intelligence" hint="Enrichment signal, not ground truth">
          <dl className="kv">
            <dt>Provider</dt><dd>{String(intel.provider ?? '—')}</dd>
            <dt>ASN / Org</dt><dd>{String(intel.asn ?? '—')} / {String(intel.organization ?? '—')}</dd>
            <dt>Country</dt><dd>{String(intel.country ?? '—')}</dd>
            <dt>Confidence</dt><dd>{intel.confidence ?? '—'}</dd>
          </dl>
        </Card>
      </div>
      <div className="grid" style={{ gridTemplateColumns: '1fr 1fr', marginTop: 16 }}>
        <Card title={`Related alerts (${related.length})`} hint="Same source or destination IP">
          {related.length === 0 ? <Empty msg="No other alerts share these endpoints." /> : (
            <table className="tbl"><thead><tr><th>Type</th><th>Peer</th><th>Risk</th><th>Status</th></tr></thead>
              <tbody>{related.map((x: any) => (
                <tr key={x.alert_uid}><td><Link to={`/alerts/${x.alert_uid}`}>{x.attack_type}</Link></td>
                  <td>{x.src_ip === a.src_ip ? x.dst_ip : x.src_ip}</td>
                  <td>{fmt(x.risk_score)}</td><td><Badge v={x.status} /></td></tr>))}</tbody></table>
          )}
        </Card>
        <Card title="Alert Timeline" >
          {(d.history ?? []).length === 0 ? <Empty msg="No transitions yet." /> : (
            <table className="tbl"><thead><tr><th>Time</th><th>Actor</th><th>Transition</th><th>Note</th></tr></thead>
              <tbody>{d.history.map((h: any, i: number) => <tr key={i}><td>{new Date(h.ts).toLocaleString()}</td><td>{h.actor}</td><td>{h.from || '—'} → {h.to}</td><td>{h.note}</td></tr>)}</tbody></table>
          )}
          <div className="row" style={{ marginTop: 12 }}>
            <input type="text" placeholder="Add analyst note…" value={note} onChange={(e) => setNote(e.target.value)} style={{ flex: 1 }} aria-label="Analyst note" />
          </div>
        </Card>
      </div>
    </div>
  );
};
export default AlertDetail;

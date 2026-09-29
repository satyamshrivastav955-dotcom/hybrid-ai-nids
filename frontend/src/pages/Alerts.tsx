import React, { useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { api } from '../services/api';
import { useFetch } from '../hooks/hooks';
import { useShortcuts } from '../hooks/shortcuts';
import { age, Badge, Card, Empty, fmt, Skeleton, SortableTable, useToast, type Col } from '../components/ui';

const Alerts: React.FC = () => {
  const [params] = useSearchParams();
  const [severity, setSeverity] = useState(params.get('severity') ?? '');
  const [status, setStatus] = useState(params.get('status') ?? '');
  const [attack, setAttack] = useState(params.get('attack') ?? '');
  const [minRisk, setMinRisk] = useState(0);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [cursor, setCursor] = useState(0);
  const toast = useToast();
  const q = useFetch(() => api.alerts({ limit: 200, ...(severity ? { severity } : {}), ...(status ? { status } : {}), min_risk: minRisk }), [severity, status, minRisk]);
  const all: any[] = (q.data as any)?.items ?? [];
  const items = all.filter((a) => !attack || `${a.attack_type} ${a.src_ip} ${a.dst_ip}`.toLowerCase().includes(attack.toLowerCase()));

  const toggle = (uid: string) => setSelected((s) => { const n = new Set(s); n.has(uid) ? n.delete(uid) : n.add(uid); return n; });

  const bulk = async (to: string) => {
    if (!selected.size) return;
    let ok = 0;
    for (const uid of selected) {
      try { await api.patchAlert(uid, { status: to, actor: 'analyst', note: 'bulk action' }); ok++; }
      catch { /* per-row failure keeps others going */ }
    }
    toast(`${ok}/${selected.size} alerts → ${to}`, ok === selected.size ? 'ok' : 'err');
    setSelected(new Set()); q.reload();
  };

  const exportSelected = () => {
    const pick = items.filter((a) => selected.size === 0 || selected.has(a.alert_uid));
    const csv = 'alert_uid,time,severity,src,dst,attack,risk,status\n' +
      pick.map((a) => [a.alert_uid, a.created_at, a.severity, a.src_ip, a.dst_ip, a.attack_type, a.risk_score, a.status].join(',')).join('\n');
    const el = document.createElement('a');
    el.href = URL.createObjectURL(new Blob([csv], { type: 'text/csv' }));
    el.download = 'alerts.csv'; el.click();
    toast(`Exported ${pick.length} alerts`, 'ok');
  };

  useShortcuts({
    j: () => setCursor((c) => Math.min(items.length - 1, c + 1)),
    k: () => setCursor((c) => Math.max(0, c - 1)),
    ' ': () => { const a = items[cursor]; if (a) toggle(a.alert_uid); },
    a: () => bulk('acknowledged'),
    r: () => bulk('resolved'),
    d: () => bulk('dismissed'),
  });

  const cols: Col<any>[] = [
    { key: 'sel', label: '', render: (a) => <input type="checkbox" checked={selected.has(a.alert_uid)} onChange={() => toggle(a.alert_uid)} aria-label={`select ${a.alert_uid}`} /> },
    { key: 'sev', label: 'Priority', render: (a) => <Badge v={a.severity} />, sort: (a) => ({ CRITICAL: 4, HIGH: 3, MEDIUM: 2, LOW: 1 } as Record<string, number>)[a.severity] ?? 0 },
    { key: 'time', label: 'Age', render: (a) => { const g = age(a.created_at); return <span className={g.stale && a.status === 'new' ? 'age-old' : ''} title={new Date(a.created_at).toLocaleString()}>{g.text}</span>; }, sort: (a) => a.created_at },
    { key: 'type', label: 'Type', render: (a) => <Link to={`/alerts/${a.alert_uid}`}>{a.attack_type}</Link>, sort: (a) => a.attack_type },
    { key: 'flow', label: 'Source → Dest', render: (a) => <span>{a.src_ip} → {a.dst_ip}</span> },
    { key: 'risk', label: 'Risk', render: (a) => fmt(a.risk_score), sort: (a) => a.risk_score, numeric: true },
    { key: 'conf', label: 'Conf', render: (a) => fmt(a.confidence), sort: (a) => a.confidence, numeric: true },
    { key: 'asg', label: 'Assignee', render: (a) => a.assignee || '—', sort: (a) => a.assignee || '' },
    { key: 'st', label: 'Status', render: (a) => <Badge v={a.status} />, sort: (a) => a.status },
  ];

  return (
    <div className="page">
      <h2>Alert Triage</h2>
      <p className="sub">Prioritise, assign and disposition the detection queue. Keys: <kbd>j</kbd>/<kbd>k</kbd> move, <kbd>space</kbd> select, <kbd>a</kbd>/<kbd>r</kbd>/<kbd>d</kbd> disposition.</p>
      <div className="grid" style={{ gridTemplateColumns: '220px 1fr' }}>
        <Card title="Filters">
          <label>Attack / IP contains<br /><input type="search" value={attack} onChange={(e) => setAttack(e.target.value)} placeholder="e.g. DDoS" aria-label="Attack filter" style={{ width: '100%' }} /></label>
          <div style={{ height: 10 }} />
          <label>Severity<br /><select value={severity} onChange={(e) => setSeverity(e.target.value)}><option value="">All</option><option>CRITICAL</option><option>HIGH</option><option>MEDIUM</option><option>LOW</option></select></label>
          <div style={{ height: 10 }} />
          <label>Status<br /><select value={status} onChange={(e) => setStatus(e.target.value)}><option value="">All</option><option value="new">new</option><option value="investigating">investigating</option><option value="acknowledged">acknowledged</option><option value="resolved">resolved</option><option value="dismissed">dismissed</option></select></label>
          <div style={{ height: 10 }} />
          <label>Min risk: {minRisk.toFixed(2)}<br /><input type="range" min={0} max={1} step={0.05} value={minRisk} onChange={(e) => setMinRisk(Number(e.target.value))} /></label>
          <div style={{ height: 10 }} />
          <div className="row">
            <button className="btn" disabled={!selected.size} onClick={exportSelected}>Export CSV</button>
          </div>
        </Card>
        <Card>
          <div className="row" style={{ justifyContent: 'space-between', marginBottom: 8 }}>
            <h3 style={{ margin: 0 }}>Alert queue ({items.length}{all.length !== items.length ? ` of ${all.length}` : ''})</h3>
            <div className="row">
              <button className="btn primary" disabled={!selected.size} onClick={() => bulk('acknowledged')}>Acknowledge ({selected.size})</button>
              <button className="btn" disabled={!selected.size} onClick={() => bulk('resolved')}>Resolve</button>
              <button className="btn" disabled={!selected.size} onClick={() => bulk('dismissed')}>Dismiss</button>
            </div>
          </div>
          <p className="hint">Select rows for bulk disposition</p>
          {q.loading ? <Skeleton rows={8} /> : items.length === 0 ? <Empty msg="No alerts match the filters." /> : (
            <SortableTable cols={cols} rows={items} initialSort="risk" />
          )}
        </Card>
      </div>
    </div>
  );
};
export default Alerts;

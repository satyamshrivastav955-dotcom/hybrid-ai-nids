import React, { useState } from 'react';
import { api } from '../services/api';
import { useFetch } from '../hooks/hooks';
import { Card, Empty } from '../components/ui';

const Reports: React.FC = () => {
  const [kind, setKind] = useState('summary');
  const [date, setDate] = useState('');
  const [showRaw, setShowRaw] = useState(false);
  const q = useFetch(() => api.reports(kind, date || undefined), [kind, date]);
  const d = q.data as any;

  const download = (fmt: 'json' | 'csv') => {
    const s = d?.summary ?? {};
    const body = fmt === 'json' ? JSON.stringify(d, null, 2)
      : 'metric,value\n' + [`total_flows,${s.total_flows}`, `attacks,${s.attacks}`].join('\n');
    const a = document.createElement('a');
    a.href = URL.createObjectURL(new Blob([body], { type: 'text/plain' }));
    a.download = `report.${fmt}`; a.click();
  };

  return (
    <div className="page">
      <h2>Reports</h2>
      <p className="sub">Professional reporting from actual database and experiment values — no invented narrative.</p>
      <div className="toolbar">
        <label>Report <select value={kind} onChange={(e) => setKind(e.target.value)}>
          <option value="summary">Daily Security Report</option>
          <option value="attacks">Attack Summary</option>
          <option value="evaluation">Model Evaluation Report</option>
          <option value="drift">Drift Report</option>
          <option value="incidents">SOC Incident Report</option>
        </select></label>
        <label>Date <input type="date" value={date} onChange={(e) => setDate(e.target.value)} aria-label="Report date" /></label>
        <button className="btn" onClick={() => setShowRaw(!showRaw)}>JSON</button>
        <button className="btn" onClick={() => download('json')}>Export JSON</button>
        <button className="btn" onClick={() => download('csv')}>Export CSV</button>
        <button className="btn" onClick={() => window.print()}>Print / PDF</button>
      </div>
      {showRaw && d && (
        <Card title="Raw JSON">
          <pre style={{ fontSize: 12, overflowX: 'auto' }}>{JSON.stringify(d, null, 2)}</pre>
        </Card>
      )}
      {!d ? <Card><Empty msg="Loading…" /></Card> : (
        <div className="grid" style={{ gridTemplateColumns: '1fr 1fr' }}>
          <Card title="Summary metrics">
            <dl className="kv">
              <dt>Total flows</dt><dd>{d.summary.total_flows}</dd>
              <dt>Attacks</dt><dd>{d.summary.attacks}</dd>
              <dt>Latest drift</dt><dd>{d.summary.latest_drift}</dd>
            </dl>
          </Card>
          <Card title="Alerts by severity">
            <table className="tbl"><thead><tr><th>Severity</th><th>Count</th></tr></thead>
              <tbody>{Object.entries(d.summary.alerts_by_severity ?? {}).map(([k, v]: [string, any]) => <tr key={k}><td>{k}</td><td>{v}</td></tr>)}</tbody></table>
          </Card>
          <Card title="Alerts by attack type">
            <table className="tbl"><thead><tr><th>Attack</th><th>Count</th></tr></thead>
              <tbody>{Object.entries(d.summary.alerts_by_attack ?? {}).map(([k, v]: [string, any]) => <tr key={k}><td>{k}</td><td>{v}</td></tr>)}</tbody></table>
          </Card>
          <Card title="Methodology">
            <p style={{ fontSize: 13 }}>{d.methodology}</p>
            <p style={{ fontSize: 12, color: '#5b6575' }}>Generated {d.generated_at}. PDF export: print this page to PDF from the browser.</p>
          </Card>
        </div>
      )}
    </div>
  );
};
export default Reports;

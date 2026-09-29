import React, { useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { api } from '../services/api';
import { Badge, Card, Empty, Skeleton } from '../components/ui';

const ThreatIntel: React.FC = () => {
  const [params] = useSearchParams();
  const [q, setQ] = useState(params.get('ip') ?? '8.8.8.8');
  const [res, setRes] = useState<any | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [hist, setHist] = useState<any[]>([]);

  const doLookup = async (ip: string) => {
    setErr(null); setLoading(true);
    try {
      const r = await api.intel(ip.trim());
      setRes(r);
      setHist((h) => [{ ip: ip.trim(), ...r, at: new Date().toLocaleString() }, ...h].slice(0, 15));
    } catch (e) { setErr(String(e)); } finally { setLoading(false); }
  };
  const search = () => doLookup(q);
  React.useEffect(() => { const ip = params.get('ip'); if (ip) { setQ(ip); doLookup(ip); } }, []); // eslint-disable-line

  return (
    <div className="page">
      <h2>Threat Intelligence</h2>
      <p className="sub">External context for an indicator. Enrichment — not ground truth.</p>
      <div className="toolbar">
        <input type="text" value={q} onChange={(e) => setQ(e.target.value)} placeholder="IP, e.g. 8.8.8.8" aria-label="Indicator" style={{ width: 260 }} />
        <button className="btn primary" onClick={search}>Lookup</button>
      </div>
      {err && <div className="err">{err}</div>}
      <div className="grid" style={{ gridTemplateColumns: '2fr 1fr' }}>
        <Card title={res ? `Indicator ${res.ip}` : 'Result'}>
          {loading ? <Skeleton rows={6} /> : !res ? <Empty msg="Run a lookup to see reputation, ASN and related alerts." /> : (
            <>
              <p><Badge v={String(res.reputation).toUpperCase() === 'MALICIOUS' ? 'CRITICAL' : String(res.reputation).toUpperCase() === 'SUSPICIOUS' ? 'HIGH' : 'LOW'} /> {res.reputation} · confidence {res.confidence}</p>
              <dl className="kv">
                <dt>IP address</dt><dd>{res.ip}</dd>
                <dt>ASN</dt><dd>{res.asn}</dd>
                <dt>Country</dt><dd>{res.country}</dd>
                <dt>Organisation</dt><dd>{res.organization}</dd>
                <dt>Last seen</dt><dd>{res.timestamp}</dd>
                <dt>Confidence</dt><dd>{res.confidence}</dd>
                <dt>Provider</dt><dd>{res.provider}</dd>
              </dl>
              <h4 style={{ marginTop: 14 }}>Related alerts ({(res.related_alerts ?? []).length})</h4>
              {(res.related_alerts ?? []).length === 0 ? <Empty msg="No related alerts." /> : (
                <table className="tbl"><thead><tr><th>Type</th><th>Risk</th><th>Status</th></tr></thead>
                  <tbody>{res.related_alerts.map((a: any) => <tr key={a.alert_uid}><td>{a.attack_type}</td><td>{Number(a.risk_score).toFixed(2)}</td><td>{a.status}</td></tr>)}</tbody></table>
              )}
            </>
          )}
        </Card>
        <div>
          <Card title="Provider status">
            <dl className="kv"><dt>Active</dt><dd>mock (offline, deterministic)</dd><dt>Real provider</dt><dd>configure ABUSEIPDB_API_KEY</dd></dl>
          </Card>
          <Card title="Lookup history">
            {hist.length === 0 ? <Empty msg="Empty." /> : (
              <table className="tbl"><thead><tr><th>Query</th><th>Time</th></tr></thead>
                <tbody>{hist.map((h, i) => <tr key={i}><td>{h.ip}</td><td>{h.at}</td></tr>)}</tbody></table>
            )}
          </Card>
        </div>
      </div>
    </div>
  );
};
export default ThreatIntel;

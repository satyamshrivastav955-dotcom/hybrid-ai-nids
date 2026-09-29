import React, { useMemo, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../services/api';
import { useFetch } from '../hooks/hooks';
import { SEV } from '../charts/palette';
import { age, Card, Empty, Skeleton } from '../components/ui';

/** Relationship-centric view: zoomable/pannable SVG entity graph, no map lib. */
const W = 660, H = 440;

const NetworkMap: React.FC = () => {
  const q = useFetch(() => api.alerts({ limit: 100 }), []);
  const [sel, setSel] = useState<string | null>(null);
  const [search, setSearch] = useState('');
  const [isolate, setIsolate] = useState(false);
  const [view, setView] = useState({ x: 0, y: 0, k: 1 });
  const drag = useRef<{ sx: number; sy: number; x: number; y: number } | null>(null);
  const items: any[] = (q.data as any)?.items ?? [];

  const graph = useMemo(() => {
    const nodes = new Map<string, { ip: string; alerts: number; risk: number }>();
    const edges = new Map<string, { a: string; b: string; n: number; risk: number }>();
    for (const a of items) {
      for (const ip of [a.src_ip, a.dst_ip]) {
        const n = nodes.get(ip) ?? { ip, alerts: 0, risk: 0 };
        n.alerts += 1; n.risk = Math.max(n.risk, a.risk_score);
        nodes.set(ip, n);
      }
      const key = [a.src_ip, a.dst_ip].sort().join('|');
      const e = edges.get(key) ?? { a: a.src_ip, b: a.dst_ip, n: 0, risk: 0 };
      e.n += 1; e.risk = Math.max(e.risk, a.risk_score);
      edges.set(key, e);
    }
    const list = [...nodes.values()].sort((x, y) => y.risk - x.risk).slice(0, 30);
    const keep = new Set(list.map((n) => n.ip));
    const pos = new Map(list.map((n, i) => {
      const angle = (2 * Math.PI * i) / Math.max(1, list.length);
      return [n.ip, { x: W / 2 + 250 * Math.cos(angle), y: H / 2 + 165 * Math.sin(angle) }];
    }));
    return { list, edges: [...edges.values()].filter((e) => keep.has(e.a) && keep.has(e.b)), pos };
  }, [items]);

  const visible = useMemo(() => {
    let { list, edges } = graph;
    if (search) list = list.filter((n) => n.ip.includes(search));
    if (sel && isolate) {
      const keep = new Set([sel]);
      edges = edges.filter((e) => { if (e.a === sel) { keep.add(e.b); return true; } if (e.b === sel) { keep.add(e.a); return true; } return false; });
      list = list.filter((n) => keep.has(n.ip));
    } else if (search) {
      const keep = new Set(list.map((n) => n.ip));
      edges = edges.filter((e) => keep.has(e.a) && keep.has(e.b));
    }
    return { list, edges };
  }, [graph, search, sel, isolate]);

  const color = (r: number) => (r >= 0.75 ? SEV.CRITICAL : r >= 0.5 ? SEV.HIGH : r >= 0.25 ? SEV.MEDIUM : SEV.LOW);
  const selAlerts = sel ? items.filter((a) => a.src_ip === sel || a.dst_ip === sel) : [];

  const onWheel = (e: React.WheelEvent) => {
    const k = Math.min(3, Math.max(0.5, view.k * (e.deltaY < 0 ? 1.1 : 0.9)));
    setView({ ...view, k });
  };
  const maxN = Math.max(1, ...graph.edges.map((e) => e.n));

  return (
    <div className="page">
      <h2>Network Map</h2>
      <p className="sub">Topology of alerting entities. Node size = alert count, colour = max risk, edge width ∝ flow volume.</p>
      <div className="toolbar">
        <input type="search" placeholder="Find IP…" value={search} onChange={(e) => setSearch(e.target.value)} aria-label="Find node" style={{ width: 200 }} />
        <button className="btn" disabled={!sel} onClick={() => setIsolate(!isolate)}>{isolate ? 'Show all' : 'Isolate entity'}</button>
        <button className="btn" onClick={() => setView({ x: 0, y: 0, k: 1 })}>Reset view</button>
        <span style={{ fontSize: 12, color: '#5b6575' }}>scroll to zoom · drag to pan · click node to select</span>
      </div>
      <div className="grid" style={{ gridTemplateColumns: '2fr 1fr' }}>
        <Card title={`Entity graph (${visible.list.length} nodes, ${visible.edges.length} links)`}>
          {q.loading ? <Skeleton rows={6} height={40} /> : graph.list.length === 0 ? <Empty msg="No alerts to map yet." /> : (
            <svg viewBox="0 0 660 440" width="100%" height={420} role="img" aria-label="Network entity graph"
              onWheel={onWheel}
              onMouseDown={(e) => { drag.current = { sx: e.clientX, sy: e.clientY, x: view.x, y: view.y }; }}
              onMouseMove={(e) => { const d = drag.current; if (d) setView({ ...view, x: d.x + (e.clientX - d.sx) / view.k, y: d.y + (e.clientY - d.sy) / view.k }); }}
              onMouseUp={() => { drag.current = null; }} onMouseLeave={() => { drag.current = null; }}
              style={{ cursor: drag.current ? 'grabbing' : 'grab', background: '#fafbfc', borderRadius: 6 }}>
              <g transform={`translate(${W / 2 + view.x},${H / 2 + view.y}) scale(${view.k}) translate(${-W / 2},${-H / 2})`}>
                {visible.edges.map((e, i) => {
                  const p1 = graph.pos.get(e.a), p2 = graph.pos.get(e.b);
                  if (!p1 || !p2) return null;
                  return <line key={i} x1={p1.x} y1={p1.y} x2={p2.x} y2={p2.y} stroke={color(e.risk)}
                    strokeWidth={0.5 + (e.n / maxN) * 4} opacity={0.5} />;
                })}
                {visible.list.map((n) => {
                  const p = graph.pos.get(n.ip)!;
                  return (
                    <g key={n.ip} onClick={() => setSel(n.ip)} style={{ cursor: 'pointer' }} tabIndex={0} role="button" aria-label={n.ip}
                      onKeyDown={(e) => { if (e.key === 'Enter') setSel(n.ip); }}>
                      <circle cx={p.x} cy={p.y} r={8 + Math.min(14, n.alerts * 3)} fill={color(n.risk)} opacity={0.85}
                        stroke={sel === n.ip ? '#1a2332' : '#fff'} strokeWidth={sel === n.ip ? 3 : 2} />
                      <text x={p.x} y={p.y + 26} textAnchor="middle" fontSize={10}>{n.ip}</text>
                    </g>
                  );
                })}
              </g>
            </svg>
          )}
          <div className="row" style={{ marginTop: 8, fontSize: 12, color: '#5b6575' }}>
            {(Object.entries(SEV) as [string, string][]).map(([k, v]) => (
              <span key={k} style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
                <span style={{ width: 10, height: 10, borderRadius: '50%', background: v, display: 'inline-block' }} />{k}
              </span>))}
          </div>
        </Card>
        <Card title="Selected entity" hint="Click a node">
          {!sel ? <Empty msg="Select a node to inspect its alerts." /> : (
            <>
              <dl className="kv">
                <dt>IP address</dt><dd>{sel}</dd>
                <dt>Country</dt><dd>—</dd>
                <dt>ASN</dt><dd>—</dd>
                <dt>Alert count</dt><dd>{selAlerts.length}</dd>
                <dt>Max risk</dt><dd>{selAlerts.length ? Math.max(...selAlerts.map((a) => a.risk_score)).toFixed(2) : '—'}</dd>
              </dl>
              <p style={{ marginTop: 8 }}><Link to={`/intel?ip=${encodeURIComponent(sel)}`}>threat intel →</Link></p>
              <h4 style={{ margin: '12px 0 4px' }}>Recent activity</h4>
              <table className="tbl"><thead><tr><th>Time</th><th>Type</th></tr></thead>
                <tbody>{selAlerts.slice(0, 8).map((a) => (
                  <tr key={a.alert_uid}><td>{age(a.created_at).text}</td>
                    <td><Link to={`/alerts/${a.alert_uid}`}>{a.attack_type}</Link></td></tr>))}</tbody></table>
            </>
          )}
        </Card>
      </div>
    </div>
  );
};
export default NetworkMap;

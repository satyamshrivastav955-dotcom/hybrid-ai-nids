import React from 'react';

export const Badge: React.FC<{ v: string }> = ({ v }) => <span className={`badge b-${v}`}>{v}</span>;

export const Card: React.FC<{ title?: string; hint?: string; children: React.ReactNode; style?: React.CSSProperties }> =
  ({ title, hint, children, style }) => (
    <div className="card" style={style}>
      {title && <h3>{title}</h3>}
      {hint && <p className="hint">{hint}</p>}
      {children}
    </div>
  );

export const Empty: React.FC<{ msg: string }> = ({ msg }) => <div className="empty">{msg}</div>;

export const RiskBar: React.FC<{ v: number }> = ({ v }) => (
  <div className="bar" title={`risk ${v.toFixed(2)}`}><div style={{ width: `${Math.round(v * 100)}%` }} /></div>
);

export const fmt = (n: number, d = 2) => (n == null ? '—' : Number(n).toFixed(d));

export const Fig: React.FC<{ file: string; caption: string }> = ({ file, caption }) => {
  const [missing, setMissing] = React.useState(false);
  if (missing) return <Empty msg={`${caption}: not generated yet — run scripts/evaluate_all.py.`} />;
  return (
    <figure style={{ margin: 0 }}>
      <img src={`/api/models/figures/${file}`} alt={caption} onError={() => setMissing(true)}
        style={{ width: '100%', border: '1px solid #e3e6eb', borderRadius: 6 }} />
      <figcaption style={{ fontSize: 12, color: '#5b6575', marginTop: 6 }}>{caption}</figcaption>
    </figure>
  );
};

/** Loading placeholder blocks. */
export const Skeleton: React.FC<{ rows?: number; height?: number }> = ({ rows = 3, height = 14 }) => (
  <div aria-busy="true" aria-label="Loading">
    {Array.from({ length: rows }).map((_, i) => (
      <div key={i} className="sk" style={{ height, marginBottom: 8 }} />
    ))}
  </div>
);

/** Toast notifications. */
type Toast = { id: number; msg: string; kind: '' | 'ok' | 'err' };
const ToastCtx = React.createContext<(msg: string, kind?: '' | 'ok' | 'err') => void>(() => {});
export const useToast = () => React.useContext(ToastCtx);
export const ToastProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [items, setItems] = React.useState<Toast[]>([]);
  const push = React.useCallback((msg: string, kind: '' | 'ok' | 'err' = '') => {
    const id = Date.now() + Math.random();
    setItems((p) => [...p, { id, msg, kind }]);
    setTimeout(() => setItems((p) => p.filter((t) => t.id !== id)), 4000);
  }, []);
  return (
    <ToastCtx.Provider value={push}>
      {children}
      <div className="toasts" role="status" aria-live="polite">
        {items.map((t) => <div key={t.id} className={`toast ${t.kind}`}>{t.msg}</div>)}
      </div>
    </ToastCtx.Provider>
  );
};

/** Sortable + paginated table. */
export interface Col<T> {
  key: string;
  label: React.ReactNode;
  render: (row: T) => React.ReactNode;
  sort?: (row: T) => string | number;
  numeric?: boolean;
}
export function SortableTable<T extends object>({
  cols, rows, pageSize = 15, initialSort,
}: {
  cols: Col<T>[]; rows: T[]; pageSize?: number; initialSort?: string;
}) {
  const [sortKey, setSortKey] = React.useState(initialSort ?? '');
  const [dir, setDir] = React.useState<1 | -1>(-1);
  const [page, setPage] = React.useState(0);
  const sorted = React.useMemo(() => {
    const c = cols.find((x) => x.key === sortKey);
    if (!c?.sort) return rows;
    return [...rows].sort((a, b) => {
      const va = c.sort!(a), vb = c.sort!(b);
      return (va < vb ? -1 : va > vb ? 1 : 0) * dir;
    });
  }, [rows, cols, sortKey, dir]);
  const pages = Math.max(1, Math.ceil(sorted.length / pageSize));
  const view = sorted.slice(page * pageSize, (page + 1) * pageSize);
  React.useEffect(() => setPage(0), [rows.length, pageSize]);
  const flip = (k: string) => {
    if (k === sortKey) setDir((d) => (d === 1 ? -1 : 1));
    else { setSortKey(k); setDir(-1); }
  };
  return (
    <>
      <div style={{ overflowX: 'auto' }}>
        <table className="tbl">
          <thead><tr>{cols.map((c) => (
            <th key={c.key} className={c.sort ? 'sortable' : ''} onClick={c.sort ? () => flip(c.key) : undefined}
              style={c.numeric ? { textAlign: 'right' } : undefined}
              aria-sort={c.key === sortKey ? (dir === 1 ? 'ascending' : 'descending') : undefined}>
              {c.label}{c.key === sortKey ? (dir === 1 ? ' ▲' : ' ▼') : ''}
            </th>))}</tr></thead>
          <tbody>{view.map((r, i) => (
            <tr key={i}>{cols.map((c) => (
              <td key={c.key} style={c.numeric ? { textAlign: 'right' } : undefined}>{c.render(r)}</td>))}</tr>))}</tbody>
        </table>
      </div>
      {pages > 1 && (
        <div className="pager">
          <button className="btn" disabled={page === 0} onClick={() => setPage(page - 1)}>‹ Prev</button>
          <span>Page {page + 1} of {pages} · {sorted.length} rows</span>
          <button className="btn" disabled={page >= pages - 1} onClick={() => setPage(page + 1)}>Next ›</button>
        </div>
      )}
    </>
  );
}

/** Tiny inline sparkline. */
export const Sparkline: React.FC<{ data: number[]; width?: number; height?: number; stroke?: string }> =
  ({ data, width = 120, height = 32, stroke = '#2456a6' }) => {
    if (data.length < 2) return <span style={{ color: '#5b6575' }}>—</span>;
    const mn = Math.min(...data), mx = Math.max(...data), rg = mx - mn || 1;
    const pts = data.map((v, i) => `${(i / (data.length - 1)) * width},${height - ((v - mn) / rg) * (height - 4) - 2}`).join(' ');
    return (
      <svg width={width} height={height} aria-hidden>
        <polyline points={pts} fill="none" stroke={stroke} strokeWidth={1.5} />
      </svg>
    );
  };

/** Change indicator. `invert` when up-is-bad (e.g. alert counts). */
export const Delta: React.FC<{ pct: number | null; invert?: boolean }> = ({ pct, invert }) => {
  if (pct == null || !isFinite(pct)) return <span style={{ color: '#5b6575' }}>—</span>;
  const up = pct >= 0;
  const bad = invert ? up : !up;
  return <span className={bad ? 'delta-up' : 'delta-dn'}>{up ? '▲' : '▼'} {Math.abs(pct).toFixed(0)}%</span>;
};

/** Relative age, e.g. "12m ago"; flags stale criticals. */
export function age(iso: string): { text: string; stale: boolean } {
  const mins = Math.max(0, (Date.now() - new Date(iso).getTime()) / 60000);
  const stale = mins > 60;
  const text = mins < 1 ? 'just now' : mins < 60 ? `${Math.floor(mins)}m ago`
    : mins < 1440 ? `${Math.floor(mins / 60)}h ago` : `${Math.floor(mins / 1440)}d ago`;
  return { text, stale };
}

/** Backend drift status -> reference-mock display label (High/Moderate/Low). */
export const driftLabel = (s: string) =>
  s === 'SEVERE' ? 'High' : s === 'MODERATE' ? 'Moderate' : s === 'STABLE' ? 'Low' : s;

/** 2x2 confusion-matrix heatmap (ensemble binary outcomes). */
export const ConfusionHeat: React.FC<{ tp: number; fp: number; tn: number; fn: number }> =
  ({ tp, fp, tn, fn }) => {
    const mx = Math.max(1, tp, fp, tn, fn);
    const cell = (v: number, label: string) => {
      const a = 0.08 + 0.85 * (v / mx);
      return (
        <td style={{ background: `rgba(36,86,166,${a.toFixed(2)})`, color: a > 0.5 ? '#fff' : '#1a2332',
          textAlign: 'center', padding: '14px 8px', fontWeight: 600 }}>
          {v.toLocaleString()}<div style={{ fontWeight: 400, fontSize: 11 }}>{label}</div>
        </td>
      );
    };
    return (
      <table className="tbl" aria-label="Confusion matrix">
        <thead><tr><th></th><th>Predicted benign</th><th>Predicted attack</th></tr></thead>
        <tbody>
          <tr><th>Actual benign</th>{cell(tn, 'TN')}{cell(fp, 'FP')}</tr>
          <tr><th>Actual attack</th>{cell(fn, 'FN')}{cell(tp, 'TP')}</tr>
        </tbody>
      </table>
    );
  };

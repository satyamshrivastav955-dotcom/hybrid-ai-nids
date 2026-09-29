import React, { useState } from 'react';
import { api } from '../services/api';
import { useFetch } from '../hooks/hooks';
import { useMode } from '../layouts/Layout';
import { Card, Empty, useToast } from '../components/ui';

const Settings: React.FC = () => {
  const { mode, setMode } = useMode();
  const perf = useFetch(api.performance);
  const [threshold, setThreshold] = useState(0.5);
  const [reason, setReason] = useState('');
  const [confirm, setConfirm] = useState('');
  const [impact, setImpact] = useState<any | null>(null);
  const toast = useToast();
  const ensWeights = (perf.data as any)?.standard_metrics?.metrics?.ensemble;

  const propose = async () => {
    try {
      const r = await api.proposeThreshold({ threshold, actor: 'analyst', reason });
      setImpact(r);
      toast(`Proposal recorded: ${r.would_escalate} escalate / ${r.would_deescalate} de-escalate`, 'ok');
    } catch (e) { toast(`Proposal failed: ${e}`, 'err'); }
    setConfirm('');
  };

  return (
    <div className="page">
      <h2>Settings</h2>
      <p className="sub">Configuration workspace. Dangerous changes require typed confirmation.</p>
      <div className="grid" style={{ gridTemplateColumns: '1fr 1fr' }}>
        <Card title="General" hint="Operating mode for this console">
          <label>Data source mode<br />
            <select value={mode} onChange={(e) => setMode(e.target.value as never)}>
              <option value="dataset">Dataset (research / replay)</option>
              <option value="live">Live network</option>
              <option value="demo">Demo (synthetic, labelled)</option>
            </select></label>
        </Card>
        <Card title="Detection thresholds" hint="Proposals are audited with impact preview — never silently applied">
          <label>Proposed decision threshold: {threshold.toFixed(2)}<br />
            <input type="range" min={0.1} max={0.9} step={0.05} value={threshold} onChange={(e) => setThreshold(Number(e.target.value))} /></label>
          <div style={{ height: 8 }} />
          <input type="text" placeholder="Reason (required for audit)…" value={reason} onChange={(e) => setReason(e.target.value)} aria-label="Reason" style={{ width: '100%' }} />
          <div style={{ height: 8 }} />
          <div className="row">
            <input type="text" placeholder="Type PROPOSE to confirm" value={confirm} onChange={(e) => setConfirm(e.target.value)} aria-label="Confirm" />
            <button className="btn primary" disabled={confirm !== 'PROPOSE' || !reason.trim()} onClick={propose}>Propose change</button>
          </div>
          {impact && (
            <dl className="kv" style={{ marginTop: 10 }}>
              <dt>Current → proposed</dt><dd>{impact.current} → {impact.proposed}</dd>
              <dt>Would escalate</dt><dd>{impact.would_escalate} stored flows</dd>
              <dt>Would de-escalate</dt><dd>{impact.would_deescalate} stored flows</dd>
              <dt>Status</dt><dd>recorded, not applied — {impact.note}</dd>
            </dl>
          )}
          <p style={{ fontSize: 12, color: '#5b6575' }}>Active trained threshold: {ensWeights ? 'see ensemble_config.json' : '0.50 default'}.</p>
        </Card>
        <Card title="Ensemble weights" hint="Persisted, validation-optimised">
          <pre style={{ fontSize: 12 }}>{JSON.stringify((perf.data as any)?.standard_metrics?.metrics?.ensemble?.weights ?? 'no evaluation yet', null, 2)}</pre>
        </Card>
        <Card title="Danger zone" hint="Type RESET to confirm">
          <input type="text" placeholder="Type RESET" value={confirm} onChange={(e) => setConfirm(e.target.value)} aria-label="Confirm" />
          <div style={{ height: 8 }} />
          <button className="btn" disabled={confirm !== 'RESET'} onClick={() => { alert('Demo data purge is handled server-side via scripts.'); setConfirm(''); }}>Purge demo traffic</button>
        </Card>
        <Card title="Threat intelligence" hint="Provider selection">
          <dl className="kv"><dt>Provider</dt><dd>mock (set THREAT_INTEL_PROVIDER + ABUSEIPDB_API_KEY for live)</dd></dl>
        </Card>
        <Card title="Security" hint="Auth design">
          <p style={{ fontSize: 13 }}>Set <code>API_KEY</code> env to require <code>X-API-Key</code> on all calls. Rate limiting (300 req/min/IP) is always on. Secrets are never committed.</p>
        </Card>
      </div>
    </div>
  );
};
export default Settings;

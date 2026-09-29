# Threat intelligence

`ml/threat_intel/providers.py` defines `ThreatIntelProvider.lookup(ip)` plus
`MockProvider` (deterministic, offline, private IPs -> benign) and
`AbuseIPDBProvider` (needs `ABUSEIPDB_API_KEY`; fails open to a labelled
fallback). Selection via `THREAT_INTEL_PROVIDER`. Results are cached 24h in
`threat_intelligence` and attached to alerts as enrichment with provider,
timestamp and confidence. Intel never overrides model evidence.

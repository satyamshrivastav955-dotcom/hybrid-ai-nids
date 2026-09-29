"""Modular threat-intelligence adapters.

Threat intel is an ENRICHMENT signal, not ground truth. Every lookup records
provider, timestamp, confidence and raw result for audit.
"""
from __future__ import annotations

import datetime
import hashlib
import ipaddress
import os
from dataclasses import dataclass


@dataclass
class IntelResult:
    ip: str
    provider: str
    reputation: str       # malicious | suspicious | benign | unknown
    confidence: float
    asn: str | None = None
    organization: str | None = None
    country: str | None = None
    lists: list | None = None
    timestamp: str = ""

    def to_dict(self) -> dict:
        return {"ip": self.ip, "provider": self.provider, "reputation": self.reputation,
                "confidence": self.confidence, "asn": self.asn, "organization": self.organization,
                "country": self.country, "lists": self.lists or [], "timestamp": self.timestamp}


class ThreatIntelProvider:
    name = "base"

    def lookup(self, ip: str) -> IntelResult:
        raise NotImplementedError

    def status(self) -> dict:
        return {"provider": self.name, "available": True}


def _stable_pseudo_reputation(ip: str) -> tuple[str, float]:
    h = int(hashlib.sha256(ip.encode()).hexdigest(), 16)
    r = (h % 1000) / 1000.0
    if r > 0.97:
        return "malicious", 0.75
    if r > 0.90:
        return "suspicious", 0.55
    return "unknown", 0.2


class MockProvider(ThreatIntelProvider):
    """Deterministic offline provider for research/demo. Clearly labelled as mock."""
    name = "mock"

    def lookup(self, ip: str) -> IntelResult:
        try:
            parsed = ipaddress.ip_address(ip)
            private = parsed.is_private
        except ValueError:
            private = False
        if private:
            rep, conf = "benign", 0.9
        else:
            rep, conf = _stable_pseudo_reputation(ip)
        return IntelResult(ip=ip, provider="mock", reputation=rep, confidence=conf,
                           asn="AS64496", organization="MockLab",
                           country="ZZ", lists=[],
                           timestamp=datetime.datetime.utcnow().isoformat() + "Z")


class AbuseIPDBProvider(ThreatIntelProvider):
    """Real provider skeleton: needs ABUSEIPDB_API_KEY env var; fails open to mock."""
    name = "abuseipdb"

    def __init__(self, api_key: str | None = None, timeout: int = 5) -> None:
        self.api_key = api_key or os.getenv("ABUSEIPDB_API_KEY", "")
        self.timeout = timeout

    def status(self) -> dict:
        return {"provider": self.name, "available": bool(self.api_key),
                "note": "requires ABUSEIPDB_API_KEY"}

    def lookup(self, ip: str) -> IntelResult:
        import httpx
        if not self.api_key:
            return MockProvider().lookup(ip)
        try:
            r = httpx.get("https://api.abuseipdb.com/api/v2/check",
                          params={"ipAddress": ip, "maxAgeInDays": 90},
                          headers={"Key": self.api_key, "Accept": "application/json"},
                          timeout=self.timeout)
            r.raise_for_status()
            data = r.json().get("data", {})
            score = int(data.get("abuseConfidenceScore", 0))
            rep = "malicious" if score >= 75 else ("suspicious" if score >= 25 else "benign")
            return IntelResult(ip=ip, provider="abuseipdb", reputation=rep,
                               confidence=score / 100.0, country=data.get("countryCode"),
                               lists=[], timestamp=datetime.datetime.utcnow().isoformat() + "Z")
        except Exception:
            fb = MockProvider().lookup(ip)
            fb.provider = "abuseipdb(fallback-mock)"
            return fb


def get_provider(name: str | None = None) -> ThreatIntelProvider:
    name = (name or os.getenv("THREAT_INTEL_PROVIDER", "mock")).lower()
    if name == "abuseipdb":
        return AbuseIPDBProvider()
    return MockProvider()

"""Risk engine: model evidence -> risk score, severity, auditable decision record."""
from __future__ import annotations


SEVERITIES = ("LOW", "MEDIUM", "HIGH", "CRITICAL")


class RiskEngine:
    def __init__(self, low: float = 0.25, medium: float = 0.5, high: float = 0.75) -> None:
        if not (0 < low < medium < high < 1):
            raise ValueError("Risk bands must satisfy 0 < low < medium < high < 1.")
        self.low, self.medium, self.high = low, medium, high

    def severity(self, risk: float) -> str:
        if risk >= self.high:
            return "CRITICAL"
        if risk >= self.medium:
            return "HIGH"
        if risk >= self.low:
            return "MEDIUM"
        return "LOW"

    def decide(self, prediction: str, risk_score: float, signals: dict,
               confidence: float = 0.0, threshold: float = 0.5) -> dict:
        risk = float(min(1.0, max(0.0, risk_score)))
        return {
            "prediction": prediction,
            "risk_score": round(risk, 4),
            "severity": self.severity(risk),
            "confidence": round(float(confidence), 4),
            "decision_threshold": threshold,
            "signals": {k: round(float(v), 4) for k, v in signals.items()},
        }

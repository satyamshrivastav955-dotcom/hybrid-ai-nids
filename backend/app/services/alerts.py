"""Alert persistence + lifecycle (new -> investigating -> acknowledged -> resolved/dismissed)."""
from __future__ import annotations

import datetime

from sqlalchemy.orm import Session

from backend.app.core.logging import new_id
from backend.app.db import models as m


TRANSITIONS = {
    "new": {"investigating", "acknowledged", "dismissed"},
    "investigating": {"acknowledged", "resolved", "dismissed"},
    "acknowledged": {"investigating", "resolved", "dismissed"},
    "resolved": set(),
    "dismissed": {"new"},
}


def _display(s: str) -> str:
    """Map C1 control chars (e.g. U+0096 left by the dataset's latin-1 fallback
    read of 'Web Attack – ...' labels) and fancy punctuation to safe display
    text. Model/DB values are unchanged; this is presentation only."""
    return (str(s).replace("–", "-").replace("—", "-")
             .replace("‘", "'").replace("’", "'").replace("“", '"').replace("”", '"'))


def create_alert(db: Session, result: dict, flow: dict, flow_id: int | None = None) -> m.Alert:
    alert = m.Alert(
        alert_uid=new_id("alert"),
        src_ip=flow.get("src_ip", ""),
        dst_ip=flow.get("dst_ip", ""),
        attack_type=_display(result.get("prediction", "Unknown")),
        risk_score=result.get("risk_score", 0.0),
        confidence=result.get("confidence", 0.0),
        severity=result.get("severity", "MEDIUM"),
        status="new" if result.get("risk_score", 0) >= 0.5 else "new",
        signals=result.get("signals", {}),
        explanation=result.get("explanation", ""),
        top_features=result.get("top_features", []),
        threat_intel=result.get("threat_intel", {}),
        flow_ref=flow_id,
    )
    db.add(alert)
    db.flush()
    db.add(m.AlertHistory(alert_uid=alert.alert_uid, actor="system",
                          from_status="", to_status="new", note="Alert created by ensemble engine."))
    db.commit()
    db.refresh(alert)
    return alert


def transition(db: Session, alert_uid: str, to_status: str, actor: str = "analyst",
               note: str = "", assignee: str | None = None) -> m.Alert:
    alert = db.query(m.Alert).filter(m.Alert.alert_uid == alert_uid).one_or_none()
    if alert is None:
        raise KeyError(f"Alert {alert_uid} not found.")
    allowed = TRANSITIONS.get(alert.status, set())
    if to_status not in allowed and to_status != alert.status:
        raise ValueError(f"Illegal transition {alert.status} -> {to_status}. Allowed: {sorted(allowed)}")
    from_status = alert.status
    alert.status = to_status
    if assignee is not None:
        alert.assignee = assignee
    alert.updated_at = datetime.datetime.utcnow()
    db.add(m.AlertHistory(alert_uid=alert_uid, actor=actor, from_status=from_status,
                          to_status=to_status, note=note))
    db.add(m.AuditLog(actor=actor, action=f"alert.{to_status}", entity=alert_uid,
                      detail={"from": from_status, "note": note}))
    db.commit()
    db.refresh(alert)
    return alert

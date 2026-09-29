"""Relational schema: flows, alerts (+history), predictions, drift, intel, versions, audit."""
from __future__ import annotations

import datetime

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.database import Base


def _utcnow():
    return datetime.datetime.utcnow()


class Flow(Base):
    __tablename__ = "flows"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ts: Mapped[datetime.datetime] = mapped_column(DateTime, default=_utcnow, index=True)
    src_ip: Mapped[str] = mapped_column(String(64), default="", index=True)
    dst_ip: Mapped[str] = mapped_column(String(64), default="", index=True)
    src_port: Mapped[int] = mapped_column(Integer, default=0)
    dst_port: Mapped[int] = mapped_column(Integer, default=0)
    protocol: Mapped[str] = mapped_column(String(16), default="")
    prediction: Mapped[str] = mapped_column(String(64), default="BENIGN", index=True)
    risk_score: Mapped[float] = mapped_column(Float, default=0.0)
    severity: Mapped[str] = mapped_column(String(16), default="LOW", index=True)
    source: Mapped[str] = mapped_column(String(16), default="dataset")  # dataset|live|demo
    features: Mapped[dict] = mapped_column(JSON, default=dict)


class Alert(Base):
    __tablename__ = "alerts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    alert_uid: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=_utcnow, index=True)
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=_utcnow, onupdate=_utcnow)
    src_ip: Mapped[str] = mapped_column(String(64), default="", index=True)
    dst_ip: Mapped[str] = mapped_column(String(64), default="", index=True)
    attack_type: Mapped[str] = mapped_column(String(64), default="Unknown", index=True)
    risk_score: Mapped[float] = mapped_column(Float, default=0.0)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    severity: Mapped[str] = mapped_column(String(16), default="MEDIUM", index=True)
    status: Mapped[str] = mapped_column(String(24), default="new", index=True)  # new|investigating|acknowledged|resolved|dismissed
    assignee: Mapped[str] = mapped_column(String(64), default="")
    signals: Mapped[dict] = mapped_column(JSON, default=dict)
    explanation: Mapped[str] = mapped_column(Text, default="")
    top_features: Mapped[list] = mapped_column(JSON, default=list)
    threat_intel: Mapped[dict] = mapped_column(JSON, default=dict)
    flow_ref: Mapped[int] = mapped_column(Integer, ForeignKey("flows.id"), nullable=True)


class AlertHistory(Base):
    __tablename__ = "alert_history"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    alert_uid: Mapped[str] = mapped_column(String(64), index=True)
    ts: Mapped[datetime.datetime] = mapped_column(DateTime, default=_utcnow)
    actor: Mapped[str] = mapped_column(String(64), default="system")
    from_status: Mapped[str] = mapped_column(String(24), default="")
    to_status: Mapped[str] = mapped_column(String(24), default="")
    note: Mapped[str] = mapped_column(Text, default="")


class ModelPrediction(Base):
    __tablename__ = "model_predictions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ts: Mapped[datetime.datetime] = mapped_column(DateTime, default=_utcnow, index=True)
    request_id: Mapped[str] = mapped_column(String(64), index=True)
    model_versions: Mapped[dict] = mapped_column(JSON, default=dict)
    signals: Mapped[dict] = mapped_column(JSON, default=dict)
    final_risk: Mapped[float] = mapped_column(Float, default=0.0)
    final_prediction: Mapped[str] = mapped_column(String(64), default="")


class DriftEvent(Base):
    __tablename__ = "drift_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ts: Mapped[datetime.datetime] = mapped_column(DateTime, default=_utcnow, index=True)
    reference_version: Mapped[str] = mapped_column(String(64), default="baseline-v1")
    aggregate_psi: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[str] = mapped_column(String(16), default="STABLE", index=True)
    top_features: Mapped[list] = mapped_column(JSON, default=list)
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
    adaptation_status: Mapped[str] = mapped_column(String(32), default="none")  # none|pending|recalibrated|retraining


class ThreatIntelCache(Base):
    __tablename__ = "threat_intelligence"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ip: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    provider: Mapped[str] = mapped_column(String(32), default="mock")
    result: Mapped[dict] = mapped_column(JSON, default=dict)
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=_utcnow, onupdate=_utcnow)


class ModelVersion(Base):
    __tablename__ = "model_versions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    model_name: Mapped[str] = mapped_column(String(64), index=True)
    version: Mapped[str] = mapped_column(String(32))
    dataset_version: Mapped[str] = mapped_column(String(32), default="")
    feature_schema_version: Mapped[str] = mapped_column(String(32), default="v1")
    metrics: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=_utcnow)


class Experiment(Base):
    __tablename__ = "experiments"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(128), index=True)
    protocol: Mapped[str] = mapped_column(String(64), default="")
    config: Mapped[dict] = mapped_column(JSON, default=dict)
    metrics: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=_utcnow)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ts: Mapped[datetime.datetime] = mapped_column(DateTime, default=_utcnow, index=True)
    actor: Mapped[str] = mapped_column(String(64), default="system")
    action: Mapped[str] = mapped_column(String(128))
    entity: Mapped[str] = mapped_column(String(128), default="")
    detail: Mapped[dict] = mapped_column(JSON, default=dict)


class SystemEvent(Base):
    __tablename__ = "system_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ts: Mapped[datetime.datetime] = mapped_column(DateTime, default=_utcnow, index=True)
    level: Mapped[str] = mapped_column(String(16), default="info")
    component: Mapped[str] = mapped_column(String(64), default="")
    message: Mapped[str] = mapped_column(Text, default="")

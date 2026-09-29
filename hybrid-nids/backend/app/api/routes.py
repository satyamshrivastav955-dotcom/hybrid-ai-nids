"""All REST routes + WebSocket endpoint."""
from __future__ import annotations

import asyncio
import datetime
import json
import logging
import time
from pathlib import Path

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from backend.app.core.config import get_settings
from backend.app.core.logging import new_id
from backend.app.core.security import check_rate_limit
from backend.app.db import models as m
from backend.app.db.database import get_db
from backend.app.schemas.schemas import AlertPatch, BatchPredictRequest, DriftComputeRequest, FlowFeatures, HealthResponse, ThresholdProposal
from backend.app.services import alerts as alert_svc
from backend.app.services.demo import demo_flow
from backend.app.services.inference import InferenceService
from backend.app.websocket.manager import manager

logger = logging.getLogger(__name__)
settings = get_settings()
service = InferenceService()
START_TIME = time.time()

router = APIRouter()


def _sanitize(obj):
    """Replace NaN/Inf with None so every response is valid JSON."""
    import math
    if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
        return None
    if isinstance(obj, dict):
        return {k: _sanitize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_sanitize(v) for v in obj]
    return obj


def _persist_flow(db: Session, flow: dict, result: dict) -> int:
    f = m.Flow(src_ip=flow.get("src_ip", ""), dst_ip=flow.get("dst_ip", ""),
               src_port=int(flow.get("src_port", 0) or 0), dst_port=int(flow.get("dst_port", 0) or 0),
               protocol=flow.get("protocol", ""), prediction=result["prediction"],
               risk_score=result["risk_score"], severity=result["severity"],
               source=flow.get("source", result.get("source", "dataset")),
               features={k: float(v) for k, v in (flow.get("features") or {}).items()})
    db.add(f)
    db.commit()
    db.refresh(f)
    return int(f.id)


# ---------- health / status ----------
@router.get("/health", response_model=HealthResponse)
def health():
    return {"status": "ok", "backend_version": settings.backend_version,
            "models_loaded": service.loaded, "models": service.status(),
            "demo_mode": settings.demo_mode, "ingestion_mode": settings.ingestion_mode}


@router.get("/system/status")
def system_status(db: Session = Depends(get_db)):
    flows = db.query(func.count(m.Flow.id)).scalar() or 0
    alerts = db.query(func.count(m.Alert.id)).scalar() or 0
    drifts = db.query(func.count(m.DriftEvent.id)).scalar() or 0
    try:
        import psutil
        cpu, ram = psutil.cpu_percent(), psutil.virtual_memory().percent
    except ImportError:
        cpu, ram = -1.0, -1.0
    last_drift = db.query(m.DriftEvent).order_by(desc(m.DriftEvent.ts)).first()
    return {"api": "online", "database": "online",
            "websocket_connections": len(manager.active),
            "models": service.status(), "uptime_seconds": round(time.time() - START_TIME, 1),
            "cpu_percent": cpu, "ram_percent": ram,
            "flows_stored": flows, "alerts_stored": alerts, "drift_events": drifts,
            "last_drift": last_drift.status if last_drift else None,
            "ingestion_mode": settings.ingestion_mode, "demo_mode": settings.demo_mode}


# ---------- prediction ----------
@router.post("/predict")
async def predict(flow: FlowFeatures, request: Request, db: Session = Depends(get_db)):
    check_rate_limit(request.client.host if request.client else "unknown")
    payload = flow.model_dump()
    source = payload.pop("source", "dataset")
    feats = payload.pop("features")
    flow_dict = {**payload, "features": feats, "source": source}
    try:
        result = service.predict_one(flow_dict, source=source)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    flow_id = _persist_flow(db, flow_dict, result)
    db.add(m.ModelPrediction(request_id=result["request_id"], model_versions=result.get("model_versions", {}),
                             signals=result["signals"], final_risk=result["risk_score"],
                             final_prediction=result["prediction"]))
    db.commit()
    alert = None
    if result["risk_score"] >= 0.5:
        alert = alert_svc.create_alert(db, result, flow_dict, flow_id)
    msg = {"type": "prediction", **result, "flow_id": flow_id,
           "alert_uid": alert.alert_uid if alert else None}
    await manager.broadcast(msg)
    return {**result, "flow_id": flow_id, "alert_uid": alert.alert_uid if alert else None}


@router.post("/predict/batch")
async def predict_batch(req: BatchPredictRequest, request: Request, db: Session = Depends(get_db)):
    check_rate_limit(request.client.host if request.client else "unknown")
    results = []
    for f in req.flows:
        payload = f.model_dump()
        source = req.source
        flow_dict = {**payload, "source": source}
        try:
            result = service.predict_one(flow_dict, source=source)
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))
        flow_id = _persist_flow(db, flow_dict, result)
        alert = alert_svc.create_alert(db, result, flow_dict, flow_id) if result["risk_score"] >= 0.5 else None
        results.append({**result, "flow_id": flow_id, "alert_uid": alert.alert_uid if alert else None})
    await manager.broadcast({"type": "batch", "count": len(results)})
    return {"count": len(results), "results": results}


# ---------- alerts ----------
@router.get("/alerts")
def list_alerts(status: str | None = None, severity: str | None = None,
                attack_type: str | None = None, min_risk: float = 0.0,
                limit: int = Query(50, le=500), offset: int = 0,
                db: Session = Depends(get_db)):
    q = db.query(m.Alert).order_by(desc(m.Alert.created_at))
    if status:
        q = q.filter(m.Alert.status == status)
    if severity:
        q = q.filter(m.Alert.severity == severity)
    if attack_type:
        q = q.filter(m.Alert.attack_type == attack_type)
    if min_risk:
        q = q.filter(m.Alert.risk_score >= min_risk)
    total = q.count()
    items = q.offset(offset).limit(limit).all()
    return {"total": total, "items": [_alert_to_dict(a) for a in items]}


def _alert_to_dict(a: m.Alert) -> dict:
    return {c: getattr(a, c) for c in ("id", "alert_uid", "src_ip", "dst_ip", "attack_type",
                                       "risk_score", "confidence", "severity", "status", "assignee",
                                       "signals", "explanation", "top_features", "threat_intel", "flow_ref")} | \
           {"created_at": a.created_at.isoformat() if a.created_at else None,
            "updated_at": a.updated_at.isoformat() if a.updated_at else None}


@router.get("/alerts/{alert_uid}")
def get_alert(alert_uid: str, db: Session = Depends(get_db)):
    a = db.query(m.Alert).filter(m.Alert.alert_uid == alert_uid).one_or_none()
    if not a:
        raise HTTPException(404, "Alert not found.")
    hist = db.query(m.AlertHistory).filter(m.AlertHistory.alert_uid == alert_uid).order_by(m.AlertHistory.ts).all()
    flow = db.query(m.Flow).filter(m.Flow.id == a.flow_ref).one_or_none() if a.flow_ref else None
    return {"alert": _alert_to_dict(a),
            "history": [{"ts": h.ts.isoformat(), "actor": h.actor, "from": h.from_status, "to": h.to_status, "note": h.note} for h in hist],
            "flow": {"id": flow.id, "src_ip": flow.src_ip, "dst_ip": flow.dst_ip,
                     "protocol": flow.protocol, "features": flow.features} if flow else None}


@router.patch("/alerts/{alert_uid}")
def patch_alert(alert_uid: str, patch: AlertPatch, db: Session = Depends(get_db)):
    try:
        a = alert_svc.transition(db, alert_uid, patch.status or "acknowledged",
                                 actor=patch.actor, note=patch.note or "",
                                 assignee=patch.assignee)
    except KeyError:
        raise HTTPException(404, "Alert not found.")
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"alert": _alert_to_dict(a)}


# ---------- traffic ----------
@router.get("/traffic")
def traffic(limit: int = Query(100, le=1000), offset: int = 0, source: str | None = None,
            db: Session = Depends(get_db)):
    q = db.query(m.Flow).order_by(desc(m.Flow.id))
    if source:
        q = q.filter(m.Flow.source == source)
    items = q.offset(offset).limit(limit).all()
    return {"items": [{"id": f.id, "ts": f.ts.isoformat(), "src_ip": f.src_ip, "dst_ip": f.dst_ip,
                       "src_port": f.src_port, "dst_port": f.dst_port, "protocol": f.protocol,
                       "prediction": f.prediction, "risk_score": f.risk_score,
                       "severity": f.severity, "source": f.source} for f in items]}


@router.get("/traffic/summary")
def traffic_summary(db: Session = Depends(get_db)):
    total = db.query(func.count(m.Flow.id)).scalar() or 0
    attacks = db.query(func.count(m.Flow.id)).filter(m.Flow.prediction != "BENIGN").scalar() or 0
    by_sev = dict(db.query(m.Flow.severity, func.count()).group_by(m.Flow.severity).all())
    by_pred = dict(db.query(m.Flow.prediction, func.count()).group_by(m.Flow.prediction).all())
    recent = db.query(m.Flow).order_by(desc(m.Flow.id)).limit(200).all()
    buckets: dict[str, dict] = {}
    for f in recent:
        key = f.ts.strftime("%H:%M") if f.ts else "?"
        b = buckets.setdefault(key, {"t": key, "flows": 0, "attacks": 0})
        b["flows"] += 1
        if f.prediction != "BENIGN":
            b["attacks"] += 1
    top_src = [
        {"ip": ip, "flows": n,
         "attacks": db.query(func.count(m.Flow.id)).filter(m.Flow.src_ip == ip, m.Flow.prediction != "BENIGN").scalar() or 0}
        for ip, n in db.query(m.Flow.src_ip, func.count(m.Flow.id)).group_by(m.Flow.src_ip)
        .order_by(desc(func.count(m.Flow.id))).limit(10).all()
    ]
    return {"total_flows": total, "attacks": attacks, "benign": total - attacks,
            "by_severity": by_sev, "by_prediction": by_pred, "top_sources": top_src,
            "timeseries": sorted(buckets.values(), key=lambda b: b["t"])}


@router.get("/traffic/by-day")
def traffic_by_day(days: int = Query(14, ge=1, le=90), db: Session = Depends(get_db)):
    """Attack frequency per day and predicted class (from stored flows)."""
    day_col = func.date(m.Flow.ts).label("day")
    rows = db.query(day_col, m.Flow.prediction, func.count(m.Flow.id)).group_by(day_col, m.Flow.prediction).all()
    by_day: dict[str, dict[str, int]] = {}
    for day, pred, n in rows:
        by_day.setdefault(str(day), {})[pred or "Unknown"] = int(n)
    out = [{"day": d, **counts} for d, counts in sorted(by_day.items())[-days:]]
    classes = sorted({p for counts in by_day.values() for p in counts})
    return {"days": out, "classes": classes}


# ---------- models ----------
@router.get("/models")
def list_models():
    from ml.registry.registry import list_models as _list
    return {"models": _list(settings.model_dir), "status": service.status()}


@router.get("/models/performance")
def model_performance():
    res_dir = Path(settings.model_dir).parent / "experiments" / "results"
    out = {}
    for name in ("standard_metrics", "ablation_metrics", "unseen_attack_metrics",
                 "temporal_metrics", "drift_metrics", "latency_metrics", "lstm_metrics"):
        p = res_dir / f"{name}.json"
        if p.exists():
            out[name] = json.loads(p.read_text(encoding="utf-8"))
    if not out:
        return {"status": "no_evaluation_run_yet",
                "message": "No evaluation has been run. Run scripts/evaluate_all.py on real data."}
    return _sanitize({"status": "ok", **out})


@router.get("/models/figures/{name}")
def model_figure(name: str):
    """Serve evaluation PNGs (confusion matrix, ROC, PR, calibration, ablation)."""
    safe = Path(name).name
    if not safe.endswith(".png") or len(safe) > 64:
        raise HTTPException(400, "Invalid figure name.")
    p = Path(settings.model_dir).parent / "experiments" / "figures" / safe
    if not p.is_file():
        raise HTTPException(404, "Figure not available. Run scripts/evaluate_all.py first.")
    return FileResponse(p, media_type="image/png")


@router.get("/drift/distributions")
def drift_distributions(feature: str = Query(..., min_length=1, max_length=128),
                        bins: int = Query(20, ge=5, le=50),
                        db: Session = Depends(get_db)):
    """Binned reference vs current histograms for one feature (shape of shift)."""
    import numpy as np
    ref_flows = db.query(m.Flow).order_by(m.Flow.id).limit(2000).all()
    cur_flows = db.query(m.Flow).order_by(desc(m.Flow.id)).limit(500).all()
    if not ref_flows or not cur_flows:
        raise HTTPException(400, "Not enough stored flows yet.")
    keys = set(ref_flows[0].features or {}) & set(cur_flows[0].features or {})
    if feature not in keys:
        raise HTTPException(400, f"Unknown feature. Available: {sorted(keys)[:50]}")
    ref = np.array([float((f.features or {}).get(feature, 0.0)) for f in ref_flows], dtype=float)
    cur = np.array([float((f.features or {}).get(feature, 0.0)) for f in cur_flows], dtype=float)
    ref = ref[np.isfinite(ref)]
    cur = cur[np.isfinite(cur)]
    if len(ref) == 0 or len(cur) == 0:
        raise HTTPException(400, "No finite values for this feature.")
    edges = np.quantile(ref, np.linspace(0, 1, bins + 1))
    edges = np.unique(edges)
    if len(edges) < 3:
        edges = np.linspace(float(ref.min()), float(ref.max() + 1e-9), bins + 1)
    r_hist, _ = np.histogram(ref, bins=edges)
    c_hist, _ = np.histogram(cur, bins=edges)
    centers = ((edges[:-1] + edges[1:]) / 2).tolist()
    return _sanitize({"feature": feature, "bins": len(centers),
                      "centers": [round(float(x), 4) for x in centers],
                      "reference": [int(x) for x in r_hist], "current": [int(x) for x in c_hist],
                      "n_reference": len(ref_flows), "n_current": len(cur_flows)})


# ---------- drift ----------
@router.get("/drift")
def drift_list(limit: int = 50, db: Session = Depends(get_db)):
    items = db.query(m.DriftEvent).order_by(desc(m.DriftEvent.ts)).limit(limit).all()
    return {"items": [{"id": d.id, "ts": d.ts.isoformat(), "reference_version": d.reference_version,
                       "aggregate_psi": d.aggregate_psi, "status": d.status,
                       "top_features": d.top_features, "adaptation_status": d.adaptation_status} for d in items]}


@router.get("/drift/features")
def drift_features(db: Session = Depends(get_db)):
    d = db.query(m.DriftEvent).order_by(desc(m.DriftEvent.ts)).first()
    if not d:
        return {"status": "no_drift_computed_yet", "features": []}
    return {"event_id": d.id, "features": (d.detail or {}).get("features", [])}


@router.get("/drift/events")
def drift_events(db: Session = Depends(get_db)):
    return {"events": _drift_items(db)}


def _drift_items(db: Session):
    return [{"id": d.id, "ts": d.ts.isoformat(), "aggregate_psi": d.aggregate_psi,
             "status": d.status, "adaptation_status": d.adaptation_status}
            for d in db.query(m.DriftEvent).order_by(desc(m.DriftEvent.ts)).limit(100).all()]


@router.post("/drift/compute")
async def drift_compute(req: DriftComputeRequest, db: Session = Depends(get_db)):
    from ml.drift.psi import compute_drift
    ref_flows = db.query(m.Flow).order_by(m.Flow.id).limit(2000).all()
    cur_flows = db.query(m.Flow).order_by(desc(m.Flow.id)).limit(req.current_window_rows).all()
    if len(ref_flows) < 50 or len(cur_flows) < 20:
        raise HTTPException(400, "Not enough stored flows to compute drift yet.")
    ref = pd.DataFrame([f.features for f in ref_flows])
    cur = pd.DataFrame([f.features for f in cur_flows])
    feats = [c for c in ref.columns if c in cur.columns]
    report = compute_drift(ref, cur, features=feats, reference_version=req.reference_version)
    top = sorted(report["features"], key=lambda r: r["psi"], reverse=True)[:5]
    ev = m.DriftEvent(reference_version=req.reference_version, aggregate_psi=report["aggregate_psi"],
                      status=report["status"], top_features=top, detail=report)
    db.add(ev)
    db.commit()
    await manager.broadcast({"type": "drift", **report})
    return report


@router.post("/system/threshold-proposal")
def threshold_proposal(p: ThresholdProposal, db: Session = Depends(get_db)):
    """Audited threshold change PROPOSAL with impact preview.

    Never mutates the live threshold: applying requires editing
    configs/ensemble.yaml and retraining/redeploying. The proposal, its
    author, reason and impact are audit-logged.
    """
    current = float(service.ens.decision_threshold) if (service.ens is not None) else 0.5
    flows = db.query(m.Flow.risk_score).all()
    scores = [r[0] for r in flows]
    if p.threshold < current:
        escalate = sum(1 for v in scores if p.threshold <= v < current)
        deescalate = 0
    else:
        escalate = 0
        deescalate = sum(1 for v in scores if current <= v < p.threshold)
    db.add(m.AuditLog(actor=p.actor, action="threshold.proposed", entity="ensemble",
                      detail={"from": current, "to": p.threshold, "reason": p.reason,
                              "would_escalate": escalate, "would_deescalate": deescalate}))
    db.add(m.SystemEvent(level="info", component="settings",
                         message=f"{p.actor} proposed decision threshold {current} -> {p.threshold}: {p.reason}"))
    db.commit()
    return {"applied": False, "current": current, "proposed": p.threshold,
            "would_escalate": escalate, "would_deescalate": deescalate, "n_flows": len(scores),
            "note": "Proposal recorded. Applying requires configs/ensemble.yaml + retrain/redeploy."}


@router.get("/drift/events/{event_id}")
def drift_event(event_id: int, db: Session = Depends(get_db)):
    d = db.query(m.DriftEvent).filter(m.DriftEvent.id == event_id).one_or_none()
    if not d:
        raise HTTPException(404, "Drift event not found.")
    return {"id": d.id, "ts": d.ts.isoformat(), "detail": d.detail,
            "adaptation_status": d.adaptation_status}


# ---------- threat intel ----------
@router.get("/threat-intel/{ip}")
def threat_intel(ip: str, db: Session = Depends(get_db)):
    from ml.threat_intel.providers import get_provider
    cached = db.query(m.ThreatIntelCache).filter(m.ThreatIntelCache.ip == ip).one_or_none()
    if cached and (datetime.datetime.utcnow() - cached.updated_at).days < 1:
        return {**cached.result, "cached": True}
    result = get_provider(settings.threat_intel_provider).lookup(ip).to_dict()
    if cached:
        cached.result, cached.provider = result, result["provider"]
    else:
        db.add(m.ThreatIntelCache(ip=ip, provider=result["provider"], result=result))
    db.commit()
    related = db.query(m.Alert).filter((m.Alert.src_ip == ip) | (m.Alert.dst_ip == ip)).limit(20).all()
    return {**result, "related_alerts": [_alert_to_dict(a) for a in related]}


# ---------- reports ----------
@router.get("/reports")
def reports(kind: str = "summary", date: str | None = Query(default=None, description="YYYY-MM-DD filter"),
            db: Session = Depends(get_db)):
    import datetime as _dt
    day = None
    if date:
        try:
            day = _dt.date.fromisoformat(date)
        except ValueError:
            raise HTTPException(400, "date must be YYYY-MM-DD.")
    fq = db.query(m.Flow)
    aq = db.query(m.Alert)
    if day is not None:
        fq = fq.filter(func.date(m.Flow.ts) == day)
        aq = aq.filter(func.date(m.Alert.created_at) == day)
    total = fq.count()
    attacks = fq.filter(m.Flow.prediction != "BENIGN").count()
    by_sev = dict(aq.with_entities(m.Alert.severity, func.count()).group_by(m.Alert.severity).all())
    by_attack = dict(aq.with_entities(m.Alert.attack_type, func.count()).group_by(m.Alert.attack_type).all())
    drift = db.query(m.DriftEvent).order_by(desc(m.DriftEvent.ts)).first()
    return {"kind": kind, "date": date, "generated_at": datetime.datetime.utcnow().isoformat() + "Z",
            "methodology": "Counts from the alerts/flows tables; model metrics only from experiments/results.",
            "summary": {"total_flows": total, "attacks": attacks, "alerts_by_severity": by_sev,
                        "alerts_by_attack": by_attack,
                        "latest_drift": drift.status if drift else "no_drift_computed_yet"}}


# ---------- websocket ----------
ws_router = APIRouter()


@ws_router.websocket("/ws/events")
async def ws_events(ws: WebSocket):
    await manager.connect(ws)
    try:
        await ws.send_json({"type": "hello", "message": "connected", "ts": time.time()})
        while True:
            try:
                await asyncio.wait_for(ws.receive_text(), timeout=30)
                await ws.send_json({"type": "heartbeat", "ts": time.time()})
            except asyncio.TimeoutError:
                await ws.send_json({"type": "heartbeat", "ts": time.time()})
    except WebSocketDisconnect:
        manager.disconnect(ws)

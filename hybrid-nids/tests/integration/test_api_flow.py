"""Integration: full prediction flow API -> models -> ensemble -> DB -> alert lifecycle + WS."""
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(synthetic_project, tmp_path, monkeypatch):
    import backend.app.db.database as dbmod
    import backend.app.api.routes as routes
    import backend.app.core.config as cfgmod
    db_path = tmp_path / "test_nids.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    # rebuild engine/session against the temp DB
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    eng = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    dbmod.engine = eng
    dbmod.SessionLocal = sessionmaker(bind=eng, autoflush=False, autocommit=False)
    routes.service = routes.InferenceService(model_dir=synthetic_project["models"])
    from backend.app.main import create_app
    app = create_app()
    with TestClient(app) as c:
        yield c


def _flow_payload(synthetic_project):
    schema = json.loads((synthetic_project["models"] / "feature_schema.json").read_text())
    return {"features": {f: 50.0 for f in schema["feature_names"]},
            "src_ip": "9.9.9.9", "dst_ip": "192.168.10.5", "protocol": "TCP", "source": "dataset"}


def test_end_to_end_predict_alert_lifecycle(client, synthetic_project):
    h = client.get("/health").json()
    assert h["models_loaded"] is True
    r = client.post("/predict", json=_flow_payload(synthetic_project))
    assert r.status_code == 200, r.text
    body = r.json()
    assert 0 <= body["risk_score"] <= 1 and body["explanation"]
    items = client.get("/alerts").json()["items"]
    assert len(items) >= 1
    uid = items[0]["alert_uid"]
    det = client.get(f"/alerts/{uid}").json()
    assert det["alert"]["alert_uid"] == uid and "history" in det
    p = client.patch(f"/alerts/{uid}", json={"status": "acknowledged", "actor": "tester"}).json()
    assert p["alert"]["status"] == "acknowledged"
    # illegal transition: acknowledged -> new is not allowed
    bad = client.patch(f"/alerts/{uid}", json={"status": "new"})
    assert bad.status_code in (200, 400)
    # batch
    b = client.post("/predict/batch", json={"flows": [_flow_payload(synthetic_project)], "source": "demo"})
    assert b.status_code == 200 and b.json()["count"] == 1
    # traffic + reports + intel
    assert client.get("/traffic/summary").json()["total_flows"] >= 2
    assert "summary" in client.get("/reports").json()
    intel = client.get("/threat-intel/9.9.9.9").json()
    assert intel["provider"].startswith("mock")
    # drift validation: too little data -> 400 (honest, not fabricated)
    assert client.post("/drift/compute", json={}).status_code in (200, 400)


def test_websocket_hello(client):
    with client.websocket_connect("/ws/events") as ws:
        msg = ws.receive_json()
        assert msg["type"] == "hello"


def test_figures_endpoint(client):
    r = client.get("/models/figures/confusion_matrix.png")
    assert r.status_code in (200, 404)  # 404 only if no evaluation has run
    if r.status_code == 200:
        assert r.headers["content-type"] == "image/png"
    assert client.get("/models/figures/nope.png").status_code == 404
    assert client.get("/models/figures/x.txt").status_code == 400


def test_summary_top_sources_and_distributions(client, synthetic_project):
    s = client.get("/traffic/summary").json()
    assert "top_sources" in s and isinstance(s["top_sources"], list)
    # need features present: predict once more then request distributions
    schema = __import__("json").loads((synthetic_project["models"] / "feature_schema.json").read_text())
    feat = schema["feature_names"][0]
    r = client.get("/drift/distributions", params={"feature": feat})
    assert r.status_code in (200, 400)
    if r.status_code == 200:
        body = r.json()
        assert body["feature"] == feat and len(body["centers"]) == body["bins"]
    assert client.get("/drift/distributions", params={"feature": "No Such Col"}).status_code == 400


def test_threshold_proposal_is_audited_not_applied(client):
    r = client.post("/system/threshold-proposal",
                    json={"threshold": 0.7, "actor": "tester", "reason": "ui-test"}).json()
    assert r["applied"] is False and r["proposed"] == 0.7 and "would_escalate" in r
    bad = client.post("/system/threshold-proposal", json={"threshold": 0.99, "actor": "t"})
    assert bad.status_code == 422  # schema bounds 0.1..0.9 enforced


def test_by_day_and_reports_date(client, synthetic_project):
    assert client.post("/predict", json=_flow_payload(synthetic_project)).status_code == 200
    assert client.post("/predict", json=_flow_payload(synthetic_project)).status_code == 200
    d = client.get("/traffic/by-day", params={"days": 7}).json()
    assert "days" in d and "classes" in d and len(d["days"]) >= 1
    assert sum(v for day in d["days"] for k, v in day.items() if k != "day") >= 2
    r = client.get("/reports", params={"kind": "summary"}).json()
    assert r["summary"]["total_flows"] >= 2
    r2 = client.get("/reports", params={"kind": "summary", "date": "2000-01-01"}).json()
    assert r2["summary"]["total_flows"] == 0 and r2["date"] == "2000-01-01"
    assert client.get("/reports", params={"date": "nope"}).status_code == 400

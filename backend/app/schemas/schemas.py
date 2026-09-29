"""Pydantic request/response schemas. Every request is validated."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

Source = Literal["dataset", "live", "demo"]
AlertStatus = Literal["new", "investigating", "acknowledged", "resolved", "dismissed"]


class FlowFeatures(BaseModel):
    features: dict[str, float] = Field(description="Flow feature name -> value (must cover trained schema)")
    src_ip: str = ""
    dst_ip: str = ""
    src_port: int = 0
    dst_port: int = 0
    protocol: str = ""
    timestamp: str | None = None
    source: Source = "dataset"


class BatchPredictRequest(BaseModel):
    flows: list[FlowFeatures] = Field(min_length=1, max_length=500)
    source: Source = "dataset"


class AlertPatch(BaseModel):
    status: AlertStatus | None = None
    assignee: str | None = None
    note: str | None = None
    actor: str = "analyst"


class DriftComputeRequest(BaseModel):
    reference_version: str = "baseline-v1"
    current_window_rows: int = Field(default=500, ge=50, le=10000)


class ThresholdProposal(BaseModel):
    threshold: float = Field(ge=0.1, le=0.9)
    actor: str = "analyst"
    reason: str = ""


class HealthResponse(BaseModel):
    status: str
    backend_version: str
    models_loaded: bool
    models: dict[str, Any]
    demo_mode: bool
    ingestion_mode: str

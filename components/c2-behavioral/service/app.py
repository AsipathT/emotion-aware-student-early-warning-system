"""
FastAPI application for Component 2 (Behavioral Engagement Trajectory) service.
"""

from typing import Any, Dict, List, Optional
from fastapi import FastAPI, HTTPException, Request
import joblib
from pydantic import BaseModel, ConfigDict

from service.pipeline import classify_records
from service.schemas import BehaviorRecord, build_envelope
from service.settings import settings


class ClassifyRequest(BaseModel):
    """Payload for POST /classify."""

    model_config = ConfigDict(extra="forbid")

    records: List[BehaviorRecord]
    week: Optional[int] = None


def create_app(bundle: Optional[Dict[str, Any]] = None) -> FastAPI:
    """
    Constructs FastAPI instance configured with model bundle.
    If bundle is None, attempts to load from settings.C2_MODEL_PATH.
    If model file is missing, the app still launches but /classify returns 503.
    """
    app = FastAPI(
        title="Component 2 Behavioral Trajectory Service",
        version="1.0.0",
        description="Predicts student engagement trajectories and returns contributing indicators.",
    )

    if bundle is not None:
        app.state.bundle = bundle
    else:
        model_path = settings.C2_MODEL_PATH
        if model_path.is_file():
            try:
                app.state.bundle = joblib.load(model_path)
            except Exception:
                app.state.bundle = None
        else:
            app.state.bundle = None

    @app.get("/health")
    def health() -> Dict[str, Any]:
        has_model = app.state.bundle is not None
        version = app.state.bundle.get("version") if has_model else None
        return {
            "status": "ok",
            "model_loaded": has_model,
            "model_version": version,
        }

    @app.post("/classify")
    def classify(payload: ClassifyRequest) -> Dict[str, Any]:
        if len(payload.records) > 5000:
            raise HTTPException(
                status_code=413,
                detail="Batch exceeds maximum limit of 5000 records.",
            )

        if app.state.bundle is None:
            raise HTTPException(
                status_code=503,
                detail="Model bundle is unavailable or not loaded.",
            )

        trajectory_records, stats = classify_records(
            payload.records, app.state.bundle, target_week=payload.week
        )
        envelope = build_envelope(trajectory_records)

        return {
            "envelope": envelope,
            "stats": stats,
        }

    return app


app = create_app()

"""Turns one set of student inputs into a stored recommendation record."""
import uuid
from datetime import datetime, timezone

from . import reference


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def build_assessment(model, student_id: str, inputs: dict, username: str, created_at: str | None = None) -> dict:
    """inputs: c1_condition, c2_trajectory, risk_probability, c3 {affective, behavioural, academic}."""
    c3 = {k: round(float(inputs["c3"][k]), 2) for k in ("affective", "behavioural", "academic")}
    probability = round(float(inputs["risk_probability"]), 2)
    c1, c2 = inputs["c1_condition"], inputs["c2_trajectory"]
    tier = reference.risk_tier(probability)
    dominant = reference.dominant_c3(c3)
    top3 = model.rank(c1, c2, tier, dominant)[:3]
    best = top3[0]
    rationale = (
        f"{best['intervention']} has the highest suitability score ({best['suitability']:.0%}) from the "
        f"{model.name} model for a student with {c1} (C1), a {c2.lower()} trajectory (C2), "
        f"{tier.lower()} dropout risk ({probability:.2f}) and {dominant.lower()} factors as the strongest cause (C3)."
    )
    return {
        "id": uuid.uuid4().hex[:12],
        "student_id": student_id,
        "created_at": created_at or now_iso(),
        "created_by": username,
        "inputs": {
            "c1_condition": c1,
            "c2_trajectory": c2,
            "risk_probability": probability,
            "risk_tier": tier,
            "c3": c3,
            "c3_dominant": dominant,
        },
        "recommendations": top3,
        "model": model.name,
        "rationale": rationale,
        "explanation": None,
    }

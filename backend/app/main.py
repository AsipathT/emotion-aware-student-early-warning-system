"""FastAPI backend for the C4 intervention recommendation app.

Run from the backend folder:  uvicorn app.main:app --reload --port 8000
"""
import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator, model_validator

from . import config, reference
from .auth import create_token, make_current_user_dependency, public_user, verify_password
from .explain import ExplanationUnavailable, generate_explanation
from .model_service import InterventionModel
from .recommend import build_assessment
from .seed import ensure_seed_data
from .storage import JsonStore

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
log = logging.getLogger("c4")

users_store = JsonStore(config.DATA_DIR / "users.json")
students_store = JsonStore(config.DATA_DIR / "students.json")
assessments_store = JsonStore(config.DATA_DIR / "assessments.json")
current_user = make_current_user_dependency(users_store)

state = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    state["model"] = InterventionModel(config.MODEL_PATH, config.TRAINING_DATA_PATH)
    log.info("Model ready: %s (%d interventions)", state["model"].name, len(state["model"].classes))
    ensure_seed_data(users_store, students_store, assessments_store, state["model"])
    if config.JWT_SECRET_IS_RANDOM:
        log.warning("JWT_SECRET is not set: using a random one, so logins end when the server restarts.")
    if not config.OPENAI_API_KEY:
        log.warning("OPENAI_API_KEY is not set: AI explanations are turned off.")
    yield


app = FastAPI(title="C4 Intervention Recommendation API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware, allow_origins=config.CORS_ORIGINS, allow_methods=["*"], allow_headers=["*"])


# ---------- request bodies ----------

class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=200)


class C3Input(BaseModel):
    affective: float = Field(ge=0, le=1)
    behavioural: float = Field(ge=0, le=1)
    academic: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def not_all_zero(self):
        if self.affective + self.behavioural + self.academic <= 0:
            raise ValueError("At least one C3 value must be above 0.")
        return self


class AssessmentCreate(BaseModel):
    c1_condition: str
    c2_trajectory: str
    risk_probability: float = Field(ge=0, le=1)
    c3: C3Input

    @field_validator("c1_condition")
    @classmethod
    def known_condition(cls, value):
        if value not in reference.CONDITIONS:
            raise ValueError(f"Must be one of: {', '.join(reference.CONDITIONS)}")
        return value

    @field_validator("c2_trajectory")
    @classmethod
    def known_trajectory(cls, value):
        if value not in reference.TRAJECTORIES:
            raise ValueError(f"Must be one of: {', '.join(reference.TRAJECTORIES)}")
        return value


class ExplanationRequest(BaseModel):
    refresh: bool = False


# ---------- helpers ----------

def find_student(student_id: str) -> dict:
    student = next((s for s in students_store.read() if s["id"] == student_id), None)
    if student is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Student {student_id} not found.")
    return student


def assessments_for(student_id: str | None = None) -> list[dict]:
    """Assessments, newest first."""
    records = assessments_store.read()
    if student_id is not None:
        records = [a for a in records if a["student_id"] == student_id]
    return sorted(records, key=lambda a: a["created_at"], reverse=True)


def past_assessments(assessment: dict, limit: int = 5) -> list[dict]:
    """Earlier assessments of the same student, oldest first."""
    earlier = [a for a in assessments_for(assessment["student_id"]) if a["created_at"] < assessment["created_at"]]
    return list(reversed(earlier[:limit]))


def summary(assessment: dict | None) -> dict | None:
    if assessment is None:
        return None
    top = assessment["recommendations"][0]
    return {
        "id": assessment["id"],
        "created_at": assessment["created_at"],
        "risk_probability": assessment["inputs"]["risk_probability"],
        "risk_tier": assessment["inputs"]["risk_tier"],
        "c2_trajectory": assessment["inputs"]["c2_trajectory"],
        "top_intervention": top["intervention"],
        "suitability": top["suitability"],
    }


# ---------- routes ----------

@app.get("/api/health")
def health():
    return {"status": "ok", "model": state["model"].name, "openai_configured": bool(config.OPENAI_API_KEY)}


@app.post("/api/auth/login")
def login(body: LoginRequest):
    user = next((u for u in users_store.read() if u["username"] == body.username.strip()), None)
    if user is None or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect username or password.")
    return {"token": create_token(user["username"]), "user": public_user(user)}


@app.get("/api/auth/me")
def me(user: dict = Depends(current_user)):
    return user


@app.get("/api/reference")
def get_reference(user: dict = Depends(current_user)):
    return {
        "conditions": reference.CONDITIONS,
        "trajectories": reference.TRAJECTORIES,
        "risk_tier_bounds": [{"upper": upper, "tier": tier} for upper, tier in reference.RISK_TIER_BOUNDS],
        "c3_dimensions": reference.C3_DIMENSIONS,
        "interventions": reference.INTERVENTIONS,
        "model": state["model"].name,
        "openai_configured": bool(config.OPENAI_API_KEY),
        "openai_model": config.OPENAI_MODEL,
    }


@app.get("/api/students")
def list_students(user: dict = Depends(current_user)):
    by_student = {}
    for assessment in assessments_for():
        by_student.setdefault(assessment["student_id"], []).append(assessment)
    return [
        {**s, "assessment_count": len(by_student.get(s["id"], [])),
         "latest_assessment": summary((by_student.get(s["id"]) or [None])[0])}
        for s in students_store.read()
    ]


@app.get("/api/students/{student_id}")
def get_student(student_id: str, user: dict = Depends(current_user)):
    student = find_student(student_id)
    history = assessments_for(student_id)
    return {"student": student, "latest_assessment": history[0] if history else None,
            "history": [summary(a) for a in history]}


@app.post("/api/students/{student_id}/assessments", status_code=status.HTTP_201_CREATED)
def create_assessment(student_id: str, body: AssessmentCreate, user: dict = Depends(current_user)):
    find_student(student_id)
    record = build_assessment(state["model"], student_id, body.model_dump(), user["username"])
    return assessments_store.append(record)


@app.get("/api/assessments")
def list_assessments(student_id: str | None = None, user: dict = Depends(current_user)):
    names = {s["id"]: s["name"] for s in students_store.read()}
    return [
        {**summary(a), "student_id": a["student_id"], "student_name": names.get(a["student_id"], a["student_id"]),
         "c1_condition": a["inputs"]["c1_condition"], "c3_dominant": a["inputs"]["c3_dominant"]}
        for a in assessments_for(student_id)
    ]


def find_assessment(assessment_id: str) -> dict:
    assessment = next((a for a in assessments_store.read() if a["id"] == assessment_id), None)
    if assessment is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Assessment not found.")
    return assessment


@app.get("/api/assessments/{assessment_id}")
def get_assessment(assessment_id: str, user: dict = Depends(current_user)):
    assessment = find_assessment(assessment_id)
    student = find_student(assessment["student_id"])
    return {"assessment": assessment, "student": student, "past": past_assessments(assessment)}


@app.post("/api/assessments/{assessment_id}/explanation")
def explain_assessment(assessment_id: str, body: ExplanationRequest | None = None,
                       user: dict = Depends(current_user)):
    assessment = find_assessment(assessment_id)
    if assessment.get("explanation") and not (body and body.refresh):
        return assessment["explanation"]
    student = find_student(assessment["student_id"])
    try:
        explanation = generate_explanation(student, assessment, past_assessments(assessment))
    except ExplanationUnavailable as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc))
    assessments_store.update(assessment_id, {"explanation": explanation})
    return explanation

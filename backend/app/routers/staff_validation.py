"""
backend/app/routers/staff_validation.py

Feature 36: Counsellor Validation Tools Router (Component 1 & Component 4 Ground-Truth).
Provides:
  - C1 Distress Labelling Queue (blind by default, deterministic reproducible ordering)
  - C1 Distress Label Confirmation & Reveal (side-by-side agree/disagree evaluation)
  - C1 Statistical Summary (Cohen's Kappa, Landis-Koch bands, Confusion Matrix, Per-class metrics, Inter-rater kappa)
  - C4 Recommendation Appropriateness Rating Queue & Submission
  - C4 Ranking Metrics Summary (P@1, P@3, NDCG@3, Top-1 Acceptable rate, Review mix)
  - Admin-only Research Export (schema "validation-export-1.0", comments strictly omitted, audited)
"""

from datetime import datetime, timezone
import hashlib
import logging
from typing import Any, Dict, List, Optional
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.database import get_db
from app.core.dependencies import get_current_admin
from app.core.privacy import scrub_text
from app.db import collections as col
from app.models.intervention_record import COL_RECOMMENDATION_REVIEWS
from app.models.user import User
from app.models.validation import (
    COL_RECOMMENDATION_RATINGS,
    COL_VALIDATION_LABELS,
)
from app.routers.export import get_eligible_consenting_pids
from app.schemas.audit import AuditAction, AuditOutcome
from app.schemas.staff_validation import (
    C1ClassMetricsItem,
    C1LabelCreateRequest,
    C1LabelCreateResponse,
    C1QueueItemResponse,
    C1QueueMessageItem,
    C1SummaryResponse,
    C4CandidateItem,
    C4QueueItemResponse,
    C4RatingCreateRequest,
    C4RatingCreateResponse,
    C4SummaryResponse,
    ValidationExportC1LabelRow,
    ValidationExportC4RatingRow,
    ValidationExportResponse,
)
from app.services.affective_explain import dominant_class
from app.services.audit import log_event
from app.services.intervention_catalog import (
    delivery_module_for,
    get_label,
    get_student_label,
)
from app.services.staff_access import (
    audit_student_view,
    is_pid_visible,
    require_staff,
    validate_pid,
)
from app.services.validation_stats import (
    calculate_c1_inter_rater_kappa,
    cohen_kappa,
    confusion_matrix,
    ndcg_at_k,
    per_class_precision_recall,
    precision_at_k,
)

logger = logging.getLogger("app.staff_validation")

router = APIRouter(
    prefix="/api/v1/staff/validation",
    tags=["Staff Validation"],
)

C1_CLASSES: List[str] = [
    "exam_anxiety",
    "conceptual_confusion",
    "academic_helplessness",
    "course_frustration",
    "motivation_erosion",
    "none",
]


# ── Component 1: Distress Labelling Workspace ─────────────────────────────────

@router.get(
    "/c1/queue",
    response_model=List[C1QueueItemResponse],
    summary="Get next unlabelled affective items for blind counsellor confirmation",
)
async def get_c1_validation_queue(
    request: Request,
    course_id: Optional[str] = Query(None, description="Optional course filter"),
    limit: int = Query(10, ge=1, le=50, description="Batch size (max 50)"),
    blind: bool = Query(True, description="Enforce blind review (must be true for unlabelled items)"),
    current_user: User = Depends(require_staff),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """
    Returns unlabelled weekly affective observation units for the calling reviewer.
    BLIND ENFORCEMENT:
      - blind=true returns only scrubbed text evidence without model prediction or scores.
      - blind=false is rejected with 422 to prevent anchoring bias.
    SAMPLING:
      - Deterministic reproducible ordering via SHA-256 hash of (pid:course:week).
    """
    if not blind:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="blind=false is prohibited for unlabelled items in queue to prevent anchoring bias.",
        )

    # 1. Resolve consented cohort
    eligible_pids = await get_eligible_consenting_pids(db)
    if not eligible_pids:
        return []

    # 2. Collect items already labelled by this reviewer
    reviewer_id_str = str(current_user.id)
    labelled_cursor = db[COL_VALIDATION_LABELS].find(
        {"reviewer_id": reviewer_id_str, "kind": "c1_distress"},
        {"pid": 1, "course_id": 1, "week_index": 1},
    )
    already_labelled: set = set()
    async for lbl in labelled_cursor:
        already_labelled.add((str(lbl.get("pid")), str(lbl.get("course_id")), int(lbl.get("week_index", 0))))

    # 3. Query candidate affective weekly observations
    match_query: Dict[str, Any] = {"pid": {"$in": list(eligible_pids)}}
    if course_id and course_id.strip():
        match_query["course_id"] = course_id.strip()

    candidate_docs = await db[col.AFFECTIVE_WEEKLY].find(match_query).to_list(length=5000)

    # 4. Filter out already-labelled items
    unlabelled = [
        d for d in candidate_docs
        if (str(d.get("pid")), str(d.get("course_id")), int(d.get("week_index", 0))) not in already_labelled
    ]

    # 5. Deterministic hash ordering for reproducible sampling
    def hash_key(doc: Dict[str, Any]) -> str:
        s = f"{doc.get('pid')}:{doc.get('course_id')}:{doc.get('week_index', 0)}"
        return hashlib.sha256(s.encode("utf-8")).hexdigest()

    unlabelled.sort(key=hash_key)
    selected_docs = unlabelled[:limit]

    # 6. Fetch scrubbed messages for each observation unit
    queue_items: List[C1QueueItemResponse] = []
    for doc in selected_docs:
        c_pid = str(doc.get("pid"))
        c_cid = str(doc.get("course_id"))
        c_wid = int(doc.get("week_index", 0))

        msg_cursor = db[col.MESSAGES].find({
            "pid": c_pid,
            "course_id": c_cid,
            "week_index": c_wid,
        }).sort("timestamp", 1).limit(50)

        raw_msgs = await msg_cursor.to_list(length=50)
        messages_list = [
            C1QueueMessageItem(
                message_id=str(m.get("message_id") or m.get("_id")),
                source_type=str(m.get("source_type") or "unknown"),
                timestamp=m["timestamp"],
                clean_text=str(m.get("clean_text") or ""),
            )
            for m in raw_msgs
        ]

        queue_items.append(
            C1QueueItemResponse(
                item_id=f"{c_pid}:{c_cid}:{c_wid}",
                pid=c_pid,
                course_id=c_cid,
                week_index=c_wid,
                message_count=len(messages_list),
                messages=messages_list,
                blind=True,
            )
        )

    # Audited view access
    await audit_student_view(
        request,
        db,
        current_user,
        pid="cohort",
        view="validation_c1_queue",
        course_id=course_id,
    )

    return queue_items


@router.post(
    "/c1/labels",
    response_model=C1LabelCreateResponse,
    summary="Record counsellor ground-truth confirmation on affective distress",
)
async def submit_c1_validation_label(
    payload: C1LabelCreateRequest,
    current_user: User = Depends(require_staff),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """
    Saves expert counsellor label for a student's weekly affective state.
    REVEAL MECHANISM:
      - Upon submission, reveals model prediction and score for immediate side-by-side comparison.
      - 409 Conflict if this reviewer has already labelled this weekly observation.
    """
    clean_pid = validate_pid(payload.pid)
    cid = payload.course_id.strip()
    wid = int(payload.week_index)
    reviewer_id_str = str(current_user.id)

    # 1. Verify consent visibility
    visible = await is_pid_visible(db, clean_pid)
    if not visible:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Student record '{clean_pid}' not found or consent not active.",
        )

    # 2. Check for duplicate label (once per reviewer per unit)
    existing = await db[COL_VALIDATION_LABELS].find_one({
        "reviewer_id": reviewer_id_str,
        "pid": clean_pid,
        "course_id": cid,
        "week_index": wid,
    })
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You have already submitted a ground-truth label for this observation.",
        )

    # 3. Retrieve model prediction from affective_weekly
    aff_doc = await db[col.AFFECTIVE_WEEKLY].find_one({
        "pid": clean_pid,
        "course_id": cid,
        "week_index": wid,
    })
    if aff_doc:
        dom_cls, dom_score = dominant_class(aff_doc.get("emotion_scores"))
    else:
        dom_cls = "none"
        dom_score = 0.0

    label_id = str(uuid.uuid4())
    label_doc = {
        "id": label_id,
        "label_id": label_id,
        "kind": "c1_distress",
        "pid": clean_pid,
        "course_id": cid,
        "week_index": wid,
        "model_top_class": dom_cls,
        "model_top_score": dom_score,
        "counsellor_label": payload.counsellor_label,
        "confidence": payload.confidence,
        "reviewer_id": reviewer_id_str,
        "created_at": datetime.now(timezone.utc),
    }

    try:
        await db[COL_VALIDATION_LABELS].insert_one(label_doc)
    except Exception as exc:
        if "duplicate key" in str(exc).lower():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="You have already submitted a ground-truth label for this observation.",
            )
        raise

    logger.info(
        "[Validation C1] Reviewer %s labelled (%s, %s, W%d) as '%s' (Model was '%s' score=%.3f)",
        reviewer_id_str,
        clean_pid,
        cid,
        wid,
        payload.counsellor_label,
        dom_cls,
        dom_score,
    )

    return C1LabelCreateResponse(
        label_id=label_id,
        pid=clean_pid,
        course_id=cid,
        week_index=wid,
        counsellor_label=payload.counsellor_label,
        confidence=payload.confidence,
        model_top_class=dom_cls,
        model_top_score=dom_score,
        agreement=(payload.counsellor_label == dom_cls),
        message="Label recorded successfully. Model prediction revealed.",
    )


@router.get(
    "/c1/summary",
    response_model=C1SummaryResponse,
    summary="Get aggregate statistical validation metrics for Component 1",
)
async def get_c1_validation_summary(
    request: Request,
    course_id: Optional[str] = Query(None, description="Optional filter by course"),
    current_user: User = Depends(require_staff),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """
    Computes statistical evaluation for Component 1:
      - Observed agreement percentage
      - Cohen's Kappa coefficient (Model vs Counsellor) with Landis-Koch band
      - 2D Confusion Matrix
      - Per-class Precision, Recall, F1 and Macro-F1
      - Inter-rater Kappa across items labelled by >= 2 distinct human reviewers
    """
    match_query: Dict[str, Any] = {"kind": "c1_distress"}
    if course_id and course_id.strip():
        match_query["course_id"] = course_id.strip()

    cursor = db[COL_VALIDATION_LABELS].find(match_query)
    all_labels = await cursor.to_list(length=10000)

    n_items = len(all_labels)
    if n_items == 0:
        empty_matrix = {c: {c2: 0 for c2 in C1_CLASSES} for c in C1_CLASSES}
        empty_per_class = {
            c: C1ClassMetricsItem(precision=0.0, recall=0.0, f1=0.0, support=0)
            for c in C1_CLASSES
        }
        return C1SummaryResponse(
            n_items=0,
            agreement_pct=0.0,
            cohen_kappa=0.0,
            cohen_kappa_band="N/A (no labels recorded yet)",
            confusion_matrix=empty_matrix,
            per_class_metrics=empty_per_class,
            macro_f1=0.0,
            inter_rater_kappa=None,
            inter_rater_band=None,
        )

    # Truth = Counsellor Label; Prediction = Model Dominant Class
    counsellor_choices = [str(l["counsellor_label"]) for l in all_labels]
    model_preds = [str(l["model_top_class"]) for l in all_labels]
    pairs = list(zip(counsellor_choices, model_preds))

    # 1. Agreement %
    matches = sum(1 for t, p in pairs if t == p)
    agreement_pct = round((matches / n_items) * 100, 2)

    # 2. Cohen's Kappa
    kappa, band = cohen_kappa(counsellor_choices, model_preds)

    # 3. Confusion Matrix
    matrix = confusion_matrix(pairs, C1_CLASSES)

    # 4. Per-Class Precision / Recall / Macro-F1
    class_stats, macro_f1 = per_class_precision_recall(pairs, C1_CLASSES)
    per_class_typed = {
        cls_key: C1ClassMetricsItem(
            precision=metrics["precision"],
            recall=metrics["recall"],
            f1=metrics["f1"],
            support=int(metrics["support"]),
        )
        for cls_key, metrics in class_stats.items()
    }

    # 5. Inter-rater agreement for multi-reviewed items
    inter_rater_result = calculate_c1_inter_rater_kappa(all_labels)
    inter_rater_kappa, inter_rater_band = (
        inter_rater_result if inter_rater_result else (None, None)
    )

    # Audit query
    await audit_student_view(
        request,
        db,
        current_user,
        pid="cohort",
        view="validation_c1_summary",
        course_id=course_id,
    )

    return C1SummaryResponse(
        n_items=n_items,
        agreement_pct=agreement_pct,
        cohen_kappa=kappa,
        cohen_kappa_band=band,
        confusion_matrix=matrix,
        per_class_metrics=per_class_typed,
        macro_f1=macro_f1,
        inter_rater_kappa=inter_rater_kappa,
        inter_rater_band=inter_rater_band,
    )


# ── Component 4: Recommendation Appropriateness Workspace ────────────────────

@router.get(
    "/c4/queue",
    response_model=List[C4QueueItemResponse],
    summary="Get recommendations unrated by this reviewer",
)
async def get_c4_validation_queue(
    request: Request,
    limit: int = Query(10, ge=1, le=50, description="Items to return"),
    current_user: User = Depends(require_staff),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """
    Returns intervention recommendations that have not yet been evaluated by the calling reviewer.
    Presents candidate rankings, suitability scores, and generated rationales.
    """
    reviewer_id_str = str(current_user.id)

    # 1. Resolve recommendations already rated by this reviewer
    rated_ids = await db[COL_RECOMMENDATION_RATINGS].distinct(
        "recommendation_id",
        {"reviewer_id": reviewer_id_str},
    )

    # 2. Resolve active consenting cohort
    eligible_pids = await get_eligible_consenting_pids(db)
    if not eligible_pids:
        return []

    # 3. Query candidate recommendations
    match_query: Dict[str, Any] = {
        "pid": {"$in": list(eligible_pids)},
    }
    if rated_ids:
        match_query["$and"] = [
            {"recommendation_id": {"$nin": rated_ids}},
            {"id": {"$nin": rated_ids}},
        ]

    recs = (
        await db[col.RECOMMENDATIONS]
        .find(match_query)
        .sort("created_at", -1)
        .limit(limit)
        .to_list(length=limit)
    )

    queue_items: List[C4QueueItemResponse] = []
    for r in recs:
        rec_id = str(r.get("recommendation_id") or r.get("id") or r.get("_id"))
        pid = str(r.get("pid"))
        wid = int(r.get("week_index", 0))

        # Join risk tier
        risk_doc = await db[col.RISK_ASSESSMENTS].find_one({"pid": pid, "week_index": wid})
        risk_tier = str(risk_doc.get("risk_tier")).lower() if risk_doc and risk_doc.get("risk_tier") else None
        course_id = str(risk_doc.get("course_id")) if risk_doc and risk_doc.get("course_id") else None

        raw_candidates = r.get("candidates") or []
        sorted_candidates = sorted(raw_candidates, key=lambda c: int(c.get("rank", 99)))

        candidates_list = [
            C4CandidateItem(
                rank=int(c.get("rank", idx + 1)),
                intervention_type=str(c.get("intervention_type", "other")),
                label=get_label(str(c.get("intervention_type", "other"))),
                student_label=get_student_label(str(c.get("intervention_type", "other"))),
                delivery_module=delivery_module_for(str(c.get("intervention_type", "other"))),
                suitability_score=round(float(c.get("suitability_score", 0.0)), 4),
                rationale=str(c.get("rationale") or "").strip(),
            )
            for idx, c in enumerate(sorted_candidates)
        ]

        queue_items.append(
            C4QueueItemResponse(
                recommendation_id=rec_id,
                pid=pid,
                course_id=course_id,
                week_index=wid,
                risk_tier=risk_tier,
                candidates=candidates_list,
                created_at=r.get("created_at") or datetime.now(timezone.utc),
            )
        )

    # Audited view
    await audit_student_view(
        request,
        db,
        current_user,
        pid="cohort",
        view="validation_c4_queue",
    )

    return queue_items


@router.post(
    "/c4/ratings",
    response_model=C4RatingCreateResponse,
    summary="Record counsellor appropriateness rating on recommendation",
)
async def submit_c4_validation_rating(
    payload: C4RatingCreateRequest,
    current_user: User = Depends(require_staff),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """
    Records human expert evaluation of recommendation appropriateness and candidate ranks.
    Guarantees:
      - Validates recommendation exists
      - Validates suitable_ranks contains valid candidate ranks (422 on invalid ranks)
      - Enforces uniqueness per reviewer (409 Conflict on duplicate)
      - Free-text comment scrubbed via scrub_text prior to storage
    """
    clean_rec_id = str(payload.recommendation_id).strip()
    reviewer_id_str = str(current_user.id)

    # 1. Look up recommendation
    rec = await db[col.RECOMMENDATIONS].find_one({
        "$or": [{"recommendation_id": clean_rec_id}, {"id": clean_rec_id}, {"_id": clean_rec_id}]
    })
    if not rec:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Recommendation '{clean_rec_id}' not found.",
        )

    # 2. Check for duplicate rating by this reviewer
    existing = await db[COL_RECOMMENDATION_RATINGS].find_one({
        "recommendation_id": clean_rec_id,
        "reviewer_id": reviewer_id_str,
    })
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You have already rated this recommendation.",
        )

    # 3. Validate suitable_ranks adhere to available candidate ranks
    candidates = rec.get("candidates") or []
    valid_ranks = {int(c.get("rank", idx + 1)) for idx, c in enumerate(candidates)}
    for r in payload.suitable_ranks:
        if r not in valid_ranks:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Rank {r} in suitable_ranks is invalid. Available ranks are: {sorted(valid_ranks)}.",
            )

    # 4. Scrub qualitative comment if provided
    scrubbed_comment = None
    if payload.comment and payload.comment.strip():
        scrubbed_comment, _ = scrub_text(payload.comment.strip())

    rating_id = str(uuid.uuid4())
    rating_doc = {
        "id": rating_id,
        "recommendation_id": clean_rec_id,
        "reviewer_id": reviewer_id_str,
        "appropriateness": payload.appropriateness,
        "suitable_ranks": payload.suitable_ranks,
        "top1_acceptable": payload.top1_acceptable,
        "comment": scrubbed_comment,
        "created_at": datetime.now(timezone.utc),
    }

    try:
        await db[COL_RECOMMENDATION_RATINGS].insert_one(rating_doc)
    except Exception as exc:
        if "duplicate key" in str(exc).lower():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="You have already rated this recommendation.",
            )
        raise

    logger.info(
        "[Validation C4] Reviewer %s rated recommendation %s (appr=%d, top1=%s, ranks=%s)",
        reviewer_id_str,
        clean_rec_id,
        payload.appropriateness,
        payload.top1_acceptable,
        payload.suitable_ranks,
    )

    return C4RatingCreateResponse(
        rating_id=rating_id,
        recommendation_id=clean_rec_id,
        appropriateness=payload.appropriateness,
        suitable_ranks=payload.suitable_ranks,
        top1_acceptable=payload.top1_acceptable,
        message="Recommendation rating recorded successfully.",
    )


@router.get(
    "/c4/summary",
    response_model=C4SummaryResponse,
    summary="Get aggregate statistical ranking metrics for Component 4",
)
async def get_c4_validation_summary(
    request: Request,
    current_user: User = Depends(require_staff),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """
    Computes ranking evaluation statistics for Component 4:
      - Mean Appropriateness (1-5 Likert)
      - Precision@1, Precision@3
      - Normalized Discounted Cumulative Gain at 3 (NDCG@3)
      - Top-1 Acceptable rate
      - Operational human review decision mix (approved, modified, rejected)
    """
    ratings = await db[COL_RECOMMENDATION_RATINGS].find({}).to_list(length=10000)

    n = len(ratings)
    if n == 0:
        return C4SummaryResponse(
            n=0,
            mean_appropriateness=0.0,
            precision_at_1=0.0,
            precision_at_3=0.0,
            ndcg_at_3=0.0,
            top1_acceptable_rate=0.0,
            acceptance_mix={"total": 0, "approved": 0, "modified": 0, "rejected": 0},
        )

    # 1. Appropriateness
    mean_appr = round(sum(int(r["appropriateness"]) for r in ratings) / n, 2)

    # 2. Precision@K and NDCG@3
    p1_scores = [precision_at_k(r.get("suitable_ranks", []), 1) for r in ratings]
    p3_scores = [precision_at_k(r.get("suitable_ranks", []), 3) for r in ratings]
    ndcg3_scores = [ndcg_at_k(r.get("suitable_ranks", []), 3) for r in ratings]

    mean_p1 = round(sum(p1_scores) / n, 4)
    mean_p3 = round(sum(p3_scores) / n, 4)
    mean_ndcg3 = round(sum(ndcg3_scores) / n, 4)

    # 3. Top-1 Acceptable rate
    top1_hits = sum(1 for r in ratings if r.get("top1_acceptable"))
    top1_rate = round(top1_hits / n, 4)

    # 4. Review acceptance mix from recommendation_reviews
    reviews = await db[COL_RECOMMENDATION_REVIEWS].find({}).to_list(length=10000)
    rev_mix: Dict[str, Any] = {
        "total": len(reviews),
        "approved": sum(1 for rev in reviews if rev.get("decision") == "approved"),
        "modified": sum(1 for rev in reviews if rev.get("decision") == "modified"),
        "rejected": sum(1 for rev in reviews if rev.get("decision") == "rejected"),
    }
    if reviews:
        rev_mix["approval_rate"] = round(rev_mix["approved"] / len(reviews), 4)

    # Audit query
    await audit_student_view(
        request,
        db,
        current_user,
        pid="cohort",
        view="validation_c4_summary",
    )

    return C4SummaryResponse(
        n=n,
        mean_appropriateness=mean_appr,
        precision_at_1=mean_p1,
        precision_at_3=mean_p3,
        ndcg_at_3=mean_ndcg3,
        top1_acceptable_rate=top1_rate,
        acceptance_mix=rev_mix,
    )


# ── Administrative Research Export ────────────────────────────────────────────

@router.get(
    "/export",
    response_model=ValidationExportResponse,
    summary="Export pseudonymous ground-truth datasets for research (Admin only)",
)
async def export_validation_datasets(
    request: Request,
    current_admin: User = Depends(get_current_admin),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """
    Exports both validation datasets (C1 labels and C4 ratings).
    PRIVACY GUARANTEES:
      - Admin role required.
      - Qualitative comments and real student identities are strictly EXCLUDED.
      - Contract schema version "validation-export-1.0".
      - Audited via AuditAction.EXPORT_GENERATED prior to release.
    """
    c1_docs = await db[COL_VALIDATION_LABELS].find({}).sort("created_at", -1).to_list(length=10000)
    c4_docs = await db[COL_RECOMMENDATION_RATINGS].find({}).sort("created_at", -1).to_list(length=10000)

    c1_rows = [
        ValidationExportC1LabelRow(
            label_id=str(d.get("label_id") or d.get("id")),
            pid=str(d["pid"]),
            course_id=str(d["course_id"]),
            week_index=int(d["week_index"]),
            model_top_class=str(d["model_top_class"]),
            model_top_score=round(float(d.get("model_top_score", 0.0)), 4),
            counsellor_label=str(d["counsellor_label"]),
            confidence=int(d.get("confidence", 2)),
            reviewer_id=str(d["reviewer_id"]),
            created_at=d["created_at"],
        )
        for d in c1_docs
    ]

    c4_rows = [
        ValidationExportC4RatingRow(
            recommendation_id=str(d["recommendation_id"]),
            reviewer_id=str(d["reviewer_id"]),
            appropriateness=int(d["appropriateness"]),
            suitable_ranks=list(d.get("suitable_ranks") or []),
            top1_acceptable=bool(d["top1_acceptable"]),
            created_at=d["created_at"],
        )
        for d in c4_docs
    ]

    # Audit logging
    await log_event(
        request=request,
        db=db,
        action=AuditAction.EXPORT_GENERATED,
        actor_id=str(current_admin.id),
        actor_role="admin",
        target_type="export",
        target_id="validation_datasets",
        outcome=AuditOutcome.SUCCESS,
        details={
            "endpoint": request.url.path,
            "schema": "validation-export-1.0",
            "c1_count": len(c1_rows),
            "c4_count": len(c4_rows),
        },
    )

    return ValidationExportResponse(
        schema="validation-export-1.0",
        exported_at=datetime.now(timezone.utc),
        c1_labels_count=len(c1_rows),
        c4_ratings_count=len(c4_rows),
        c1_labels=c1_rows,
        c4_ratings=c4_rows,
    )

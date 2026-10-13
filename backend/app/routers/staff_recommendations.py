"""
backend/app/routers/staff_recommendations.py

Feature 32: Staff Intervention Recommendation Panel (Component 4 Adaptive Recommendations).
Provides:
  - GET /api/v1/staff/recommendations: Filterable triage list of ranked intervention batches.
  - GET /api/v1/staff/recommendations/{recommendation_id}: Full ranked candidate inspection with scores and rationales.
"""

import math
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.database import get_db
from app.db import collections as col
from app.models.user import User
from app.routers.export import get_eligible_consenting_pids
from app.schemas.staff_recommendations import (
    StaffRecommendationCandidateDetail,
    StaffRecommendationDetailResponse,
    StaffRecommendationListItem,
    StaffRecommendationListResponse,
    StaffRecommendationTopCandidate,
)
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

router = APIRouter(prefix="/api/v1/staff/recommendations", tags=["staff-recommendations"])

TIER_RANKS = {
    "critical": 4,
    "high": 3,
    "medium": 2,
    "low": 1,
    "unknown": 0,
}

DECIDED_STATUSES = {"approved", "modified", "rejected"}


# ── GET /api/v1/staff/recommendations ─────────────────────────────────────────

@router.get(
    "",
    response_model=StaffRecommendationListResponse,
    summary="List intervention recommendations",
    description="Returns filterable triage list of C4 intervention batches. Filter by review status (pending, reviewed, all), risk tier, or PID. Sorted critical tier first, then newest.",
)
async def list_recommendations(
    request: Request,
    review: str = Query("pending", description="Filter by review state: pending, reviewed, or all"),
    pid: Optional[str] = Query(None, description="Optional filter by student pseudonymous PID"),
    tier: Optional[str] = Query(None, description="Optional filter by joined risk tier"),
    page: int = Query(1, ge=1, description="Page index (1-based)"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page (max 100)"),
    current_user: User = Depends(require_staff),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> StaffRecommendationListResponse:
    eligible_pids = await get_eligible_consenting_pids(db)
    if not eligible_pids:
        await audit_student_view(
            request,
            db,
            current_user,
            pid="cohort",
            view="recommendation_list",
        )
        return StaffRecommendationListResponse(
            items=[],
            total_count=0,
            page=page,
            page_size=page_size,
            total_pages=0,
        )

    # Base filter for consenting students
    match_filter: Dict[str, Any] = {"pid": {"$in": list(eligible_pids)}}

    if pid:
        clean_pid = str(pid).strip()
        if clean_pid not in eligible_pids:
            # PID is either invalid or unconsented -> empty results
            await audit_student_view(
                request,
                db,
                current_user,
                pid=clean_pid,
                view="recommendation_list",
            )
            return StaffRecommendationListResponse(
                items=[],
                total_count=0,
                page=page,
                page_size=page_size,
                total_pages=0,
            )
        match_filter["pid"] = clean_pid

    # Review status filter
    review_mode = review.strip().lower()
    if review_mode == "pending":
        # A recommendation is pending when its status is NOT in approved, modified, rejected
        match_filter["status"] = {"$nin": list(DECIDED_STATUSES)}
    elif review_mode == "reviewed":
        # A recommendation is reviewed when status is one of approved, modified, rejected
        match_filter["status"] = {"$in": list(DECIDED_STATUSES)}
    # If review == "all", no status filter is applied

    # Fetch recommendations from MongoDB
    cursor = db[col.RECOMMENDATIONS].find(match_filter)
    raw_recs = await cursor.to_list(length=1000)

    # Batch lookup joined risk_tiers from RISK_ASSESSMENTS
    rec_pairs = list({(r.get("pid"), r.get("week_index")) for r in raw_recs if r.get("pid")})
    risk_tier_map: Dict[tuple, str] = {}
    if rec_pairs:
        or_conditions = [{"pid": p, "week_index": w} for p, w in rec_pairs]
        async for rdoc in db[col.RISK_ASSESSMENTS].find(
            {"$or": or_conditions},
            {"pid": 1, "week_index": 1, "risk_tier": 1},
        ):
            risk_tier_map[(rdoc["pid"], rdoc["week_index"])] = str(rdoc.get("risk_tier", "unknown")).lower()

    # Process items
    processed_items: List[StaffRecommendationListItem] = []
    for r in raw_recs:
        p = str(r["pid"])
        w = int(r.get("week_index", 0))
        rec_id = str(r.get("recommendation_id") or r.get("_id"))
        status_val = str(r.get("status", "proposed")).strip()

        # Joined risk tier
        r_tier = risk_tier_map.get((p, w))
        if not r_tier:
            # Fallback to latest risk doc for this student
            latest_risk = await db[col.RISK_ASSESSMENTS].find_one(
                {"pid": p},
                sort=[("week_index", -1)],
            )
            r_tier = str(latest_risk.get("risk_tier", "unknown")).lower() if latest_risk else "unknown"

        # Tier filter check
        if tier and str(tier).strip().lower() != r_tier:
            continue

        candidates = r.get("candidates") or []
        # Sort candidates by rank ascending
        sorted_candidates = sorted(candidates, key=lambda c: int(c.get("rank", 99)))
        top_cand: Optional[StaffRecommendationTopCandidate] = None
        if sorted_candidates:
            first_c = sorted_candidates[0]
            top_type = str(first_c.get("intervention_type", "other"))
            top_cand = StaffRecommendationTopCandidate(
                rank=int(first_c.get("rank", 1)),
                intervention_type=top_type,
                label=get_label(top_type),
                suitability_score=round(float(first_c.get("suitability_score", 0.0)), 4),
            )

        processed_items.append(
            StaffRecommendationListItem(
                recommendation_id=rec_id,
                pid=p,
                week_index=w,
                status=status_val,
                candidate_count=len(candidates),
                top_candidate=top_cand,
                risk_tier=r_tier if r_tier != "unknown" else None,
            )
        )

    # Sorting: critical tier first, then newest week
    processed_items.sort(
        key=lambda x: (
            TIER_RANKS.get((x.risk_tier or "unknown").lower(), 0),
            x.week_index,
        ),
        reverse=True,
    )

    total_count = len(processed_items)
    total_pages = math.ceil(total_count / page_size) if total_count > 0 else 0
    start_idx = (page - 1) * page_size
    paged_items = processed_items[start_idx : start_idx + page_size]

    # Audit access
    await audit_student_view(
        request,
        db,
        current_user,
        pid=pid or "cohort",
        view="recommendation_list",
    )

    return StaffRecommendationListResponse(
        items=paged_items,
        total_count=total_count,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


# ── GET /api/v1/staff/recommendations/{recommendation_id} ─────────────────────

@router.get(
    "/{recommendation_id}",
    response_model=StaffRecommendationDetailResponse,
    summary="Get full recommendation batch detail",
    description="Returns detailed ranked intervention candidates with suitability scores, rationales, and context course link.",
)
async def get_recommendation_detail(
    recommendation_id: str,
    request: Request,
    current_user: User = Depends(require_staff),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> StaffRecommendationDetailResponse:
    clean_id = str(recommendation_id).strip()

    # Find recommendation document by recommendation_id or _id
    rec_doc = await db[col.RECOMMENDATIONS].find_one(
        {"$or": [{"recommendation_id": clean_id}, {"_id": clean_id}]}
    )
    if not rec_doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Intervention recommendation '{clean_id}' not found.",
        )

    clean_pid = validate_pid(str(rec_doc["pid"]))

    # Verify student research consent
    visible = await is_pid_visible(db, clean_pid)
    if not visible:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Student record '{clean_pid}' not found or consent not active.",
        )

    week_idx = int(rec_doc.get("week_index", 0))

    # Look up corresponding risk assessment for context_course_id and risk_tier
    risk_doc = await db[col.RISK_ASSESSMENTS].find_one(
        {"pid": clean_pid, "week_index": week_idx}
    )
    if not risk_doc:
        # Fallback to latest risk doc for student
        risk_doc = await db[col.RISK_ASSESSMENTS].find_one(
            {"pid": clean_pid},
            sort=[("week_index", -1)],
        )

    context_course_id = str(risk_doc["course_id"]) if risk_doc and risk_doc.get("course_id") else None
    risk_tier = str(risk_doc["risk_tier"]).lower() if risk_doc and risk_doc.get("risk_tier") else None

    # If context_course_id is still None, check ENROLMENTS
    if not context_course_id:
        enr_doc = await db[col.ENROLMENTS].find_one(
            {"pid": clean_pid, "status": "active"}
        )
        if enr_doc and enr_doc.get("course_id"):
            context_course_id = str(enr_doc["course_id"])

    # Build ranked candidates list
    raw_candidates = rec_doc.get("candidates") or []
    sorted_candidates = sorted(raw_candidates, key=lambda c: int(c.get("rank", 99)))

    detail_candidates: List[StaffRecommendationCandidateDetail] = []
    for c in sorted_candidates:
        itype = str(c.get("intervention_type", "other"))
        score_val = round(float(c.get("suitability_score", 0.0)), 4) if c.get("suitability_score") is not None else 0.0
        rationale_val = str(c.get("rationale") or "").strip()

        detail_candidates.append(
            StaffRecommendationCandidateDetail(
                rank=int(c.get("rank", 1)),
                intervention_type=itype,
                label=get_label(itype),
                student_label=get_student_label(itype),
                delivery_module=delivery_module_for(itype),
                suitability_score=score_val,
                rationale=rationale_val,
            )
        )

    # Audited view access
    await audit_student_view(
        request,
        db,
        current_user,
        pid=clean_pid,
        view="recommendation_detail",
        course_id=context_course_id,
        week_index=week_idx,
    )

    return StaffRecommendationDetailResponse(
        recommendation_id=str(rec_doc.get("recommendation_id") or rec_doc["_id"]),
        pid=clean_pid,
        week_index=week_idx,
        status=str(rec_doc.get("status", "proposed")),
        candidates=detail_candidates,
        risk_tier=risk_tier,
        context_course_id=context_course_id,
    )

"""
backend/app/main.py

FastAPI application entry point.

Responsibilities
----------------
- Create and configure the FastAPI application instance.
- Register CORS middleware with origins from settings.
- Mount all API routers.
- Provide lifespan hooks for startup / shutdown logic.
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from datetime import datetime, timezone

from app.core.config import settings
from app.routers import health



# ── Lifespan ──────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Code before `yield` runs at startup; code after runs at shutdown.
    """
    # ---- startup ----
    print(f"[startup]  environment : {settings.app_env}")
    print(f"[startup]  database    : MongoDB Atlas ({settings.mongo_db_name})")
    try:
        from app.core.database import client, db
        await client.admin.command('ping')
        print("[startup]  MongoDB Atlas connected successfully.")

        # Feature 6: Seed initial default consent notice if collection is empty
        notice_count = await db.consent_notices.count_documents({})
        if notice_count == 0:
            import uuid
            DEFAULT_NOTICE_TEXT = (
                "To help us notice when students may need support, this LMS records how you use it: "
                "logins, page and video activity, submissions, grades, attendance and the messages you post. "
                "Messages and activity are processed with your identity replaced by a code before any analysis. "
                "Results are only seen by authorised counsellors and academic staff, who use them to offer help. "
                "They are never used for grading or disciplinary action. "
                "You can withdraw at any time in your profile, and this will not affect your access to your courses."
            )
            now = datetime.now(timezone.utc)
            seed_doc = {
                "_id": str(uuid.uuid4()),
                "id": str(uuid.uuid4()),
                "version": 1,
                "text": DEFAULT_NOTICE_TEXT,
                "effective_from": now,
                "is_active": True,
            }
            await db.consent_notices.insert_one(seed_doc)
        # Feature 7: Ensure audit log collection indexes
        from app.repositories.audit_repo import ensure_indexes
        await ensure_indexes(db)
        print("[startup]  Feature 7: Audit log indexes ensured.")

        # Feature 21/23/Readback: Validate component API keys on startup
        from app.core.component_auth import validate_component_api_keys
        validate_component_api_keys(settings.COMPONENT_API_KEYS, settings.app_env)
    except Exception as exc:
        print(f"[startup]  Warning: MongoDB startup check failed: {exc}")

    # --- Dushan: forum indexes ---
    try:
        from app.core.database import db as _db
        await _db.forum_threads.create_index(
            [("course_id", 1), ("last_activity_at", -1)],
            background=True,
        )
        await _db.forum_posts.create_index(
            [("thread_id", 1), ("created_at", 1)],
            background=True,
        )
    except Exception as exc:
        print(f"[startup]  Warning: forum index creation failed: {exc}")

    # --- Dushan: chat indexes ---
    try:
        from app.core.database import db as _db2
        await _db2.chat_conversations.create_index(
            "participant_key", unique=True, background=True,
        )
        await _db2.chat_conversations.create_index(
            [("participant_ids", 1), ("last_message_at", -1)],
            background=True,
        )
        await _db2.chat_messages.create_index(
            [("conversation_id", 1), ("created_at", 1)],
            background=True,
        )
        await _db2.chat_messages.create_index(
            [("recipient_id", 1), ("read_at", 1)],
            background=True,
        )
    except Exception as exc:
        print(f"[startup]  Warning: chat index creation failed: {exc}")

    # --- Dushan: journal indexes ---
    try:
        from app.core.database import db as _db3
        await _db3.journal_entries.create_index(
            [("author_id", 1), ("course_id", 1), ("week_start", 1)],
            unique=True,
            background=True,
        )
        await _db3.journal_entries.create_index(
            [("course_id", 1), ("week_start", 1)],
            background=True,
        )
    except Exception as exc:
        print(f"[startup]  Warning: journal index creation failed: {exc}")

    # --- Dushan: review indexes ---
    try:
        from app.core.database import db as _db_rev
        await _db_rev.recommendation_reviews.create_index(
            [("recommendation_id", 1)],
            unique=True,
            background=True,
        )
        await _db_rev.intervention_records.create_index(
            [("id", 1)],
            unique=True,
            background=True,
        )
        await _db_rev.intervention_records.create_index(
            [("pid", 1), ("created_at", -1)],
            background=True,
        )
        await _db_rev.intervention_records.create_index(
            [("status", 1)],
            background=True,
        )
    except Exception as exc:
        print(f"[startup]  Warning: review index creation failed: {exc}")

    # --- Dushan: intervention indexes ---
    try:
        from app.core.database import db as _db_int
        await _db_int.intervention_records.create_index(
            [("assigned_to", 1)],
            background=True,
        )
    except Exception as exc:
        print(f"[startup]  Warning: intervention index creation failed: {exc}")

    # --- Dushan: notification indexes ---
    try:
        from app.core.database import db as _db_notif
        await _db_notif.notifications.create_index(
            [("user_id", 1), ("created_at", -1)],
            background=True,
        )
        await _db_notif.notifications.create_index(
            [("user_id", 1), ("read_at", 1)],
            background=True,
        )
        await _db_notif.notifications.create_index(
            [("dedupe_key", 1)],
            unique=True,
            sparse=True,
            background=True,
        )
    except Exception as exc:
        print(f"[startup]  Warning: notification index creation failed: {exc}")

    # --- Dushan: resource indexes ---
    try:
        from app.core.database import db as _db_res
        await _db_res.support_resources.create_index(
            [("is_active", 1), ("resource_type", 1)],
            background=True,
        )
    except Exception as exc:
        print(f"[startup]  Warning: resource index creation failed: {exc}")

    # --- Dushan: slot indexes ---
    try:
        from app.core.database import db as _db_slot
        await _db_slot.counselling_slots.create_index(
            [("counsellor_id", 1), ("start_at", 1)],
            background=True,
        )
        await _db_slot.counselling_slots.create_index(
            [("booked_by_user_id", 1), ("start_at", 1)],
            background=True,
        )
        await _db_slot.counselling_slots.create_index(
            [("start_at", 1)],
            background=True,
        )
    except Exception as exc:
        print(f"[startup]  Warning: counselling slot index creation failed: {exc}")

    # --- Dushan: mentoring indexes ---
    try:
        from app.core.database import db as _db_mentor
        await _db_mentor.mentoring_assignments.create_index(
            [("intervention_id", 1)],
            unique=True,
            partialFilterExpression={"status": "active"},
            background=True,
        )
        await _db_mentor.mentoring_assignments.create_index(
            [("mentor_user_id", 1), ("status", 1)],
            background=True,
        )
        await _db_mentor.mentoring_assignments.create_index(
            [("mentee_user_id", 1), ("status", 1)],
            background=True,
        )
    except Exception as exc:
        print(f"[startup]  Warning: mentoring assignment index creation failed: {exc}")



    if getattr(settings, "ENABLE_SCHEDULER", False):
        try:
            from app.jobs.scheduler import start_scheduler
            start_scheduler()
            print("[startup]  Background APScheduler started.")
        except Exception as exc:
            print(f"[startup]  Warning: failed to start scheduler: {exc}")

    # Feature 22: Pipeline scheduler lifecycle
    if getattr(settings, "SCHEDULER_ENABLED", False):
        try:
            from app.pipeline.scheduler import start_pipeline_scheduler
            start_pipeline_scheduler()
            print("[startup]  Feature 22 Pipeline scheduler started.")
        except Exception as exc:
            print(f"[startup]  Warning: failed to start pipeline scheduler: {exc}")

    yield
    # ---- shutdown ----
    if getattr(settings, "SCHEDULER_ENABLED", False):
        try:
            from app.pipeline.scheduler import stop_pipeline_scheduler
            stop_pipeline_scheduler()
            print("[shutdown] Feature 22 Pipeline scheduler stopped.")
        except Exception:
            pass

    if getattr(settings, "ENABLE_SCHEDULER", False):
        try:
            from app.jobs.scheduler import stop_scheduler
            stop_scheduler()
            print("[shutdown] Background APScheduler stopped.")
        except Exception:
            pass

    from app.core.database import client
    client.close()
    print("[shutdown] application stopped")


# ── Application factory ───────────────────────────────────────────────────────
def create_app() -> FastAPI:
    app = FastAPI(
        title="Emotion-Aware Student Early Warning System",
        description=(
            "AI-driven platform that combines student emotional states, "
            "longitudinal engagement patterns, and academic performance to "
            "predict dropout risk and recommend cause-matched interventions."
        ),
        version="0.1.0",
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
        lifespan=lifespan,
    )

    # ── Feature 7: Request Tracking Middleware ────────────────────────────────
    from app.core.middleware import RequestTrackingMiddleware  # noqa: E402
    app.add_middleware(RequestTrackingMiddleware)

    # ── CORS ──────────────────────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,   # e.g. ["http://localhost:5173"]
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Feature 7: Global 401 / 403 ACCESS_DENIED Exception Handler ───────────
    from fastapi import HTTPException, Request  # noqa: E402
    from fastapi.responses import JSONResponse  # noqa: E402
    from app.core.security import decode_token  # noqa: E402
    from app.schemas.audit import AuditAction, AuditOutcome  # noqa: E402
    from app.services.audit import log_event  # noqa: E402

    @app.exception_handler(HTTPException)
    async def audit_access_denied_handler(request: Request, exc: HTTPException):
        if exc.status_code in (401, 403):
            actor_id = "anonymous"
            actor_role = "anonymous"
            auth_header = request.headers.get("authorization", "")
            if auth_header.startswith("Bearer "):
                token = auth_header.split(" ", 1)[1].strip()
                try:
                    payload = decode_token(token)
                    actor_id = str(payload.get("sub") or "anonymous")
                    actor_role = str(payload.get("role") or "anonymous")
                except Exception:
                    pass

            try:
                from app.core.database import db
                await log_event(
                    request=request,
                    db=db,
                    action=AuditAction.ACCESS_DENIED,
                    actor_id=actor_id,
                    actor_role=actor_role,
                    outcome=AuditOutcome.DENIED,
                    details={
                        "status_code": exc.status_code,
                        "endpoint": request.url.path,
                        "reason": str(exc.detail)[:120],
                    },
                )
            except Exception:
                pass  # Non-critical: never suppress response

        headers = getattr(exc, "headers", None)
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
            headers=headers,
        )

    # ── Routers ───────────────────────────────────────────────────────────────
    app.include_router(health.router)

    from app.routers import auth  # noqa: E402
    app.include_router(auth.router)

    from app.routers import users  # noqa: E402
    app.include_router(users.router)

    from app.routers import courses  # noqa: E402
    app.include_router(courses.router)

    from app.routers import admin  # noqa: E402
    app.include_router(admin.router)

    from app.routers import enrollments  # noqa: E402
    app.include_router(enrollments.router)

    from app.routers import assignments  # noqa: E402
    app.include_router(assignments.router)

    from app.routers import quizzes  # noqa: E402
    app.include_router(quizzes.router)

    from app.routers import gradebook  # noqa: E402
    app.include_router(gradebook.router)

    from app.routers import attendance  # noqa: E402
    app.include_router(attendance.router)

    from app.routers import course_content  # noqa: E402
    app.include_router(course_content.router)

    # --- Communication / interventions ---
    from app.routers import forum  # noqa: E402
    app.include_router(forum.router)

    from app.routers import chat  # noqa: E402
    app.include_router(chat.router)

    from app.routers import journal  # noqa: E402
    app.include_router(journal.router)

    # --- Compliance, audit, governance ---
    from app.routers import consent  # noqa: E402
    app.include_router(consent.router)

    from app.routers import audit  # noqa: E402
    app.include_router(audit.router)

    from app.routers import privacy  # noqa: E402
    app.include_router(privacy.router)

    from app.routers import contract  # noqa: E402
    app.include_router(contract.router)

    from app.routers import export  # noqa: E402
    app.include_router(export.router)

    # --- ML ingestion, telemetry, and pipeline ---
    from app.routers import ingest  # noqa: E402
    app.include_router(ingest.router)

    from app.routers import pipeline  # noqa: E402
    app.include_router(pipeline.router)

    from app.routers import telemetry  # noqa: E402
    app.include_router(telemetry.router)

    # --- Dushan: staff workspace ---
    try:
        from app.routers import staff_affective  # noqa: E402
        app.include_router(staff_affective.router)
    except Exception as exc:
        import logging
        logging.getLogger("app.main").warning(
            "Failed to register staff_affective router: %s", exc
        )

    try:
        from app.routers import staff_students  # noqa: E402
        app.include_router(staff_students.router)
    except Exception as exc:
        import logging
        logging.getLogger("app.main").warning(
            "Failed to register staff_students router: %s", exc
        )

    try:
        from app.routers import staff_recommendations  # noqa: E402
        app.include_router(staff_recommendations.router)
    except Exception as exc:
        import logging
        logging.getLogger("app.main").warning(
            "Failed to register staff_recommendations router: %s", exc
        )

    try:
        from app.routers import staff_review  # noqa: E402
        app.include_router(staff_review.router)
    except Exception as exc:
        import logging
        logging.getLogger("app.main").warning(
            "Failed to register staff_review router: %s", exc
        )

    try:
        from app.routers import staff_interventions  # noqa: E402
        app.include_router(staff_interventions.router)
    except Exception as exc:
        import logging
        logging.getLogger("app.main").warning(
            "Failed to register staff_interventions router: %s", exc
        )

    try:
        from app.routers import notifications  # noqa: E402
        app.include_router(notifications.router)
    except Exception as exc:
        import logging
        logging.getLogger("app.main").warning(
            "Failed to register notifications router: %s", exc
        )

    try:
        from app.routers import support_student  # noqa: E402
        app.include_router(support_student.router)
    except Exception as exc:
        import logging
        logging.getLogger("app.main").warning(
            "Failed to register support_student router: %s", exc
        )

    try:
        from app.routers import staff_outcomes  # noqa: E402
        app.include_router(staff_outcomes.router)
    except Exception as exc:
        import logging
        logging.getLogger("app.main").warning(
            "Failed to register staff_outcomes router: %s", exc
        )

    try:
        from app.routers import support_staff_resources  # noqa: E402
        app.include_router(support_staff_resources.router)
    except Exception as exc:
        import logging
        logging.getLogger("app.main").warning(
            "Failed to register support_staff_resources router: %s", exc
        )

    try:
        from app.routers import support_staff_slots  # noqa: E402
        app.include_router(support_staff_slots.router)
    except Exception as exc:
        import logging
        logging.getLogger("app.main").warning(
            "Failed to register support_staff_slots router: %s", exc
        )

    try:
        from app.routers import support_staff_mentoring  # noqa: E402
        app.include_router(support_staff_mentoring.router)
    except Exception as exc:
        import logging
        logging.getLogger("app.main").warning(
            "Failed to register support_staff_mentoring router: %s", exc
        )

    return app


app: FastAPI = create_app()

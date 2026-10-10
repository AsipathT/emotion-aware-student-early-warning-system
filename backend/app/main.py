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
            print("[startup]  Feature 6: Default Consent Notice v1 seeded successfully.")
    except Exception as exc:
        print(f"[startup]  Warning: MongoDB startup check failed: {exc}")
    yield
    # ---- shutdown ----
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

    # ── CORS ──────────────────────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,   # e.g. ["http://localhost:5173"]
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
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

    from app.routers import privacy  # noqa: E402
    app.include_router(privacy.router)

    from app.routers import consent  # noqa: E402
    app.include_router(consent.router)

    return app


app: FastAPI = create_app()

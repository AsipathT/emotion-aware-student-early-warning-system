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
    except Exception as exc:
        print(f"[startup]  Warning: journal index creation failed: {exc}")

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

    from app.routers import privacy  # noqa: E402
    app.include_router(privacy.router)

    from app.routers import consent  # noqa: E402
    app.include_router(consent.router)

    from app.routers import audit  # noqa: E402
    app.include_router(audit.router)

    from app.routers import contract  # noqa: E402
    app.include_router(contract.router)

    from app.routers import export  # noqa: E402
    app.include_router(export.router)
    # --- Dushan: communication / interventions ---
    from app.routers import forum  # noqa: E402
    app.include_router(forum.router)

    from app.routers import chat  # noqa: E402
    app.include_router(chat.router)

    from app.routers import ingest  # noqa: E402
    app.include_router(ingest.router)

    return app


app: FastAPI = create_app()

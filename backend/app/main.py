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

from app.core.config import settings
from app.routers import health  # add further routers here as the project grows


# ── Lifespan ──────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Code before `yield` runs at startup; code after runs at shutdown.
    Add database pool warm-up, scheduler start, etc. here.
    """
    # ---- startup ----
    print(f"[startup]  environment : {settings.app_env}")
    print(f"[startup]  database    : {settings.postgres_host}:{settings.postgres_port}/{settings.postgres_db}")
    yield
    # ---- shutdown ----
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
    # All routes are versioned under /api/v1/ (see development.md §1)
    app.include_router(health.router)

    from app.routers import auth  # noqa: E402 (avoid circular import at module level)
    app.include_router(auth.router)

    from app.routers import users  # noqa: E402
    app.include_router(users.router)

    from app.routers import courses  # noqa: E402
    app.include_router(courses.router)

    from app.routers import admin  # noqa: E402
    app.include_router(admin.router)

    from app.routers import enrollments  # noqa: E402
    app.include_router(enrollments.router)

    return app


app: FastAPI = create_app()

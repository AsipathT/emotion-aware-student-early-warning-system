"""
backend/app/core/middleware.py

Feature 7: Request Tracking Middleware.
Provides:
  - Generates a unique UUID4 request_id for each HTTP request.
  - Resolves client IP address (respecting X-Forwarded-For only when TRUSTED_PROXY is True).
  - Extracts the user-agent header.
  - Stores request_id, client_ip, and user_agent on request.state for downstream logging.
  - Injects X-Request-ID header into every HTTP response.
"""

import uuid
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.config import settings


class RequestTrackingMiddleware(BaseHTTPMiddleware):
    """
    Middleware that tracks request correlation IDs and client metadata.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        # 1. Generate or correlate request ID
        request_id = request.headers.get("x-request-id") or str(uuid.uuid4())

        # 2. Extract Client IP
        if settings.TRUSTED_PROXY:
            forwarded = request.headers.get("x-forwarded-for")
            if forwarded:
                client_ip = forwarded.split(",")[0].strip()
            elif request.client:
                client_ip = request.client.host
            else:
                client_ip = "127.0.0.1"
        else:
            client_ip = request.client.host if request.client else "127.0.0.1"

        # 3. Extract User Agent
        user_agent = request.headers.get("user-agent", "unknown")

        # 4. Attach to request.state
        request.state.request_id = request_id
        request.state.client_ip = client_ip
        request.state.user_agent = user_agent

        # 5. Process request
        response: Response = await call_next(request)

        # 6. Inject X-Request-ID into response header
        response.headers["X-Request-ID"] = request_id

        return response

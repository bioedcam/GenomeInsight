"""Authentication system for GenomeInsight (P4-21a).

Optional PIN/password authentication with bcrypt hashing,
session cookies, and 4-hour inactivity timeout.

When auth is disabled (no password set), all requests pass through.
When enabled, all API endpoints require a valid session cookie,
except /api/health which is always exempt.
"""

from __future__ import annotations

import secrets
import time

import bcrypt
import structlog
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from backend.config import get_settings

logger = structlog.get_logger(__name__)

# ── Password hashing ─────────────────────────────────────────────────


def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    """Verify a password against a bcrypt hash."""
    return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))


# ── Session store (in-memory, server-side) ────────────────────────────

# Maps session_id -> last_active timestamp (epoch seconds)
_sessions: dict[str, float] = {}


def create_session() -> str:
    """Create a new session and return the session ID."""
    session_id = secrets.token_urlsafe(32)
    _sessions[session_id] = time.time()
    return session_id


def validate_session(session_id: str, timeout_hours: int = 4) -> bool:
    """Check if a session is valid (exists and not expired)."""
    last_active = _sessions.get(session_id)
    if last_active is None:
        return False
    if time.time() - last_active > timeout_hours * 3600:
        # Expired — clean up
        _sessions.pop(session_id, None)
        return False
    # Touch — keep session alive on activity
    _sessions[session_id] = time.time()
    return True


def destroy_session(session_id: str) -> None:
    """Remove a session."""
    _sessions.pop(session_id, None)


def clear_all_sessions() -> None:
    """Remove all sessions (for testing or password change)."""
    _sessions.clear()


def _get_session_count() -> int:
    """Return the number of active sessions (for testing)."""
    return len(_sessions)


# ── Auth middleware ───────────────────────────────────────────────────

# Paths that are always exempt from auth
_AUTH_EXEMPT_PATHS = frozenset(
    {
        "/api/health",
        "/api/auth/login",
        "/api/auth/status",
        "/api/auth/set-password",
    }
)

# Prefixes that are always exempt (setup wizard must work without auth)
_AUTH_EXEMPT_PREFIXES = ("/api/setup",)


def _is_auth_exempt(path: str) -> bool:
    """Check if a path is exempt from authentication."""
    if path in _AUTH_EXEMPT_PATHS:
        return True
    for prefix in _AUTH_EXEMPT_PREFIXES:
        if path.startswith(prefix):
            return True
    # Non-API paths (static files, SPA routes) are exempt
    if not path.startswith("/api/"):
        return True
    return False


class AuthMiddleware(BaseHTTPMiddleware):
    """Middleware that enforces session-based auth when enabled.

    When auth_enabled is False or no password hash is set, all requests
    pass through. When enabled, non-exempt API requests must have a
    valid session cookie.
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        settings = get_settings()

        # Auth disabled — pass through
        if not settings.auth_enabled or not settings.auth_password_hash:
            return await call_next(request)

        # Exempt paths pass through
        if _is_auth_exempt(request.url.path):
            return await call_next(request)

        # Check session cookie
        session_id = request.cookies.get("gi_session")
        if not session_id or not validate_session(
            session_id, settings.session_timeout_hours
        ):
            return JSONResponse(
                status_code=401,
                content={"detail": "Authentication required"},
            )

        return await call_next(request)

"""Audit logging middleware for capturing POST, PUT, DELETE, PATCH actions."""

import json
from typing import Callable
from uuid import UUID
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionFactory
from app.models.audit_log import AuditLog
from app.core.security import decode_token


AUDITABLE_METHODS = {"POST", "PUT", "DELETE", "PATCH"}

AUDITABLE_PATHS = {
    "/api/v1/auth/login": ("auth", "login"),
    "/api/v1/auth/logout": ("auth", "logout"),
    "/api/v1/auth/register": ("auth", "register"),
    "/api/v1/loans": ("loan", "create"),
    "/api/v1/payments": ("payment", "create"),
    "/api/v1/payments/with-voucher": ("payment", "submit_voucher"),
    "/api/v1/customers": ("customer", "create"),
    "/api/v1/lender/users": ("user", "create"),
    "/api/v1/lender/loans": ("loan", "create"),
    "/api/v1/lender/payments": ("payment", "create"),
    "/api/v1/lender/payments/{id}/approve": ("payment", "approve"),
    "/api/v1/lender/payments/{id}/reject": ("payment", "reject"),
    "/api/v1/admin/lenders": ("lender", "create"),
    "/api/v1/admin/users": ("user", "create"),
    "/api/v1/me/loans": ("loan", "create"),
    "/api/v1/me/payments": ("payment", "create"),
}


def get_client_ip(request: Request) -> str | None:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else None


async def get_user_info_from_request(
    request: Request,
) -> tuple[UUID | None, str | None, str | None, UUID | None]:
    """Extract user info from request.state if set by auth middleware."""
    user_id = getattr(request.state, "user_id", None)
    user_email = getattr(request.state, "user_email", None)
    user_name = getattr(request.state, "user_name", None)
    lender_id = getattr(request.state, "lender_id", None)
    return user_id, user_email, user_name, lender_id


def get_user_info_from_authorization_header(
    request: Request,
) -> tuple[UUID | None, str | None, str | None, UUID | None]:
    """Extract user info from bearer access token when request.state is empty."""
    auth_header = request.headers.get("authorization")
    if not auth_header:
        return None, None, None, None

    try:
        scheme, token = auth_header.split(" ", 1)
        if scheme.lower() != "bearer" or not token:
            return None, None, None, None
        claims = decode_token(token)
        if claims.get("type") != "access":
            return None, None, None, None
    except Exception:
        return None, None, None, None

    user_id = None
    lender_id = None

    try:
        sub = claims.get("sub")
        user_id = UUID(str(sub)) if sub else None
    except Exception:
        user_id = None

    try:
        lender = claims.get("lender_id")
        lender_id = UUID(str(lender)) if lender else None
    except Exception:
        lender_id = None

    email = claims.get("email")
    first_name = str(claims.get("first_name") or "").strip()
    last_name = str(claims.get("last_name") or "").strip()
    full_name = f"{first_name} {last_name}".strip() or None

    return user_id, (str(email) if email else None), full_name, lender_id


async def get_login_user_info_from_request(
    request: Request,
) -> tuple[UUID | None, str | None, str | None, UUID | None]:
    """Extract login user metadata from request body for /auth/login."""
    if request.url.path != "/api/v1/auth/login":
        return None, None, None, None

    try:
        body = await request.body()
        if not body:
            return None, None, None, None
        payload = json.loads(body.decode("utf-8") if isinstance(body, bytes) else body)
        email = payload.get("email")
        if email:
            return None, str(email), None, None
    except Exception:
        pass
    return None, None, None, None


def get_login_user_info_cached(
    request: Request,
) -> tuple[UUID | None, str | None, str | None, UUID | None]:
    """Get cached login info from request state (captured before body was consumed)."""
    if request.url.path != "/api/v1/auth/login":
        return None, None, None, None
    email = getattr(request.state, "_login_email", None)
    if email:
        return None, str(email), None, None
    return None, None, None, None


def get_login_user_info_from_response(
    path: str, response: Response
) -> tuple[UUID | None, str | None, str | None, UUID | None]:
    """Extract login user metadata from successful /auth/login response body."""
    if path != "/api/v1/auth/login":
        return None, None, None, None

    body = getattr(response, "body", None)
    if not body:
        return None, None, None, None

    try:
        payload = json.loads(body.decode("utf-8") if isinstance(body, bytes) else body)
        user = payload.get("user") or {}
        user_id = UUID(str(user.get("id"))) if user.get("id") else None
        lender_id = UUID(str(user.get("lender_id"))) if user.get("lender_id") else None
        email = user.get("email")
        first_name = str(user.get("first_name") or "").strip()
        last_name = str(user.get("last_name") or "").strip()
        user_name = f"{first_name} {last_name}".strip() or None
        return user_id, (str(email) if email else None), user_name, lender_id
    except Exception:
        return None, None, None, None


def extract_resource(path: str, method: str) -> tuple[str, str]:
    """Extract resource_type and action from path and method."""
    clean_path = path.replace("/api/v1/", "")

    if clean_path.startswith("lender/"):
        clean_path = clean_path.replace("lender/", "")
    if clean_path.startswith("admin/"):
        clean_path = clean_path.replace("admin/", "")

    parts = [p for p in clean_path.split("/") if p]
    if len(parts) >= 1:
        resource_type = parts[0]
        action = method.lower()

        if len(parts) >= 3:
            try:
                UUID(parts[1])
                action = parts[2]
            except Exception:
                action = parts[1]
        elif len(parts) >= 2:
            action = parts[1]

        if action in ("approve", "reject"):
            return resource_type, action
        if action in ("login", "logout", "register", "submit", "submit-review"):
            return resource_type, action
        if method == "POST":
            return resource_type, "create"
        elif method in ("PUT", "PATCH"):
            return resource_type, "update"
        elif method == "DELETE":
            return resource_type, "delete"

        return resource_type, action

    return clean_path, method.lower()


class AuditMiddleware(BaseHTTPMiddleware):
    """Middleware to automatically log auditable API requests."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        method = request.method
        path = request.url.path

        if method not in AUDITABLE_METHODS:
            return await call_next(request)

        if path == "/api/v1/auth/login":
            try:
                body = await request.body()
                if body:
                    payload = json.loads(
                        body.decode("utf-8") if isinstance(body, bytes) else body
                    )
                    email = payload.get("email")
                    if email:
                        request.state._login_email = email
            except Exception:
                pass

        response = await call_next(request)

        if response.status_code >= 400:
            return response

        user_id, user_email, user_name, lender_id = get_login_user_info_cached(request)

        if user_id is None and hasattr(request.state, "current_user"):
            cu = request.state.current_user
            if cu:
                user_id = getattr(cu, "id", None)
                user_email = getattr(cu, "email", None)
                user_name = (
                    f"{getattr(cu, 'first_name', '')} {getattr(cu, 'last_name', '')}".strip()
                    or None
                )
                lender_id = getattr(cu, "lender_id", None)

        if user_id is None:
            user_id, user_email, user_name, lender_id = (
                get_user_info_from_authorization_header(request)
            )

        if user_id is None and path == "/api/v1/auth/login":
            login_info = get_login_user_info_cached(request)
            if login_info[1]:
                user_id, user_email, user_name, lender_id = login_info
            else:
                user_id, user_email, user_name, lender_id = (
                    get_login_user_info_from_response(path, response)
                )

        ip_address = get_client_ip(request)
        ua = request.headers.get("user-agent")
        user_agent = ua[:500] if ua else None

        resource_type, action = AUDITABLE_PATHS.get(
            path, extract_resource(path, method)
        )

        if resource_type in ("health", "docs", "openapi", "redoc"):
            return response

        try:
            async with AsyncSessionFactory() as session:
                log_entry = AuditLog(
                    action=action,
                    resource_type=resource_type,
                    resource_id=None,
                    description=f"{method} {path}",
                    user_id=user_id,
                    user_email=user_email,
                    user_name=user_name,
                    lender_id=lender_id,
                    ip_address=ip_address,
                    user_agent=user_agent,
                )
                session.add(log_entry)
                await session.commit()
        except Exception:
            pass

        return response

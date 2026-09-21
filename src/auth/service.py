"""Authentication service: header parsing, role resolution, and FastAPI dependencies."""

from __future__ import annotations

from typing import Any

from fastapi import Depends, HTTPException, Request, status

from src.app_logging import get_logger
from src.auth.models import AuthContext, Role

logger = get_logger('auth')

# Cloudflare Access headers injected automatically by cloudflared
_CF_EMAIL_HEADER = 'cf-access-authenticated-user-email'


def _resolve_role_cloudflare(request: Request) -> AuthContext:
    """Resolve role from Cloudflare Access headers.

    Priority:
    1. Email in ``CF_CREATOR_EMAILS`` → Creator
    2. Email in ``CF_USER_EMAILS``    → User
    3. No header / unrecognised       → Guest
    """
    settings = request.app.state.settings
    raw_email: str | None = request.headers.get(_CF_EMAIL_HEADER)

    # In local development without Cloudflare edge proxy, allow DEV_MOCK_EMAIL or loopback dev headers
    if not raw_email or not raw_email.strip():
        if settings.dev_mock_email:
            raw_email = settings.dev_mock_email
        else:
            client_host = request.client.host if request.client else ''
            if client_host in ('127.0.0.1', 'localhost', '::1', 'testclient'):
                raw_email = request.headers.get('x-dev-email') or request.query_params.get('dev_email')

    if not raw_email or not raw_email.strip():
        return AuthContext(role=Role.GUEST)

    email = raw_email.strip().lower()
    name = email.split('@')[0].capitalize()

    if email in settings.cf_creator_emails:
        return AuthContext(role=Role.CREATOR, email=email, name=name)

    if email in settings.cf_user_emails:
        return AuthContext(role=Role.USER, email=email, name=name)

    # Authenticated via Cloudflare but email not in any allow-list → Guest
    logger.info('Authenticated email %r not in any allow-list, assigned Guest role', email)
    return AuthContext(role=Role.GUEST, email=email, name=name)


def _resolve_role_disabled(settings: Any = None) -> AuthContext:
    """When auth is disabled everyone is a Creator (backward-compatible default)."""
    email = getattr(settings, 'dev_mock_email', None)
    name = email.split('@')[0].capitalize() if email else 'Host'
    return AuthContext(role=Role.CREATOR, email=email, name=name)


async def get_current_auth(request: Request) -> AuthContext:
    """FastAPI dependency that resolves the current request's :class:`AuthContext`.

    Reads ``settings.auth_mode`` to decide which resolver to use:
    - ``"disabled"``   → always Creator (dev / CI / standalone)
    - ``"cloudflare"`` → inspect Cloudflare Access headers
    """
    settings = request.app.state.settings
    mode = settings.auth_mode

    if mode == 'disabled':
        return _resolve_role_disabled(settings)

    if mode == 'cloudflare':
        return _resolve_role_cloudflare(request)

    # Fallback safety net: unknown mode → treat as disabled
    logger.warning('Unknown AUTH_MODE %r, falling back to disabled (Creator for all)', mode)
    return _resolve_role_disabled(settings)


def require_role(min_role: Role):
    """Return a FastAPI dependency that enforces a minimum role level.

    Usage::

        @router.get('/libraries', dependencies=[Depends(require_role(Role.CREATOR))])
        async def list_libraries(...): ...
    """

    async def _dependency(auth: AuthContext = Depends(get_current_auth)) -> AuthContext:
        if not auth.has_role(min_role):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f'Access restricted to {min_role.name.lower()}s.',
            )
        return auth

    return _dependency

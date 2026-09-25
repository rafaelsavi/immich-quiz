"""Authentication service: header parsing, role resolution, and FastAPI dependencies."""

from __future__ import annotations

import base64
import json
from typing import Any

from fastapi import Depends, HTTPException, Request, status

from src.app_logging import get_logger
from src.auth.models import AuthContext, Role

logger = get_logger('auth')

# Cloudflare Access & reverse proxy (Caddy/Traefik/Nginx) identity headers
_CF_EMAIL_HEADERS = (
    'cf-access-authenticated-user-email',
    'x-auth-email',
    'x-user-email',
    'x-forwarded-email',
)

_CF_NAME_HEADERS = (
    'cf-access-authenticated-user-name',
    'x-user-name',
    'x-auth-name',
    'x-forwarded-user-name',
    'x-forwarded-user',
    'remote-user',
)

_CF_JWT_HEADER = 'cf-access-jwt-assertion'


def _extract_identity_from_jwt(jwt_token: str) -> tuple[str | None, str | None]:
    """Extract display name and email claims from an unverified JWT assertion payload.

    Cloudflare Access edge cryptographically validates JWTs before forwarding
    them to origin servers. This utility safely decodes the claims payload to
    retrieve standard identity attributes without requiring external crypto dependencies.
    """
    parts = jwt_token.strip().split('.')
    if len(parts) != 3:
        return None, None
    payload_b64 = parts[1]
    rem = len(payload_b64) % 4
    if rem:
        payload_b64 += '=' * (4 - rem)
    try:
        data = json.loads(base64.urlsafe_b64decode(payload_b64.encode('ascii')))
        if not isinstance(data, dict):
            return None, None

        # Build list of candidate claim containers to support Cloudflare's
        # various payload layouts:
        # 1. Root level claims (standard JWT)
        # 2. 'oidc_fields' (Cloudflare Access OIDC attribute mappings)
        # 3. 'identity' (nested user identity object)
        # 4. 'identity.oidc_fields'
        # 5. 'custom' / 'custom_claims' / 'user_identity'
        containers: list[dict[str, Any]] = [data]
        for key in ('oidc_fields', 'identity', 'custom', 'custom_claims', 'user_identity'):
            val = data.get(key)
            if isinstance(val, dict):
                containers.append(val)
                if key == 'identity':
                    nested_oidc = val.get('oidc_fields')
                    if isinstance(nested_oidc, dict):
                        containers.append(nested_oidc)

        name: str | None = None
        for container in containers:
            for claim in ('name', 'preferred_username', 'user_name', 'nickname', 'display_name'):
                v = container.get(claim)
                if isinstance(v, str) and v.strip():
                    name = v.strip()
                    break
            if name:
                break

            given = container.get('given_name')
            if isinstance(given, str) and given.strip():
                family = container.get('family_name')
                if isinstance(family, str) and family.strip():
                    name = f'{given.strip()} {family.strip()}'
                else:
                    name = given.strip()
                break

        email: str | None = None
        for container in containers:
            for claim in ('email', 'user_email', 'mail'):
                v = container.get(claim)
                if isinstance(v, str) and v.strip():
                    email = v.strip().lower()
                    break
            if email:
                break

        return name, email
    except Exception as exc:
        logger.debug('Failed to decode JWT assertion claims: %s', exc)
        return None, None


def _resolve_role_cloudflare(request: Request) -> AuthContext:
    """Resolve role and identity from Cloudflare Access headers, JWT, or reverse proxies.

    Priority:
    1. Email or Name in ``CF_CREATOR_EMAILS`` → Creator
    2. Email or Name in ``CF_USER_EMAILS``    → User
    3. No header / unrecognised               → Guest
    """
    settings = request.app.state.settings

    # 1. Resolve raw email from known headers
    raw_email: str | None = None
    for hdr in _CF_EMAIL_HEADERS:
        if (val := request.headers.get(hdr)) and val.strip():
            raw_email = val.strip()
            break

    # 2. Resolve raw name from known headers
    raw_name: str | None = None
    for hdr in _CF_NAME_HEADERS:
        if (val := request.headers.get(hdr)) and val.strip():
            raw_name = val.strip()
            break

    # 3. If name or email is missing, check Cloudflare JWT assertion
    if jwt_token := request.headers.get(_CF_JWT_HEADER):
        jwt_name, jwt_email = _extract_identity_from_jwt(jwt_token)
        if not raw_name and jwt_name:
            raw_name = jwt_name
        if not raw_email and jwt_email:
            raw_email = jwt_email

    # 4. In local development without Cloudflare edge proxy, allow loopback dev headers
    # --- DEV TESTING HOOK ---
    # To quickly test a specific identity in code without headers or query params, uncomment:
    # raw_email = "creator@example.com"  # or "user@example.com", etc.
    # raw_name = "Fulano"
    client_host = request.client.host if request.client else ''
    is_loopback = client_host in ('127.0.0.1', 'localhost', '::1', 'testclient')

    if (not raw_email or not raw_email.strip()) and is_loopback:
        raw_email = request.headers.get('x-dev-email') or request.query_params.get('dev_email')

    if (not raw_name or not raw_name.strip()) and is_loopback:
        raw_name = request.headers.get('x-dev-name') or request.query_params.get('dev_name')

    if (not raw_email or not raw_email.strip()) and (not raw_name or not raw_name.strip()):
        return AuthContext(role=Role.GUEST)

    email = raw_email.strip().lower() if raw_email and raw_email.strip() else None

    # Determine final display name
    if raw_name and raw_name.strip():
        name = raw_name.strip()
    elif email:
        name = email.split('@')[0].capitalize()
    else:
        name = None

    # Check allowlists against both email and lowercase name/username
    identifiers: set[str] = set()
    if email:
        identifiers.add(email)
    if name:
        identifiers.add(name.lower())

    if identifiers & settings.cf_creator_emails:
        return AuthContext(role=Role.CREATOR, email=email, name=name)

    if identifiers & settings.cf_user_emails:
        return AuthContext(role=Role.USER, email=email, name=name)

    # Authenticated via proxy/Cloudflare but identifier not in any allow-list → Guest
    logger.info('Authenticated identity (%s, %s) not in any allow-list, assigned Guest role', email, name)
    return AuthContext(role=Role.GUEST, email=email, name=name)


def _resolve_role_disabled(settings: Any = None) -> AuthContext:
    """When auth is disabled everyone is a Creator (backward-compatible default)."""
    # --- DEV TESTING HOOK ---
    # To test custom name/email under AUTH_MODE=disabled without Cloudflare:
    # return AuthContext(role=Role.CREATOR, email="admin@example.com", name="Creator")
    return AuthContext(role=Role.CREATOR, email=None, name='Host')


async def get_current_auth(request: Request) -> AuthContext:
    """FastAPI dependency that resolves the current request's :class:`AuthContext`.

    Reads ``settings.auth_mode`` to decide which resolver to use:
    - ``"disabled"``   → always Creator (dev / CI / standalone)
    - ``"cloudflare"`` → inspect Cloudflare Access headers
    """
    # --- DEV TESTING HOOK ---
    # To bypass all resolvers and immediately simulate any role (GUEST, USER, CREATOR):
    # return AuthContext(role=Role.USER, email="test@example.com", name="Tester")

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

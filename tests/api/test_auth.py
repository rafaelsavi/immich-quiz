"""Unit and API integration tests for authentication and role-based access control."""

from __future__ import annotations

from pathlib import Path

import pytest
from conftest import FakeImmichClient
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.testclient import TestClient

from src.auth.models import AuthContext, Role
from src.auth.service import (
    _resolve_role_cloudflare,
    _resolve_role_disabled,
    require_role,
)
from src.config import AppSettings
from src.main import create_app


def test_role_enum_ordering() -> None:
    """Verify Role enum ordering and comparisons."""
    assert Role.GUEST < Role.USER < Role.CREATOR
    assert Role.CREATOR > Role.USER > Role.GUEST
    assert Role.USER >= Role.USER
    assert Role.USER >= Role.GUEST
    assert not (Role.GUEST >= Role.USER)
    assert not (Role.USER >= Role.CREATOR)


def test_auth_context_properties() -> None:
    """Verify AuthContext helper properties and methods."""
    guest_ctx = AuthContext(role=Role.GUEST)
    assert not guest_ctx.authenticated
    assert guest_ctx.role_label == 'guest'
    assert guest_ctx.has_role(Role.GUEST)
    assert not guest_ctx.has_role(Role.USER)
    assert not guest_ctx.has_role(Role.CREATOR)

    user_ctx = AuthContext(role=Role.USER, email='user@example.com', name='Alice')
    assert user_ctx.authenticated
    assert user_ctx.role_label == 'user'
    assert user_ctx.has_role(Role.GUEST)
    assert user_ctx.has_role(Role.USER)
    assert not user_ctx.has_role(Role.CREATOR)

    creator_ctx = AuthContext(role=Role.CREATOR, email='creator@example.com', name='Bob')
    assert creator_ctx.authenticated
    assert creator_ctx.role_label == 'creator'
    assert creator_ctx.has_role(Role.GUEST)
    assert creator_ctx.has_role(Role.USER)
    assert creator_ctx.has_role(Role.CREATOR)


def test_resolve_role_disabled() -> None:
    """When auth is disabled, role is always CREATOR."""
    ctx = _resolve_role_disabled()
    assert ctx.role == Role.CREATOR
    assert not ctx.authenticated


def test_resolve_role_cloudflare_resolution() -> None:
    """Verify Cloudflare header resolution against email allow-lists."""
    settings = AppSettings(
        immich_server_url='https://placeholder.example.com/api',
        immich_libraries={'family': 'token'},
        data_path=Path('/tmp'),
        auth_mode='cloudflare',
        cf_creator_emails=frozenset({'creator@example.com'}),
        cf_user_emails=frozenset({'user1@example.com', 'user2@example.com'}),
    )

    app = FastAPI()
    app.state.settings = settings

    def make_req(email: str | None) -> Request:
        headers: list[tuple[bytes, bytes]] = []
        if email is not None:
            headers.append((b'cf-access-authenticated-user-email', email.encode('utf-8')))
        scope = {
            'type': 'http',
            'app': app,
            'headers': headers,
        }
        return Request(scope)

    # 1. No header -> Guest
    ctx = _resolve_role_cloudflare(make_req(None))
    assert ctx.role == Role.GUEST
    assert not ctx.authenticated

    # 2. Empty or whitespace header -> Guest
    ctx = _resolve_role_cloudflare(make_req('   '))
    assert ctx.role == Role.GUEST
    assert not ctx.authenticated

    # 3. Creator email (case-insensitive) -> Creator
    ctx = _resolve_role_cloudflare(make_req('CREATOR@EXAMPLE.COM'))
    assert ctx.role == Role.CREATOR
    assert ctx.email == 'creator@example.com'
    assert ctx.authenticated

    # 4. User email -> User
    ctx = _resolve_role_cloudflare(make_req('user1@example.com'))
    assert ctx.role == Role.USER
    assert ctx.email == 'user1@example.com'
    assert ctx.authenticated

    # 5. Unknown email -> Guest (with email preserved)
    ctx = _resolve_role_cloudflare(make_req('stranger@example.com'))
    assert ctx.role == Role.GUEST
    assert ctx.email == 'stranger@example.com'
    assert ctx.authenticated


@pytest.mark.asyncio
async def test_require_role_dependency_enforcement() -> None:
    """Verify require_role allows authorized callers and raises HTTP 403 for unauthorized callers."""
    creator_dep = require_role(Role.CREATOR)
    user_dep = require_role(Role.USER)

    creator_ctx = AuthContext(role=Role.CREATOR)
    user_ctx = AuthContext(role=Role.USER)
    guest_ctx = AuthContext(role=Role.GUEST)

    # Creator accessing Creator endpoint -> OK
    assert await creator_dep(creator_ctx) == creator_ctx
    # User accessing Creator endpoint -> 403
    with pytest.raises(HTTPException) as exc_info:
        await creator_dep(user_ctx)
    assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
    assert 'restricted to creators' in str(exc_info.value.detail)

    # Guest accessing User endpoint -> 403
    with pytest.raises(HTTPException) as exc_info:
        await user_dep(guest_ctx)
    assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
    assert 'restricted to users' in str(exc_info.value.detail)

    # User accessing User endpoint -> OK
    assert await user_dep(user_ctx) == user_ctx


def test_auth_me_endpoint_disabled_mode(tmp_path: Path) -> None:
    """GET /api/auth/me returns creator when auth_mode is disabled."""
    settings = AppSettings(
        immich_server_url='https://placeholder.example.com/api',
        immich_libraries={'family': 'token'},
        data_path=tmp_path,
        auth_mode='disabled',
    )
    app = create_app(settings=settings)
    app.state.immich_client = FakeImmichClient()

    with TestClient(app) as client:
        resp = client.get('/api/auth/me')
        assert resp.status_code == 200
        data = resp.json()
        assert data['role'] == 'creator'
        assert data['email'] is None
        assert data['authenticated'] is False


def test_auth_me_and_route_rbac_cloudflare_mode(tmp_path: Path) -> None:
    """Integration test of GET /api/auth/me and RBAC route enforcement in Cloudflare mode."""
    creator_email = 'owner@example.com'
    user_email = 'player@example.com'

    settings = AppSettings(
        immich_server_url='https://placeholder.example.com/api',
        immich_libraries={'family': 'token'},
        data_path=tmp_path,
        auth_mode='cloudflare',
        cf_creator_emails=frozenset({creator_email}),
        cf_user_emails=frozenset({user_email}),
    )
    app = create_app(settings=settings)
    app.state.immich_client = FakeImmichClient()

    with TestClient(app) as client:
        # 1. Unauthenticated / Guest request (no header)
        resp = client.get('/api/auth/me')
        assert resp.status_code == 200
        assert resp.json()['role'] == 'guest'
        assert resp.json()['authenticated'] is False

        # Guest trying to access Creator route (/api/libraries) -> 403
        resp = client.get('/api/libraries')
        assert resp.status_code == 403

        # Guest trying to access User route (/api/leaderboard) -> 403
        resp = client.get('/api/leaderboard')
        assert resp.status_code == 403

        # Guest trying to list challenges -> 403
        resp = client.get('/api/challenge/list')
        assert resp.status_code == 403

        # 2. User request (authenticated as user)
        user_headers = {'cf-access-authenticated-user-email': user_email}
        resp = client.get('/api/auth/me', headers=user_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data['role'] == 'user'
        assert data['email'] == user_email
        assert data['authenticated'] is True

        # User accessing User route (/api/leaderboard) -> 200
        resp = client.get('/api/leaderboard', headers=user_headers)
        assert resp.status_code == 200

        # User accessing User route (/api/challenge/list) -> 200
        resp = client.get('/api/challenge/list', headers=user_headers)
        assert resp.status_code == 200

        # User trying to access Creator route (/api/libraries) -> 403
        resp = client.get('/api/libraries', headers=user_headers)
        assert resp.status_code == 403

        # User trying to access Creator route (/api/game/setup) -> 403
        resp = client.post('/api/game/setup', json={'players': ['Alice']}, headers=user_headers)
        assert resp.status_code == 403

        # 3. Creator request (authenticated as creator)
        creator_headers = {'cf-access-authenticated-user-email': creator_email}
        resp = client.get('/api/auth/me', headers=creator_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data['role'] == 'creator'
        assert data['email'] == creator_email
        assert data['authenticated'] is True

        # Creator accessing Creator route (/api/libraries) -> 200
        resp = client.get('/api/libraries', headers=creator_headers)
        assert resp.status_code == 200

        # Creator accessing User route (/api/leaderboard) -> 200
        resp = client.get('/api/leaderboard', headers=creator_headers)
        assert resp.status_code == 200

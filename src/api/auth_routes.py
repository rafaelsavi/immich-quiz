"""Authentication API endpoint returning the current user's role and identity."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from src.auth.models import AuthContext
from src.auth.service import get_current_auth

auth_router = APIRouter(prefix='/api/auth', tags=['auth'])


@auth_router.get('/me')
async def get_current_user(auth: AuthContext = Depends(get_current_auth)) -> dict[str, Any]:
    """Return the resolved role, email, and authentication status for the current request."""
    return {
        'role': auth.role_label,
        'email': auth.email,
        'name': auth.name,
        'authenticated': auth.authenticated,
    }

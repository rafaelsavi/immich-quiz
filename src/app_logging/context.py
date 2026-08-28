"""Thread-safe and async-safe contextual logging state using contextvars."""

from __future__ import annotations

import contextvars
from collections.abc import Generator
from contextlib import contextmanager
from typing import Any

# Asynchronous / thread-local context variables for structured tracing
ctx_request_id: contextvars.ContextVar[str | None] = contextvars.ContextVar('request_id', default=None)
ctx_match_id: contextvars.ContextVar[str | None] = contextvars.ContextVar('match_id', default=None)
ctx_player_name: contextvars.ContextVar[str | None] = contextvars.ContextVar('player_name', default=None)
ctx_library_name: contextvars.ContextVar[str | None] = contextvars.ContextVar('library_name', default=None)


def get_current_context() -> dict[str, Any]:
    """Retrieve a dictionary of all currently active logging context variables."""
    ctx: dict[str, Any] = {}
    if req_id := ctx_request_id.get():
        ctx['request_id'] = req_id
    if match_id := ctx_match_id.get():
        ctx['match_id'] = match_id
    if player := ctx_player_name.get():
        ctx['player_name'] = player
    if lib := ctx_library_name.get():
        ctx['library_name'] = lib
    return ctx


@contextmanager
def bind_match_context(
    match_id: str | None,
    player_name: str | None = None,
    library_name: str | None = None,
) -> Generator[None, None, None]:
    """Context manager to bind match-specific variables for the duration of a block."""
    token_match = ctx_match_id.set(match_id)
    token_player = ctx_player_name.set(player_name)
    token_lib = ctx_library_name.set(library_name)
    try:
        yield
    finally:
        ctx_match_id.reset(token_match)
        ctx_player_name.reset(token_player)
        ctx_library_name.reset(token_lib)


@contextmanager
def bind_request_context(
    request_id: str | None,
    match_id: str | None = None,
) -> Generator[None, None, None]:
    """Context manager to bind HTTP request-specific variables for the duration of a request."""
    token_req = ctx_request_id.set(request_id)
    token_match = ctx_match_id.set(match_id) if match_id is not None else None
    try:
        yield
    finally:
        ctx_request_id.reset(token_req)
        if token_match is not None:
            ctx_match_id.reset(token_match)


def clear_context() -> None:
    """Reset all active logging context variables to None."""
    ctx_request_id.set(None)
    ctx_match_id.set(None)
    ctx_player_name.set(None)
    ctx_library_name.set(None)

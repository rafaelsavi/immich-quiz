"""FastAPI / Starlette middleware for request tracing, context binding, and access logging."""

from __future__ import annotations

import time
import uuid
from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from src.logging.context import ctx_match_id, ctx_request_id
from src.logging.setup import get_logger

logger = get_logger('api')


def _extract_match_id(path: str) -> str | None:
    """Extract match_id from path pattern like /api/matches/{match_id}/..."""
    parts = path.strip('/').split('/')
    if len(parts) >= 3 and parts[0] == 'api' and parts[1] == 'matches':
        candidate = parts[2]
        if candidate not in {'setup', 'active', 'preflight'}:
            return candidate
    return None


class LoggingContextMiddleware(BaseHTTPMiddleware):
    """Middleware that injects request/match context and logs structured HTTP metrics."""

    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        # Extract or generate Request ID
        request_id = request.headers.get('X-Request-ID') or f'req_{uuid.uuid4().hex[:8]}'
        token_req = ctx_request_id.set(request_id)

        # Extract Match ID from URL path or header
        match_id = request.headers.get('X-Match-ID') or _extract_match_id(request.url.path)
        token_match = ctx_match_id.set(match_id)

        start_time = time.perf_counter()

        try:
            response = await call_next(request)
            duration_ms = (time.perf_counter() - start_time) * 1000.0

            # Attach X-Request-ID to response headers
            response.headers['X-Request-ID'] = request_id

            # Log API requests (exclude noisy static assets from INFO unless 4xx/5xx)
            path = request.url.path
            is_static = path.startswith('/static/') or path.endswith(
                ('.ico', '.png', '.svg', '.js', '.css', '.webmanifest')
            )

            if not is_static or response.status_code >= 400:
                status_emoji = '🟢' if response.status_code < 400 else ('🟡' if response.status_code < 500 else '🔴')
                logger.info(
                    '%s %s %s -> %d %s (%.1fms)',
                    status_emoji,
                    request.method,
                    path,
                    response.status_code,
                    response.status_code,
                    duration_ms,
                )

            return response
        except Exception as exc:
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            logger.exception(
                '🔴 %s %s -> 500 ERROR (%.1fms): %s',
                request.method,
                request.url.path,
                duration_ms,
                exc,
            )
            raise
        finally:
            ctx_request_id.reset(token_req)
            ctx_match_id.reset(token_match)

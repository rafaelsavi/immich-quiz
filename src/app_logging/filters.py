"""Logging filters for context enrichment and sensitive credential redaction."""

from __future__ import annotations

import logging
import re

from src.app_logging.context import ctx_library_name, ctx_match_id, ctx_player_name, ctx_request_id

# Regex pattern to match API keys, bearer tokens, or sensitive header strings
_SENSITIVE_PATTERNS = [
    re.compile(r'(?i)(api[_-]?key|token|authorization|x-api-key)\s*[:=]\s*["\']?([a-zA-Z0-9_\-\.]{8,})["\']?'),
]


def redact_sensitive_text(text: str) -> str:
    """Mask sensitive tokens or API keys within a string, preserving only last 4 characters."""
    result = text
    for pattern in _SENSITIVE_PATTERNS:

        def _repl(match: re.Match[str]) -> str:
            key_name = match.group(1)
            secret = match.group(2)
            masked = '******' if len(secret) <= 6 else f'******{secret[-4:]}'
            return f'{key_name}={masked}'

        result = pattern.sub(_repl, result)
    return result


class ContextFilter(logging.Filter):
    """Enriches LogRecord instances with thread/async contextvars (match_id, request_id, etc.)."""

    def filter(self, record: logging.LogRecord) -> bool:
        # Attach context attributes to record if not already explicitly provided
        if not hasattr(record, 'match_id'):
            record.match_id = ctx_match_id.get()
        if not hasattr(record, 'request_id'):
            record.request_id = ctx_request_id.get()
        if not hasattr(record, 'player_name'):
            record.player_name = ctx_player_name.get()
        if not hasattr(record, 'library_name'):
            record.library_name = ctx_library_name.get()

        # Deduce a clean subsystem name from logger name (e.g. 'immich_quiz.match' -> 'match')
        if not hasattr(record, 'subsystem'):
            name = record.name
            if name.startswith('immich_quiz.'):
                record.subsystem = name.removeprefix('immich_quiz.')
            elif name.startswith('src.'):
                record.subsystem = name.removeprefix('src.')
            elif name == 'uvicorn.access':
                record.subsystem = 'api'
            elif name.startswith('uvicorn'):
                record.subsystem = 'server'
            else:
                record.subsystem = name

        return True


class RedactionFilter(logging.Filter):
    """Redacts API keys and sensitive tokens from log messages and formatting arguments."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = redact_sensitive_text(record.msg)

        if record.args:
            if isinstance(record.args, dict):
                record.args = {
                    k: redact_sensitive_text(str(v)) if isinstance(v, str) else v for k, v in record.args.items()
                }
            elif isinstance(record.args, (list, tuple)):
                record.args = tuple(redact_sensitive_text(str(a)) if isinstance(a, str) else a for a in record.args)

        return True

"""Observability and structured logging package for Immich Quiz."""

from __future__ import annotations

from src.app_logging.context import (
    bind_match_context,
    bind_request_context,
    clear_context,
    get_current_context,
)
from src.app_logging.middleware import LoggingContextMiddleware
from src.app_logging.setup import (
    LOGGER_API,
    LOGGER_IMMICH,
    LOGGER_MATCH,
    LOGGER_SCORING,
    LOGGER_STORAGE,
    LOGGER_SYNC,
    get_logger,
    setup_logging,
)

__all__ = [
    'LOGGER_API',
    'LOGGER_IMMICH',
    'LOGGER_MATCH',
    'LOGGER_SCORING',
    'LOGGER_STORAGE',
    'LOGGER_SYNC',
    'LoggingContextMiddleware',
    'bind_match_context',
    'bind_request_context',
    'clear_context',
    'get_current_context',
    'get_logger',
    'setup_logging',
]

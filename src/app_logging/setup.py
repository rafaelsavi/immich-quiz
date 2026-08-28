"""Central logging initialization and configuration engine."""

from __future__ import annotations

import logging
import sys
from typing import TYPE_CHECKING

from src.app_logging.filters import ContextFilter, RedactionFilter
from src.app_logging.formatter import ConsoleLogFormatter

if TYPE_CHECKING:
    from src.config import AppSettings

# Subsystem logger names
LOGGER_MATCH = 'immich_quiz.match'
LOGGER_SCORING = 'immich_quiz.scoring'
LOGGER_SYNC = 'immich_quiz.sync'
LOGGER_IMMICH = 'immich_quiz.immich'
LOGGER_API = 'immich_quiz.api'
LOGGER_STORAGE = 'immich_quiz.storage'


def _parse_level(level_name: str | None, default: int = logging.INFO) -> int:
    """Safely convert a string log level (e.g. 'DEBUG', 'INFO') to logging int constant."""
    if not level_name:
        return default
    cleaned = level_name.strip().upper()
    if hasattr(logging, 'getLevelNamesMapping'):
        return logging.getLevelNamesMapping().get(cleaned, default)
    val = getattr(logging, cleaned, None)
    if isinstance(val, int):
        return val
    return default


def setup_logging(settings: AppSettings | None = None) -> None:
    """Initialize and configure the application-wide logging system."""
    # Determine base log level
    base_level_str = getattr(settings, 'log_level', 'INFO') if settings else 'INFO'
    base_level = _parse_level(base_level_str, logging.INFO)

    # Root Logger Setup
    root_logger = logging.getLogger()
    root_logger.setLevel(base_level)

    # Remove any existing handlers on root to prevent duplicate log lines
    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)

    # Standard Console Handler targeting stdout (captured by docker logs)
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.DEBUG)  # Handlers pass all records; loggers filter by level

    # Attach filters
    context_filter = ContextFilter()
    redaction_filter = RedactionFilter()
    handler.addFilter(context_filter)
    handler.addFilter(redaction_filter)

    # Attach formatter
    formatter = ConsoleLogFormatter()
    handler.setFormatter(formatter)

    root_logger.addHandler(handler)

    # Configure subsystem log levels if custom overrides are specified
    subsystem_overrides = {
        LOGGER_SCORING: getattr(settings, 'log_level_scoring', None),
        LOGGER_SYNC: getattr(settings, 'log_level_sync', None),
        LOGGER_IMMICH: getattr(settings, 'log_level_immich', None),
        LOGGER_MATCH: getattr(settings, 'log_level_match', None),
        LOGGER_API: getattr(settings, 'log_level_api', None),
        LOGGER_STORAGE: getattr(settings, 'log_level_storage', None),
    }

    for logger_name, override_val in subsystem_overrides.items():
        sub_logger = logging.getLogger(logger_name)
        if override_val:
            sub_logger.setLevel(_parse_level(override_val, base_level))
        else:
            sub_logger.setLevel(base_level)

    # Tune third-party noisier loggers
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('asyncio').setLevel(logging.WARNING)
    logging.getLogger('httpx').setLevel(logging.WARNING)
    logging.getLogger('httpcore').setLevel(logging.WARNING)
    logging.getLogger('uvicorn.error').handlers = []
    logging.getLogger('uvicorn.access').handlers = []


def get_logger(name: str) -> logging.Logger:
    """Return a namespaced application logger."""
    if not name.startswith('immich_quiz.') and not name.startswith('src.'):
        return logging.getLogger(f'immich_quiz.{name}')
    return logging.getLogger(name)

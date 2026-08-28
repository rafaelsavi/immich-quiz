"""Unit tests for structured logging, console formatting, context binding, and credential redaction."""

from __future__ import annotations

import logging

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.config import AppSettings, ConfigError
from src.logging import (
    LOGGER_MATCH,
    LOGGER_SCORING,
    LoggingContextMiddleware,
    bind_match_context,
    bind_request_context,
    clear_context,
    get_current_context,
    setup_logging,
)
from src.logging.filters import ContextFilter, RedactionFilter, redact_sensitive_text
from src.logging.formatter import ConsoleLogFormatter


@pytest.fixture(autouse=True)
def _reset_context() -> None:
    clear_context()
    yield
    clear_context()


# ---------------------------------------------------------------------------
# Redaction Filter Tests
# ---------------------------------------------------------------------------


def test_redact_sensitive_text() -> None:
    text = 'Connecting with api_key=secret_1234567890 and token: my_secret_token_1234'
    redacted = redact_sensitive_text(text)
    assert 'secret_1234567890' not in redacted
    assert 'my_secret_token_1234' not in redacted
    assert 'api_key=******7890' in redacted
    assert 'token=******1234' in redacted


def test_redaction_filter_in_log_record() -> None:
    filt = RedactionFilter()
    record = logging.LogRecord(
        name='test',
        level=logging.INFO,
        pathname='test.py',
        lineno=1,
        msg='Failed auth with api_key=supersecrettoken123',
        args=(),
        exc_info=None,
    )
    filt.filter(record)
    assert 'supersecrettoken123' not in record.msg
    assert 'api_key=******n123' in record.msg


def test_redaction_filter_in_record_args() -> None:
    filt = RedactionFilter()
    record = logging.LogRecord(
        name='test',
        level=logging.INFO,
        pathname='test.py',
        lineno=1,
        msg='Header: %s',
        args=('x-api-key: header_secret_9999',),
        exc_info=None,
    )
    filt.filter(record)
    assert 'header_secret_9999' not in record.args[0]
    assert 'x-api-key=******9999' in record.args[0]


# ---------------------------------------------------------------------------
# Context Binding Tests
# ---------------------------------------------------------------------------


def test_context_binding_and_clearing() -> None:
    assert get_current_context() == {}

    with bind_match_context('match_12345678_abcd', player_name='Alice', library_name='Vacation'):
        ctx = get_current_context()
        assert ctx['match_id'] == 'match_12345678_abcd'
        assert ctx['player_name'] == 'Alice'
        assert ctx['library_name'] == 'Vacation'

    assert get_current_context() == {}


def test_context_filter_injects_into_record() -> None:
    filt = ContextFilter()
    with bind_match_context('8f2a1b3c4d', player_name='Bob'), bind_request_context('req_9876'):
        record = logging.LogRecord(
            name='immich_quiz.scoring',
            level=logging.INFO,
            pathname='scoring.py',
            lineno=10,
            msg='Calculated decay',
            args=(),
            exc_info=None,
        )
        filt.filter(record)
        assert record.match_id == '8f2a1b3c4d'
        assert record.request_id == 'req_9876'
        assert record.player_name == 'Bob'
        assert record.subsystem == 'scoring'


# ---------------------------------------------------------------------------
# Formatter Tests
# ---------------------------------------------------------------------------


def test_console_formatter_plain() -> None:
    formatter = ConsoleLogFormatter(use_colors=False)
    record = logging.LogRecord(
        name='immich_quiz.match',
        level=logging.INFO,
        pathname='test.py',
        lineno=1,
        msg='Match created successfully',
        args=(),
        exc_info=None,
    )
    record.match_id = '8f2a1b3c-extra'
    record.subsystem = 'match'

    output = formatter.format(record)
    assert '[INFO ]' in output
    assert '[match:8f2a1b3c]' in output
    assert 'Match created successfully' in output


def test_console_formatter_with_library_context() -> None:
    formatter = ConsoleLogFormatter(use_colors=False)
    record = logging.LogRecord(
        name='immich_quiz.sync',
        level=logging.WARNING,
        pathname='sync.py',
        lineno=1,
        msg='Sync timed out',
        args=(),
        exc_info=None,
    )
    record.library_name = 'FamilyArchive'
    record.subsystem = 'sync'

    output = formatter.format(record)
    assert '[WARN ]' in output or '[WARNING]' in output
    assert '[sync:FamilyArchive]' in output
    assert 'Sync timed out' in output


# ---------------------------------------------------------------------------
# Configuration & Setup Tests
# ---------------------------------------------------------------------------


def test_setup_logging_and_overrides() -> None:
    settings = AppSettings(
        immich_server_url='http://localhost:2283',
        immich_libraries={'Default': 'dummy_key'},
        log_level='WARNING',
        log_level_scoring='DEBUG',
        log_level_match='INFO',
    )
    setup_logging(settings)

    root_logger = logging.getLogger()
    assert root_logger.level == logging.WARNING

    scoring_logger = logging.getLogger(LOGGER_SCORING)
    assert scoring_logger.level == logging.DEBUG

    match_logger = logging.getLogger(LOGGER_MATCH)
    assert match_logger.level == logging.INFO


def test_invalid_log_level_raises() -> None:
    with pytest.raises(ConfigError, match='LOG_LEVEL'):
        AppSettings(
            immich_server_url='http://localhost:2283',
            immich_libraries={'Default': 'dummy_key'},
            log_level='INVALID_LEVEL',
        )


# ---------------------------------------------------------------------------
# Middleware Tracing Tests
# ---------------------------------------------------------------------------


def test_logging_middleware_tracing() -> None:
    app = FastAPI()
    app.add_middleware(LoggingContextMiddleware)

    @app.get('/api/matches/{match_id}/status')
    def get_status(match_id: str) -> dict[str, str]:
        ctx = get_current_context()
        return {'match_id': ctx.get('match_id', ''), 'request_id': ctx.get('request_id', '')}

    client = TestClient(app)
    response = client.get('/api/matches/test_match_999/status', headers={'X-Request-ID': 'custom_req_123'})

    assert response.status_code == 200
    data = response.json()
    assert data['match_id'] == 'test_match_999'
    assert data['request_id'] == 'custom_req_123'
    assert response.headers.get('X-Request-ID') == 'custom_req_123'

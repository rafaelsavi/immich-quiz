from __future__ import annotations

from datetime import date

import pytest

from src import config
from src.config import ConfigError, load_settings


@pytest.fixture(autouse=True)
def isolated_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(config, 'load_dotenv', lambda *args, **kwargs: False)
    for key in (
        'IMMICH_SERVER_URL',
        'IMMICH_LIBRARIES',
        'LEADERBOARD_CSV_PATH',
        'APP_TITLE',
        'APP_TAGLINE',
        'INCLUDE_SHARED_ALBUMS',
        'INCLUDE_PARTNER_ASSETS',
        'APP_HOST',
        'APP_PORT',
        'FETCH_PHOTOS_DATE_LOWER_BOUND',
        'FETCH_PHOTOS_DATE_UPPER_BOUND',
        'SCORE_MAX_POINTS',
        'LOCATION_SCORE_DECAY_KM',
        'DATE_SCORE_DECAY_DAYS',
        'LANGUAGE',
    ):
        monkeypatch.delenv(key, raising=False)


def test_missing_server_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv('IMMICH_LIBRARIES', '{"family": "token"}')
    with pytest.raises(ConfigError, match='IMMICH_SERVER_URL'):
        load_settings()


def test_missing_libraries(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv('IMMICH_SERVER_URL', 'https://example.test/api')
    with pytest.raises(ConfigError, match='IMMICH_LIBRARIES'):
        load_settings()


def test_malformed_libraries_json(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv('IMMICH_SERVER_URL', 'https://example.test/api')
    monkeypatch.setenv('IMMICH_LIBRARIES', '{not json}')
    with pytest.raises(ConfigError, match='valid JSON'):
        load_settings()


def test_empty_libraries_mapping(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv('IMMICH_SERVER_URL', 'https://example.test/api')
    monkeypatch.setenv('IMMICH_LIBRARIES', '{}')
    with pytest.raises(ConfigError, match='non-empty JSON object'):
        load_settings()


def test_blank_library_key_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv('IMMICH_SERVER_URL', 'https://example.test/api')
    monkeypatch.setenv('IMMICH_LIBRARIES', '{"family": "  "}')
    with pytest.raises(ConfigError, match='non-empty API key'):
        load_settings()


def test_non_integer_port(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv('IMMICH_SERVER_URL', 'https://example.test/api')
    monkeypatch.setenv('IMMICH_LIBRARIES', '{"family": "token"}')
    monkeypatch.setenv('APP_PORT', 'not-a-port')
    with pytest.raises(ConfigError, match='APP_PORT'):
        load_settings()


def test_valid_settings_normalizes_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv('IMMICH_SERVER_URL', 'https://example.test/api/')
    monkeypatch.setenv('IMMICH_LIBRARIES', '{" family ": " token "}')

    settings = load_settings()

    assert settings.immich_server_url == 'https://example.test/api'
    assert settings.immich_libraries == {'family': 'token'}
    assert settings.app_title == 'Immich Quiz'
    assert settings.app_tagline == ''
    assert settings.include_shared_albums is False
    assert settings.include_partner_assets is False
    assert settings.app_host == '127.0.0.1'
    assert settings.app_port == 8010
    assert settings.fetch_photos_date_lower_bound is None
    assert settings.fetch_photos_date_upper_bound is None
    assert settings.score_max_points == 100
    assert settings.location_score_decay_km == 500.0
    assert settings.date_score_decay_days == 500.0


@pytest.mark.parametrize(
    'raw_url, expected_url',
    [
        ('https://example.test', 'https://example.test/api'),
        ('https://example.test/', 'https://example.test/api'),
        ('https://example.test/api', 'https://example.test/api'),
        ('https://example.test/api/', 'https://example.test/api'),
        ('http://192.168.1.10:2283', 'http://192.168.1.10:2283/api'),
        ('http://192.168.1.10:2283/', 'http://192.168.1.10:2283/api'),
    ],
)
def test_server_url_adds_api_if_missing(monkeypatch: pytest.MonkeyPatch, raw_url: str, expected_url: str) -> None:
    monkeypatch.setenv('IMMICH_SERVER_URL', raw_url)
    monkeypatch.setenv('IMMICH_LIBRARIES', '{"family": "token"}')
    settings = load_settings()
    assert settings.immich_server_url == expected_url


def test_date_bounds_parse_when_valid(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv('IMMICH_SERVER_URL', 'https://example.test/api')
    monkeypatch.setenv('IMMICH_LIBRARIES', '{"family": "token"}')
    monkeypatch.setenv('FETCH_PHOTOS_DATE_LOWER_BOUND', '2020-01-01')
    monkeypatch.setenv('FETCH_PHOTOS_DATE_UPPER_BOUND', '2024-12-31')

    settings = load_settings()

    assert settings.fetch_photos_date_lower_bound == date(2020, 1, 1)
    assert settings.fetch_photos_date_upper_bound == date(2024, 12, 31)


def test_date_lower_bound_rejects_invalid_format(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv('IMMICH_SERVER_URL', 'https://example.test/api')
    monkeypatch.setenv('IMMICH_LIBRARIES', '{"family": "token"}')
    monkeypatch.setenv('FETCH_PHOTOS_DATE_LOWER_BOUND', '2020/01/01')

    with pytest.raises(ConfigError, match='FETCH_PHOTOS_DATE_LOWER_BOUND'):
        load_settings()


def test_date_bounds_reject_inverted_range(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv('IMMICH_SERVER_URL', 'https://example.test/api')
    monkeypatch.setenv('IMMICH_LIBRARIES', '{"family": "token"}')
    monkeypatch.setenv('FETCH_PHOTOS_DATE_LOWER_BOUND', '2025-01-01')
    monkeypatch.setenv('FETCH_PHOTOS_DATE_UPPER_BOUND', '2024-12-31')

    with pytest.raises(ConfigError, match='on or before'):
        load_settings()


def test_include_shared_albums_accepts_true(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv('IMMICH_SERVER_URL', 'https://example.test/api')
    monkeypatch.setenv('IMMICH_LIBRARIES', '{"family": "token"}')
    monkeypatch.setenv('INCLUDE_SHARED_ALBUMS', 'true')

    settings = load_settings()

    assert settings.include_shared_albums is True


def test_include_shared_albums_rejects_invalid(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv('IMMICH_SERVER_URL', 'https://example.test/api')
    monkeypatch.setenv('IMMICH_LIBRARIES', '{"family": "token"}')
    monkeypatch.setenv('INCLUDE_SHARED_ALBUMS', 'maybe')

    with pytest.raises(ConfigError, match='INCLUDE_SHARED_ALBUMS'):
        load_settings()


def test_include_partner_assets_accepts_true(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv('IMMICH_SERVER_URL', 'https://example.test/api')
    monkeypatch.setenv('IMMICH_LIBRARIES', '{"family": "token"}')
    monkeypatch.setenv('INCLUDE_PARTNER_ASSETS', 'true')

    settings = load_settings()

    assert settings.include_partner_assets is True


def test_include_partner_assets_rejects_invalid(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv('IMMICH_SERVER_URL', 'https://example.test/api')
    monkeypatch.setenv('IMMICH_LIBRARIES', '{"family": "token"}')
    monkeypatch.setenv('INCLUDE_PARTNER_ASSETS', 'maybe')

    with pytest.raises(ConfigError, match='INCLUDE_PARTNER_ASSETS'):
        load_settings()


def test_custom_app_title(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv('IMMICH_SERVER_URL', 'https://example.test/api')
    monkeypatch.setenv('IMMICH_LIBRARIES', '{"family": "token"}')
    monkeypatch.setenv('APP_TITLE', 'Quiz Night')

    settings = load_settings()

    assert settings.app_title == 'Quiz Night'


def test_score_max_points_rejects_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv('IMMICH_SERVER_URL', 'https://example.test/api')
    monkeypatch.setenv('IMMICH_LIBRARIES', '{"family": "token"}')
    monkeypatch.setenv('SCORE_MAX_POINTS', '0')

    with pytest.raises(ConfigError, match='SCORE_MAX_POINTS'):
        load_settings()


def test_location_score_decay_km_rejects_non_positive(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv('IMMICH_SERVER_URL', 'https://example.test/api')
    monkeypatch.setenv('IMMICH_LIBRARIES', '{"family": "token"}')
    monkeypatch.setenv('LOCATION_SCORE_DECAY_KM', '-1')

    with pytest.raises(ConfigError, match='LOCATION_SCORE_DECAY_KM'):
        load_settings()


def test_date_score_decay_days_rejects_non_numeric(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv('IMMICH_SERVER_URL', 'https://example.test/api')
    monkeypatch.setenv('IMMICH_LIBRARIES', '{"family": "token"}')
    monkeypatch.setenv('DATE_SCORE_DECAY_DAYS', 'fast')

    with pytest.raises(ConfigError, match='DATE_SCORE_DECAY_DAYS'):
        load_settings()


def test_language_setting_supports_pt(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv('IMMICH_SERVER_URL', 'https://example.test/api')
    monkeypatch.setenv('IMMICH_LIBRARIES', '{"family": "token"}')
    monkeypatch.setenv('LANGUAGE', 'pt')

    settings = load_settings()

    assert settings.language == 'PT'


def test_language_setting_rejects_invalid(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv('IMMICH_SERVER_URL', 'https://example.test/api')
    monkeypatch.setenv('IMMICH_LIBRARIES', '{"family": "token"}')
    monkeypatch.setenv('LANGUAGE', 'fr')

    with pytest.raises(ConfigError, match='LANGUAGE'):
        load_settings()

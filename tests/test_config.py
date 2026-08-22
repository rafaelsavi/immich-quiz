from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from src import config
from src.config import AppSettings, ConfigError, load_settings


@pytest.fixture(autouse=True)
def isolated_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(config, 'load_dotenv', lambda *args, **kwargs: False)
    for key in (
        'IMMICH_SERVER_URL',
        'IMMICH_LIBRARIES',
        'APP_TITLE',
        'APP_TAGLINE',
        'APP_HOST',
        'APP_PORT',
        'DATE_LOWER_BOUND',
        'DATE_UPPER_BOUND',
        'FETCH_PHOTOS_DATE_LOWER_BOUND',
        'FETCH_PHOTOS_DATE_UPPER_BOUND',
        'LOCATION_SCORE_DECAY_KM',
        'DATE_SCORE_DECAY_DAYS',
        'LANGUAGE',
        'DATA_PATH',
        'DATA_DIR',
        'COUNTRY_WHITELIST',
        'COUNTRY_BLACKLIST',
        'CITY_WHITELIST',
        'CITY_BLACKLIST',
        'PEOPLE_WHITELIST',
        'PEOPLE_BLACKLIST',
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
    assert settings.app_host == '127.0.0.1'
    assert settings.app_port == 8010
    assert settings.date_lower_bound is None
    assert settings.date_upper_bound is None
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
    monkeypatch.setenv('DATE_LOWER_BOUND', '2020-01-01')
    monkeypatch.setenv('DATE_UPPER_BOUND', '2024-12-31')

    settings = load_settings()

    assert settings.date_lower_bound == date(2020, 1, 1)
    assert settings.date_upper_bound == date(2024, 12, 31)


def test_legacy_fetch_photos_date_bounds_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv('IMMICH_SERVER_URL', 'https://example.test/api')
    monkeypatch.setenv('IMMICH_LIBRARIES', '{"family": "token"}')
    monkeypatch.setenv('FETCH_PHOTOS_DATE_LOWER_BOUND', '2019-05-01')
    monkeypatch.setenv('FETCH_PHOTOS_DATE_UPPER_BOUND', '2023-08-31')

    settings = load_settings()

    assert settings.date_lower_bound == date(2019, 5, 1)
    assert settings.date_upper_bound == date(2023, 8, 31)


def test_date_lower_bound_rejects_invalid_format(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv('IMMICH_SERVER_URL', 'https://example.test/api')
    monkeypatch.setenv('IMMICH_LIBRARIES', '{"family": "token"}')
    monkeypatch.setenv('DATE_LOWER_BOUND', '2020/01/01')

    with pytest.raises(ConfigError, match='DATE_LOWER_BOUND'):
        load_settings()


def test_date_bounds_reject_inverted_range(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv('IMMICH_SERVER_URL', 'https://example.test/api')
    monkeypatch.setenv('IMMICH_LIBRARIES', '{"family": "token"}')
    monkeypatch.setenv('DATE_LOWER_BOUND', '2025-01-01')
    monkeypatch.setenv('DATE_UPPER_BOUND', '2024-12-31')

    with pytest.raises(ConfigError, match='on or before'):
        load_settings()


def test_custom_app_title(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv('IMMICH_SERVER_URL', 'https://example.test/api')
    monkeypatch.setenv('IMMICH_LIBRARIES', '{"family": "token"}')
    monkeypatch.setenv('APP_TITLE', 'Quiz Night')

    settings = load_settings()

    assert settings.app_title == 'Quiz Night'


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


@pytest.mark.parametrize(
    'raw_val, expected',
    [
        (None, frozenset()),
        ('', frozenset()),
        ('   ', frozenset()),
        ('Brazil', frozenset({'brazil'})),
        ('Brazil, France, Germany', frozenset({'brazil', 'france', 'germany'})),
        ('  brazil  ,  FRANCE , Germany ', frozenset({'brazil', 'france', 'germany'})),
        (' , alice , , Bob, ', frozenset({'alice', 'bob'})),
    ],
)
def test_parse_comma_set(raw_val: str | None, expected: frozenset[str]) -> None:
    from src.config import _parse_comma_set

    assert _parse_comma_set(raw_val) == expected


def test_default_whitelists_and_blacklists_are_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv('IMMICH_SERVER_URL', 'https://example.test/api')
    monkeypatch.setenv('IMMICH_LIBRARIES', '{"family": "token"}')

    settings = load_settings()

    assert settings.country_whitelist == frozenset()
    assert settings.country_blacklist == frozenset()
    assert settings.city_whitelist == frozenset()
    assert settings.city_blacklist == frozenset()
    assert settings.people_whitelist == frozenset()
    assert settings.people_blacklist == frozenset()


def test_custom_whitelists_and_blacklists_parsed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv('IMMICH_SERVER_URL', 'https://example.test/api')
    monkeypatch.setenv('IMMICH_LIBRARIES', '{"family": "token"}')
    monkeypatch.setenv('COUNTRY_WHITELIST', 'Brazil, Argentina')
    monkeypatch.setenv('COUNTRY_BLACKLIST', 'Chile')
    monkeypatch.setenv('CITY_WHITELIST', 'Rio de Janeiro, Florianopolis')
    monkeypatch.setenv('CITY_BLACKLIST', 'Curitiba')
    monkeypatch.setenv('PEOPLE_WHITELIST', 'Alice, Bob Smith')
    monkeypatch.setenv('PEOPLE_BLACKLIST', 'Charlie')

    settings = load_settings()

    assert settings.country_whitelist == frozenset({'brazil', 'argentina'})
    assert settings.country_blacklist == frozenset({'chile'})
    assert settings.city_whitelist == frozenset({'rio de janeiro', 'florianopolis'})
    assert settings.city_blacklist == frozenset({'curitiba'})
    assert settings.people_whitelist == frozenset({'alice', 'bob smith'})
    assert settings.people_blacklist == frozenset({'charlie'})


def test_data_path_configuration(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv('IMMICH_SERVER_URL', 'https://example.test/api')
    monkeypatch.setenv('IMMICH_LIBRARIES', '{"family": "token"}')
    monkeypatch.setenv('DATA_PATH', str(tmp_path / 'custom_data'))

    settings = load_settings()

    assert settings.data_path == (tmp_path / 'custom_data').resolve()
    assert settings.metadata_db_path == (tmp_path / 'custom_data' / 'metadata.db').resolve()
    assert settings.leaderboard_db_path == (tmp_path / 'custom_data' / 'leaderboard.db').resolve()


def test_country_whitelist_blacklist_overlap_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv('IMMICH_SERVER_URL', 'https://example.test/api')
    monkeypatch.setenv('IMMICH_LIBRARIES', '{"family": "token"}')
    monkeypatch.setenv('COUNTRY_WHITELIST', 'Brazil, France')
    monkeypatch.setenv('COUNTRY_BLACKLIST', 'France, Germany')

    with pytest.raises(ConfigError, match='COUNTRY_WHITELIST and COUNTRY_BLACKLIST cannot overlap: france'):
        load_settings()


def test_city_whitelist_blacklist_overlap_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv('IMMICH_SERVER_URL', 'https://example.test/api')
    monkeypatch.setenv('IMMICH_LIBRARIES', '{"family": "token"}')
    monkeypatch.setenv('CITY_WHITELIST', 'Paris, London')
    monkeypatch.setenv('CITY_BLACKLIST', 'London, Berlin')

    with pytest.raises(ConfigError, match='CITY_WHITELIST and CITY_BLACKLIST cannot overlap: london'):
        load_settings()


def test_people_whitelist_blacklist_overlap_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv('IMMICH_SERVER_URL', 'https://example.test/api')
    monkeypatch.setenv('IMMICH_LIBRARIES', '{"family": "token"}')
    monkeypatch.setenv('PEOPLE_WHITELIST', 'Alice, Bob')
    monkeypatch.setenv('PEOPLE_BLACKLIST', 'Bob, Charlie')

    with pytest.raises(ConfigError, match='PEOPLE_WHITELIST and PEOPLE_BLACKLIST cannot overlap: bob'):
        load_settings()


def test_auto_delta_sync_interval_hours_config(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv('IMMICH_SERVER_URL', 'https://example.test/api')
    monkeypatch.setenv('IMMICH_LIBRARIES', '{"family": "token"}')
    monkeypatch.setenv('AUTO_DELTA_SYNC_INTERVAL_HOURS', '6')

    settings = load_settings()
    assert settings.auto_delta_sync_interval_hours == 6

    monkeypatch.setenv('AUTO_DELTA_SYNC_INTERVAL_HOURS', '-1')
    with pytest.raises(ConfigError, match='AUTO_DELTA_SYNC_INTERVAL_HOURS'):
        load_settings()


def test_auto_full_sync_interval_hours_config(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv('IMMICH_SERVER_URL', 'https://example.test/api')
    monkeypatch.setenv('IMMICH_LIBRARIES', '{"family": "token"}')
    monkeypatch.setenv('AUTO_FULL_SYNC_INTERVAL_HOURS', '48')

    settings = load_settings()
    assert settings.auto_full_sync_interval_hours == 48

    monkeypatch.setenv('AUTO_FULL_SYNC_INTERVAL_HOURS', '-1')
    with pytest.raises(ConfigError, match='AUTO_FULL_SYNC_INTERVAL_HOURS'):
        load_settings()


def test_app_settings_dataclass_defaults() -> None:
    settings = AppSettings(
        immich_server_url='https://example.test',
        immich_libraries={'family': 'token'},
    )
    assert settings.immich_server_url == 'https://example.test/api'
    assert settings.immich_libraries == {'family': 'token'}
    assert settings.app_title == 'Immich Quiz'
    assert settings.app_tagline == ''
    assert settings.app_host == '127.0.0.1'
    assert settings.app_port == 8010
    assert settings.language == 'EN'
    assert settings.location_score_decay_km == 500.0
    assert settings.date_score_decay_days == 500.0
    assert settings.date_lower_bound is None
    assert settings.date_upper_bound is None
    assert settings.country_whitelist == frozenset()
    assert settings.country_blacklist == frozenset()
    assert settings.city_whitelist == frozenset()
    assert settings.city_blacklist == frozenset()
    assert settings.people_whitelist == frozenset()
    assert settings.people_blacklist == frozenset()
    assert settings.data_path == Path('data').resolve()
    assert settings.auto_sync_on_startup is True
    assert settings.auto_delta_sync_interval_hours == 6
    assert settings.auto_full_sync_interval_hours == 120


def test_app_settings_dataclass_validations() -> None:
    with pytest.raises(ConfigError, match='IMMICH_SERVER_URL is required'):
        AppSettings(immich_server_url='', immich_libraries={'a': 'b'})

    with pytest.raises(ConfigError, match='on or before'):
        AppSettings(
            immich_server_url='https://example.test',
            immich_libraries={'a': 'b'},
            date_lower_bound=date(2025, 1, 1),
            date_upper_bound=date(2024, 1, 1),
        )

    with pytest.raises(ConfigError, match='COUNTRY_WHITELIST and COUNTRY_BLACKLIST cannot overlap'):
        AppSettings(
            immich_server_url='https://example.test',
            immich_libraries={'a': 'b'},
            country_whitelist=frozenset({'brazil'}),
            country_blacklist=frozenset({'brazil'}),
        )


def test_empty_and_whitespace_env_vars_fallback_to_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv('IMMICH_SERVER_URL', 'https://example.test/api')
    monkeypatch.setenv('IMMICH_LIBRARIES', '{"family": "token"}')
    monkeypatch.setenv('APP_TITLE', '   ')
    monkeypatch.setenv('APP_TAGLINE', '')
    monkeypatch.setenv('APP_HOST', '  ')
    monkeypatch.setenv('APP_PORT', '')
    monkeypatch.setenv('LOCATION_SCORE_DECAY_KM', '')
    monkeypatch.setenv('DATE_SCORE_DECAY_DAYS', '')
    monkeypatch.setenv('LANGUAGE', '  ')
    monkeypatch.setenv('DATA_PATH', '')
    monkeypatch.setenv('AUTO_SYNC_ON_STARTUP', '')
    monkeypatch.setenv('AUTO_DELTA_SYNC_INTERVAL_HOURS', '')
    monkeypatch.setenv('AUTO_FULL_SYNC_INTERVAL_HOURS', '')

    settings = load_settings()
    assert settings.app_title == 'Immich Quiz'
    assert settings.app_tagline == ''
    assert settings.app_host == '127.0.0.1'
    assert settings.app_port == 8010
    assert settings.language == 'EN'
    assert settings.location_score_decay_km == 500.0
    assert settings.date_score_decay_days == 500.0
    assert settings.data_path == Path('data').resolve()
    assert settings.auto_sync_on_startup is True
    assert settings.auto_delta_sync_interval_hours == 6
    assert settings.auto_full_sync_interval_hours == 120


@pytest.mark.parametrize('invalid_port', ['0', '-1', '65536', '70000'])
def test_app_port_rejects_out_of_range(monkeypatch: pytest.MonkeyPatch, invalid_port: str) -> None:
    monkeypatch.setenv('IMMICH_SERVER_URL', 'https://example.test/api')
    monkeypatch.setenv('IMMICH_LIBRARIES', '{"family": "token"}')
    monkeypatch.setenv('APP_PORT', invalid_port)

    with pytest.raises(ConfigError, match='APP_PORT must be between 1 and 65535'):
        load_settings()


@pytest.mark.parametrize('invalid_float', ['nan', 'inf', '-inf', '0', '-5.0'])
def test_location_score_decay_rejects_non_finite_or_non_positive(
    monkeypatch: pytest.MonkeyPatch, invalid_float: str
) -> None:
    monkeypatch.setenv('IMMICH_SERVER_URL', 'https://example.test/api')
    monkeypatch.setenv('IMMICH_LIBRARIES', '{"family": "token"}')
    monkeypatch.setenv('LOCATION_SCORE_DECAY_KM', invalid_float)

    with pytest.raises(ConfigError, match='LOCATION_SCORE_DECAY_KM must be greater than 0'):
        load_settings()


@pytest.mark.parametrize('invalid_float', ['nan', 'inf', '-inf', '0', '-10.0'])
def test_date_score_decay_rejects_non_finite_or_non_positive(
    monkeypatch: pytest.MonkeyPatch, invalid_float: str
) -> None:
    monkeypatch.setenv('IMMICH_SERVER_URL', 'https://example.test/api')
    monkeypatch.setenv('IMMICH_LIBRARIES', '{"family": "token"}')
    monkeypatch.setenv('DATE_SCORE_DECAY_DAYS', invalid_float)

    with pytest.raises(ConfigError, match='DATE_SCORE_DECAY_DAYS must be greater than 0'):
        load_settings()


def test_app_settings_dataclass_port_and_decay_validation() -> None:
    with pytest.raises(ConfigError, match='APP_PORT must be between 1 and 65535'):
        AppSettings(
            immich_server_url='https://example.test',
            immich_libraries={'a': 'b'},
            app_port=0,
        )

    with pytest.raises(ConfigError, match='LOCATION_SCORE_DECAY_KM must be greater than 0'):
        AppSettings(
            immich_server_url='https://example.test',
            immich_libraries={'a': 'b'},
            location_score_decay_km=float('nan'),
        )

    with pytest.raises(ConfigError, match='DATE_SCORE_DECAY_DAYS must be greater than 0'):
        AppSettings(
            immich_server_url='https://example.test',
            immich_libraries={'a': 'b'},
            date_score_decay_days=float('inf'),
        )


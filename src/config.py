from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from src.i18n import SupportedLanguage


class ConfigError(ValueError):
    pass


def _parse_comma_set(value: str | None) -> frozenset[str]:
    """Parse comma-separated string into a normalized lowercase set."""
    if not value or not value.strip():
        return frozenset()
    return frozenset(item.strip().lower() for item in value.split(',') if item.strip())


def _validate_no_overlap(set_a: frozenset[str], set_b: frozenset[str], name_a: str, name_b: str) -> None:
    overlap = set_a & set_b
    if overlap:
        raise ConfigError(f'{name_a} and {name_b} cannot overlap: {", ".join(sorted(overlap))}')


@dataclass(frozen=True)
class AppSettings:
    # Required
    immich_server_url: str
    immich_libraries: dict[str, str]

    # Application & Server
    app_title: str = 'Immich Quiz'
    app_tagline: str = ''
    app_host: str = '127.0.0.1'
    app_port: int = 8010
    language: str = 'EN'

    # Scoring
    location_score_decay_km: float = 500.0
    date_score_decay_days: float = 500.0

    # Library filters
    date_lower_bound: date | None = None
    date_upper_bound: date | None = None
    country_whitelist: frozenset[str] = frozenset()
    country_blacklist: frozenset[str] = frozenset()
    city_whitelist: frozenset[str] = frozenset()
    city_blacklist: frozenset[str] = frozenset()
    people_whitelist: frozenset[str] = frozenset()
    people_blacklist: frozenset[str] = frozenset()

    # Data folder and storage settings
    data_path: Path = Path('data')
    auto_sync_on_startup: bool = True
    auto_delta_sync_interval_hours: int = 6
    auto_full_sync_interval_hours: int = 120

    def __post_init__(self) -> None:
        # Normalize server URL
        url = self.immich_server_url.strip().rstrip('/')
        if not url:
            raise ConfigError('IMMICH_SERVER_URL is required')
        if not url.endswith('/api'):
            url = f'{url}/api'
        object.__setattr__(self, 'immich_server_url', url)

        # Resolve data path to absolute
        object.__setattr__(self, 'data_path', self.data_path.expanduser().resolve())

        # Validate date range
        if (
            self.date_lower_bound is not None
            and self.date_upper_bound is not None
            and self.date_lower_bound > self.date_upper_bound
        ):
            raise ConfigError('DATE_LOWER_BOUND must be on or before DATE_UPPER_BOUND')

        # Validate filter overlaps
        _validate_no_overlap(self.country_whitelist, self.country_blacklist, 'COUNTRY_WHITELIST', 'COUNTRY_BLACKLIST')
        _validate_no_overlap(self.city_whitelist, self.city_blacklist, 'CITY_WHITELIST', 'CITY_BLACKLIST')
        _validate_no_overlap(self.people_whitelist, self.people_blacklist, 'PEOPLE_WHITELIST', 'PEOPLE_BLACKLIST')

    @property
    def metadata_db_path(self) -> Path:
        return self.data_path / 'metadata.db'

    @property
    def leaderboard_db_path(self) -> Path:
        return self.data_path / 'leaderboard.db'


def _parse_language(value: str) -> str:
    normalized = value.strip().upper()
    if normalized not in {lang.value for lang in SupportedLanguage}:
        raise ConfigError("LANGUAGE must be 'EN' or 'PT'")
    return normalized


def _parse_library_map(value: str) -> dict[str, str]:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise ConfigError('IMMICH_LIBRARIES must be valid JSON object mapping library names to API keys') from exc
    if not isinstance(parsed, dict) or not parsed:
        raise ConfigError('IMMICH_LIBRARIES must be a non-empty JSON object')

    normalized: dict[str, str] = {}
    for key, token in parsed.items():
        if not isinstance(key, str) or not key.strip():
            raise ConfigError('IMMICH_LIBRARIES keys must be non-empty strings')
        if not isinstance(token, str) or not token.strip():
            raise ConfigError(f"IMMICH_LIBRARIES value for '{key}' must be a non-empty API key string")
        normalized[key.strip()] = token.strip()
    return normalized


def _parse_bool(value: str, env_name: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {'1', 'true', 'yes', 'on'}:
        return True
    if normalized in {'0', 'false', 'no', 'off'}:
        return False
    raise ConfigError(f'{env_name} must be a boolean (true/false)')


def _parse_int(value: str, env_name: str) -> int:
    try:
        return int(value.strip())
    except ValueError as exc:
        raise ConfigError(f'{env_name} must be an integer') from exc


def _parse_int_range(value: str, env_name: str, *, min_value: int, max_value: int) -> int:
    parsed = _parse_int(value, env_name)
    if parsed < min_value or parsed > max_value:
        raise ConfigError(f'{env_name} must be between {min_value} and {max_value}')
    return parsed


def _parse_positive_float(value: str, env_name: str) -> float:
    try:
        parsed = float(value.strip())
    except ValueError as exc:
        raise ConfigError(f'{env_name} must be a number') from exc
    if parsed <= 0:
        raise ConfigError(f'{env_name} must be greater than 0')
    return parsed


def _parse_date(value: str, env_name: str) -> date:
    cleaned = value.strip()
    try:
        return datetime.strptime(cleaned, '%Y-%m-%d').date()
    except ValueError as exc:
        raise ConfigError(f'{env_name} must be a valid date in YYYY-MM-DD format') from exc


def _get_env(*names: str) -> str | None:
    """Return the first non-empty stripped environment variable matching any of the given names."""
    for name in names:
        val = os.getenv(name)
        if val is not None and val.strip():
            return val.strip()
    return None


def load_settings() -> AppSettings:
    load_dotenv()

    server_url = os.getenv('IMMICH_SERVER_URL', '').strip()
    if not server_url:
        raise ConfigError('IMMICH_SERVER_URL is required')

    raw_libraries = os.getenv('IMMICH_LIBRARIES', '').strip()
    if not raw_libraries:
        raise ConfigError('IMMICH_LIBRARIES is required')

    kwargs: dict[str, Any] = {
        'immich_server_url': server_url,
        'immich_libraries': _parse_library_map(raw_libraries),
    }

    if val := _get_env('APP_TITLE'):
        kwargs['app_title'] = val
    if val := _get_env('APP_TAGLINE'):
        kwargs['app_tagline'] = val
    if val := _get_env('APP_HOST'):
        kwargs['app_host'] = val
    if val := _get_env('APP_PORT'):
        kwargs['app_port'] = _parse_int(val, 'APP_PORT')
    if val := _get_env('LANGUAGE'):
        kwargs['language'] = _parse_language(val)

    if val := _get_env('LOCATION_SCORE_DECAY_KM'):
        kwargs['location_score_decay_km'] = _parse_positive_float(val, 'LOCATION_SCORE_DECAY_KM')
    if val := _get_env('DATE_SCORE_DECAY_DAYS'):
        kwargs['date_score_decay_days'] = _parse_positive_float(val, 'DATE_SCORE_DECAY_DAYS')

    if val := _get_env('DATE_LOWER_BOUND', 'FETCH_PHOTOS_DATE_LOWER_BOUND'):
        kwargs['date_lower_bound'] = _parse_date(val, 'DATE_LOWER_BOUND')
    if val := _get_env('DATE_UPPER_BOUND', 'FETCH_PHOTOS_DATE_UPPER_BOUND'):
        kwargs['date_upper_bound'] = _parse_date(val, 'DATE_UPPER_BOUND')

    if val := _get_env('DATA_PATH', 'DATA_DIR'):
        kwargs['data_path'] = Path(val)
    if val := _get_env('AUTO_SYNC_ON_STARTUP'):
        kwargs['auto_sync_on_startup'] = _parse_bool(val, 'AUTO_SYNC_ON_STARTUP')
    if val := _get_env('AUTO_DELTA_SYNC_INTERVAL_HOURS'):
        kwargs['auto_delta_sync_interval_hours'] = _parse_int_range(
            val, 'AUTO_DELTA_SYNC_INTERVAL_HOURS', min_value=0, max_value=8760
        )
    if val := _get_env('AUTO_FULL_SYNC_INTERVAL_HOURS'):
        kwargs['auto_full_sync_interval_hours'] = _parse_int_range(
            val, 'AUTO_FULL_SYNC_INTERVAL_HOURS', min_value=0, max_value=8760
        )

    if val := _get_env('COUNTRY_WHITELIST'):
        kwargs['country_whitelist'] = _parse_comma_set(val)
    if val := _get_env('COUNTRY_BLACKLIST'):
        kwargs['country_blacklist'] = _parse_comma_set(val)
    if val := _get_env('CITY_WHITELIST'):
        kwargs['city_whitelist'] = _parse_comma_set(val)
    if val := _get_env('CITY_BLACKLIST'):
        kwargs['city_blacklist'] = _parse_comma_set(val)
    if val := _get_env('PEOPLE_WHITELIST'):
        kwargs['people_whitelist'] = _parse_comma_set(val)
    if val := _get_env('PEOPLE_BLACKLIST'):
        kwargs['people_blacklist'] = _parse_comma_set(val)

    return AppSettings(**kwargs)

"""Configuration system, environment variable parsing, and validation for Immich Quiz."""

from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from src.i18n import SupportedLanguage

# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class ConfigError(ValueError):
    """Raised when configuration parsing or invariant validation fails."""

    pass


# ---------------------------------------------------------------------------
# Parsing and Sanitization Helpers
# ---------------------------------------------------------------------------


def _get_env(*names: str) -> str | None:
    """Return the first non-empty stripped environment variable matching any of the given names."""
    for name in names:
        val = os.getenv(name)
        if val is not None and val.strip():
            return val.strip()
    return None


def _parse_bool(value: str, env_name: str) -> bool:
    """Parse a boolean environment string (e.g. true/1/yes/on vs false/0/no/off)."""
    normalized = value.strip().lower()
    if normalized in {'1', 'true', 'yes', 'on'}:
        return True
    if normalized in {'0', 'false', 'no', 'off'}:
        return False
    raise ConfigError(f'{env_name} must be a boolean (true/false)')


def _parse_int(value: str, env_name: str) -> int:
    """Parse a base-10 integer string."""
    try:
        return int(value.strip())
    except ValueError as exc:
        raise ConfigError(f'{env_name} must be an integer') from exc


def _parse_int_range(value: str, env_name: str, *, min_value: int, max_value: int) -> int:
    """Parse an integer and enforce inclusive [min_value, max_value] range bounds."""
    parsed = _parse_int(value, env_name)
    if parsed < min_value or parsed > max_value:
        raise ConfigError(f'{env_name} must be between {min_value} and {max_value}')
    return parsed


def _parse_positive_float(value: str, env_name: str) -> float:
    """Parse a strictly positive (> 0.0) finite floating point number."""
    try:
        parsed = float(value.strip())
    except ValueError as exc:
        raise ConfigError(f'{env_name} must be a number') from exc
    if math.isnan(parsed) or math.isinf(parsed) or parsed <= 0:
        raise ConfigError(f'{env_name} must be greater than 0')
    return parsed


def _parse_date(value: str, env_name: str) -> date:
    """Parse a date formatted strictly as 'YYYY-MM-DD'."""
    cleaned = value.strip()
    try:
        return datetime.strptime(cleaned, '%Y-%m-%d').date()
    except ValueError as exc:
        raise ConfigError(f'{env_name} must be a valid date in YYYY-MM-DD format') from exc


def _parse_language(value: str) -> SupportedLanguage:
    """Parse and normalize language code string to a SupportedLanguage enum."""
    raw = value.strip()
    norm = raw.lower().replace('_', '-')
    if norm.startswith('pt'):
        return SupportedLanguage.PT
    if norm.startswith('en'):
        return SupportedLanguage.EN
    raise ConfigError(f"LANGUAGE must be 'en-US' (or 'en') or 'pt-BR' (or 'pt'), got '{value}'")


def _parse_comma_set(value: str | None) -> frozenset[str]:
    """Parse comma-separated string into a normalized lowercase set."""
    if not value or not value.strip():
        return frozenset()
    return frozenset(item.strip().lower() for item in value.split(',') if item.strip())


def _parse_library_map(value: str) -> dict[str, str]:
    """Parse JSON mapping of library names to Immich API keys."""
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


def _normalize_url(value: str, env_name: str = 'IMMICH_SERVER_URL') -> str:
    """Normalize server URL by stripping trailing slashes and ensuring '/api' path suffix."""
    url = value.strip().rstrip('/')
    if not url:
        raise ConfigError(f'{env_name} is required')
    if not url.endswith('/api'):
        url = f'{url}/api'
    return url


def _validate_no_overlap(set_a: frozenset[str], set_b: frozenset[str], name_a: str, name_b: str) -> None:
    """Ensure whitelist and blacklist sets are completely disjoint."""
    overlap = set_a & set_b
    if overlap:
        raise ConfigError(f'{name_a} and {name_b} cannot overlap: {", ".join(sorted(overlap))}')


# ---------------------------------------------------------------------------
# Application Settings Model
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AppSettings:
    """Validated, immutable application settings loaded from environment or configuration."""

    # 1. Immich Connection & Credentials
    immich_server_url: str
    immich_libraries: dict[str, str]

    # 2. Application & Server Network
    app_title: str = 'Immich Quiz'
    app_tagline: str = ''
    app_host: str = '127.0.0.1'
    app_port: int = 8010
    language: SupportedLanguage = SupportedLanguage.EN

    # 4. Global Filter Safeguards
    date_lower_bound: date | None = None
    date_upper_bound: date | None = None
    country_whitelist: frozenset[str] = frozenset()
    country_blacklist: frozenset[str] = frozenset()
    city_whitelist: frozenset[str] = frozenset()
    city_blacklist: frozenset[str] = frozenset()
    people_whitelist: frozenset[str] = frozenset()
    people_blacklist: frozenset[str] = frozenset()
    tag_whitelist: frozenset[str] = frozenset()
    tag_blacklist: frozenset[str] = frozenset()

    # 5. Storage Paths & Sync Scheduling
    data_path: Path = Path('data')
    auto_sync_on_startup: bool = True
    auto_delta_sync_interval_hours: int = 6
    auto_full_sync_interval_hours: int = 120

    # 6. Logging & Observability
    log_level: str = 'INFO'
    log_level_scoring: str | None = None
    log_level_sync: str | None = None
    log_level_immich: str | None = None
    log_level_match: str | None = None
    log_level_api: str | None = None

    def __post_init__(self) -> None:
        # Normalize and validate Immich server URL
        normalized_url = _normalize_url(self.immich_server_url, 'IMMICH_SERVER_URL')
        object.__setattr__(self, 'immich_server_url', normalized_url)

        # Resolve data path to absolute filesystem path
        object.__setattr__(self, 'data_path', self.data_path.expanduser().resolve())

        # Validate network port
        if not (1 <= self.app_port <= 65535):
            raise ConfigError('APP_PORT must be between 1 and 65535')

        # Validate auto sync intervals
        if not (0 <= self.auto_delta_sync_interval_hours <= 8760):
            raise ConfigError('AUTO_DELTA_SYNC_INTERVAL_HOURS must be between 0 and 8760')
        if not (0 <= self.auto_full_sync_interval_hours <= 8760):
            raise ConfigError('AUTO_FULL_SYNC_INTERVAL_HOURS must be between 0 and 8760')

        # Validate date range bounds
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
        _validate_no_overlap(self.tag_whitelist, self.tag_blacklist, 'TAG_WHITELIST', 'TAG_BLACKLIST')

        # Validate and normalize log levels
        valid_levels = {'DEBUG', 'INFO', 'WARNING', 'WARN', 'ERROR', 'CRITICAL'}
        norm_log_level = self.log_level.strip().upper()
        if norm_log_level == 'WARN':
            norm_log_level = 'WARNING'
        if norm_log_level not in valid_levels:
            raise ConfigError(f'LOG_LEVEL must be one of {sorted(valid_levels)}, got {self.log_level!r}')
        object.__setattr__(self, 'log_level', norm_log_level)

    @property
    def metadata_db_path(self) -> Path:
        """Absolute path to the SQLite metadata database."""
        return self.data_path / 'metadata.db'

    @property
    def leaderboard_db_path(self) -> Path:
        """Absolute path to the SQLite leaderboard database."""
        return self.data_path / 'leaderboard.db'


# ---------------------------------------------------------------------------
# Settings Factory
# ---------------------------------------------------------------------------


def load_settings() -> AppSettings:
    """Load, parse, validate, and return the application configuration from environment variables."""
    load_dotenv()

    # Required settings
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

    # Application & Server
    if val := _get_env('APP_TITLE'):
        kwargs['app_title'] = val
    if val := _get_env('APP_TAGLINE'):
        kwargs['app_tagline'] = val
    if val := _get_env('APP_HOST'):
        kwargs['app_host'] = val
    if val := _get_env('APP_PORT'):
        kwargs['app_port'] = _parse_int_range(val, 'APP_PORT', min_value=1, max_value=65535)
    if val := _get_env('LANGUAGE'):
        kwargs['language'] = _parse_language(val)

    # Date Bounds
    if val := _get_env('DATE_LOWER_BOUND', 'FETCH_PHOTOS_DATE_LOWER_BOUND'):
        kwargs['date_lower_bound'] = _parse_date(val, 'DATE_LOWER_BOUND')
    if val := _get_env('DATE_UPPER_BOUND', 'FETCH_PHOTOS_DATE_UPPER_BOUND'):
        kwargs['date_upper_bound'] = _parse_date(val, 'DATE_UPPER_BOUND')

    # Storage & Background Sync Schedules
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

    # Filter Whitelists & Blacklists
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
    if val := _get_env('TAG_WHITELIST'):
        kwargs['tag_whitelist'] = _parse_comma_set(val)
    if val := _get_env('TAG_BLACKLIST'):
        kwargs['tag_blacklist'] = _parse_comma_set(val)

    # Logging & Observability
    if val := _get_env('LOG_LEVEL'):
        kwargs['log_level'] = val.strip().upper()
    if val := _get_env('LOG_LEVEL_SCORING'):
        kwargs['log_level_scoring'] = val.strip().upper()
    if val := _get_env('LOG_LEVEL_SYNC'):
        kwargs['log_level_sync'] = val.strip().upper()
    if val := _get_env('LOG_LEVEL_IMMICH'):
        kwargs['log_level_immich'] = val.strip().upper()
    if val := _get_env('LOG_LEVEL_MATCH'):
        kwargs['log_level_match'] = val.strip().upper()
    if val := _get_env('LOG_LEVEL_API'):
        kwargs['log_level_api'] = val.strip().upper()

    return AppSettings(**kwargs)

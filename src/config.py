from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from dotenv import load_dotenv


class ConfigError(ValueError):
    pass


def _parse_comma_set(value: str | None) -> frozenset[str]:
    """Parse comma-separated string into a normalized lowercase set."""
    if not value or not value.strip():
        return frozenset()
    return frozenset(item.strip().lower() for item in value.split(',') if item.strip())


@dataclass(frozen=True)
class AppSettings:
    immich_server_url: str
    immich_libraries: dict[str, str]
    app_title: str
    app_tagline: str
    include_shared_albums: bool
    include_partner_assets: bool
    fetch_photos_date_lower_bound: date | None
    fetch_photos_date_upper_bound: date | None
    app_host: str
    app_port: int
    score_max_points: int
    location_score_decay_km: float
    date_score_decay_days: float
    language: str
    # Diversity Safeguards (cleanly isolated for future tuning)
    photo_diversity_min_distance_km: float
    photo_diversity_min_time_seconds: float
    # Data folder and storage settings
    data_path: Path = Path('data')
    auto_sync_on_startup: bool = True

    # New filter boundaries & whitelists/blacklists
    country_whitelist: frozenset[str] = frozenset()
    country_blacklist: frozenset[str] = frozenset()
    city_whitelist: frozenset[str] = frozenset()
    city_blacklist: frozenset[str] = frozenset()
    people_whitelist: frozenset[str] = frozenset()
    people_blacklist: frozenset[str] = frozenset()


    @property
    def metadata_db_path(self) -> Path:
        return self.data_path / 'metadata.db'

    @property
    def leaderboard_db_path(self) -> Path:
        return self.data_path / 'leaderboard.db'

def _parse_language(value: str) -> str:
    normalized = value.strip().upper()
    if normalized not in {'EN', 'PT'}:
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


def _parse_int_range(value: str, env_name: str, *, min_value: int, max_value: int) -> int:
    try:
        parsed = int(value.strip())
    except ValueError as exc:
        raise ConfigError(f'{env_name} must be an integer') from exc
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


def _parse_optional_date(value: str, env_name: str) -> date | None:
    cleaned = value.strip()
    if not cleaned:
        return None
    try:
        return datetime.strptime(cleaned, '%Y-%m-%d').date()
    except ValueError as exc:
        raise ConfigError(f'{env_name} must be a valid date in YYYY-MM-DD format') from exc


def load_settings() -> AppSettings:
    load_dotenv()

    server_url = os.getenv('IMMICH_SERVER_URL', '').strip().rstrip('/')
    if not server_url:
        raise ConfigError('IMMICH_SERVER_URL is required')
    if not server_url.endswith('/api'):
        server_url = f'{server_url}/api'

    app_title = os.getenv('APP_TITLE', 'Immich Quiz').strip() or 'Immich Quiz'
    app_tagline = os.getenv('APP_TAGLINE', '').strip()

    raw_libraries = os.getenv('IMMICH_LIBRARIES', '').strip()
    if not raw_libraries:
        raise ConfigError('IMMICH_LIBRARIES is required')

    libraries = _parse_library_map(raw_libraries)
    include_shared_albums = _parse_bool(os.getenv('INCLUDE_SHARED_ALBUMS', 'false'), 'INCLUDE_SHARED_ALBUMS')
    include_partner_assets = _parse_bool(os.getenv('INCLUDE_PARTNER_ASSETS', 'false'), 'INCLUDE_PARTNER_ASSETS')
    fetch_photos_date_lower_bound = _parse_optional_date(
        os.getenv('FETCH_PHOTOS_DATE_LOWER_BOUND', ''),
        'FETCH_PHOTOS_DATE_LOWER_BOUND',
    )
    fetch_photos_date_upper_bound = _parse_optional_date(
        os.getenv('FETCH_PHOTOS_DATE_UPPER_BOUND', ''),
        'FETCH_PHOTOS_DATE_UPPER_BOUND',
    )
    if (
        fetch_photos_date_lower_bound is not None
        and fetch_photos_date_upper_bound is not None
        and fetch_photos_date_lower_bound > fetch_photos_date_upper_bound
    ):
        raise ConfigError('FETCH_PHOTOS_DATE_LOWER_BOUND must be on or before FETCH_PHOTOS_DATE_UPPER_BOUND')

    host = os.getenv('APP_HOST', '127.0.0.1').strip() or '127.0.0.1'
    port_raw = os.getenv('APP_PORT', '8010').strip()
    try:
        port = int(port_raw)
    except ValueError as exc:
        raise ConfigError('APP_PORT must be an integer') from exc

    score_max_points = _parse_int_range(
        os.getenv('SCORE_MAX_POINTS', '100'),
        'SCORE_MAX_POINTS',
        min_value=1,
        max_value=10000,
    )
    location_score_decay_km = _parse_positive_float(
        os.getenv('LOCATION_SCORE_DECAY_KM', '500'),
        'LOCATION_SCORE_DECAY_KM',
    )
    date_score_decay_days = _parse_positive_float(
        os.getenv('DATE_SCORE_DECAY_DAYS', '500'),
        'DATE_SCORE_DECAY_DAYS',
    )
    language = _parse_language(os.getenv('LANGUAGE', 'EN'))

    try:
        photo_diversity_min_distance_km = float(os.getenv('PHOTO_DIVERSITY_MIN_DISTANCE_KM', '0.1'))
    except ValueError:
        photo_diversity_min_distance_km = 0.1

    try:
        photo_diversity_min_time_seconds = float(os.getenv('PHOTO_DIVERSITY_MIN_TIME_SECONDS', '60.0'))
    except ValueError:
        photo_diversity_min_time_seconds = 60.0

    data_path_raw = os.getenv('DATA_PATH') or os.getenv('DATA_DIR') or 'data'
    data_path = Path(data_path_raw).expanduser().resolve()
    auto_sync_on_startup = _parse_bool(os.getenv('AUTO_SYNC_ON_STARTUP', 'true'), 'AUTO_SYNC_ON_STARTUP')

    country_whitelist = _parse_comma_set(os.getenv('COUNTRY_WHITELIST'))
    country_blacklist = _parse_comma_set(os.getenv('COUNTRY_BLACKLIST'))
    city_whitelist = _parse_comma_set(os.getenv('CITY_WHITELIST'))
    city_blacklist = _parse_comma_set(os.getenv('CITY_BLACKLIST'))
    people_whitelist = _parse_comma_set(os.getenv('PEOPLE_WHITELIST'))
    people_blacklist = _parse_comma_set(os.getenv('PEOPLE_BLACKLIST'))

    return AppSettings(
        immich_server_url=server_url,
        immich_libraries=libraries,
        app_title=app_title,
        app_tagline=app_tagline,
        include_shared_albums=include_shared_albums,
        include_partner_assets=include_partner_assets,
        fetch_photos_date_lower_bound=fetch_photos_date_lower_bound,
        fetch_photos_date_upper_bound=fetch_photos_date_upper_bound,
        app_host=host,
        app_port=port,
        score_max_points=score_max_points,
        location_score_decay_km=location_score_decay_km,
        date_score_decay_days=date_score_decay_days,
        language=language,
        photo_diversity_min_distance_km=photo_diversity_min_distance_km,
        photo_diversity_min_time_seconds=photo_diversity_min_time_seconds,
        data_path=data_path,
        auto_sync_on_startup=auto_sync_on_startup,
        country_whitelist=country_whitelist,
        country_blacklist=country_blacklist,
        city_whitelist=city_whitelist,
        city_blacklist=city_blacklist,
        people_whitelist=people_whitelist,
        people_blacklist=people_blacklist,
    )

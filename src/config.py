from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from dotenv import load_dotenv


class ConfigError(ValueError):
    pass


@dataclass(frozen=True)
class AppSettings:
    immich_server_url: str
    immich_libraries: dict[str, str]
    leaderboard_csv_path: Path
    app_title: str
    app_tagline: str
    include_shared_albums: bool
    fetch_photos_date_lower_bound: date | None
    fetch_photos_date_upper_bound: date | None
    app_host: str
    app_port: int
    quiz_image_max_height_px: int
    score_max_points: int
    location_score_decay_km: float
    date_score_decay_days: float
    language: str = 'EN'


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
    csv_path = Path(os.getenv('LEADERBOARD_CSV_PATH', 'data/leaderboard.csv')).expanduser().resolve()
    include_shared_albums = _parse_bool(os.getenv('INCLUDE_SHARED_ALBUMS', 'false'), 'INCLUDE_SHARED_ALBUMS')
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

    quiz_image_max_height_px = _parse_int_range(
        os.getenv('QUIZ_IMAGE_MAX_HEIGHT_PX', '420'),
        'QUIZ_IMAGE_MAX_HEIGHT_PX',
        min_value=200,
        max_value=1600,
    )
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

    return AppSettings(
        immich_server_url=server_url,
        immich_libraries=libraries,
        leaderboard_csv_path=csv_path,
        app_title=app_title,
        app_tagline=app_tagline,
        include_shared_albums=include_shared_albums,
        fetch_photos_date_lower_bound=fetch_photos_date_lower_bound,
        fetch_photos_date_upper_bound=fetch_photos_date_upper_bound,
        app_host=host,
        app_port=port,
        quiz_image_max_height_px=quiz_image_max_height_px,
        score_max_points=score_max_points,
        location_score_decay_km=location_score_decay_km,
        date_score_decay_days=date_score_decay_days,
        language=language,
    )

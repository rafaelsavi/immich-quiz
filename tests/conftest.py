from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from src.config import AppSettings
from src.main import create_app


def make_asset(
    asset_id: str,
    latitude: float | None = -27.5969,
    longitude: float | None = -48.5495,
    captured: str | None = '2024-01-14T10:11:12Z',
    media_type: str = 'IMAGE',
) -> dict[str, Any]:
    return {
        'id': asset_id,
        'type': media_type,
        'exifInfo': {
            'latitude': latitude,
            'longitude': longitude,
            'dateTimeOriginal': captured,
        },
        'fileCreatedAt': captured,
    }


def setup_payload(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        'players': ['Alice'],
        'round_count': 5,
        'round_length': '1m',
        'location_mode': True,
        'date_mode': True,
        'library_name': 'family',
        'album_ids': [],
        'album_name': '-',
    }
    payload.update(overrides)
    return payload


class FakeImmichClient:
    def __init__(self, assets: list[dict[str, Any]] | None = None) -> None:
        self.assets = assets if assets is not None else [make_asset('asset-1')]
        self.search_calls = 0
        self.closed = False
        self.last_include_shared_albums = False

    def list_libraries(self) -> list[str]:
        return ['family']

    async def validate_access(self, library_name: str) -> None:
        return None

    async def list_albums(self, library_name: str, include_shared_albums: bool = False) -> list[dict[str, str]]:
        self.last_include_shared_albums = include_shared_albums
        return [{'id': 'album-1', 'name': 'Holidays'}]

    async def search_assets(
        self,
        library_name: str,
        album_ids: list[str] | None = None,
        *,
        include_shared_albums: bool = False,
        include_partner_assets: bool = False,
        size: int = 250,
        page: int = 1,
    ) -> list[dict[str, Any]]:
        self.search_calls += 1
        return self.assets

    async def search_random_assets(
        self,
        library_name: str,
        album_ids: list[str] | None = None,
        size: int = 250,
        include_shared_albums: bool = False,
        include_partner_assets: bool = False,
    ) -> list[dict[str, Any]]:
        self.search_calls += 1
        return self.assets

    async def get_asset_bytes(self, library_name: str, asset_id: str) -> tuple[bytes, str]:
        return b'fake-jpg', 'image/jpeg'

    async def aclose(self) -> None:
        self.closed = True


def build_client(
    tmp_path: Path,
    immich: FakeImmichClient,
    app_title: str = 'Immich Quiz',
    app_tagline: str = '',
    include_shared_albums: bool = False,
    include_partner_assets: bool = False,
    fetch_photos_date_lower_bound: date | None = None,
    fetch_photos_date_upper_bound: date | None = None,
    score_max_points: int = 100,
    location_score_decay_km: float = 500.0,
    date_score_decay_days: float = 500.0,
    language: str = 'EN',
) -> TestClient:
    settings = AppSettings(
        immich_server_url='https://placeholder.example.com/api',
        immich_libraries={'family': 'token'},
        leaderboard_csv_path=tmp_path / 'leaderboard.csv',
        app_title=app_title,
        app_tagline=app_tagline,
        include_shared_albums=include_shared_albums,
        include_partner_assets=include_partner_assets,
        fetch_photos_date_lower_bound=fetch_photos_date_lower_bound,
        fetch_photos_date_upper_bound=fetch_photos_date_upper_bound,
        app_host='127.0.0.1',
        app_port=8010,
        score_max_points=score_max_points,
        location_score_decay_km=location_score_decay_km,
        date_score_decay_days=date_score_decay_days,
        language=language,
    )
    app = create_app(settings=settings)
    app.state.immich_client = immich
    return TestClient(app)


@pytest.fixture
def immich() -> FakeImmichClient:
    return FakeImmichClient()


@pytest.fixture
def client(tmp_path: Path, immich: FakeImmichClient) -> TestClient:
    return build_client(tmp_path, immich)

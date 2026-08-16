from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from src.config import AppSettings
from src.immich.client import CityInfo, PersonInfo, SearchQuery, TimelineBounds
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
    def __init__(
        self,
        assets: list[dict[str, Any]] | None = None,
        people: list[PersonInfo] | None = None,
        timeline_bounds: TimelineBounds | None = None,
        countries: list[str] | None = None,
        cities: list[CityInfo] | None = None,
    ) -> None:
        self.assets = assets if assets is not None else [make_asset('asset-1')]
        self.people = people if people is not None else [PersonInfo(id='p1', name='Alice')]
        self.timeline_bounds = timeline_bounds or TimelineBounds(min_date=date(2020, 1, 1), max_date=date(2024, 12, 31))
        self.countries = countries if countries is not None else ['Brazil', 'France']
        self.cities = (
            cities
            if cities is not None
            else [
                CityInfo(name='Florianopolis', country='Brazil'),
                CityInfo(name='Paris', country='France'),
            ]
        )
        self.search_calls = 0
        self.closed = False
        self.last_include_shared_albums = False
        self.last_query: SearchQuery | None = None

    def list_libraries(self) -> list[str]:
        return ['family']

    async def validate_access(self, library_name: str) -> None:
        return None

    async def list_albums(self, library_name: str, include_shared_albums: bool = False) -> list[dict[str, str]]:
        self.last_include_shared_albums = include_shared_albums
        return [{'id': 'album-1', 'name': 'Holidays'}]

    async def list_people(
        self,
        library_name: str,
        whitelist: frozenset[str] = frozenset(),
        blacklist: frozenset[str] = frozenset(),
    ) -> list[PersonInfo]:
        filtered = [
            p
            for p in self.people
            if (not whitelist or p.name.lower() in whitelist) and (not blacklist or p.name.lower() not in blacklist)
        ]
        return filtered

    async def get_timeline_bounds(self, library_name: str) -> TimelineBounds:
        return self.timeline_bounds

    async def list_countries(
        self,
        library_name: str,
        whitelist: frozenset[str] = frozenset(),
        blacklist: frozenset[str] = frozenset(),
    ) -> list[str]:
        filtered = [
            c
            for c in self.countries
            if (not whitelist or c.lower() in whitelist) and (not blacklist or c.lower() not in blacklist)
        ]
        return filtered

    async def list_cities(
        self,
        library_name: str,
        whitelist: frozenset[str] = frozenset(),
        blacklist: frozenset[str] = frozenset(),
    ) -> list[CityInfo]:
        filtered = [
            c
            for c in self.cities
            if (not whitelist or c.name.lower() in whitelist) and (not blacklist or c.name.lower() not in blacklist)
        ]
        return filtered

    async def search_assets(
        self,
        library_name: str,
        album_ids: list[str] | None = None,
        *,
        query: SearchQuery | None = None,
        include_shared_albums: bool = False,
        include_partner_assets: bool = False,
        size: int = 250,
        page: int = 1,
    ) -> list[dict[str, Any]]:
        self.search_calls += 1
        self.last_query = query
        return self._apply_person_filter(self.assets, query)

    async def search_random_assets(
        self,
        library_name: str,
        album_ids: list[str] | None = None,
        size: int = 250,
        include_shared_albums: bool = False,
        include_partner_assets: bool = False,
        *,
        query: SearchQuery | None = None,
        min_date: date | None = None,
        max_date: date | None = None,
    ) -> list[dict[str, Any]]:
        self.search_calls += 1
        self.last_query = query
        return self._apply_person_filter(self.assets, query)

    def _apply_person_filter(
        self,
        assets: list[dict[str, Any]],
        query: SearchQuery | None,
    ) -> list[dict[str, Any]]:
        """Simulate person filtering in test fake (OR: any match; AND: all must match)."""
        if not query or not query.person_ids:
            return assets
        target_ids = set(query.person_ids)
        is_and = query.people_mode.upper() == 'AND'
        result = []
        for asset in assets:
            asset_people = asset.get('people') or asset.get('faces') or []
            asset_person_ids = {
                str(p.get('id', '')).strip() for p in asset_people if isinstance(p, dict) and p.get('id')
            }
            if is_and:
                if target_ids.issubset(asset_person_ids):
                    result.append(asset)
            else:
                if asset_person_ids & target_ids:
                    result.append(asset)
        return result

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
        data_path=tmp_path,
        auto_sync_on_startup=False,
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

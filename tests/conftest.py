"""Shared pytest fixtures, test data builders, and mock helpers for Immich Quiz test suite."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from src.config import AppSettings
from src.main import create_app
from src.models import SyncStatus
from src.storage.metadata import MetadataStore


@dataclass(frozen=True)
class PersonInfo:
    id: str
    name: str


@dataclass(frozen=True)
class CityInfo:
    name: str
    country: str | None = None


@dataclass(frozen=True)
class TimelineBounds:
    min_date: date | None
    max_date: date | None


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
        'libraries': [],
        'albums': [],
        'album_names': [],
        'people': [],
        'person_names': [],
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
        self.assets_explicit = assets is not None
        self.assets = assets if assets is not None else [make_asset('asset-1')]
        self.people = people if people is not None else [PersonInfo(id='p1', name='Alice')]
        self.timeline_bounds = timeline_bounds
        self.countries = countries
        self.cities = cities
        self.search_calls = 0
        self.closed = False
        self.last_include_shared = False
        self.last_query = None

    def list_libraries(self) -> list[str]:
        return ['family']

    async def validate_access(self, library_name: str) -> None:
        return None

    async def list_albums(self, library_name: str, include_shared: bool = False) -> list[dict[str, str]]:
        self.last_include_shared = include_shared
        return [{'id': 'album-1', 'name': 'Holidays'}]

    async def get_asset_bytes(self, library_name: str, asset_id: str) -> tuple[bytes, str]:
        return b'fake-jpg', 'image/jpeg'

    async def aclose(self) -> None:
        self.closed = True


def seed_test_metadata(
    store: MetadataStore,
    library_name: str,
    immich: FakeImmichClient,
) -> None:
    # 1. Upsert people (merging from immich.people and any asset people)
    people_map: dict[str, str] = {p.id: p.name for p in immich.people}
    for a in immich.assets or []:
        p_list = a.get('people') or a.get('faces') or []
        for p in p_list:
            pid = str(p.get('id', '')) if isinstance(p, dict) else str(p)
            pname = (p.get('name', f'Person {pid}') if isinstance(p, dict) else f'Person {pid}') or f'Person {pid}'
            if pid and pid not in people_map:
                people_map[pid] = pname

    people_data = [{'id': pid, 'name': pname} for pid, pname in people_map.items()]
    store.upsert_people(library_name, people_data)

    # 2. Upsert tags
    tags_map: dict[str, str] = {}
    for a in immich.assets or []:
        t_list = a.get('tags') or []
        for t in t_list:
            tid = str(t.get('id', '')) if isinstance(t, dict) else str(t)
            tname = (t.get('name', f'Tag {tid}') if isinstance(t, dict) else f'Tag {tid}') or f'Tag {tid}'
            if tid and tid not in tags_map:
                tags_map[tid] = tname
    if tags_map:
        store.upsert_tags(library_name, [{'id': tid, 'name': tname} for tid, tname in tags_map.items()])

    # 3. Upsert albums
    store.upsert_albums(library_name, [{'id': 'album-1', 'name': 'Holidays', 'isShared': 0}])

    # 4. Upsert assets batch
    asset_records: list[dict[str, Any]] = []
    asset_people: list[tuple[str, str]] = []
    asset_albums: list[tuple[str, str]] = []
    asset_tags: list[tuple[str, str]] = []

    if immich.assets_explicit or (not immich.cities and not immich.countries and not immich.timeline_bounds):
        for a in immich.assets:
            aid = str(a.get('id', '')).strip()
            if not aid:
                continue
            exif = a.get('exifInfo') or a.get('exif') or {}
            lat = exif.get('latitude')
            lon = exif.get('longitude')
            country = exif.get('country')
            city = exif.get('city')
            captured = exif.get('dateTimeOriginal') or a.get('fileCreatedAt') or a.get('createdAt')

            asset_records.append(
                {
                    'id': aid,
                    'is_shared': 1 if a.get('isShared') or a.get('is_shared') else 0,
                    'is_partner': 1 if a.get('isPartner') or a.get('is_partner') else 0,
                    'file_type': a.get('type', 'IMAGE'),
                    'latitude': float(lat) if lat is not None else None,
                    'longitude': float(lon) if lon is not None else None,
                    'country': country,
                    'city': city,
                    'capture_datetime': captured,
                }
            )

            p_list = a.get('people') or a.get('faces') or []
            for p in p_list:
                pid = str(p.get('id', '')) if isinstance(p, dict) else str(p)
                if pid:
                    asset_people.append((aid, pid))

            alb_list = a.get('albums')
            if alb_list is not None:
                for alb in alb_list:
                    albid = str(alb.get('id', '')) if isinstance(alb, dict) else str(alb)
                    if albid:
                        asset_albums.append((aid, albid))
            else:
                asset_albums.append((aid, 'album-1'))

            t_list = a.get('tags') or []
            for t in t_list:
                tid = str(t.get('id', '')) if isinstance(t, dict) else str(t)
                if tid:
                    asset_tags.append((aid, tid))
    else:
        extra_idx = 1
        tb = immich.timeline_bounds
        min_date_str = tb.min_date.isoformat() if tb and tb.min_date else '2018-03-01'
        max_date_str = tb.max_date.isoformat() if tb and tb.max_date else '2023-11-30'

        if immich.cities:
            for i, c in enumerate(immich.cities):
                aid = f'filter-asset-{extra_idx}'
                extra_idx += 1
                dt_str = min_date_str if i == 0 else (max_date_str if i == len(immich.cities) - 1 else '2020-06-15')
                asset_records.append(
                    {
                        'id': aid,
                        'is_shared': 0,
                        'is_partner': 0,
                        'file_type': 'IMAGE',
                        'latitude': -27.59,
                        'longitude': -48.54,
                        'country': c.country,
                        'city': c.name,
                        'capture_datetime': f'{dt_str}T12:00:00Z',
                    }
                )
                asset_albums.append((aid, 'album-1'))

        if immich.countries:
            existing_countries = {r['country'] for r in asset_records if r.get('country')}
            for co in immich.countries:
                if co not in existing_countries:
                    aid = f'filter-asset-{extra_idx}'
                    extra_idx += 1
                    asset_records.append(
                        {
                            'id': aid,
                            'is_shared': 0,
                            'is_partner': 0,
                            'file_type': 'IMAGE',
                            'latitude': -27.59,
                            'longitude': -48.54,
                            'country': co,
                            'city': None,
                            'capture_datetime': f'{max_date_str}T12:00:00Z',
                        }
                    )
                    asset_albums.append((aid, 'album-1'))

        if immich.timeline_bounds:
            if not any(r.get('capture_datetime', '')[:7] == min_date_str[:7] for r in asset_records):
                aid = f'filter-asset-{extra_idx}'
                extra_idx += 1
                asset_records.append(
                    {
                        'id': aid,
                        'is_shared': 0,
                        'is_partner': 0,
                        'file_type': 'IMAGE',
                        'latitude': -27.59,
                        'longitude': -48.54,
                        'country': 'Brazil',
                        'city': 'Florianopolis',
                        'capture_datetime': f'{min_date_str}T12:00:00Z',
                    }
                )
                asset_albums.append((aid, 'album-1'))
            if not any(r.get('capture_datetime', '')[:7] == max_date_str[:7] for r in asset_records):
                aid = f'filter-asset-{extra_idx}'
                extra_idx += 1
                asset_records.append(
                    {
                        'id': aid,
                        'is_shared': 0,
                        'is_partner': 0,
                        'file_type': 'IMAGE',
                        'latitude': -27.59,
                        'longitude': -48.54,
                        'country': 'Brazil',
                        'city': 'Florianopolis',
                        'capture_datetime': f'{max_date_str}T12:00:00Z',
                    }
                )
                asset_albums.append((aid, 'album-1'))

        if immich.people:
            for i, p in enumerate(immich.people):
                if i < len(asset_records):
                    asset_people.append((asset_records[i]['id'], p.id))
                else:
                    aid = f'filter-asset-{extra_idx}'
                    extra_idx += 1
                    asset_records.append(
                        {
                            'id': aid,
                            'is_shared': 0,
                            'is_partner': 0,
                            'file_type': 'IMAGE',
                            'latitude': -27.59,
                            'longitude': -48.54,
                            'country': 'Brazil',
                            'city': 'Florianopolis',
                            'capture_datetime': f'{min_date_str}T12:00:00Z',
                        }
                    )
                    asset_people.append((aid, p.id))
                    asset_albums.append((aid, 'album-1'))

    store.upsert_assets_batch(library_name, asset_records, asset_people, asset_albums, asset_tags)
    store.set_sync_state(
        library_name,
        status=SyncStatus.idle,
        total_assets=len(asset_records),
        synced_assets=len(asset_records),
    )


def build_client(
    tmp_path: Path,
    immich: FakeImmichClient,
    app_title: str = 'Immich Quiz',
    app_tagline: str = '',
    date_lower_bound: date | None = None,
    date_upper_bound: date | None = None,
    location_score_decay_km: float = 500.0,
    date_score_decay_days: float = 500.0,
    language: str = 'EN',
    country_whitelist: frozenset[str] = frozenset(),
    country_blacklist: frozenset[str] = frozenset(),
    city_whitelist: frozenset[str] = frozenset(),
    city_blacklist: frozenset[str] = frozenset(),
    people_whitelist: frozenset[str] = frozenset(),
    people_blacklist: frozenset[str] = frozenset(),
    tag_whitelist: frozenset[str] = frozenset(),
    tag_blacklist: frozenset[str] = frozenset(),
    immich_libraries: dict[str, str] | None = None,
    auto_seed: bool = True,
) -> TestClient:
    settings = AppSettings(
        immich_server_url='https://placeholder.example.com/api',
        immich_libraries=immich_libraries or {'family': 'token'},
        app_title=app_title,
        app_tagline=app_tagline,
        date_lower_bound=date_lower_bound,
        date_upper_bound=date_upper_bound,
        app_host='127.0.0.1',
        app_port=8010,
        location_score_decay_km=location_score_decay_km,
        date_score_decay_days=date_score_decay_days,
        language=language,
        data_path=tmp_path,
        auto_sync_on_startup=False,
        country_whitelist=country_whitelist,
        country_blacklist=country_blacklist,
        city_whitelist=city_whitelist,
        city_blacklist=city_blacklist,
        people_whitelist=people_whitelist,
        people_blacklist=people_blacklist,
        tag_whitelist=tag_whitelist,
        tag_blacklist=tag_blacklist,
    )
    app = create_app(settings=settings)
    app.state.immich_client = immich
    if auto_seed and hasattr(app.state, 'metadata_store'):
        for lib in settings.immich_libraries:
            seed_test_metadata(app.state.metadata_store, lib, immich)
    return TestClient(app)


@pytest.fixture
def immich() -> FakeImmichClient:
    return FakeImmichClient()


@pytest.fixture
def client(tmp_path: Path, immich: FakeImmichClient) -> TestClient:
    return build_client(tmp_path, immich)

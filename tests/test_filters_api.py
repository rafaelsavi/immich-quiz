from __future__ import annotations

import time
from datetime import date
from pathlib import Path
from typing import Any, cast

import pytest
from cachetools import TTLCache

from src.api.routes import FILTERS_CACHE_TTL_SECONDS, _filters_cache
from src.game.selector import load_asset_pool, select_round_asset
from src.immich.client import CityInfo, ImmichClient, ImmichClientError, PersonInfo, TimelineBounds
from src.models import (
    GameSetupRequest,
)
from src.storage.session import MatchState
from tests.conftest import FakeImmichClient, build_client


@pytest.fixture(autouse=True)
def clear_filters_cache() -> None:
    _filters_cache.clear()


def make_filter_asset(
    asset_id: str,
    latitude: float | None = -27.5969,
    longitude: float | None = -48.5495,
    captured: str | None = '2022-06-15T12:00:00Z',
    country: str | None = 'Brazil',
    city: str | None = 'Florianopolis',
    people_ids: list[str] | None = None,
    media_type: str = 'IMAGE',
) -> dict[str, Any]:
    people_data = [{'id': pid, 'name': f'Person {pid}'} for pid in (people_ids or [])]
    return {
        'id': asset_id,
        'type': media_type,
        'exifInfo': {
            'latitude': latitude,
            'longitude': longitude,
            'dateTimeOriginal': captured,
            'country': country,
            'city': city,
        },
        'fileCreatedAt': captured,
        'people': people_data,
    }


def test_filters_cache_configuration() -> None:
    assert FILTERS_CACHE_TTL_SECONDS == 300
    assert isinstance(_filters_cache, TTLCache)
    assert _filters_cache.maxsize == 64
    assert _filters_cache.ttl == 300


def test_get_filters_success_and_caching(tmp_path: Path) -> None:
    fake_people = [PersonInfo(id='p1', name='Alice'), PersonInfo(id='p2', name='Bob')]
    fake_bounds = TimelineBounds(min_date=date(2018, 3, 1), max_date=date(2023, 11, 30))
    fake_countries = ['Brazil', 'France', 'Italy']
    fake_cities = [
        CityInfo(name='Florianopolis', country='Brazil'),
        CityInfo(name='Paris', country='France'),
        CityInfo(name='Rome', country='Italy'),
    ]

    immich = FakeImmichClient(
        people=fake_people,
        timeline_bounds=fake_bounds,
        countries=fake_countries,
        cities=fake_cities,
    )
    client = build_client(tmp_path, immich)

    # 1. First call fetches fresh data and caches it
    t0 = time.perf_counter()
    response = client.get('/api/filters?library_name=family')
    t_first = time.perf_counter() - t0

    assert response.status_code == 200
    data = response.json()

    assert data['date_range'] == {'min_month': '2018-03', 'max_month': '2023-11'}
    assert data['countries'] == ['Brazil', 'France', 'Italy']
    assert len(data['cities']) == 3
    assert data['cities'][0] == {'name': 'Florianopolis', 'country': 'Brazil'}
    assert data['cities'][1] == {'name': 'Paris', 'country': 'France'}
    assert data['cities'][2] == {'name': 'Rome', 'country': 'Italy'}
    assert len(data['people']) == 2
    assert data['people'][0] == {'id': 'p1', 'name': 'Alice'}
    assert data['people'][1] == {'id': 'p2', 'name': 'Bob'}

    # Verify cache is populated
    assert 'family' in _filters_cache

    # 2. Mutate the client state to prove that second call uses cached response
    immich.people = [PersonInfo(id='p99', name='Mutated')]
    immich.countries = ['Spain']

    t0 = time.perf_counter()
    cached_response = client.get('/api/filters?library_name=family')
    t_cached = time.perf_counter() - t0

    assert cached_response.status_code == 200
    cached_data = cached_response.json()
    assert cached_data['countries'] == ['Brazil', 'France', 'Italy']
    assert cached_data['people'][0]['name'] == 'Alice'
    assert t_cached < t_first + 0.05


def test_get_filters_env_date_bounds_override(tmp_path: Path) -> None:
    fake_bounds = TimelineBounds(min_date=date(2010, 1, 1), max_date=date(2025, 1, 1))
    immich = FakeImmichClient(timeline_bounds=fake_bounds)

    # App settings specify tighter bounds
    client = build_client(
        tmp_path,
        immich,
        fetch_photos_date_lower_bound=date(2021, 5, 1),
        fetch_photos_date_upper_bound=date(2022, 12, 31),
    )

    response = client.get('/api/filters?library_name=family')
    assert response.status_code == 200
    data = response.json()
    assert data['date_range'] == {'min_month': '2021-05', 'max_month': '2022-12'}


def test_get_filters_error_handling(tmp_path: Path) -> None:
    immich = FakeImmichClient()

    async def failing_list_people(library_name: str, **kwargs: Any) -> list[PersonInfo]:
        raise ImmichClientError(f'Unknown library "{library_name}"')

    immich.list_people = failing_list_people  # type: ignore[assignment]
    client = build_client(tmp_path, immich)

    response = client.get('/api/filters?library_name=invalid_lib')
    assert response.status_code == 400
    assert 'Unknown library' in response.json()['detail']


def test_preflight_custom_filters_validation(tmp_path: Path) -> None:
    immich = FakeImmichClient(
        assets=[
            make_filter_asset(
                'a1', latitude=-27.59, longitude=-48.54, captured='2022-06-15T10:00:00Z', people_ids=['p1', 'p2']
            ),
            make_filter_asset(
                'a2', latitude=48.85, longitude=2.35, captured='2023-08-20T10:00:00Z', people_ids=['p1', 'p2']
            ),
            make_filter_asset(
                'a3', latitude=35.67, longitude=139.65, captured='2023-10-10T10:00:00Z', people_ids=['p1', 'p2']
            ),
            make_filter_asset(
                'a4', latitude=40.71, longitude=-74.00, captured='2023-11-12T10:00:00Z', people_ids=['p1', 'p2']
            ),
            make_filter_asset(
                'a5', latitude=-33.86, longitude=151.20, captured='2023-12-01T10:00:00Z', people_ids=['p1', 'p2']
            ),
        ]
    )
    client = build_client(tmp_path, immich)

    # 1. Preflight with OR mode
    payload = {
        'library_name': 'family',
        'round_count': 5,
        'location_mode': True,
        'date_mode': True,
        'person_ids': ['p1', 'p2'],
        'people_mode': 'OR',
        'countries': ['Brazil', 'France'],
        'cities': ['Florianopolis', 'Paris'],
        'min_date': '2022-01-01',
        'max_date': '2024-01-01',
        'album_ids': ['album-1'],
    }
    response = client.post('/api/game/preflight', json=payload)
    assert response.status_code == 200
    res_data = response.json()
    assert res_data['active_filters'] == ['location', 'date', 'albums', 'people', 'countries', 'cities', 'date_range']
    assert res_data['min_date'] == '2022-01-01'
    assert res_data['max_date'] == '2024-01-01'

    # 2. Preflight with AND mode
    payload['people_mode'] = 'AND'
    response_and = client.post('/api/game/preflight', json=payload)
    assert response_and.status_code == 200
    res_and_data = response_and.json()
    assert 'people_all' in res_and_data['active_filters']


def test_preflight_effective_date_bounds(tmp_path: Path) -> None:
    immich = FakeImmichClient(
        assets=[
            make_filter_asset('a1', captured='2022-06-15T10:00:00Z'),
            make_filter_asset('a2', captured='2022-07-15T10:00:00Z'),
            make_filter_asset('a3', captured='2022-08-15T10:00:00Z'),
            make_filter_asset('a4', captured='2022-09-15T10:00:00Z'),
            make_filter_asset('a5', captured='2022-10-15T10:00:00Z'),
        ]
    )
    # Env bounds: [2021-01-01, 2023-01-01]
    client = build_client(
        tmp_path,
        immich,
        fetch_photos_date_lower_bound=date(2021, 1, 1),
        fetch_photos_date_upper_bound=date(2023, 1, 1),
    )

    # Request bounds: [2022-01-01, 2024-01-01] -> Effective bounds: [2022-01-01, 2023-01-01]
    payload = {
        'library_name': 'family',
        'round_count': 5,
        'location_mode': True,
        'date_mode': True,
        'min_date': '2022-01-01',
        'max_date': '2024-01-01',
    }
    response = client.post('/api/game/preflight', json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data['min_date'] == '2022-01-01'
    assert data['max_date'] == '2023-01-01'


def test_preflight_diversity_enforcement(tmp_path: Path) -> None:
    # 3 photos: Photo 1 and Photo 2 are close (<100m, <60s). Photo 3 is far.
    asset1 = make_filter_asset('a1', latitude=-27.5969, longitude=-48.5495, captured='2024-01-14T10:00:00Z')
    asset2 = make_filter_asset('a2', latitude=-27.5970, longitude=-48.5495, captured='2024-01-14T10:00:10Z')
    asset3 = make_filter_asset('a3', latitude=48.8566, longitude=2.3522, captured='2024-06-15T12:00:00Z')

    immich = FakeImmichClient(assets=[asset1, asset2, asset3])
    client = build_client(tmp_path, immich)

    payload = {
        'library_name': 'family',
        'round_count': 5,
        'location_mode': True,
        'date_mode': True,
    }
    response = client.post('/api/game/preflight', json=payload)
    assert response.status_code == 200
    data = response.json()

    # Out of 3 assets, only 2 satisfy distance (>=100m) and time (>=60s) separation
    assert data['eligible_count'] == 2
    assert data['required'] == 5
    assert data['ok'] is False


def test_preflight_immich_error(tmp_path: Path) -> None:
    immich = FakeImmichClient()

    async def failing_search_assets(*args: Any, **kwargs: Any) -> list[dict[str, Any]]:
        raise ImmichClientError('Immich API search connection failed')

    immich.search_assets = failing_search_assets  # type: ignore[method-assign]
    client = build_client(tmp_path, immich)

    payload = {
        'library_name': 'family',
        'round_count': 5,
    }
    response = client.post('/api/game/preflight', json=payload)
    assert response.status_code == 400
    assert 'search connection failed' in response.json()['detail']


@pytest.mark.asyncio
async def test_selector_load_asset_pool_filters() -> None:
    asset_match = make_filter_asset(
        'a1', country='Brazil', city='Florianopolis', people_ids=['p1'], captured='2022-05-10T10:00:00Z'
    )
    asset_wrong_country = make_filter_asset(
        'a2', country='France', city='Paris', people_ids=['p1'], captured='2022-05-10T10:00:00Z'
    )
    asset_wrong_person = make_filter_asset(
        'a3', country='Brazil', city='Florianopolis', people_ids=['p2'], captured='2022-05-10T10:00:00Z'
    )
    asset_wrong_date = make_filter_asset(
        'a4', country='Brazil', city='Florianopolis', people_ids=['p1'], captured='2019-01-01T10:00:00Z'
    )

    immich = FakeImmichClient(assets=[asset_match, asset_wrong_country, asset_wrong_person, asset_wrong_date])

    setup = GameSetupRequest(
        players=['Player 1'],
        round_count=5,
        location_mode=True,
        date_mode=True,
        library_name='family',
        person_ids=['p1'],
        people_mode='OR',
        countries=['Brazil'],
        cities=['Florianopolis'],
        min_date=date(2021, 1, 1),
        max_date=date(2023, 1, 1),
    )

    state = MatchState(match_id='test-match', setup=setup)
    await load_asset_pool(state, cast(ImmichClient, immich), min_capture_date=None, max_capture_date=None)

    # Only asset_match meets all filter criteria
    assert set(state.asset_pool.keys()) == {'a1'}
    assert immich.last_query is not None
    assert immich.last_query.person_ids == ('p1',)
    assert immich.last_query.countries == ('Brazil',)
    assert immich.last_query.cities == ('Florianopolis',)
    assert immich.last_query.min_date == date(2021, 1, 1)
    assert immich.last_query.max_date == date(2023, 1, 1)


@pytest.mark.asyncio
async def test_selector_respects_diversity_on_round_selection() -> None:
    asset1 = make_filter_asset('a1', latitude=-27.5969, longitude=-48.5495, captured='2024-01-14T10:00:00Z')
    asset2_close = make_filter_asset('a2', latitude=-27.5970, longitude=-48.5495, captured='2024-01-14T10:00:10Z')
    asset3_far = make_filter_asset('a3', latitude=48.8566, longitude=2.3522, captured='2024-06-15T12:00:00Z')

    immich = FakeImmichClient(assets=[asset1, asset2_close, asset3_far])

    setup = GameSetupRequest(
        players=['Player 1'],
        round_count=5,
        location_mode=True,
        date_mode=True,
        library_name='family',
    )
    state = MatchState(match_id='test-match', setup=setup)
    state.played_asset_ids.add('a1')
    state.asset_pool = {
        'a1': ImmichClient.extract_answer(asset1),
        'a2': ImmichClient.extract_answer(asset2_close),
        'a3': ImmichClient.extract_answer(asset3_far),
    }

    round_asset = await select_round_asset(
        state,
        cast(ImmichClient, immich),
        client_excluded=set(),
        min_capture_date=None,
        max_capture_date=None,
        min_dist_km=0.1,
        min_time_sec=60.0,
    )

    # a2 should be rejected because it is within 100m / 60s of played asset a1; a3 should be chosen
    assert round_asset is not None
    assert round_asset.asset_id == 'a3'


def test_game_setup_accepts_filter_criteria(tmp_path: Path) -> None:
    immich = FakeImmichClient(
        assets=[
            make_filter_asset('a1', latitude=-27.59, longitude=-48.54),
            make_filter_asset('a2', latitude=48.85, longitude=2.35),
            make_filter_asset('a3', latitude=35.67, longitude=139.65),
            make_filter_asset('a4', latitude=40.71, longitude=-74.00),
            make_filter_asset('a5', latitude=-33.86, longitude=151.20),
        ]
    )
    client = build_client(tmp_path, immich)

    payload = {
        'players': ['Alice'],
        'round_count': 5,
        'round_length': '1m',
        'location_mode': True,
        'date_mode': True,
        'library_name': 'family',
        'album_ids': [],
        'person_ids': ['p1'],
        'people_mode': 'AND',
        'countries': ['Brazil'],
        'cities': ['Florianopolis'],
        'min_date': '2022-01-01',
        'max_date': '2023-12-31',
    }
    response = client.post('/api/game/setup', json=payload)
    assert response.status_code == 200
    data = response.json()
    assert 'match_id' in data
    assert data['players'] == ['Alice']

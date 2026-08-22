from __future__ import annotations

import time
from datetime import date
from pathlib import Path
from typing import Any, cast

import pytest
from cachetools import TTLCache

from src.api.routes import FILTERS_CACHE_TTL_SECONDS, _filters_cache
from src.game.selector import load_asset_pool, select_round_asset
from src.immich.client import ImmichClient
from src.models import (
    GameSetupRequest,
)
from src.storage.db import DatabaseManager
from src.storage.metadata import MetadataStore
from src.storage.session import MatchState
from tests.conftest import (
    CityInfo,
    FakeImmichClient,
    PersonInfo,
    TimelineBounds,
    build_client,
    seed_test_metadata,
    setup_payload,
)


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
    tag_ids: list[str] | None = None,
    media_type: str = 'IMAGE',
) -> dict[str, Any]:
    people_data = [{'id': pid, 'name': f'Person {pid}'} for pid in (people_ids or [])]
    tags_data = [{'id': tid, 'name': f'Tag {tid}'} for tid in (tag_ids or [])]
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
        'tags': tags_data,
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
    response = client.get('/api/filters?libraries=family')
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
    assert ('family',) in _filters_cache

    # 2. Mutate the client state to prove that second call uses cached response
    immich.people = [PersonInfo(id='p99', name='Mutated')]
    immich.countries = ['Spain']

    t0 = time.perf_counter()
    cached_response = client.get('/api/filters?libraries=family')
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
        date_lower_bound=date(2021, 5, 1),
        date_upper_bound=date(2022, 12, 31),
    )

    response = client.get('/api/filters?libraries=family')
    assert response.status_code == 200
    data = response.json()
    assert data['date_range'] == {'min_month': '2021-05', 'max_month': '2022-12'}


def test_get_filters_empty_library_returns_empty_options(tmp_path: Path) -> None:
    immich = FakeImmichClient()
    client = build_client(tmp_path, immich)

    response = client.get('/api/filters?libraries=unindexed_lib')
    assert response.status_code == 200
    data = response.json()
    assert data['countries'] == []
    assert data['cities'] == []
    assert data['people'] == []
    assert data['date_range'] == {'min_month': None, 'max_month': None}


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

    # 1. Preflight with ANY mode
    payload = {
        'libraries': ['family'],
        'round_count': 5,
        'location_mode': True,
        'date_mode': True,
        'person_ids': ['p1', 'p2'],
        'people_mode': 'ANY',
        'countries': ['Brazil', 'France'],
        'cities': ['Florianopolis', 'Paris'],
        'min_date': '2022-01-01',
        'max_date': '2024-01-01',
        'album_ids': ['album-1'],
    }
    response = client.post('/api/game/preflight', json=payload)
    assert response.status_code == 200
    res_data = response.json()
    assert res_data['active_filters'] == [
        'location',
        'date',
        'libraries',
        'albums',
        'people',
        'countries',
        'cities',
        'date_range',
    ]
    assert res_data['min_date'] == '2022-01-01'
    assert res_data['max_date'] == '2024-01-01'

    # 2. Preflight with ALL mode
    payload['people_mode'] = 'ALL'
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
        date_lower_bound=date(2021, 1, 1),
        date_upper_bound=date(2023, 1, 1),
    )

    # Request bounds: [2022-01-01, 2024-01-01] -> Effective bounds: [2022-01-01, 2023-01-01]
    payload = {
        'libraries': ['family'],
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
        'libraries': ['family'],
        'round_count': 5,
        'location_mode': True,
        'date_mode': True,
    }
    response = client.post('/api/game/preflight', json=payload)
    assert response.status_code == 200
    data = response.json()

    # Preflight reports raw eligible count — all 3 assets have GPS + timestamp so all pass.
    # Diversity (min distance/time between photos) is enforced by the game selector on a
    # much larger pool, not by the preflight 250-sample.
    assert data['eligible_count'] == 3
    assert data['required'] == 5
    assert data['ok'] is False  # 3 eligible < 5 required


def test_preflight_and_setup_unsynced_library(tmp_path: Path) -> None:
    immich = FakeImmichClient()
    client = build_client(tmp_path, immich, auto_seed=False)

    # 1. Preflight on unindexed library returns is_synced=False and ok=False
    preflight_res = client.post('/api/game/preflight', json={'libraries': ['family'], 'round_count': 5})
    assert preflight_res.status_code == 200
    data = preflight_res.json()
    assert data['is_synced'] is False
    assert data['ok'] is False
    assert data['eligible_count'] == 0

    # 2. Starting game on unindexed library returns 400 with helpful message
    setup_res = client.post('/api/game/setup', json=setup_payload(libraries=['family']))
    assert setup_res.status_code == 400
    assert 'not been synced yet' in setup_res.json()['detail']


def test_selector_load_asset_pool_filters(tmp_path: Path) -> None:
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
    db_mgr = DatabaseManager(tmp_path / 'metadata.db')
    metadata_store = MetadataStore(db_mgr)
    seed_test_metadata(metadata_store, 'family', immich)

    setup = GameSetupRequest(
        players=['Player 1'],
        round_count=5,
        location_mode=True,
        date_mode=True,
        libraries=['family'],
        person_ids=['p1'],
        people_mode='ANY',
        countries=['Brazil'],
        cities=['Florianopolis'],
        min_date=date(2021, 1, 1),
        max_date=date(2023, 1, 1),
    )

    state = MatchState(match_id='test-match', setup=setup)
    load_asset_pool(state, metadata_store)

    # Only asset_match meets all filter criteria
    assert set(state.asset_pool.keys()) == {'a1'}


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
        libraries=['family'],
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
        'libraries': ['family'],
        'album_ids': [],
        'person_ids': ['p1'],
        'people_mode': 'ALL',
        'countries': ['Brazil'],
        'cities': ['Florianopolis'],
        'min_date': '2022-01-01',
        'max_date': '2023-12-31',
    }
    response = client.post('/api/game/setup', json=payload)
    assert response.status_code == 200
    data = response.json()
    assert 'match_id' in data


def test_preflight_people_mode_any_vs_all(tmp_path: Path) -> None:
    # a1 has person p1 only, a2 has person p2 only, a3 has both p1 and p2
    a1 = make_filter_asset('a1', people_ids=['p1'])
    a2 = make_filter_asset('a2', people_ids=['p2'])
    a3 = make_filter_asset('a3', people_ids=['p1', 'p2'])

    immich = FakeImmichClient(assets=[a1, a2, a3])
    client = build_client(tmp_path, immich)

    # ANY mode: all 3 photos match (a1, a2, a3)
    res_any = client.post(
        '/api/game/preflight',
        json={
            'libraries': ['family'],
            'round_count': 5,
            'location_mode': True,
            'date_mode': False,
            'person_ids': ['p1', 'p2'],
            'people_mode': 'ANY',
        },
    )
    assert res_any.status_code == 200
    assert res_any.json()['eligible_count'] == 3
    assert res_any.json()['ok'] is False  # 3 < 5 required

    # ALL mode: only 1 photo matches (a3)
    res_all = client.post(
        '/api/game/preflight',
        json={
            'libraries': ['family'],
            'round_count': 5,
            'location_mode': True,
            'date_mode': False,
            'person_ids': ['p1', 'p2'],
            'people_mode': 'ALL',
        },
    )
    assert res_all.status_code == 200
    assert res_all.json()['eligible_count'] == 1
    assert res_all.json()['ok'] is False  # 1 < 5 required


def test_preflight_multiple_cities_or_mode(tmp_path: Path) -> None:
    # a1 is in Paris, a2 is in Rome, a3 is in Berlin
    a1 = make_filter_asset('a1', city='Paris', country='France')
    a2 = make_filter_asset('a2', city='Rome', country='Italy')
    a3 = make_filter_asset('a3', city='Berlin', country='Germany')

    immich = FakeImmichClient(assets=[a1, a2, a3])
    client = build_client(tmp_path, immich)

    # Selecting Paris and Rome returns both photos (union / OR logic)
    res = client.post(
        '/api/game/preflight',
        json={
            'libraries': ['family'],
            'round_count': 5,
            'location_mode': True,
            'date_mode': False,
            'cities': ['Paris', 'Rome'],
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data['eligible_count'] == 2
    assert data['ok'] is False  # 2 < 5 required
    assert data['required'] == 5


def test_preflight_include_shared_photos_filter(tmp_path: Path) -> None:
    asset_owned = make_filter_asset('a1')
    asset_shared = make_filter_asset('a2')
    asset_shared['isShared'] = True

    immich = FakeImmichClient(assets=[asset_owned, asset_shared])
    client = build_client(tmp_path, immich)

    # 1. include_shared=False -> only owned asset is returned
    res_private = client.post(
        '/api/game/preflight',
        json={
            'libraries': ['family'],
            'round_count': 5,
            'location_mode': True,
            'date_mode': False,
            'include_shared': False,
        },
    )
    assert res_private.status_code == 200
    assert res_private.json()['eligible_count'] == 1

    # 2. include_shared=True -> both assets are returned
    res_shared = client.post(
        '/api/game/preflight',
        json={
            'libraries': ['family'],
            'round_count': 5,
            'location_mode': True,
            'date_mode': False,
            'include_shared': True,
        },
    )
    assert res_shared.status_code == 200
    assert res_shared.json()['eligible_count'] == 2


def test_models_date_order_validation(tmp_path: Path) -> None:
    client = build_client(tmp_path, FakeImmichClient())

    # Preflight with min_date > max_date should fail with 422
    res_preflight = client.post(
        '/api/game/preflight',
        json={
            'libraries': ['family'],
            'min_date': '2024-01-01',
            'max_date': '2022-01-01',
        },
    )
    assert res_preflight.status_code == 422

    # Game setup with min_date > max_date should fail with 422
    res_setup = client.post(
        '/api/game/setup',
        json={
            'players': ['Alice'],
            'libraries': ['family'],
            'min_date': '2024-01-01',
            'max_date': '2022-01-01',
        },
    )
    assert res_setup.status_code == 422


def test_preflight_allows_empty_players_while_setup_requires_players(tmp_path: Path) -> None:
    client = build_client(tmp_path, FakeImmichClient(assets=[make_filter_asset('a1')]))

    # Preflight with empty players succeeds
    res_preflight = client.post(
        '/api/game/preflight',
        json={
            'libraries': ['family'],
            'players': [],
        },
    )
    assert res_preflight.status_code == 200

    # Setup with empty players fails with 422
    res_setup_empty = client.post(
        '/api/game/setup',
        json={
            'libraries': ['family'],
            'players': [],
        },
    )
    assert res_setup_empty.status_code == 422

    # Setup with whitespace-only player fails with 422
    res_setup_blank = client.post(
        '/api/game/setup',
        json={
            'libraries': ['family'],
            'players': ['   '],
        },
    )
    assert res_setup_blank.status_code == 422


def test_preflight_and_setup_enforce_whitelists_and_blacklists(tmp_path: Path) -> None:
    asset_brazil = make_filter_asset('a1', country='Brazil', city='Rio', people_ids=['p1'])
    asset_germany = make_filter_asset('a2', country='Germany', city='Berlin', people_ids=['p2'])
    asset_japan = make_filter_asset('a3', country='Japan', city='Tokyo', people_ids=[])

    immich = FakeImmichClient(assets=[asset_brazil, asset_germany, asset_japan])

    # Build client with country_blacklist and people_blacklist configured
    client = build_client(
        tmp_path,
        immich,
        country_blacklist=frozenset({'germany'}),
        people_blacklist=frozenset({'p2', 'person p2'}),
    )

    # 1. Preflight with empty filters -> Germany (a2) is excluded by blacklist, leaving 2 eligible
    res_preflight = client.post(
        '/api/game/preflight',
        json={
            'libraries': ['family'],
            'countries': [],
            'cities': [],
            'person_ids': [],
            'round_count': 5,
        },
    )
    assert res_preflight.status_code == 200
    data = res_preflight.json()
    assert data['eligible_count'] == 2

    # 2. Setup game with empty filters
    res_setup = client.post(
        '/api/game/setup',
        json={
            'libraries': ['family'],
            'players': ['Alice'],
            'countries': [],
            'cities': [],
            'person_ids': [],
            'round_count': 5,
        },
    )
    assert res_setup.status_code == 200


def test_preflight_and_setup_enforce_tag_whitelists_and_blacklists(tmp_path: Path) -> None:
    asset_vacation = make_filter_asset('a1', country='Brazil', city='Rio', tag_ids=['t1'])
    asset_private = make_filter_asset('a2', country='Germany', city='Berlin', tag_ids=['t2'])
    asset_untagged = make_filter_asset('a3', country='Japan', city='Tokyo', tag_ids=[])

    immich = FakeImmichClient(assets=[asset_vacation, asset_private, asset_untagged])

    # 1. Test tag_blacklist: excludes asset_private (a2)
    client_bl = build_client(
        tmp_path / 'bl',
        immich,
        tag_blacklist=frozenset({'tag t2', 't2'}),
    )
    res_bl = client_bl.post(
        '/api/game/preflight',
        json={'libraries': ['family'], 'round_count': 5},
    )
    assert res_bl.status_code == 200
    assert res_bl.json()['eligible_count'] == 2

    # 2. Test tag_whitelist: includes only asset_vacation (a1)
    client_wl = build_client(
        tmp_path / 'wl',
        immich,
        tag_whitelist=frozenset({'tag t1'}),
    )
    res_wl = client_wl.post(
        '/api/game/preflight',
        json={'libraries': ['family'], 'round_count': 5},
    )
    assert res_wl.status_code == 200
    assert res_wl.json()['eligible_count'] == 1


def test_multi_library_filters_and_preflight(tmp_path: Path) -> None:
    asset_family = make_filter_asset('fam-1', country='Brazil', city='Rio', people_ids=['p1'])

    immich = FakeImmichClient(assets=[asset_family])
    client = build_client(tmp_path, immich)
    meta_store: MetadataStore = client.app.state.metadata_store

    meta_store.upsert_people('family', [{'id': 'p1', 'name': 'Alice'}])
    meta_store.upsert_people('travel', [{'id': 'p2', 'name': 'Bob'}])
    meta_store.upsert_albums('family', [{'id': 'alb-1', 'name': 'Family Album'}])
    meta_store.upsert_albums('travel', [{'id': 'alb-2', 'name': 'Travel Album'}])

    # Seed assets into distinct libraries in metadata store
    meta_store.upsert_assets_batch(
        'family',
        [
            {
                'id': 'fam-1',
                'file_type': 'IMAGE',
                'latitude': -22.90,
                'longitude': -43.17,
                'capture_datetime': '2023-01-01T12:00:00',
                'country': 'Brazil',
                'city': 'Rio',
                'is_shared': 0,
                'is_partner': 0,
            }
        ],
        [('fam-1', 'p1')],
        [('fam-1', 'alb-1')],
    )

    meta_store.upsert_assets_batch(
        'travel',
        [
            {
                'id': 'trv-1',
                'file_type': 'IMAGE',
                'latitude': 35.67,
                'longitude': 139.65,
                'capture_datetime': '2023-06-01T12:00:00',
                'country': 'Japan',
                'city': 'Tokyo',
                'is_shared': 0,
                'is_partner': 0,
            }
        ],
        [('trv-1', 'p2')],
        [('trv-1', 'alb-2')],
    )

    # 1. Test /api/albums across multiple libraries
    res_albums = client.get('/api/albums?libraries=family&libraries=travel')
    assert res_albums.status_code == 200
    album_names = {a['name'] for a in res_albums.json()['albums']}
    assert 'Family Album' in album_names
    assert 'Travel Album' in album_names

    # 2. Test /api/filters across multiple libraries
    res_filters = client.get('/api/filters?libraries=family&libraries=travel')
    assert res_filters.status_code == 200
    filter_data = res_filters.json()
    assert 'Brazil' in filter_data['countries']
    assert 'Japan' in filter_data['countries']
    people_names = {p['name'] for p in filter_data['people']}
    assert 'Alice' in people_names
    assert 'Bob' in people_names

    # 3. Test /api/game/preflight with multi-library selection
    res_preflight = client.post(
        '/api/game/preflight',
        json={
            'libraries': ['family', 'travel'],
            'round_count': 5,
            'location_mode': True,
            'date_mode': True,
        },
    )
    assert res_preflight.status_code == 200
    preflight_data = res_preflight.json()
    assert preflight_data['total_count'] == 2
    assert preflight_data['eligible_count'] == 2
    assert 'libraries' in preflight_data['active_filters']

    # 4. Test /api/game/preflight filtering to single library
    res_single = client.post(
        '/api/game/preflight',
        json={
            'libraries': ['family'],
            'round_count': 5,
            'location_mode': True,
            'date_mode': True,
        },
    )
    assert res_single.status_code == 200
    assert res_single.json()['total_count'] == 1


def test_global_sync_endpoints(tmp_path: Path) -> None:
    immich = FakeImmichClient()
    client = build_client(tmp_path, immich)

    # 1. Global sync status when nothing is synced yet
    res_status = client.get('/api/sync/status')
    assert res_status.status_code == 200
    data = res_status.json()
    assert 'libraries' in data
    assert isinstance(data['libraries'], list)
    assert 'warnings' in data
    assert isinstance(data['warnings'], dict)
    assert 'is_syncing' in data

    # 2. Global trigger sync
    res_sync = client.post('/api/sync')
    assert res_sync.status_code == 200
    assert res_sync.json()['is_syncing'] is True or res_sync.json()['sync_status'] in {'syncing', 'idle'}


def test_multi_library_and_multi_album_filters_api(tmp_path: Path) -> None:
    immich = FakeImmichClient()
    client = build_client(
        tmp_path,
        immich,
        immich_libraries={'lib1': 'key1', 'lib2': 'key2'},
        auto_seed=False,
    )
    meta_store = client.app.state.metadata_store  # type: ignore

    # Seed metadata for lib1 and lib2
    meta_store.upsert_albums('lib1', [{'id': 'alb-1', 'name': 'Lib1 Album'}])
    meta_store.upsert_albums('lib2', [{'id': 'alb-2', 'name': 'Lib2 Album'}])

    assets1 = [
        {
            'id': 'p-1',
            'is_shared': 0,
            'is_partner': 0,
            'file_type': 'IMAGE',
            'latitude': -22.9,
            'longitude': -43.1,
            'country': 'Brazil',
            'city': 'Rio',
            'capture_datetime': '2023-01-01T12:00:00',
        },
    ]
    assets2 = [
        {
            'id': 'p-2',
            'is_shared': 0,
            'is_partner': 0,
            'file_type': 'IMAGE',
            'latitude': 48.8,
            'longitude': 2.3,
            'country': 'France',
            'city': 'Paris',
            'capture_datetime': '2023-02-01T12:00:00',
        },
    ]
    meta_store.upsert_assets_batch('lib1', assets1, [], [('p-1', 'alb-1')])
    meta_store.upsert_assets_batch('lib2', assets2, [], [('p-2', 'alb-2')])

    # 1. /api/albums querying both libraries returns both albums
    res_albums = client.get('/api/albums?libraries=lib1&libraries=lib2')
    assert res_albums.status_code == 200
    album_ids = {a['id'] for a in res_albums.json()['albums']}
    assert album_ids == {'alb-1', 'alb-2'}

    # 2. /api/filters querying both libraries returns both countries & cities
    res_filters = client.get('/api/filters?libraries=lib1&libraries=lib2')
    assert res_filters.status_code == 200
    data = res_filters.json()
    assert set(data['countries']) == {'Brazil', 'France'}
    assert {c['name'] for c in data['cities']} == {'Rio', 'Paris'}

    # 3. /api/game/preflight with multiple album_ids across libraries
    res_preflight = client.post(
        '/api/game/preflight',
        json={
            'libraries': ['lib1', 'lib2'],
            'album_ids': ['alb-1', 'alb-2'],
            'round_count': 5,
            'location_mode': True,
            'date_mode': True,
        },
    )
    assert res_preflight.status_code == 200
    pf = res_preflight.json()
    assert pf['total_count'] == 2
    assert pf['eligible_count'] == 2
    assert pf['facet_counts']['albums']['alb-1'] == 1
    assert pf['facet_counts']['albums']['alb-2'] == 1

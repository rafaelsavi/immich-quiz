from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from src.config import AppSettings
from src.main import create_app
from src.models import CityOption, PeopleMode, SyncMode, SyncStage, SyncStatus
from src.storage.db import DatabaseManager
from src.storage.metadata import AssetFilterCriteria, MetadataStore
from src.storage.sync import SyncEngine


@pytest.fixture
def db_mgr(tmp_path: Path) -> DatabaseManager:
    return DatabaseManager(tmp_path / 'test_metadata.db')


@pytest.fixture
def meta_store(db_mgr: DatabaseManager) -> MetadataStore:
    return MetadataStore(db_mgr)


def test_db_manager_init(db_mgr: DatabaseManager) -> None:
    assert db_mgr.db_path.exists()
    with db_mgr.connection() as conn:
        cursor = conn.execute('PRAGMA journal_mode;')
        row = cursor.fetchone()
        assert row[0].lower() == 'wal'


def test_metadata_store_schema_and_sync_state(meta_store: MetadataStore) -> None:
    assert not meta_store.has_synced_assets(['family'])
    state = meta_store.get_sync_state('family')
    assert state['sync_status'] == SyncStatus.idle.value
    assert state['total_assets'] == 0

    meta_store.set_sync_state(
        'family',
        status=SyncStatus.syncing,
        total_assets=100,
        synced_assets=25,
    )
    state = meta_store.get_sync_state('family')
    assert state['sync_status'] == SyncStatus.syncing.value
    assert state['total_assets'] == 100
    assert state['synced_assets'] == 25


def test_metadata_store_upsert_and_queries(meta_store: MetadataStore) -> None:
    # 1. Upsert People & Albums
    meta_store.upsert_people('family', [{'id': 'p1', 'name': 'Alice'}, {'id': 'p2', 'name': 'Bob'}])
    meta_store.upsert_albums('family', [{'id': 'a1', 'name': 'Summer Trip', 'isShared': 0}])

    # 2. Upsert Assets Batch
    assets = [
        {
            'id': 'asset-1',
            'is_shared': 0,
            'is_partner': 0,
            'file_type': 'IMAGE',
            'latitude': 35.6895,
            'longitude': 139.6917,
            'country': 'Japan',
            'city': 'Tokyo',
            'capture_datetime': '2023-05-10T12:00:00',
        },
        {
            'id': 'asset-2',
            'is_shared': 0,
            'is_partner': 0,
            'file_type': 'IMAGE',
            'latitude': 48.8566,
            'longitude': 2.3522,
            'country': 'France',
            'city': 'Paris',
            'capture_datetime': '2022-08-15T14:30:00',
        },
        {
            'id': 'asset-3',
            'is_shared': 1,
            'is_partner': 0,
            'file_type': 'IMAGE',
            'latitude': 48.8566,
            'longitude': 2.3522,
            'country': 'France',
            'city': 'Paris',
            'capture_datetime': '2021-06-01T10:00:00',
        },
        {
            'id': 'asset-4',
            'is_shared': 0,
            'is_partner': 0,
            'file_type': 'VIDEO',  # Should be excluded
            'latitude': 35.6895,
            'longitude': 139.6917,
            'country': 'Japan',
            'city': 'Tokyo',
            'capture_datetime': '2023-05-10T12:05:00',
        },
    ]

    asset_people = [
        ('asset-1', 'p1'),
        ('asset-1', 'p2'),
        ('asset-2', 'p1'),
    ]

    asset_albums = [
        ('asset-1', 'a1'),
    ]

    meta_store.upsert_assets_batch('family', assets, asset_people, asset_albums)
    assert meta_store.has_synced_assets(['family'])

    # Test count & candidate fetching parity
    # Query 1: All private images
    c1 = AssetFilterCriteria(library_names=('family',))
    count1 = meta_store.count_eligible_assets(c1)
    cand1 = meta_store.fetch_candidate_assets(c1)
    # asset-1, asset-2 (asset-3 is shared, asset-4 is video)
    assert count1 == 2
    assert len(cand1) == 2
    assert set(cand1.keys()) == {'asset-1', 'asset-2'}

    # Query 2: Include shared photos
    c2 = AssetFilterCriteria(library_names=('family',), include_shared=True)
    count2 = meta_store.count_eligible_assets(c2)
    cand2 = meta_store.fetch_candidate_assets(c2)
    assert count2 == 3
    assert set(cand2.keys()) == {'asset-1', 'asset-2', 'asset-3'}

    # Query 3: Country filter 'Japan'
    c3 = AssetFilterCriteria(library_names=('family',), countries=('Japan',))
    count3 = meta_store.count_eligible_assets(c3)
    cand3 = meta_store.fetch_candidate_assets(c3)
    assert count3 == 1
    assert 'asset-1' in cand3

    # Query 4: People filter with ALL mode (both p1 and p2 by ID)
    c4 = AssetFilterCriteria(library_names=('family',), person_ids=('p1', 'p2'), people_mode=PeopleMode.ALL)
    count4 = meta_store.count_eligible_assets(c4)
    cand4 = meta_store.fetch_candidate_assets(c4)
    assert count4 == 1
    assert 'asset-1' in cand4

    # Query 5: People filter with ANY mode (p1 or p2 by ID)
    c5 = AssetFilterCriteria(library_names=('family',), person_ids=('p1', 'p2'), people_mode=PeopleMode.ANY)
    count5 = meta_store.count_eligible_assets(c5)
    cand5 = meta_store.fetch_candidate_assets(c5)
    assert count5 == 2
    assert set(cand5.keys()) == {'asset-1', 'asset-2'}

    # Query 6: Date bounds (year 2023)
    c6 = AssetFilterCriteria(library_names=('family',), min_date=date(2023, 1, 1), max_date=date(2023, 12, 31))
    count6 = meta_store.count_eligible_assets(c6)
    cand6 = meta_store.fetch_candidate_assets(c6)
    assert count6 == 1
    assert 'asset-1' in cand6

    # Query 7: Album filter 'a1' (by ID)
    c7 = AssetFilterCriteria(library_names=('family',), album_ids=('a1',))
    count7 = meta_store.count_eligible_assets(c7)
    cand7 = meta_store.fetch_candidate_assets(c7)
    assert count7 == 1
    assert 'asset-1' in cand7

    # Query 8: People filter by Name ('Alice', 'Bob')
    c8 = AssetFilterCriteria(library_names=('family',), person_ids=('Alice', 'Bob'), people_mode=PeopleMode.ALL)
    assert meta_store.count_eligible_assets(c8) == 1

    # Query 9: Album filter by Name ('Summer Trip')
    c9 = AssetFilterCriteria(library_names=('family',), album_ids=('Summer Trip',))
    assert meta_store.count_eligible_assets(c9) == 1

    # Query 8: get_asset_counts breakdown
    counts = meta_store.get_asset_counts(
        AssetFilterCriteria(library_names=('family',), location_mode=True, date_mode=True, include_shared=True)
    )
    assert counts['total_count'] == 3
    assert counts['gps_count'] == 3
    assert counts['date_count'] == 3
    assert counts['eligible_count'] == 3


def test_metadata_store_filter_options(meta_store: MetadataStore, tmp_path: Path) -> None:
    assets = [
        {
            'id': 'a-1',
            'is_shared': 0,
            'is_partner': 0,
            'file_type': 'IMAGE',
            'country': 'Japan',
            'city': 'Tokyo',
            'capture_datetime': '2023-05-10T12:00:00',
        },
        {
            'id': 'a-2',
            'is_shared': 0,
            'is_partner': 0,
            'file_type': 'IMAGE',
            'country': 'France',
            'city': 'Paris',
            'capture_datetime': '2022-08-15T14:30:00',
        },
    ]
    meta_store.upsert_people('family', [{'id': 'p1', 'name': 'Alice'}, {'id': 'p2', 'name': 'Bob'}])
    meta_store.upsert_assets_batch('family', assets, [('a-1', 'p1'), ('a-2', 'p2')], [])

    settings = AppSettings(
        immich_server_url='https://example.com/api',
        immich_libraries={'family': 'token'},
        app_title='Quiz',
        app_tagline='',
        date_lower_bound=None,
        date_upper_bound=None,
        app_host='127.0.0.1',
        app_port=8010,
        location_score_decay_km=500.0,
        date_score_decay_days=500.0,
        language='EN',
        data_path=tmp_path,
        auto_sync_on_startup=False,
        country_whitelist=frozenset({'japan'}),  # Whitelist only Japan
    )

    filters = meta_store.get_filter_options(['family'], settings)
    assert filters.countries == ['Japan']
    assert filters.cities == [CityOption(name='Tokyo', country='Japan')]
    assert len(filters.people) == 2
    assert filters.date_range.min_month == '2022-08'
    assert filters.date_range.max_month == '2023-05'


def test_metadata_store_filter_options_ownership_filtering(meta_store: MetadataStore, tmp_path: Path) -> None:
    meta_store.upsert_people(
        'family',
        [
            {'id': 'p-own', 'name': 'Alice'},
            {'id': 'p-shared', 'name': 'Bob'},
            {'id': 'p-partner', 'name': 'Charlie'},
            {'id': 'p-partner-shared', 'name': 'Diana'},
            {'id': 'p-video', 'name': 'Eve'},
        ],
    )
    assets = [
        {
            'id': 'asset-own',
            'is_shared': 0,
            'is_partner': 0,
            'file_type': 'IMAGE',
            'country': 'Japan',
            'city': 'Tokyo',
            'capture_datetime': '2022-05-10T12:00:00',
        },
        {
            'id': 'asset-shared',
            'is_shared': 1,
            'is_partner': 0,
            'file_type': 'IMAGE',
            'country': 'France',
            'city': 'Paris',
            'capture_datetime': '2023-06-15T12:00:00',
        },
        {
            'id': 'asset-partner',
            'is_shared': 0,
            'is_partner': 1,
            'file_type': 'IMAGE',
            'country': 'Italy',
            'city': 'Rome',
            'capture_datetime': '2024-07-20T12:00:00',
        },
        {
            'id': 'asset-partner-shared',
            'is_shared': 1,
            'is_partner': 1,
            'file_type': 'IMAGE',
            'country': 'Spain',
            'city': 'Madrid',
            'capture_datetime': '2025-08-25T12:00:00',
        },
        {
            'id': 'asset-video',
            'is_shared': 0,
            'is_partner': 0,
            'file_type': 'VIDEO',
            'country': 'Germany',
            'city': 'Berlin',
            'capture_datetime': '2020-01-01T12:00:00',
        },
    ]
    asset_people = [
        ('asset-own', 'p-own'),
        ('asset-shared', 'p-shared'),
        ('asset-partner', 'p-partner'),
        ('asset-partner-shared', 'p-partner-shared'),
        ('asset-video', 'p-video'),
    ]
    meta_store.upsert_assets_batch('family', assets, asset_people, [])

    settings = AppSettings(
        immich_server_url='https://example.com/api',
        immich_libraries={'family': 'token'},
        app_title='Quiz',
        app_tagline='',
        date_lower_bound=None,
        date_upper_bound=None,
        app_host='127.0.0.1',
        app_port=8010,
        location_score_decay_km=500.0,
        date_score_decay_days=500.0,
        language='EN',
        data_path=tmp_path,
        auto_sync_on_startup=False,
    )

    # Discovers all options from all assets in the library
    f_options = meta_store.get_filter_options(['family'], settings)
    assert f_options.countries == ['France', 'Italy', 'Japan', 'Spain']
    assert [c.name for c in f_options.cities] == ['Madrid', 'Paris', 'Rome', 'Tokyo']
    assert [p.name for p in f_options.people] == ['Alice', 'Bob', 'Charlie', 'Diana']
    assert f_options.date_range.min_month == '2022-05'
    assert f_options.date_range.max_month == '2025-08'


def test_metadata_store_date_bounds_clamping(meta_store: MetadataStore, tmp_path: Path) -> None:
    assets = [
        {
            'id': 'a-1',
            'is_shared': 0,
            'is_partner': 0,
            'file_type': 'IMAGE',
            'capture_datetime': '2015-06-10T12:00:00',
        },
        {
            'id': 'a-2',
            'is_shared': 0,
            'is_partner': 0,
            'file_type': 'IMAGE',
            'capture_datetime': '2023-08-20T12:00:00',
        },
    ]
    meta_store.upsert_assets_batch('family', assets, [], [])

    # Case 1: Lower bound in .env (1960-01) is older than actual photos (2015-06) -> min_month should be 2015-06
    settings_loose_lower = AppSettings(
        immich_server_url='https://example.com/api',
        immich_libraries={'family': 'token'},
        app_title='Quiz',
        app_tagline='',
        date_lower_bound=date(1960, 1, 1),
        date_upper_bound=date(2030, 1, 1),
        app_host='127.0.0.1',
        app_port=8010,
        location_score_decay_km=500.0,
        date_score_decay_days=500.0,
        language='EN',
        data_path=tmp_path,
        auto_sync_on_startup=False,
    )
    res1 = meta_store.get_filter_options(['family'], settings_loose_lower)
    assert res1.date_range.min_month == '2015-06'
    assert res1.date_range.max_month == '2023-08'

    # Case 2: Lower bound in .env (2020-01) is tighter than actual photos (2015-06) -> min_month should be 2020-01
    settings_tight_lower = AppSettings(
        immich_server_url='https://example.com/api',
        immich_libraries={'family': 'token'},
        app_title='Quiz',
        app_tagline='',
        date_lower_bound=date(2020, 1, 1),
        date_upper_bound=date(2022, 12, 31),
        app_host='127.0.0.1',
        app_port=8010,
        location_score_decay_km=500.0,
        date_score_decay_days=500.0,
        language='EN',
        data_path=tmp_path,
        auto_sync_on_startup=False,
    )
    res2 = meta_store.get_filter_options(['family'], settings_tight_lower)
    assert res2.date_range.min_month == '2020-01'
    assert res2.date_range.max_month == '2022-12'


def test_metadata_store_prune_and_invalidation(meta_store: MetadataStore) -> None:
    assets = [
        {'id': 'a-1', 'is_shared': 0, 'is_partner': 0, 'file_type': 'IMAGE'},
        {'id': 'a-2', 'is_shared': 0, 'is_partner': 0, 'file_type': 'IMAGE'},
        {'id': 'a-3', 'is_shared': 0, 'is_partner': 0, 'file_type': 'IMAGE'},
    ]
    meta_store.upsert_assets_batch('family', assets, [], [])
    assert meta_store.count_eligible_assets(AssetFilterCriteria(library_names=('family',))) == 3

    # Invalidate a single asset
    meta_store.mark_asset_invalid('a-2')
    assert meta_store.count_eligible_assets(AssetFilterCriteria(library_names=('family',))) == 2

    # Prune missing: only 'a-1' is active
    pruned = meta_store.prune_missing_assets('family', {'a-1'})
    assert pruned == 1
    assert meta_store.count_eligible_assets(AssetFilterCriteria(library_names=('family',))) == 1


@pytest.mark.asyncio
async def test_sync_engine_flow(tmp_path: Path) -> None:
    db_mgr = DatabaseManager(tmp_path / 'sync_test.db')
    meta_store = MetadataStore(db_mgr)

    class MockImmichClient:
        def __init__(self) -> None:
            self._user_id_by_key: dict[str, str] = {'token': 'user-me'}

        def _library_key(self, library_name: str) -> str:
            return 'token'

        async def _current_user_id(self, key: str) -> str:
            return 'user-me'

        async def _request_json(self, method: str, path: str, key: str, json: Any = None) -> Any:
            if path == '/people':
                return [{'id': 'p1', 'name': 'Charlie'}]
            if path == '/albums':
                return [{'id': 'alb-1', 'name': 'Trip 2024', 'isShared': False}]
            if path == '/albums/alb-1':
                return {'assets': [{'id': 'asset-sync-1'}]}
            if path == '/search/metadata':
                page = json.get('page', 1)
                if page == 1:
                    return {
                        'total': 1,
                        'assets': [
                            {
                                'id': 'asset-sync-1',
                                'type': 'IMAGE',
                                'ownerId': 'user-me',
                                'exifInfo': {
                                    'latitude': 40.7128,
                                    'longitude': -74.0060,
                                    'country': 'United States',
                                    'city': 'New York',
                                    'dateTimeOriginal': '2024-04-10T10:00:00Z',
                                },
                                'people': [{'id': 'p1'}],
                            }
                        ],
                    }
                return {'total': 1, 'assets': []}
            return {}

        async def get_asset_count(self, library_name: str) -> int | None:
            return 1

        def _extract_total_assets(self, raw: Any) -> int | None:
            return raw.get('total')

        def _extract_asset_items(self, raw: Any) -> list[dict[str, Any]]:
            return raw.get('assets', [])

    mock_client = MockImmichClient()
    sync_engine = SyncEngine(mock_client, meta_store)  # type: ignore

    await sync_engine.sync_library('family')

    status = sync_engine.get_sync_status('family')
    assert status['sync_status'] == 'idle'
    assert status['total_assets'] == 1
    assert status['synced_assets'] == 1

    assert meta_store.has_synced_assets(['family'])
    crit = AssetFilterCriteria(library_names=('family',))
    assert meta_store.count_eligible_assets(crit) == 1
    cand = meta_store.fetch_candidate_assets(crit)
    assert 'asset-sync-1' in cand
    assert cand['asset-sync-1'].country == 'United States'
    assert cand['asset-sync-1'].city == 'New York'


@pytest.mark.asyncio
async def test_sync_engine_warns_when_asset_count_fails(tmp_path: Path) -> None:
    db_mgr = DatabaseManager(tmp_path / 'sync_warn_test.db')
    meta_store = MetadataStore(db_mgr)

    class MockImmichClientNoCount:
        def __init__(self) -> None:
            self._user_id_by_key: dict[str, str] = {'token': 'user-me'}

        def _library_key(self, library_name: str) -> str:
            return 'token'

        async def _current_user_id(self, key: str) -> str:
            return 'user-me'

        async def _request_json(self, method: str, path: str, key: str, json: Any = None) -> Any:
            if path == '/people':
                return []
            if path == '/albums':
                return []
            if path == '/search/metadata':
                return {'assets': []}
            return {}

        async def get_asset_count(self, library_name: str) -> int | None:
            return None

        def _extract_total_assets(self, raw: Any) -> int | None:
            return None

        def _extract_asset_items(self, raw: Any) -> list[dict[str, Any]]:
            return []

    mock_client = MockImmichClientNoCount()
    sync_engine = SyncEngine(mock_client, meta_store)  # type: ignore

    await sync_engine.sync_library('family')
    status = sync_engine.get_sync_status('family')
    assert 'warnings' in status
    assert '/search/statistics' in status['warnings']['family']


def test_api_sync_and_filters_endpoints(tmp_path: Path) -> None:
    settings = AppSettings(
        immich_server_url='https://example.com/api',
        immich_libraries={'family': 'token'},
        app_title='Quiz',
        app_tagline='',
        date_lower_bound=None,
        date_upper_bound=None,
        app_host='127.0.0.1',
        app_port=8010,
        location_score_decay_km=500.0,
        date_score_decay_days=500.0,
        language='EN',
        data_path=tmp_path,
        auto_sync_on_startup=False,
    )

    app = create_app(settings=settings)
    client = TestClient(app)

    # Populate SQLite with test data
    meta_store: MetadataStore = app.state.metadata_store
    meta_store.upsert_assets_batch(
        'family',
        [
            {
                'id': 'api-asset-1',
                'is_shared': 0,
                'is_partner': 0,
                'file_type': 'IMAGE',
                'country': 'Italy',
                'city': 'Rome',
                'latitude': 41.9028,
                'longitude': 12.4964,
                'capture_datetime': '2023-09-20T11:00:00',
            }
        ],
        [],
        [],
    )

    # Test GET /api/filters
    res_filters = client.get('/api/filters?libraries=family')
    assert res_filters.status_code == 200
    data_filters = res_filters.json()
    assert data_filters['countries'] == ['Italy']
    assert any(c['name'] == 'Rome' and c['country'] == 'Italy' for c in data_filters['cities'])

    # Test GET /api/sync/status
    res_status = client.get('/api/sync/status')
    assert res_status.status_code == 200
    data_status = res_status.json()
    assert 'sync_status' in data_status

    # Test POST /api/sync and POST /api/sync?force_full=true
    res_post_sync = client.post('/api/sync')
    assert res_post_sync.status_code == 200
    res_post_sync_full = client.post('/api/sync?force_full=true')
    assert res_post_sync_full.status_code == 200

    # Test POST /api/game/preflight
    preflight_payload = {
        'players': ['Player 1'],
        'round_count': 5,
        'location_mode': True,
        'date_mode': True,
        'game_mode': 'pinpoint',
        'libraries': ['family'],
        'countries': ['Italy'],
    }
    res_preflight = client.post('/api/game/preflight', json=preflight_payload)
    assert res_preflight.status_code == 200
    data_preflight = res_preflight.json()
    assert data_preflight['eligible_count'] == 1
    assert data_preflight['total_count'] == 1
    assert data_preflight['gps_count'] == 1
    assert data_preflight['date_count'] == 1
    assert data_preflight['location_mode'] is True
    assert data_preflight['date_mode'] is True
    assert 'countries' in data_preflight['active_filters']

    # Test POST /api/game/setup
    setup_payload = {
        'players': ['Alice'],
        'round_count': 5,
        'round_length': '1m',
        'location_mode': True,
        'date_mode': True,
        'library_name': 'family',
        'album_ids': [],
        'game_mode': 'pinpoint',
    }
    res_setup = client.post('/api/game/setup', json=setup_payload)
    assert res_setup.status_code == 200
    data_setup = res_setup.json()
    match_id = data_setup['match_id']

    # Test POST /api/question
    res_q = client.post('/api/question', json={'match_id': match_id, 'played_asset_ids': []})
    assert res_q.status_code == 200
    data_q = res_q.json()
    assert data_q['asset_id'] == 'api-asset-1'

    # Test asset invalidation on /media failure
    client.get('/api/media/api-asset-1')
    # Since Immich mock client fails get_asset_bytes in this raw client test or returns 400,
    # verify that metadata_store invalidates the asset
    assert meta_store.count_eligible_assets(AssetFilterCriteria(library_names=('family',))) == 0


def test_null_and_none_sanitization_in_db(db_mgr: DatabaseManager, meta_store: MetadataStore, tmp_path: Path) -> None:
    # Test that assets with None or string 'None' for city/country are stored as SQL NULL
    meta_store.upsert_assets_batch(
        'family',
        [
            {
                'id': 'asset-none-1',
                'is_shared': 0,
                'is_partner': 0,
                'file_type': 'IMAGE',
                'country': None,
                'city': None,
            },
            {
                'id': 'asset-none-2',
                'is_shared': 0,
                'is_partner': 0,
                'file_type': 'IMAGE',
                'country': 'None',
                'city': 'none',
            },
        ],
        [],
        [],
    )

    rows = db_mgr.fetch_all("SELECT id, country, city FROM assets WHERE id IN ('asset-none-1', 'asset-none-2')")
    for r in rows:
        assert r['country'] is None
        assert r['city'] is None

    settings = AppSettings(
        immich_server_url='https://example.com/api',
        immich_libraries={'family': 'token'},
        app_title='Quiz',
        app_tagline='',
        date_lower_bound=None,
        date_upper_bound=None,
        app_host='127.0.0.1',
        app_port=8010,
        location_score_decay_km=500.0,
        date_score_decay_days=500.0,
        language='EN',
        data_path=tmp_path,
        auto_sync_on_startup=False,
    )

    filters = meta_store.get_filter_options(['family'], settings)
    assert 'None' not in filters.countries
    assert not any(c.name.lower() == 'none' for c in filters.cities)


def test_upsert_assets_batch_foreign_key_safety(db_mgr: DatabaseManager, meta_store: MetadataStore) -> None:
    # Insert one known person and one known album
    meta_store.upsert_people('family', [{'id': 'known-p1', 'name': 'Alice'}])
    meta_store.upsert_albums('family', [{'id': 'known-a1', 'name': 'Summer', 'isShared': 0}])

    # Upsert an asset that references both a known person/album and an unknown/unnamed person/album
    meta_store.upsert_assets_batch(
        'family',
        [
            {
                'id': 'asset-fk-1',
                'is_shared': 0,
                'is_partner': 0,
                'file_type': 'IMAGE',
                'country': 'Spain',
                'city': 'Madrid',
            }
        ],
        [
            ('asset-fk-1', 'known-p1'),
            ('asset-fk-1', 'unnamed-face-999'),  # Should not raise ForeignKey error
        ],
        [
            ('asset-fk-1', 'known-a1'),
            ('asset-fk-1', 'deleted-album-888'),  # Should not raise ForeignKey error
        ],
    )

    people_links = db_mgr.fetch_all("SELECT * FROM asset_people WHERE asset_id = 'asset-fk-1'")
    assert len(people_links) == 1
    assert people_links[0]['person_id'] == 'known-p1'

    album_links = db_mgr.fetch_all("SELECT * FROM asset_albums WHERE asset_id = 'asset-fk-1'")
    assert len(album_links) == 1
    assert album_links[0]['album_id'] == 'known-a1'


def test_times_played_tracking_and_sync_preservation(meta_store: MetadataStore, db_mgr: DatabaseManager) -> None:
    # 1. Insert assets
    meta_store.upsert_assets_batch(
        'family',
        [
            {'id': 'tp-1', 'is_shared': 0, 'is_partner': 0, 'file_type': 'IMAGE'},
            {'id': 'tp-2', 'is_shared': 0, 'is_partner': 0, 'file_type': 'IMAGE'},
        ],
        [],
        [],
    )

    # Verify initial defaults: times_played=0, last_played_at=None
    row1 = db_mgr.fetch_one("SELECT times_played, last_played_at FROM assets WHERE id = 'tp-1'")
    assert row1['times_played'] == 0
    assert row1['last_played_at'] is None

    # 2. Record asset play
    meta_store.record_asset_played('tp-1')
    row1_played = db_mgr.fetch_one("SELECT times_played, last_played_at FROM assets WHERE id = 'tp-1'")
    assert row1_played['times_played'] == 1
    assert row1_played['last_played_at'] is not None

    # Record batch plays
    meta_store.record_assets_played(['tp-1', 'tp-2'])
    row1_second = db_mgr.fetch_one("SELECT times_played FROM assets WHERE id = 'tp-1'")
    row2_first = db_mgr.fetch_one("SELECT times_played FROM assets WHERE id = 'tp-2'")
    assert row1_second['times_played'] == 2
    assert row2_first['times_played'] == 1

    # 3. Re-running sync (upsert_assets_batch) MUST preserve times_played and last_played_at
    meta_store.upsert_assets_batch(
        'family',
        [
            {'id': 'tp-1', 'is_shared': 0, 'is_partner': 0, 'file_type': 'IMAGE', 'city': 'New City'},
            {'id': 'tp-2', 'is_shared': 0, 'is_partner': 0, 'file_type': 'IMAGE', 'city': 'New City 2'},
        ],
        [],
        [],
    )

    row1_synced = db_mgr.fetch_one("SELECT times_played, last_played_at, city FROM assets WHERE id = 'tp-1'")
    assert row1_synced['times_played'] == 2
    assert row1_synced['last_played_at'] is not None
    assert row1_synced['city'] == 'New City'


def test_fetch_candidate_assets_prioritizes_least_played(meta_store: MetadataStore) -> None:
    # Insert 3 assets
    meta_store.upsert_assets_batch(
        'family',
        [
            {'id': 'fresh-1', 'is_shared': 0, 'is_partner': 0, 'file_type': 'IMAGE'},
            {'id': 'played-1', 'is_shared': 0, 'is_partner': 0, 'file_type': 'IMAGE'},
            {'id': 'played-2', 'is_shared': 0, 'is_partner': 0, 'file_type': 'IMAGE'},
        ],
        [],
        [],
    )

    # Mark played-1 and played-2 as played
    meta_store.record_assets_played(['played-1', 'played-1', 'played-2'])

    # Fetching candidates with limit 1 should prioritize fresh-1 (times_played = 0)
    candidates = meta_store.fetch_candidate_assets(AssetFilterCriteria(library_names=('family',)), limit=1)
    assert len(candidates) == 1
    assert 'fresh-1' in candidates


def test_whitelist_and_blacklist_enforcement_in_metadata_store(meta_store: MetadataStore) -> None:
    # Seed people
    meta_store.upsert_people(
        'family',
        [
            {'id': 'p-alice', 'name': 'Alice'},
            {'id': 'p-bob', 'name': 'Bob'},
            {'id': 'p-charlie', 'name': 'Charlie'},
        ],
    )

    # Seed tags
    meta_store.upsert_tags(
        'family',
        [
            {'id': 't-vacation', 'name': 'Vacation'},
            {'id': 't-private', 'name': 'Private'},
            {'id': 't-nature', 'name': 'Nature'},
        ],
    )

    # Seed assets with varying countries, cities, and people
    meta_store.upsert_assets_batch(
        'family',
        [
            # Asset 1: Brazil, Rio, Alice
            {
                'id': 'a1',
                'is_shared': 0,
                'is_partner': 0,
                'file_type': 'IMAGE',
                'country': 'Brazil',
                'city': 'Rio',
                'latitude': -22.9,
                'longitude': -43.1,
                'capture_datetime': '2023-01-01T10:00:00',
            },
            # Asset 2: Germany, Berlin, Charlie
            {
                'id': 'a2',
                'is_shared': 0,
                'is_partner': 0,
                'file_type': 'IMAGE',
                'country': 'Germany',
                'city': 'Berlin',
                'latitude': 52.5,
                'longitude': 13.4,
                'capture_datetime': '2023-02-01T10:00:00',
            },
            # Asset 3: Japan, Tokyo, Bob
            {
                'id': 'a3',
                'is_shared': 0,
                'is_partner': 0,
                'file_type': 'IMAGE',
                'country': 'Japan',
                'city': 'Tokyo',
                'latitude': 35.6,
                'longitude': 139.6,
                'capture_datetime': '2023-03-01T10:00:00',
            },
            # Asset 4: Japan, Kyoto, No tagged people (landscape)
            {
                'id': 'a4',
                'is_shared': 0,
                'is_partner': 0,
                'file_type': 'IMAGE',
                'country': 'Japan',
                'city': 'Kyoto',
                'latitude': 35.0,
                'longitude': 135.7,
                'capture_datetime': '2023-04-01T10:00:00',
            },
        ],
        [
            ('a1', 'p-alice'),
            ('a2', 'p-charlie'),
            ('a3', 'p-bob'),
        ],
        [],
        [
            ('a1', 't-vacation'),
            ('a2', 't-private'),
            ('a3', 't-nature'),
        ],
    )

    # 1. Unfiltered query with no blacklists/whitelists -> all 4 assets
    c_base = AssetFilterCriteria(library_names=('family',))
    assert meta_store.count_eligible_assets(c_base) == 4

    # 2. Country Blacklist: Germany excluded -> a1, a3, a4 (3 assets)
    c_country_bl = AssetFilterCriteria(library_names=('family',), country_blacklist=frozenset({'germany'}))
    assert meta_store.count_eligible_assets(c_country_bl) == 3
    assert 'a2' not in meta_store.fetch_candidate_assets(c_country_bl)

    # 3. City Blacklist: Berlin excluded -> a1, a3, a4 (3 assets)
    c_city_bl = AssetFilterCriteria(library_names=('family',), city_blacklist=frozenset({'berlin'}))
    assert meta_store.count_eligible_assets(c_city_bl) == 3
    assert 'a2' not in meta_store.fetch_candidate_assets(c_city_bl)

    # 4. People Blacklist by Name: "Charlie" excluded -> a1, a3, a4 (3 assets)
    c_people_bl_name = AssetFilterCriteria(library_names=('family',), people_blacklist=frozenset({'charlie'}))
    assert meta_store.count_eligible_assets(c_people_bl_name) == 3
    assert 'a2' not in meta_store.fetch_candidate_assets(c_people_bl_name)

    # 5. People Blacklist by ID: "p-charlie" excluded -> a1, a3, a4 (3 assets)
    c_people_bl_id = AssetFilterCriteria(library_names=('family',), people_blacklist=frozenset({'p-charlie'}))
    assert meta_store.count_eligible_assets(c_people_bl_id) == 3
    assert 'a2' not in meta_store.fetch_candidate_assets(c_people_bl_id)

    # 6. Country Whitelist: only Japan -> a3, a4 (2 assets)
    c_country_wl = AssetFilterCriteria(library_names=('family',), country_whitelist=frozenset({'japan'}))
    assert meta_store.count_eligible_assets(c_country_wl) == 2
    candidates_wl = meta_store.fetch_candidate_assets(c_country_wl)
    assert set(candidates_wl.keys()) == {'a3', 'a4'}

    # 7. City Whitelist: only Rio -> a1 (1 asset)
    c_city_wl = AssetFilterCriteria(library_names=('family',), city_whitelist=frozenset({'rio'}))
    assert meta_store.count_eligible_assets(c_city_wl) == 1
    assert 'a1' in meta_store.fetch_candidate_assets(c_city_wl)

    # 8. People Whitelist: Alice and Bob -> a1 (Alice), a3 (Bob), and a4 (landscape without people)
    # a2 (Charlie) is excluded because Charlie is not whitelisted.
    c_people_wl = AssetFilterCriteria(library_names=('family',), people_whitelist=frozenset({'alice', 'bob'}))
    assert meta_store.count_eligible_assets(c_people_wl) == 3
    candidates_people_wl = meta_store.fetch_candidate_assets(c_people_wl)
    assert set(candidates_people_wl.keys()) == {'a1', 'a3', 'a4'}

    # 9. Tag Blacklist by Name: "Private" excluded -> a1, a3, a4 (3 assets)
    c_tag_bl_name = AssetFilterCriteria(library_names=('family',), tag_blacklist=frozenset({'private'}))
    assert meta_store.count_eligible_assets(c_tag_bl_name) == 3
    assert 'a2' not in meta_store.fetch_candidate_assets(c_tag_bl_name)

    # 10. Tag Blacklist by ID: "t-private" excluded -> a1, a3, a4 (3 assets)
    c_tag_bl_id = AssetFilterCriteria(library_names=('family',), tag_blacklist=frozenset({'t-private'}))
    assert meta_store.count_eligible_assets(c_tag_bl_id) == 3
    assert 'a2' not in meta_store.fetch_candidate_assets(c_tag_bl_id)

    # 11. Tag Whitelist by Name: "vacation" and "nature" -> a1, a3 (2 assets, untagged a4 and private a2 excluded)
    c_tag_wl_name = AssetFilterCriteria(library_names=('family',), tag_whitelist=frozenset({'vacation', 'nature'}))
    assert meta_store.count_eligible_assets(c_tag_wl_name) == 2
    candidates_tag_wl = meta_store.fetch_candidate_assets(c_tag_wl_name)
    assert set(candidates_tag_wl.keys()) == {'a1', 'a3'}

    # 12. Tag Whitelist by ID: "t-vacation" -> a1 (1 asset)
    c_tag_wl_id = AssetFilterCriteria(library_names=('family',), tag_whitelist=frozenset({'t-vacation'}))
    assert meta_store.count_eligible_assets(c_tag_wl_id) == 1
    assert 'a1' in meta_store.fetch_candidate_assets(c_tag_wl_id)


def test_asset_filter_criteria_from_setup_factory() -> None:
    from src.config import AppSettings
    from src.models import GameSetupRequest

    settings = AppSettings(
        immich_server_url='http://immich.local',
        immich_libraries={'family': 'key'},
        app_title='Immich Quiz',
        app_tagline='Tagline',
        date_lower_bound=date(2020, 1, 1),
        date_upper_bound=date(2024, 12, 31),
        app_host='127.0.0.1',
        app_port=8010,
        location_score_decay_km=500.0,
        date_score_decay_days=500.0,
        language='EN',
        country_whitelist=frozenset({'brazil'}),
        country_blacklist=frozenset({'germany'}),
        city_whitelist=frozenset({'rio'}),
        city_blacklist=frozenset({'berlin'}),
        people_whitelist=frozenset({'alice'}),
        people_blacklist=frozenset({'bob'}),
        tag_whitelist=frozenset({'vacation'}),
        tag_blacklist=frozenset({'private'}),
    )

    setup = GameSetupRequest(
        libraries=['family'],
        players=['Player 1'],
        round_count=5,
        location_mode=True,
        date_mode=True,
        min_date=date(2015, 1, 1),  # earlier than settings lower bound (2020-01-01)
        max_date=date(2025, 1, 1),  # later than settings upper bound (2024-12-31)
    )

    criteria = AssetFilterCriteria.from_setup(setup, settings)
    assert criteria.library_names == ('family',)
    assert criteria.min_date == date(2020, 1, 1)  # clamped to settings lower bound
    assert criteria.max_date == date(2024, 12, 31)  # clamped to settings upper bound
    assert criteria.country_whitelist == frozenset({'brazil'})
    assert criteria.country_blacklist == frozenset({'germany'})
    assert criteria.city_whitelist == frozenset({'rio'})
    assert criteria.city_blacklist == frozenset({'berlin'})
    assert criteria.people_whitelist == frozenset({'alice'})
    assert criteria.people_blacklist == frozenset({'bob'})
    assert criteria.tag_whitelist == frozenset({'vacation'})
    assert criteria.tag_blacklist == frozenset({'private'})


def test_get_facet_counts(meta_store: MetadataStore) -> None:
    meta_store.upsert_people('lib', [{'id': 'p1', 'name': 'Alice'}, {'id': 'p2', 'name': 'Bob'}])
    meta_store.upsert_albums('lib', [{'id': 'alb1', 'name': 'Japan Trip'}, {'id': 'alb2', 'name': 'France Trip'}])
    assets = [
        {
            'id': 'a1',
            'is_shared': 0,
            'is_partner': 0,
            'file_type': 'IMAGE',
            'latitude': 35.68,
            'longitude': 139.76,
            'country': 'Japan',
            'city': 'Tokyo',
            'capture_datetime': '2023-05-10T12:00:00',
        },
        {
            'id': 'a2',
            'is_shared': 0,
            'is_partner': 0,
            'file_type': 'IMAGE',
            'latitude': 35.01,
            'longitude': 135.76,
            'country': 'Japan',
            'city': 'Kyoto',
            'capture_datetime': '2023-05-12T12:00:00',
        },
        {
            'id': 'a3',
            'is_shared': 0,
            'is_partner': 0,
            'file_type': 'IMAGE',
            'latitude': 48.85,
            'longitude': 2.35,
            'country': 'France',
            'city': 'Paris',
            'capture_datetime': '2022-08-15T14:30:00',
        },
    ]
    meta_store.upsert_assets_batch(
        'lib',
        assets,
        [('a1', 'p1'), ('a2', 'p1'), ('a3', 'p2')],  # Alice in Japan (a1, a2); Bob in France (a3)
        [('a1', 'alb1'), ('a2', 'alb1'), ('a3', 'alb2')],
    )

    # 1. Base criteria without user filters
    base_criteria = AssetFilterCriteria(library_names=('lib',), location_mode=True, date_mode=True)
    counts = meta_store.get_facet_counts(base_criteria)
    assert counts.countries == {'Japan': 2, 'France': 1}
    assert counts.cities == {'Tokyo': 1, 'Kyoto': 1, 'Paris': 1}
    assert counts.people['p1'] == 2
    assert counts.people['p2'] == 1
    assert counts.people['Alice'] == 2
    assert counts.people['Bob'] == 1
    assert counts.albums['alb1'] == 2
    assert counts.albums['alb2'] == 1
    assert counts.albums['Japan Trip'] == 2
    assert counts.albums['France Trip'] == 1

    # 2. Filtered by Person: Alice ('p1')
    alice_criteria = AssetFilterCriteria(
        library_names=('lib',),
        location_mode=True,
        date_mode=True,
        person_ids=('p1',),
    )
    alice_counts = meta_store.get_facet_counts(alice_criteria)
    # Countries: Japan has 2, France has 0 (so France not in dict or 0)
    assert alice_counts.countries == {'Japan': 2}
    # Cities: Tokyo has 1, Kyoto has 1, Paris has 0
    assert alice_counts.cities == {'Tokyo': 1, 'Kyoto': 1}
    # People (excluding person filter): all people show their base count with lib
    assert alice_counts.people['p1'] == 2
    assert alice_counts.people['p2'] == 1
    # Albums: alb1 (Japan) has 2, alb2 (France) has 0
    assert alice_counts.albums['alb1'] == 2
    assert alice_counts.albums['Japan Trip'] == 2


def test_tags_and_state_and_sync_metadata(meta_store: MetadataStore) -> None:
    # 1. Tags upsert & get
    meta_store.upsert_tags('lib', [{'id': 't1', 'name': 'Vacation'}, {'id': 't2', 'name': 'Food'}])
    tags = meta_store.get_tags(['lib'])
    assert len(tags) == 2
    assert tags[0] == {'id': 't2', 'name': 'Food'}
    assert tags[1] == {'id': 't1', 'name': 'Vacation'}

    # 2. Assets with state, immich_updated_at, and tags
    assets = [
        {
            'id': 'a10',
            'is_shared': 0,
            'is_partner': 0,
            'file_type': 'IMAGE',
            'latitude': 25.7617,
            'longitude': -80.1918,
            'country': 'United States',
            'state': 'Florida',
            'city': 'Miami',
            'capture_datetime': '2023-01-15T12:00:00',
            'immich_updated_at': '2023-01-16T10:00:00Z',
        },
    ]
    meta_store.upsert_assets_batch(
        'lib',
        assets,
        asset_people=[],
        asset_albums=[],
        asset_tags=[('a10', 't1'), ('a10', 't2')],
    )

    criteria = AssetFilterCriteria(library_names=('lib',), location_mode=True, date_mode=True)
    candidates = meta_store.fetch_candidate_assets(criteria)
    assert 'a10' in candidates
    ans = candidates['a10']
    assert ans.state == 'Florida'
    assert ans.city == 'Miami'
    assert ans.country == 'United States'

    # Check database rows directly for immich_updated_at and asset_tags
    row = meta_store._db.fetch_one('SELECT state, immich_updated_at FROM assets WHERE id = ?', ('a10',))
    assert row is not None
    assert row['state'] == 'Florida'
    assert row['immich_updated_at'] == '2023-01-16T10:00:00Z'

    tag_rows = meta_store._db.fetch_all('SELECT tag_id FROM asset_tags WHERE asset_id = ? ORDER BY tag_id', ('a10',))
    assert [r['tag_id'] for r in tag_rows] == ['t1', 't2']

    # 3. Sync state with all new delta-sync fields
    meta_store.set_sync_state(
        'lib',
        status=SyncStatus.idle,
        total_assets=1,
        synced_assets=1,
        last_sync_at='2023-01-16T12:00:00Z',
        last_full_sync_at='2023-01-16T12:00:00Z',
        last_immich_updated_at='2023-01-16T10:00:00Z',
        sync_mode=SyncMode.full,
        last_sync_duration_seconds=1.23,
    )
    sync_state = meta_store.get_sync_state('lib')
    assert sync_state['last_sync_at'] == '2023-01-16T12:00:00Z'
    assert sync_state['last_full_sync_at'] == '2023-01-16T12:00:00Z'
    assert sync_state['last_immich_updated_at'] == '2023-01-16T10:00:00Z'
    assert sync_state['sync_mode'] == SyncMode.full.value
    assert sync_state['last_sync_duration_seconds'] == 1.23


def test_upsert_assets_batch_clears_stale_junctions(meta_store: MetadataStore) -> None:
    meta_store.upsert_people('lib', [{'id': 'p1', 'name': 'Alice'}, {'id': 'p2', 'name': 'Bob'}])
    meta_store.upsert_albums('lib', [{'id': 'a1', 'name': 'Alb 1'}, {'id': 'a2', 'name': 'Alb 2'}])
    meta_store.upsert_tags('lib', [{'id': 't1', 'name': 'Tag 1'}, {'id': 't2', 'name': 'Tag 2'}])

    assets = [
        {
            'id': 'asset-mod-1',
            'is_shared': 0,
            'is_partner': 0,
            'file_type': 'IMAGE',
            'latitude': 10.0,
            'longitude': 20.0,
            'country': 'Spain',
            'city': 'Madrid',
            'capture_datetime': '2023-01-01T00:00:00',
        }
    ]

    # Initial upsert with p1, p2, a1, t1, t2
    meta_store.upsert_assets_batch(
        'lib',
        assets,
        asset_people=[('asset-mod-1', 'p1'), ('asset-mod-1', 'p2')],
        asset_albums=[('asset-mod-1', 'a1')],
        asset_tags=[('asset-mod-1', 't1'), ('asset-mod-1', 't2')],
    )

    def get_junctions():
        p = [
            r['person_id']
            for r in meta_store._db.fetch_all(
                'SELECT person_id FROM asset_people WHERE asset_id = ? ORDER BY person_id',
                ('asset-mod-1',),
            )
        ]
        t = [
            r['tag_id']
            for r in meta_store._db.fetch_all(
                'SELECT tag_id FROM asset_tags WHERE asset_id = ? ORDER BY tag_id',
                ('asset-mod-1',),
            )
        ]
        a = [
            r['album_id']
            for r in meta_store._db.fetch_all(
                'SELECT album_id FROM asset_albums WHERE asset_id = ? ORDER BY album_id',
                ('asset-mod-1',),
            )
        ]
        return p, t, a

    people, tags, albums = get_junctions()
    assert people == ['p1', 'p2']
    assert tags == ['t1', 't2']
    assert albums == ['a1']

    # Modified re-upsert: p2 only, a2 only, t1 only
    meta_store.upsert_assets_batch(
        'lib',
        assets,
        asset_people=[('asset-mod-1', 'p2')],
        asset_albums=[('asset-mod-1', 'a2')],
        asset_tags=[('asset-mod-1', 't1')],
    )

    people, tags, albums = get_junctions()
    assert people == ['p2']
    assert tags == ['t1']
    assert albums == ['a2']


@pytest.mark.asyncio
async def test_sync_engine_delta_vs_full_sync(tmp_path: Path) -> None:
    db_mgr = DatabaseManager(tmp_path / 'delta_sync_test.db')
    meta_store = MetadataStore(db_mgr)

    captured_payloads: list[dict[str, Any]] = []

    class MockDeltaImmichClient:
        def __init__(self) -> None:
            self._user_id_by_key = {'token': 'user-me'}

        def _library_key(self, library_name: str) -> str:
            return 'token'

        async def _current_user_id(self, key: str) -> str:
            return 'user-me'

        async def _request_json(self, method: str, path: str, key: str, json: Any = None) -> Any:
            if path == '/people':
                return []
            if path == '/albums':
                return []
            if path == '/tags':
                return []
            if path == '/search/metadata':
                captured_payloads.append(dict(json or {}))
                page = (json or {}).get('page', 1)
                if page == 1:
                    return {
                        'total': 1,
                        'assets': [
                            {
                                'id': 'delta-asset-1',
                                'type': 'IMAGE',
                                'ownerId': 'user-me',
                                'updatedAt': '2024-05-01T12:00:00Z',
                                'exifInfo': {
                                    'latitude': 41.3879,
                                    'longitude': 2.1699,
                                    'country': 'Spain',
                                    'city': 'Barcelona',
                                    'dateTimeOriginal': '2024-04-10T10:00:00Z',
                                },
                            }
                        ],
                    }
                return {'total': 1, 'assets': []}
            return {}

        async def get_asset_count(self, library_name: str) -> int | None:
            return 1

        def _extract_total_assets(self, raw: Any) -> int | None:
            return raw.get('total')

        def _extract_asset_items(self, raw: Any) -> list[dict[str, Any]]:
            return raw.get('assets', [])

    mock_client = MockDeltaImmichClient()
    sync_engine = SyncEngine(mock_client, meta_store)  # type: ignore

    # 1. First sync should run FULL sync (no previous updated_at recorded)
    await sync_engine.sync_library('family')
    status1 = sync_engine.get_sync_status('family')
    assert status1['sync_status'] == 'idle'
    assert status1['sync_mode'] == SyncMode.full.value
    assert status1['last_immich_updated_at'] == '2024-05-01T12:00:00Z'
    assert len(captured_payloads) == 2  # page 1 and page 2
    assert 'updatedAfter' not in captured_payloads[0]

    captured_payloads.clear()

    # 2. Second sync should run DELTA sync automatically (uses updatedAfter)
    await sync_engine.sync_library('family')
    status2 = sync_engine.get_sync_status('family')
    assert status2['sync_status'] == 'idle'
    assert status2['sync_mode'] == SyncMode.delta.value
    assert len(captured_payloads) == 2
    assert captured_payloads[0].get('updatedAfter') == '2024-05-01T12:00:00Z'

    captured_payloads.clear()

    # 3. Third sync with force_full=True should run FULL sync
    await sync_engine.sync_library('family', force_full=True)
    status3 = sync_engine.get_sync_status('family')
    assert status3['sync_status'] == 'idle'
    assert status3['sync_mode'] == SyncMode.full.value
    assert len(captured_payloads) == 2
    assert 'updatedAfter' not in captured_payloads[0]


@pytest.mark.asyncio
async def test_hundreds_of_albums_parallel_and_delta_skip(tmp_path: Path) -> None:
    db_mgr = DatabaseManager(tmp_path / 'albums_perf_test.db')
    meta_store = MetadataStore(db_mgr)

    album_detail_calls: list[str] = []

    class MockAlbumsClient:
        def __init__(self) -> None:
            self._user_id_by_key = {'token': 'user-me'}

        def _library_key(self, library_name: str) -> str:
            return 'token'

        async def _current_user_id(self, key: str) -> str:
            return 'user-me'

        async def _request_json(self, method: str, path: str, key: str, json: Any = None) -> Any:
            if path == '/people':
                return []
            if path == '/tags':
                return []
            if path == '/albums':
                # Return 50 albums
                return [
                    {
                        'id': f'alb-{i}',
                        'albumName': f'Album {i}',
                        'assetCount': 10,
                        'updatedAt': '2024-01-01T00:00:00Z',
                    }
                    for i in range(50)
                ]
            if path.startswith('/albums/'):
                album_detail_calls.append(path)
                alb_id = path.split('/')[-1]
                return {
                    'id': alb_id,
                    'assets': [{'id': f'asset-{alb_id}'}],
                }
            if path == '/search/metadata':
                page = (json or {}).get('page', 1)
                if page == 1:
                    return {
                        'total': 1,
                        'assets': [
                            {
                                'id': 'asset-alb-0',
                                'type': 'IMAGE',
                                'ownerId': 'user-me',
                                'updatedAt': '2024-05-01T12:00:00Z',
                            }
                        ],
                    }
                return {'total': 1, 'assets': []}
            return {}

        async def get_asset_count(self, library_name: str) -> int | None:
            return 1

        def _extract_total_assets(self, raw: Any) -> int | None:
            return raw.get('total')

        def _extract_asset_items(self, raw: Any) -> list[dict[str, Any]]:
            return raw.get('assets', [])

    mock_client = MockAlbumsClient()
    sync_engine = SyncEngine(mock_client, meta_store)  # type: ignore

    # 1. Full sync: all 50 albums are fetched in parallel
    await sync_engine.sync_library('family')
    assert len(album_detail_calls) == 50
    album_detail_calls.clear()

    # 2. Delta sync with no modified albums: 0 album detail calls made!
    await sync_engine.sync_library('family')
    assert len(album_detail_calls) == 0


def test_sync_stages_telemetry(meta_store: MetadataStore) -> None:
    # Test setting and getting sync state with sync_stage
    meta_store.set_sync_state(
        'vacation',
        status=SyncStatus.syncing,
        sync_mode=SyncMode.full,
        sync_stage=SyncStage.fetching_albums,
        total_assets=50,
        synced_assets=10,
    )
    state = meta_store.get_sync_state('vacation')
    assert state['sync_status'] == SyncStatus.syncing.value
    assert state['sync_mode'] == SyncMode.full.value
    assert state['sync_stage'] == SyncStage.fetching_albums.value
    assert state['total_assets'] == 50
    assert state['synced_assets'] == 10

    # Test transitioning to idle
    meta_store.set_sync_state(
        'vacation',
        status=SyncStatus.idle,
        sync_mode=SyncMode.full,
        sync_stage=SyncStage.idle,
        total_assets=100,
        synced_assets=100,
    )
    state_idle = meta_store.get_sync_state('vacation')
    assert state_idle['sync_status'] == SyncStatus.idle.value
    assert state_idle['sync_stage'] == SyncStage.idle.value


def test_is_sync_due_logic() -> None:
    now = datetime(2026, 8, 17, 12, 0, 0, tzinfo=timezone.utc)

    # Disabled interval returns False
    assert not SyncEngine.is_sync_due(None, 0, now=now)
    assert not SyncEngine.is_sync_due('2026-08-17T00:00:00Z', 0, now=now)

    # Never synced before returns True if interval > 0
    assert SyncEngine.is_sync_due(None, 6, now=now)

    # 5 hours ago with 6 hour interval -> False
    five_hours_ago = (now - timedelta(hours=5)).isoformat()
    assert not SyncEngine.is_sync_due(five_hours_ago, 6, now=now)

    # 6 hours ago with 6 hour interval -> True
    six_hours_ago = (now - timedelta(hours=6)).isoformat()
    assert SyncEngine.is_sync_due(six_hours_ago, 6, now=now)

    # 25 hours ago with 24 hour interval -> True
    day_ago = (now - timedelta(hours=25)).isoformat()
    assert SyncEngine.is_sync_due(day_ago, 24, now=now)


@pytest.mark.asyncio
async def test_check_and_trigger_scheduled_sync(meta_store: MetadataStore) -> None:
    class DummyImmichClient:
        def _library_key(self, name: str) -> str:
            return 'key'

        async def _current_user_id(self, key: str) -> str:
            return 'user-1'

        async def _request_json(self, method: str, path: str, key: str, json: Any = None) -> Any:
            return []

        async def get_asset_count(self, library_name: str) -> int | None:
            return 0

        def _extract_total_assets(self, raw: Any) -> int | None:
            return 0

        def _extract_asset_items(self, raw: Any) -> list[dict[str, Any]]:
            return []

    client = DummyImmichClient()
    sync_engine = SyncEngine(client, meta_store)  # type: ignore

    now = datetime(2026, 8, 17, 12, 0, 0, tzinfo=timezone.utc)

    # 1. When full sync is due (25h ago), triggers full sync
    meta_store.set_sync_state(
        'family',
        status=SyncStatus.idle,
        last_sync_at=(now - timedelta(hours=2)).isoformat(),
        last_full_sync_at=(now - timedelta(hours=25)).isoformat(),
    )
    task1 = sync_engine.check_and_trigger_scheduled_sync(
        'family',
        delta_interval_hours=6,
        full_interval_hours=24,
        now=now,
    )
    assert task1 is not None
    await task1

    # 2. When full sync is recent (10h ago) but delta sync is due (7h ago), triggers delta sync
    meta_store.set_sync_state(
        'family',
        status=SyncStatus.idle,
        last_sync_at=(now - timedelta(hours=7)).isoformat(),
        last_full_sync_at=(now - timedelta(hours=10)).isoformat(),
    )
    task2 = sync_engine.check_and_trigger_scheduled_sync(
        'family',
        delta_interval_hours=6,
        full_interval_hours=24,
        now=now,
    )
    assert task2 is not None
    await task2

    # 3. When both are recent (last sync 2h ago, full 10h ago), neither is triggered
    meta_store.set_sync_state(
        'family',
        status=SyncStatus.idle,
        last_sync_at=(now - timedelta(hours=2)).isoformat(),
        last_full_sync_at=(now - timedelta(hours=10)).isoformat(),
    )
    task3 = sync_engine.check_and_trigger_scheduled_sync(
        'family',
        delta_interval_hours=6,
        full_interval_hours=24,
        now=now,
    )
    assert task3 is None


def test_multi_library_isolated_sync(meta_store: MetadataStore) -> None:
    """Verify that syncing multiple libraries with overlapping assets, people, albums, and tags preserves all data."""
    # 1. Setup Library 1: Rafael (assets 1, 2, 3)
    meta_store.upsert_people('Rafael', [{'id': 'p1', 'name': 'Alice'}, {'id': 'p2', 'name': 'Bob'}])
    meta_store.upsert_albums('Rafael', [{'id': 'alb1', 'name': 'Trip 2022'}, {'id': 'alb2', 'name': 'Family Shared'}])
    meta_store.upsert_tags('Rafael', [{'id': 't1', 'name': 'Vacation'}, {'id': 't2', 'name': 'Favorites'}])

    assets_lib1 = [
        {
            'id': 'ast-1',
            'is_shared': 0,
            'is_partner': 0,
            'file_type': 'IMAGE',
            'latitude': 10.0,
            'longitude': 20.0,
            'country': 'Brazil',
            'city': 'Rio',
            'capture_datetime': '2022-01-01T12:00:00',
        },
        {
            'id': 'ast-2',
            'is_shared': 0,
            'is_partner': 0,
            'file_type': 'IMAGE',
            'latitude': 11.0,
            'longitude': 21.0,
            'country': 'Brazil',
            'city': 'Rio',
            'capture_datetime': '2022-02-01T12:00:00',
        },
        {
            'id': 'ast-3',
            'is_shared': 0,
            'is_partner': 0,
            'file_type': 'IMAGE',
            'latitude': 12.0,
            'longitude': 22.0,
            'country': 'France',
            'city': 'Paris',
            'capture_datetime': '2022-03-01T12:00:00',
        },
    ]
    meta_store.upsert_assets_batch(
        'Rafael',
        assets_lib1,
        asset_people=[('ast-1', 'p1'), ('ast-2', 'p2')],
        asset_albums=[('ast-1', 'alb1'), ('ast-2', 'alb2')],
        asset_tags=[('ast-1', 't1'), ('ast-2', 't2')],
    )

    assert meta_store.count_library_assets('Rafael') == 3
    assert meta_store.get_indexed_album_ids('Rafael') == {'alb1', 'alb2'}

    # 2. Setup Library 2: Savi-Japjec (assets 2, 3 overlapping with Rafael, plus 4)
    meta_store.upsert_people('Savi-Japjec', [{'id': 'p2', 'name': 'Bob'}, {'id': 'p3', 'name': 'Charlie'}])
    meta_store.upsert_albums(
        'Savi-Japjec', [{'id': 'alb2', 'name': 'Family Shared'}, {'id': 'alb3', 'name': 'Savi Wedding'}]
    )
    meta_store.upsert_tags('Savi-Japjec', [{'id': 't2', 'name': 'Favorites'}, {'id': 't3', 'name': 'Nature'}])

    assets_lib2 = [
        {
            'id': 'ast-2',
            'is_shared': 1,
            'is_partner': 0,
            'file_type': 'IMAGE',
            'latitude': 11.0,
            'longitude': 21.0,
            'country': 'Brazil',
            'city': 'Rio',
            'capture_datetime': '2022-02-01T12:00:00',
        },
        {
            'id': 'ast-3',
            'is_shared': 0,
            'is_partner': 0,
            'file_type': 'IMAGE',
            'latitude': 12.0,
            'longitude': 22.0,
            'country': 'France',
            'city': 'Paris',
            'capture_datetime': '2022-03-01T12:00:00',
        },
        {
            'id': 'ast-4',
            'is_shared': 0,
            'is_partner': 0,
            'file_type': 'IMAGE',
            'latitude': 13.0,
            'longitude': 23.0,
            'country': 'Japan',
            'city': 'Tokyo',
            'capture_datetime': '2022-04-01T12:00:00',
        },
    ]
    meta_store.upsert_assets_batch(
        'Savi-Japjec',
        assets_lib2,
        asset_people=[('ast-2', 'p2'), ('ast-3', 'p3')],
        asset_albums=[('ast-2', 'alb2'), ('ast-3', 'alb3')],
        asset_tags=[('ast-2', 't2'), ('ast-3', 't3')],
    )

    # 3. Verify BOTH libraries maintain their assets independently!
    assert meta_store.count_library_assets('Rafael') == 3
    assert meta_store.count_library_assets('Savi-Japjec') == 3
    assert meta_store.get_indexed_album_ids('Rafael') == {'alb1', 'alb2'}
    assert meta_store.get_indexed_album_ids('Savi-Japjec') == {'alb2', 'alb3'}

    # 4. Check get_albums query separation and union
    alb_rafael = meta_store.get_albums(['Rafael'])
    assert {a['id'] for a in alb_rafael} == {'alb1', 'alb2'}

    alb_savi = meta_store.get_albums(['Savi-Japjec'])
    assert {a['id'] for a in alb_savi} == {'alb2', 'alb3'}

    alb_both = meta_store.get_albums(['Rafael', 'Savi-Japjec'])
    assert {a['id'] for a in alb_both} == {'alb1', 'alb2', 'alb3'}

    # 5. Check get_tags query separation and union
    tags_rafael = meta_store.get_tags(['Rafael'])
    assert {t['id'] for t in tags_rafael} == {'t1', 't2'}

    tags_savi = meta_store.get_tags(['Savi-Japjec'])
    assert {t['id'] for t in tags_savi} == {'t2', 't3'}

    tags_both = meta_store.get_tags(['Rafael', 'Savi-Japjec'])
    assert {t['id'] for t in tags_both} == {'t1', 't2', 't3'}

    # 6. Test pruning on Rafael does not touch Savi-Japjec
    # Prune Rafael so only ast-1 and ast-2 remain
    deleted = meta_store.prune_missing_assets('Rafael', {'ast-1', 'ast-2'})
    assert deleted == 1
    assert meta_store.count_library_assets('Rafael') == 2
    assert meta_store.count_library_assets('Savi-Japjec') == 3  # Unchanged!


def test_multi_album_filtering_across_libraries(meta_store: MetadataStore) -> None:
    """Verify filtering and facet counts with multiple albums across multiple libraries."""
    meta_store.upsert_albums('lib1', [{'id': 'alb-a', 'name': 'Summer'}, {'id': 'alb-b', 'name': 'Winter'}])
    meta_store.upsert_albums('lib2', [{'id': 'alb-c', 'name': 'Spring'}, {'id': 'alb-d', 'name': 'Autumn'}])

    assets1 = [
        {
            'id': 'img-1',
            'is_shared': 0,
            'is_partner': 0,
            'file_type': 'IMAGE',
            'latitude': 10.0,
            'longitude': 10.0,
            'country': 'Italy',
            'city': 'Rome',
            'capture_datetime': '2023-01-01T12:00:00',
        },
        {
            'id': 'img-2',
            'is_shared': 0,
            'is_partner': 0,
            'file_type': 'IMAGE',
            'latitude': 20.0,
            'longitude': 20.0,
            'country': 'Spain',
            'city': 'Madrid',
            'capture_datetime': '2023-02-01T12:00:00',
        },
    ]
    assets2 = [
        {
            'id': 'img-3',
            'is_shared': 0,
            'is_partner': 0,
            'file_type': 'IMAGE',
            'latitude': 30.0,
            'longitude': 30.0,
            'country': 'Germany',
            'city': 'Berlin',
            'capture_datetime': '2023-03-01T12:00:00',
        },
        {
            'id': 'img-4',
            'is_shared': 0,
            'is_partner': 0,
            'file_type': 'IMAGE',
            'latitude': 40.0,
            'longitude': 40.0,
            'country': 'Japan',
            'city': 'Kyoto',
            'capture_datetime': '2023-04-01T12:00:00',
        },
    ]

    meta_store.upsert_assets_batch('lib1', assets1, [], [('img-1', 'alb-a'), ('img-2', 'alb-b')])
    meta_store.upsert_assets_batch('lib2', assets2, [], [('img-3', 'alb-c'), ('img-4', 'alb-d')])

    # Filter with multiple albums across both libraries
    criteria = AssetFilterCriteria(
        library_names=('lib1', 'lib2'),
        album_ids=('Summer', 'Spring'),
    )
    count = meta_store.count_eligible_assets(criteria)
    candidates = meta_store.fetch_candidate_assets(criteria)
    assert count == 2
    assert set(candidates.keys()) == {'img-1', 'img-3'}

    # Facet counts for albums
    facets = meta_store.get_facet_counts(criteria)
    assert facets.albums.get('alb-a') == 1
    assert facets.albums.get('alb-b') == 1
    assert facets.albums.get('alb-c') == 1
    assert facets.albums.get('alb-d') == 1


def test_optimized_ownership_and_safeguards_query(meta_store: MetadataStore) -> None:
    """Verify that get_asset_counts and get_facet_counts correctly exclude shared/partner assets."""
    meta_store.upsert_albums('lib1', [{'id': 'shared-alb', 'name': 'Shared Trip', 'isShared': 1}])
    meta_store.upsert_people(
        'lib1', [{'id': 'p-black', 'name': 'Blocked Person'}, {'id': 'p-ok', 'name': 'Good Person'}]
    )

    assets = [
        {
            'id': 'a-ok',
            'is_shared': 0,
            'is_partner': 0,
            'file_type': 'IMAGE',
            'latitude': 10.0,
            'longitude': 10.0,
            'country': 'Brazil',
            'city': 'Rio',
            'capture_datetime': '2023-01-01T12:00:00',
        },
        {
            'id': 'a-shared',
            'is_shared': 1,
            'is_partner': 0,
            'file_type': 'IMAGE',
            'latitude': 10.0,
            'longitude': 10.0,
            'country': 'Brazil',
            'city': 'Rio',
            'capture_datetime': '2023-01-01T12:00:00',
        },
        {
            'id': 'a-partner',
            'is_shared': 0,
            'is_partner': 1,
            'file_type': 'IMAGE',
            'latitude': 10.0,
            'longitude': 10.0,
            'country': 'Brazil',
            'city': 'Rio',
            'capture_datetime': '2023-01-01T12:00:00',
        },
        {
            'id': 'a-in-shared-alb',
            'is_shared': 0,
            'is_partner': 0,
            'file_type': 'IMAGE',
            'latitude': 10.0,
            'longitude': 10.0,
            'country': 'Brazil',
            'city': 'Rio',
            'capture_datetime': '2023-01-01T12:00:00',
        },
        {
            'id': 'a-blocked-person',
            'is_shared': 0,
            'is_partner': 0,
            'file_type': 'IMAGE',
            'latitude': 10.0,
            'longitude': 10.0,
            'country': 'Brazil',
            'city': 'Rio',
            'capture_datetime': '2023-01-01T12:00:00',
        },
    ]

    meta_store.upsert_assets_batch(
        'lib1',
        assets,
        [('a-ok', 'p-ok'), ('a-blocked-person', 'p-black')],
        [('a-in-shared-alb', 'shared-alb')],
    )

    criteria = AssetFilterCriteria(
        library_names=('lib1',),
        location_mode=True,
        date_mode=True,
        include_shared=False,
        people_blacklist=frozenset({'Blocked Person'}),
    )

    counts = meta_store.get_asset_counts(criteria)
    assert counts['eligible_count'] == 1
    assert counts['total_count'] == 1

    candidates = meta_store.fetch_candidate_assets(criteria)
    assert list(candidates.keys()) == ['a-ok']

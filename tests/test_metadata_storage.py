from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from src.config import AppSettings
from src.main import create_app
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
    assert not meta_store.has_synced_assets('family')
    state = meta_store.get_sync_state('family')
    assert state['sync_status'] == 'idle'
    assert state['total_assets'] == 0

    meta_store.set_sync_state(
        'family',
        status='syncing',
        total_assets=100,
        synced_assets=25,
    )
    state = meta_store.get_sync_state('family')
    assert state['sync_status'] == 'syncing'
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
    assert meta_store.has_synced_assets('family')

    # Test count & candidate fetching parity
    # Query 1: All private images
    c1 = AssetFilterCriteria(library_name='family')
    count1 = meta_store.count_eligible_assets(c1)
    cand1 = meta_store.fetch_candidate_assets(c1)
    # asset-1, asset-2 (asset-3 is shared, asset-4 is video)
    assert count1 == 2
    assert len(cand1) == 2
    assert set(cand1.keys()) == {'asset-1', 'asset-2'}

    # Query 2: Include shared albums
    c2 = AssetFilterCriteria(library_name='family', include_shared_albums=True)
    count2 = meta_store.count_eligible_assets(c2)
    cand2 = meta_store.fetch_candidate_assets(c2)
    assert count2 == 3
    assert set(cand2.keys()) == {'asset-1', 'asset-2', 'asset-3'}

    # Query 3: Country filter 'Japan'
    c3 = AssetFilterCriteria(library_name='family', countries=('Japan',))
    count3 = meta_store.count_eligible_assets(c3)
    cand3 = meta_store.fetch_candidate_assets(c3)
    assert count3 == 1
    assert 'asset-1' in cand3

    # Query 4: People filter with AND mode (both p1 and p2)
    c4 = AssetFilterCriteria(library_name='family', person_ids=('p1', 'p2'), people_mode='AND')
    count4 = meta_store.count_eligible_assets(c4)
    cand4 = meta_store.fetch_candidate_assets(c4)
    assert count4 == 1
    assert 'asset-1' in cand4

    # Query 5: People filter with OR mode (p1 or p2)
    c5 = AssetFilterCriteria(library_name='family', person_ids=('p1', 'p2'), people_mode='OR')
    count5 = meta_store.count_eligible_assets(c5)
    cand5 = meta_store.fetch_candidate_assets(c5)
    assert count5 == 2
    assert set(cand5.keys()) == {'asset-1', 'asset-2'}

    # Query 6: Date bounds (year 2023)
    c6 = AssetFilterCriteria(library_name='family', min_date=date(2023, 1, 1), max_date=date(2023, 12, 31))
    count6 = meta_store.count_eligible_assets(c6)
    cand6 = meta_store.fetch_candidate_assets(c6)
    assert count6 == 1
    assert 'asset-1' in cand6

    # Query 7: Album filter 'a1'
    c7 = AssetFilterCriteria(library_name='family', album_ids=('a1',))
    count7 = meta_store.count_eligible_assets(c7)
    cand7 = meta_store.fetch_candidate_assets(c7)
    assert count7 == 1
    assert 'asset-1' in cand7

    # Query 8: get_asset_counts breakdown
    counts = meta_store.get_asset_counts(
        AssetFilterCriteria(library_name='family', location_mode=True, date_mode=True, include_shared_albums=True)
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
        include_shared_albums=False,
        include_partner_assets=False,
        fetch_photos_date_lower_bound=None,
        fetch_photos_date_upper_bound=None,
        app_host='127.0.0.1',
        app_port=8010,
        score_max_points=100,
        location_score_decay_km=500.0,
        date_score_decay_days=500.0,
        language='EN',
        photo_diversity_min_distance_km=0.1,
        photo_diversity_min_time_seconds=60.0,
        data_path=tmp_path,
        auto_sync_on_startup=False,
        country_whitelist=frozenset({'japan'}),  # Whitelist only Japan
    )

    filters = meta_store.get_filter_options('family', settings)
    assert filters.countries == ['Japan']
    assert len(filters.cities) == 2
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

    def make_settings(*, include_shared_albums: bool, include_partner_assets: bool) -> AppSettings:
        return AppSettings(
            immich_server_url='https://example.com/api',
            immich_libraries={'family': 'token'},
            app_title='Quiz',
            app_tagline='',
            include_shared_albums=include_shared_albums,
            include_partner_assets=include_partner_assets,
            fetch_photos_date_lower_bound=None,
            fetch_photos_date_upper_bound=None,
            app_host='127.0.0.1',
            app_port=8010,
            score_max_points=100,
            location_score_decay_km=500.0,
            date_score_decay_days=500.0,
            language='EN',
            photo_diversity_min_distance_km=0.1,
            photo_diversity_min_time_seconds=60.0,
            data_path=tmp_path,
            auto_sync_on_startup=False,
        )

    # 1. Default: include_shared=False, include_partner=False (only personal photos)
    f_default = meta_store.get_filter_options(
        'family',
        make_settings(include_shared_albums=False, include_partner_assets=False),
    )
    assert f_default.countries == ['Japan']
    assert [c.name for c in f_default.cities] == ['Tokyo']
    assert [p.name for p in f_default.people] == ['Alice']
    assert f_default.date_range.min_month == '2022-05'
    assert f_default.date_range.max_month == '2022-05'

    # 2. Shared enabled: include_shared=True, include_partner=False
    f_shared = meta_store.get_filter_options(
        'family',
        make_settings(include_shared_albums=True, include_partner_assets=False),
    )
    assert f_shared.countries == ['France', 'Japan']
    assert [c.name for c in f_shared.cities] == ['Paris', 'Tokyo']
    assert [p.name for p in f_shared.people] == ['Alice', 'Bob']
    assert f_shared.date_range.min_month == '2022-05'
    assert f_shared.date_range.max_month == '2023-06'

    # 3. Partner enabled: include_shared=False, include_partner=True
    # Partner photos included unless they belong to a shared album
    f_partner = meta_store.get_filter_options(
        'family',
        make_settings(include_shared_albums=False, include_partner_assets=True),
    )
    assert f_partner.countries == ['Italy', 'Japan']
    assert [c.name for c in f_partner.cities] == ['Rome', 'Tokyo']
    assert [p.name for p in f_partner.people] == ['Alice', 'Charlie']
    assert f_partner.date_range.min_month == '2022-05'
    assert f_partner.date_range.max_month == '2024-07'

    # 4. Both enabled: include_shared=True, include_partner=True
    f_both = meta_store.get_filter_options(
        'family',
        make_settings(include_shared_albums=True, include_partner_assets=True),
    )
    assert f_both.countries == ['France', 'Italy', 'Japan', 'Spain']
    assert [c.name for c in f_both.cities] == ['Madrid', 'Paris', 'Rome', 'Tokyo']
    assert [p.name for p in f_both.people] == ['Alice', 'Bob', 'Charlie', 'Diana']
    assert f_both.date_range.min_month == '2022-05'
    assert f_both.date_range.max_month == '2025-08'


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
        include_shared_albums=False,
        include_partner_assets=False,
        fetch_photos_date_lower_bound=date(1960, 1, 1),
        fetch_photos_date_upper_bound=date(2030, 1, 1),
        app_host='127.0.0.1',
        app_port=8010,
        score_max_points=100,
        location_score_decay_km=500.0,
        date_score_decay_days=500.0,
        language='EN',
        photo_diversity_min_distance_km=0.1,
        photo_diversity_min_time_seconds=60.0,
        data_path=tmp_path,
        auto_sync_on_startup=False,
    )
    res1 = meta_store.get_filter_options('family', settings_loose_lower)
    assert res1.date_range.min_month == '2015-06'
    assert res1.date_range.max_month == '2023-08'

    # Case 2: Lower bound in .env (2020-01) is tighter than actual photos (2015-06) -> min_month should be 2020-01
    settings_tight_lower = AppSettings(
        immich_server_url='https://example.com/api',
        immich_libraries={'family': 'token'},
        app_title='Quiz',
        app_tagline='',
        include_shared_albums=False,
        include_partner_assets=False,
        fetch_photos_date_lower_bound=date(2020, 1, 1),
        fetch_photos_date_upper_bound=date(2022, 12, 31),
        app_host='127.0.0.1',
        app_port=8010,
        score_max_points=100,
        location_score_decay_km=500.0,
        date_score_decay_days=500.0,
        language='EN',
        photo_diversity_min_distance_km=0.1,
        photo_diversity_min_time_seconds=60.0,
        data_path=tmp_path,
        auto_sync_on_startup=False,
    )
    res2 = meta_store.get_filter_options('family', settings_tight_lower)
    assert res2.date_range.min_month == '2020-01'
    assert res2.date_range.max_month == '2022-12'


def test_metadata_store_prune_and_invalidation(meta_store: MetadataStore) -> None:
    assets = [
        {'id': 'a-1', 'is_shared': 0, 'is_partner': 0, 'file_type': 'IMAGE'},
        {'id': 'a-2', 'is_shared': 0, 'is_partner': 0, 'file_type': 'IMAGE'},
        {'id': 'a-3', 'is_shared': 0, 'is_partner': 0, 'file_type': 'IMAGE'},
    ]
    meta_store.upsert_assets_batch('family', assets, [], [])
    assert meta_store.count_eligible_assets(AssetFilterCriteria(library_name='family')) == 3

    # Invalidate a single asset
    meta_store.mark_asset_invalid('a-2')
    assert meta_store.count_eligible_assets(AssetFilterCriteria(library_name='family')) == 2

    # Prune missing: only 'a-1' is active
    pruned = meta_store.prune_missing_assets('family', {'a-1'})
    assert pruned == 1
    assert meta_store.count_eligible_assets(AssetFilterCriteria(library_name='family')) == 1


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

    assert meta_store.has_synced_assets('family')
    crit = AssetFilterCriteria(library_name='family')
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
    assert 'warning' in status
    assert '/search/statistics' in status['warning']


def test_api_sync_and_filters_endpoints(tmp_path: Path) -> None:
    settings = AppSettings(
        immich_server_url='https://example.com/api',
        immich_libraries={'family': 'token'},
        app_title='Quiz',
        app_tagline='',
        include_shared_albums=False,
        include_partner_assets=False,
        fetch_photos_date_lower_bound=None,
        fetch_photos_date_upper_bound=None,
        app_host='127.0.0.1',
        app_port=8010,
        score_max_points=100,
        location_score_decay_km=500.0,
        date_score_decay_days=500.0,
        language='EN',
        photo_diversity_min_distance_km=0.1,
        photo_diversity_min_time_seconds=60.0,
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
    res_filters = client.get('/api/filters?library_name=family')
    assert res_filters.status_code == 200
    data_filters = res_filters.json()
    assert data_filters['countries'] == ['Italy']
    assert any(c['name'] == 'Rome' and c['country'] == 'Italy' for c in data_filters['cities'])

    # Test GET /api/sync/status
    res_status = client.get('/api/sync/status?library_name=family')
    assert res_status.status_code == 200
    data_status = res_status.json()
    assert 'sync_status' in data_status

    # Test POST /api/game/preflight
    preflight_payload = {
        'players': ['Player 1'],
        'round_count': 5,
        'location_mode': True,
        'date_mode': True,
        'game_mode': 'pinpoint',
        'library_name': 'family',
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
        'smart_map_zoom': True,
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
    client.get('/api/media/api-asset-1?library_name=family')
    # Since Immich mock client fails get_asset_bytes in this raw client test or returns 400,
    # verify that metadata_store invalidates the asset
    assert meta_store.count_eligible_assets(AssetFilterCriteria(library_name='family')) == 0


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
        include_shared_albums=False,
        include_partner_assets=False,
        fetch_photos_date_lower_bound=None,
        fetch_photos_date_upper_bound=None,
        app_host='127.0.0.1',
        app_port=8010,
        score_max_points=100,
        location_score_decay_km=500.0,
        date_score_decay_days=500.0,
        language='EN',
        photo_diversity_min_distance_km=0.1,
        photo_diversity_min_time_seconds=60.0,
        data_path=tmp_path,
        auto_sync_on_startup=False,
    )

    filters = meta_store.get_filter_options('family', settings)
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

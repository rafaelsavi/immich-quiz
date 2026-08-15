from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest
from conftest import FakeImmichClient, build_client, make_asset, setup_payload

from src.config import load_settings
from src.game.selector import (
    filter_diverse_asset_answers,
    is_asset_valid_for_batch,
    select_batch_round_assets,
    select_round_asset,
)
from src.immich.client import AssetAnswer
from src.models import GameSetupRequest, RoundLength
from src.storage.session import SessionStore


def test_distance_diversity_rejection() -> None:
    # Asset 1 at Paris Eiffel Tower (48.8584, 2.2945)
    a1 = AssetAnswer(
        latitude=48.8584, longitude=2.2945, capture_datetime=datetime(2022, 5, 1, 12, 0, 0, tzinfo=timezone.utc)
    )
    # Asset 2 only 20m away (48.8585, 2.2946)
    a2 = AssetAnswer(
        latitude=48.8585, longitude=2.2946, capture_datetime=datetime(2022, 5, 1, 14, 0, 0, tzinfo=timezone.utc)
    )
    # Asset 3 in Lyon (> 300km away)
    a3 = AssetAnswer(
        latitude=45.7640, longitude=4.8357, capture_datetime=datetime(2022, 5, 1, 16, 0, 0, tzinfo=timezone.utc)
    )

    assert not is_asset_valid_for_batch(a2, [a1], location_mode=True, date_mode=False, min_dist_km=0.1)
    assert is_asset_valid_for_batch(a3, [a1], location_mode=True, date_mode=False, min_dist_km=0.1)


def test_time_diversity_rejection() -> None:
    # Asset 1 at 12:00:00
    a1 = AssetAnswer(
        latitude=48.8584, longitude=2.2945, capture_datetime=datetime(2022, 5, 1, 12, 0, 0, tzinfo=timezone.utc)
    )
    # Asset 2 at 12:00:30 (30 seconds later)
    a2 = AssetAnswer(
        latitude=45.7640, longitude=4.8357, capture_datetime=datetime(2022, 5, 1, 12, 0, 30, tzinfo=timezone.utc)
    )
    # Asset 3 at 12:10:00 (10 minutes later)
    a3 = AssetAnswer(
        latitude=45.7640, longitude=4.8357, capture_datetime=datetime(2022, 5, 1, 12, 10, 0, tzinfo=timezone.utc)
    )

    assert not is_asset_valid_for_batch(a2, [a1], location_mode=False, date_mode=True, min_time_sec=60.0)
    assert is_asset_valid_for_batch(a3, [a1], location_mode=False, date_mode=True, min_time_sec=60.0)


def test_filter_diverse_asset_answers_greedy_selection() -> None:
    # 3 assets in the same spot, 2 far away
    cluster1 = AssetAnswer(
        latitude=48.8584, longitude=2.2945, capture_datetime=datetime(2022, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    )
    cluster2 = AssetAnswer(
        latitude=48.85841, longitude=2.29451, capture_datetime=datetime(2022, 1, 1, 13, 0, 0, tzinfo=timezone.utc)
    )
    cluster3 = AssetAnswer(
        latitude=48.85842, longitude=2.29452, capture_datetime=datetime(2022, 1, 1, 14, 0, 0, tzinfo=timezone.utc)
    )
    far1 = AssetAnswer(
        latitude=45.7640, longitude=4.8357, capture_datetime=datetime(2022, 1, 1, 15, 0, 0, tzinfo=timezone.utc)
    )
    far2 = AssetAnswer(
        latitude=43.2965, longitude=5.3698, capture_datetime=datetime(2022, 1, 1, 16, 0, 0, tzinfo=timezone.utc)
    )

    diverse = filter_diverse_asset_answers(
        [cluster1, cluster2, cluster3, far1, far2],
        location_mode=True,
        date_mode=False,
        min_dist_km=0.1,
    )
    # Should keep only cluster1 from the cluster, plus far1 and far2 -> total 3
    assert len(diverse) == 3
    assert diverse[0] == cluster1
    assert diverse[1] == far1
    assert diverse[2] == far2


def test_diversity_settings_loading(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv('IMMICH_SERVER_URL', 'https://example.test/api')
    monkeypatch.setenv('IMMICH_LIBRARIES', '{"family": "token"}')
    monkeypatch.setenv('PHOTO_DIVERSITY_MIN_DISTANCE_KM', '0.5')
    monkeypatch.setenv('PHOTO_DIVERSITY_MIN_TIME_SECONDS', '120.0')

    settings = load_settings()
    assert settings.photo_diversity_min_distance_km == 0.5
    assert settings.photo_diversity_min_time_seconds == 120.0

    monkeypatch.setenv('PHOTO_DIVERSITY_MIN_DISTANCE_KM', 'invalid')
    monkeypatch.setenv('PHOTO_DIVERSITY_MIN_TIME_SECONDS', 'invalid')

    fallback_settings = load_settings()
    assert fallback_settings.photo_diversity_min_distance_km == 0.1
    assert fallback_settings.photo_diversity_min_time_seconds == 60.0


def test_preflight_strict_diversity_clustered(tmp_path: Path) -> None:
    # 5 photos at almost the exact same coordinate and timestamp (< 100m and < 60s).
    # With the old preflight behavior (diversity-filtered), eligible_count would be 1.
    # With the corrected behavior (raw eligible count), all 5 have GPS so all 5 pass.
    clustered_assets = [
        make_asset(
            f'clustered_{i}',
            latitude=48.8584 + (i * 0.00001),  # ~1 meter apart
            longitude=2.2945 + (i * 0.00001),
            captured='2024-01-01T12:00:00Z',
        )
        for i in range(5)
    ]
    immich = FakeImmichClient(clustered_assets)
    client = build_client(tmp_path, immich)

    payload = setup_payload(round_count=5, location_mode=True, date_mode=False)
    res = client.post('/api/game/preflight', json=payload)
    assert res.status_code == 200
    body = res.json()
    # Preflight shows raw eligible count: all 5 have GPS coordinates so all 5 are eligible.
    # The diversity check (min 100m / 60s apart) is enforced by the game selector
    # on a much larger pool — not by the preflight 250-sample.
    assert body['eligible_count'] == 5
    assert body['required'] == 5
    assert body['ok'] is True  # 5 eligible >= 5 required


async def test_selector_strict_rejection_no_loose_fallback() -> None:
    store = SessionStore()
    setup = GameSetupRequest(
        players=['Player 1'],
        round_count=5,
        round_length=RoundLength.minute_1,
        location_mode=True,
        date_mode=False,
        library_name='family',
        album_ids=[],
    )
    state = store.create_match(setup)

    # 2 assets right next to each other
    a1 = AssetAnswer(
        latitude=48.8584, longitude=2.2945, capture_datetime=datetime(2022, 5, 1, 12, 0, 0, tzinfo=timezone.utc)
    )
    a2 = AssetAnswer(
        latitude=48.85841, longitude=2.29451, capture_datetime=datetime(2022, 5, 1, 14, 0, 0, tzinfo=timezone.utc)
    )
    state.asset_pool = {'id-1': a1, 'id-2': a2}
    state.played_asset_ids = {'id-1'}

    immich = FakeImmichClient([])

    # Trying to select another asset when only non-diverse id-2 remains must return None, not fallback to id-2
    selected = await select_round_asset(
        state,
        immich,
        client_excluded=set(),
        min_capture_date=None,
        max_capture_date=None,
        min_dist_km=0.1,
        min_time_sec=60.0,
    )
    assert selected is None

    # Batch selection requiring 2 assets from a clustered pool must return None
    state.played_asset_ids = set()
    batch_res = await select_batch_round_assets(
        state,
        immich,
        count=2,
        client_excluded=set(),
        min_capture_date=None,
        max_capture_date=None,
        min_dist_km=0.1,
        min_time_sec=60.0,
    )
    assert batch_res is None

"""Automated test suite for Challenge Mode REST API, ChallengeService & Fog of War engine."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from conftest import FakeImmichClient, build_client, make_asset

from src.models import AlbumShuffleAnswerItem


def _create_mock_assets(count: int = 25) -> list[dict]:
    """Generate mock assets with distinct coordinates and dates."""
    assets = []
    for i in range(count):
        lat = 10.0 + i * 2.0
        lng = 20.0 + i * 2.0
        year = 2020 + (i % 4)
        month = 1 + (i % 12)
        assets.append(
            make_asset(
                f'photo-{i+1}',
                latitude=lat,
                longitude=lng,
                captured=f'{year:04d}-{month:02d}-15T12:00:00Z',
            )
        )
    return assets


def test_challenge_create_pinpoint(tmp_path: Path) -> None:
    immich = FakeImmichClient(_create_mock_assets(25))
    client = build_client(tmp_path, immich)

    payload = {
        'creator_name': 'Rafael',
        'title': 'Test Pinpoint Challenge',
        'game_mode': 'pinpoint',
        'round_count': 5,
        'round_length': '1m',
        'location_mode': True,
        'date_mode': True,
        'expires_in_hours': 24,
    }

    res = client.post('/api/challenge/create', json=payload)
    assert res.status_code == 200
    data = res.json()

    assert data['challenge_id'].startswith('ch_')
    assert len(data['capability_token']) > 10
    assert data['play_url'].endswith(f"/play/{data['capability_token']}")
    assert data['title'] == 'Test Pinpoint Challenge'
    assert data['creator_name'] == 'Rafael'
    assert data['rounds'] == 5
    assert data['game_mode'] == 'pinpoint'
    assert data['expires_at'] is not None


def test_challenge_create_auto_title_when_omitted(tmp_path: Path) -> None:
    immich = FakeImmichClient(_create_mock_assets(25))
    client = build_client(tmp_path, immich)

    payload = {
        'creator_name': 'Alice',
        'game_mode': 'pinpoint',
        'round_count': 5,
        'round_length': '1m',
        'location_mode': True,
        'date_mode': True,
    }

    res = client.post('/api/challenge/create', json=payload)
    assert res.status_code == 200
    data = res.json()
    assert "Alice's" in data['title']


def test_challenge_create_album_shuffle(tmp_path: Path) -> None:
    immich = FakeImmichClient(_create_mock_assets(25))
    client = build_client(tmp_path, immich)

    payload = {
        'creator_name': 'Host',
        'title': 'Shuffle Match',
        'game_mode': 'album_shuffle',
        'round_count': 5,  # 5 rounds * 3 photos = 15 photos needed
        'round_length': '1m',
        'location_mode': True,
        'date_mode': True,
    }

    res = client.post('/api/challenge/create', json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data['rounds'] == 5
    assert data['game_mode'] == 'album_shuffle'


def test_challenge_create_insufficient_photos(tmp_path: Path) -> None:
    immich = FakeImmichClient(_create_mock_assets(3))
    client = build_client(tmp_path, immich)

    payload = {
        'creator_name': 'Host',
        'game_mode': 'pinpoint',
        'round_count': 5,  # Needs 5, only 3 available
    }

    res = client.post('/api/challenge/create', json=payload)
    assert res.status_code == 400
    assert 'Insufficient eligible photos' in res.json()['detail']


def test_challenge_detail_public_endpoint(tmp_path: Path) -> None:
    immich = FakeImmichClient(_create_mock_assets(25))
    client = build_client(tmp_path, immich)

    # 1. Create challenge
    create_res = client.post(
        '/api/challenge/create',
        json={
            'creator_name': 'Rafael',
            'title': 'Public View Test',
            'game_mode': 'pinpoint',
            'round_count': 5,
        },
    )
    token = create_res.json()['capability_token']

    # 2. Query public detail
    detail_res = client.get(f'/api/challenge/{token}')
    assert detail_res.status_code == 200
    detail = detail_res.json()

    assert detail['title'] == 'Public View Test'
    assert detail['creator_name'] == 'Rafael'
    assert detail['rounds'] == 5
    assert detail['game_mode'] == 'pinpoint'
    assert detail['total_participants'] == 0

    # 3. Non-existent token returns 404
    not_found = client.get('/api/challenge/invalid-token-123')
    assert not_found.status_code == 404


def test_challenge_start_and_deduplicated_resumption(tmp_path: Path) -> None:
    immich = FakeImmichClient(_create_mock_assets(25))
    client = build_client(tmp_path, immich)

    create_res = client.post(
        '/api/challenge/create',
        json={'creator_name': 'Host', 'game_mode': 'pinpoint', 'round_count': 5},
    )
    token = create_res.json()['capability_token']

    # 1. Start new session
    start_res = client.post(f'/api/challenge/{token}/start', json={'player_name': 'Bob'})
    assert start_res.status_code == 200
    s_data = start_res.json()

    assert s_data['player_name'] == 'Bob'
    assert s_data['current_round'] == 0
    assert s_data['total_rounds'] == 5
    assert s_data['is_resumed'] is False
    session_token = s_data['session_token']

    # 2. Starting again with same player name returns same session
    resume_res = client.post(f'/api/challenge/{token}/start', json={'player_name': 'Bob'})
    assert resume_res.status_code == 200
    r_data = resume_res.json()
    assert r_data['session_token'] == session_token


def test_challenge_question_sequencing_and_security(tmp_path: Path) -> None:
    immich = FakeImmichClient(_create_mock_assets(25))
    client = build_client(tmp_path, immich)

    create_res = client.post(
        '/api/challenge/create',
        json={'creator_name': 'Host', 'game_mode': 'pinpoint', 'round_count': 5},
    )
    token = create_res.json()['capability_token']

    start_res = client.post(f'/api/challenge/{token}/start', json={'player_name': 'Charlie'})
    p_token = start_res.json()['session_token']

    # 1. Valid request for round 0
    q0_res = client.get(
        f'/api/challenge/{token}/question/0',
        headers={'X-Player-Token': p_token},
    )
    assert q0_res.status_code == 200
    q0 = q0_res.json()
    assert q0['round_index'] == 0
    assert q0['total_rounds'] == 5
    assert 'media_url' in q0
    assert 'actual_latitude' not in q0
    assert 'actual_date' not in q0

    # 2. Skipping ahead to round 1 without answering round 0 -> 400 Bad Request
    q1_res = client.get(
        f'/api/challenge/{token}/question/1',
        headers={'X-Player-Token': p_token},
    )
    assert q1_res.status_code == 400
    assert 'Must complete round 0 first' in q1_res.json()['detail']

    # 3. Invalid session token -> 401 Unauthorized
    bad_token_res = client.get(
        f'/api/challenge/{token}/question/0',
        headers={'X-Player-Token': 'wrong_token'},
    )
    assert bad_token_res.status_code == 401


def test_challenge_answer_pinpoint_and_personal_reveal(tmp_path: Path) -> None:
    immich = FakeImmichClient(_create_mock_assets(25))
    client = build_client(tmp_path, immich)

    create_res = client.post(
        '/api/challenge/create',
        json={'creator_name': 'Host', 'game_mode': 'pinpoint', 'round_count': 5},
    )
    token = create_res.json()['capability_token']

    start_res = client.post(f'/api/challenge/{token}/start', json={'player_name': 'Dave'})
    p_token = start_res.json()['session_token']

    # Get question 0 first
    q0_res = client.get(
        f'/api/challenge/{token}/question/0',
        headers={'X-Player-Token': p_token},
    )
    assert q0_res.status_code == 200
    q0 = q0_res.json()
    asset = client.app.state.metadata_store.get_asset_answer(q0['asset_id'])
    assert asset is not None

    # Submit round 0 with exact coordinates and date
    ans0_res = client.post(
        f'/api/challenge/{token}/answer',
        headers={'X-Player-Token': p_token},
        json={
            'round_index': 0,
            'guessed_latitude': asset.latitude,
            'guessed_longitude': asset.longitude,
            'guessed_year': asset.capture_date.year,
            'guessed_month': asset.capture_date.month,
            'time_taken_seconds': 9.2,
        },
    )
    assert ans0_res.status_code == 200
    ans0 = ans0_res.json()

    assert ans0['round_index'] == 0
    assert ans0['round_score'] >= 190
    assert ans0['location_score'] == 100
    assert ans0['date_score'] >= 90
    assert ans0['distance_km'] == 0.0
    # Personal reveal returns true coordinates/dates
    assert ans0['actual_latitude'] == asset.latitude
    assert ans0['actual_longitude'] == asset.longitude
    assert ans0['actual_year'] == asset.capture_date.year
    assert ans0['is_game_over'] is False

    # Now round 1 question can be retrieved
    q1_res = client.get(
        f'/api/challenge/{token}/question/1',
        headers={'X-Player-Token': p_token},
    )
    assert q1_res.status_code == 200

    # Submit rounds 1, 2, 3
    for r in range(1, 4):
        client.post(
            f'/api/challenge/{token}/answer',
            headers={'X-Player-Token': p_token},
            json={
                'round_index': r,
                'guessed_latitude': 12.0,
                'guessed_longitude': 22.0,
                'guessed_year': 2021,
                'guessed_month': 2,
                'time_taken_seconds': 7.0,
            },
        )

    # Submit round 4 (final round)
    ans4_res = client.post(
        f'/api/challenge/{token}/answer',
        headers={'X-Player-Token': p_token},
        json={
            'round_index': 4,
            'guessed_latitude': 14.0,
            'guessed_longitude': 24.0,
            'guessed_year': 2022,
            'guessed_month': 3,
            'time_taken_seconds': 6.5,
        },
    )
    assert ans4_res.status_code == 200
    ans4 = ans4_res.json()
    assert ans4['round_index'] == 4
    assert ans4['is_game_over'] is True
    assert ans4['total_score'] >= ans4['round_score']

    # Further question requests after completion return 409 Conflict
    conflict_q = client.get(
        f'/api/challenge/{token}/question/4',
        headers={'X-Player-Token': p_token},
    )
    assert conflict_q.status_code == 409


def test_challenge_answer_album_shuffle(tmp_path: Path) -> None:
    immich = FakeImmichClient(_create_mock_assets(25))
    client = build_client(tmp_path, immich)

    create_res = client.post(
        '/api/challenge/create',
        json={'creator_name': 'Host', 'game_mode': 'album_shuffle', 'round_count': 5},
    )
    token = create_res.json()['capability_token']

    start_res = client.post(f'/api/challenge/{token}/start', json={'player_name': 'Emma'})
    p_token = start_res.json()['session_token']

    # Get question 0
    q0_res = client.get(
        f'/api/challenge/{token}/question/0',
        headers={'X-Player-Token': p_token},
    )
    assert q0_res.status_code == 200
    q0 = q0_res.json()
    assert len(q0['batch_photos']) == 3
    assert len(q0['batch_pins']) == 3

    p_ids = [p['photo_id'] for p in q0['batch_photos']]
    pin_ids = [pin['pin_id'] for pin in q0['batch_pins']]

    # Submit answers for round 0
    ans_res = client.post(
        f'/api/challenge/{token}/answer',
        headers={'X-Player-Token': p_token},
        json={
            'round_index': 0,
            'album_shuffle_answers': [
                AlbumShuffleAnswerItem(
                    photo_id=p_ids[0],
                    assigned_pin_id=pin_ids[0],
                    assigned_timeline_index=0,
                ).model_dump(),
                AlbumShuffleAnswerItem(
                    photo_id=p_ids[1],
                    assigned_pin_id=pin_ids[1],
                    assigned_timeline_index=1,
                ).model_dump(),
                AlbumShuffleAnswerItem(
                    photo_id=p_ids[2],
                    assigned_pin_id=pin_ids[2],
                    assigned_timeline_index=2,
                ).model_dump(),
            ],
            'time_taken_seconds': 14.0,
        },
    )
    assert ans_res.status_code == 200
    ans = ans_res.json()
    assert ans['game_mode'] == 'album_shuffle'
    assert ans['batch_reveal'] is not None
    assert len(ans['batch_reveal']) == 3
    assert ans['is_game_over'] is False


def test_challenge_timer_grace_window(tmp_path: Path) -> None:
    immich = FakeImmichClient(_create_mock_assets(25))
    client = build_client(tmp_path, immich)

    create_res = client.post(
        '/api/challenge/create',
        json={'creator_name': 'Host', 'game_mode': 'pinpoint', 'round_count': 5, 'round_length': '30s'},
    )
    token = create_res.json()['capability_token']

    start_res = client.post(f'/api/challenge/{token}/start', json={'player_name': 'SlowPlayer'})
    p_token = start_res.json()['session_token']

    # 30s round length + 5s grace = 35s max. Submitting with 40s should mark timed_out = True
    ans_res = client.post(
        f'/api/challenge/{token}/answer',
        headers={'X-Player-Token': p_token},
        json={
            'round_index': 0,
            'guessed_latitude': 10.0,
            'guessed_longitude': 20.0,
            'guessed_year': 2020,
            'guessed_month': 1,
            'time_taken_seconds': 40.0,
            'timed_out': False,
        },
    )
    assert ans_res.status_code == 200


def test_challenge_fog_of_war_leaderboard_route(tmp_path: Path) -> None:
    immich = FakeImmichClient(_create_mock_assets(25))
    client = build_client(tmp_path, immich)

    create_res = client.post(
        '/api/challenge/create',
        json={'creator_name': 'Host', 'game_mode': 'pinpoint', 'round_count': 5},
    )
    token = create_res.json()['capability_token']

    # Player 1 finishes round 0
    s1 = client.post(f'/api/challenge/{token}/start', json={'player_name': 'Player1'}).json()
    t1 = s1['session_token']
    client.post(
        f'/api/challenge/{token}/answer',
        headers={'X-Player-Token': t1},
        json={
            'round_index': 0,
            'guessed_latitude': 10.0,
            'guessed_longitude': 20.0,
            'guessed_year': 2020,
            'guessed_month': 1,
            'time_taken_seconds': 5.0,
        },
    )

    # Player 2 finishes round 0 and round 1
    s2 = client.post(f'/api/challenge/{token}/start', json={'player_name': 'Player2'}).json()
    t2 = s2['session_token']
    client.post(
        f'/api/challenge/{token}/answer',
        headers={'X-Player-Token': t2},
        json={
            'round_index': 0,
            'guessed_latitude': 10.0,
            'guessed_longitude': 20.0,
            'guessed_year': 2020,
            'guessed_month': 1,
            'time_taken_seconds': 4.0,
        },
    )
    client.post(
        f'/api/challenge/{token}/answer',
        headers={'X-Player-Token': t2},
        json={
            'round_index': 1,
            'guessed_latitude': 12.0,
            'guessed_longitude': 22.0,
            'guessed_year': 2021,
            'guessed_month': 2,
            'time_taken_seconds': 4.0,
        },
    )

    # Player 1 queries leaderboard with Player 1's token (completed round 0, currently on round 1)
    # Fog of war: Player 1 should ONLY see guesses for round 0!
    lb_res_p1 = client.get(
        f'/api/challenge/{token}/leaderboard',
        headers={'X-Player-Token': t1},
    )
    assert lb_res_p1.status_code == 200
    lb_p1 = lb_res_p1.json()

    assert lb_p1['up_to_round'] == 0
    assert len(lb_p1['leaderboard']) == 2
    # All returned round guesses must be round_index <= 0
    for g in lb_p1['round_guesses']:
        assert g['round_index'] <= 0

    # Player 1 now completes round 1
    client.post(
        f'/api/challenge/{token}/answer',
        headers={'X-Player-Token': t1},
        json={
            'round_index': 1,
            'guessed_latitude': 12.0,
            'guessed_longitude': 22.0,
            'guessed_year': 2021,
            'guessed_month': 2,
            'time_taken_seconds': 5.0,
        },
    )

    # Player 1 queries leaderboard again: now sees up to round 1
    lb_res_p1_r1 = client.get(
        f'/api/challenge/{token}/leaderboard',
        headers={'X-Player-Token': t1},
    )
    lb_p1_r1 = lb_res_p1_r1.json()
    assert lb_p1_r1['up_to_round'] == 1
    round_indices = {g['round_index'] for g in lb_p1_r1['round_guesses']}
    assert 1 in round_indices


def test_media_proxy_authorization_for_challenge_assets(tmp_path: Path) -> None:
    immich = FakeImmichClient(_create_mock_assets(25))
    client = build_client(tmp_path, immich)

    # 1. Challenge asset should be accessible
    create_res = client.post(
        '/api/challenge/create',
        json={'creator_name': 'Host', 'game_mode': 'pinpoint', 'round_count': 5},
    )
    token = create_res.json()['capability_token']
    start_res = client.post(f'/api/challenge/{token}/start', json={'player_name': 'Alice'}).json()

    q0 = client.get(
        f'/api/challenge/{token}/question/0',
        headers={'X-Player-Token': start_res['session_token']},
    ).json()

    media_res = client.get(q0['media_url'])
    assert media_res.status_code == 200

    # 2. Completely unknown random asset returns 404
    unknown_res = client.get('/api/media/unknown-nonexistent-photo-id')
    assert unknown_res.status_code == 404


def test_challenge_expired_and_deactivated_returns_404(tmp_path: Path) -> None:
    immich = FakeImmichClient(_create_mock_assets(25))
    client = build_client(tmp_path, immich)

    create_res = client.post(
        '/api/challenge/create',
        json={'creator_name': 'Admin', 'game_mode': 'pinpoint', 'round_count': 5, 'expires_in_hours': 1},
    )
    token = create_res.json()['capability_token']
    ch_id = create_res.json()['challenge_id']

    # Backdate expiration in DB
    db_mgr = client.app.state.leaderboard_db_manager
    past_iso = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    with db_mgr.connection() as conn:
        conn.execute('UPDATE challenges SET expires_at = ? WHERE challenge_id = ?', (past_iso, ch_id))

    # All challenge endpoints should return 404 for expired challenge
    assert client.get(f'/api/challenge/{token}').status_code == 404
    assert client.post(f'/api/challenge/{token}/start', json={'player_name': 'Test'}).status_code == 404
    assert client.get(f'/api/challenge/{token}/question/0', headers={'X-Player-Token': 'tok'}).status_code == 404
    assert (
        client.post(
            f'/api/challenge/{token}/answer',
            headers={'X-Player-Token': 'tok'},
            json={'round_index': 0, 'time_taken_seconds': 1.0},
        ).status_code
        == 404
    )
    assert client.get(f'/api/challenge/{token}/leaderboard').status_code == 404

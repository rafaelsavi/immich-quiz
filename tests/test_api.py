from __future__ import annotations

from datetime import date
from pathlib import Path

from conftest import FakeImmichClient, build_client, make_asset, setup_payload
from fastapi.testclient import TestClient


def start_match(client: TestClient, **overrides: object) -> str:
    response = client.post('/api/game/setup', json=setup_payload(**overrides))
    assert response.status_code == 200
    return response.json()['match_id']


def answer_question(client: TestClient, match_id: str, question_id: str) -> dict[str, object]:
    response = client.post(
        '/api/answer',
        json={
            'match_id': match_id,
            'question_id': question_id,
            'guessed_latitude': -27.5969,
            'guessed_longitude': -48.5495,
            'guessed_year': 2024,
            'guessed_month': 1,
        },
    )
    return {'status': response.status_code, 'body': response.json()}


def test_question_payload_strips_answers(client: TestClient) -> None:
    match_id = start_match(client, players=['Alice', 'Bob'])

    response = client.post('/api/question', json={'match_id': match_id, 'played_asset_ids': []})
    assert response.status_code == 200
    data = response.json()

    assert 'actual_latitude' not in data
    assert 'actual_longitude' not in data
    assert 'actual_date' not in data
    assert 'exifInfo' not in data
    assert data['media_url'].startswith('/api/media/')
    assert data['player_number'] == 1
    assert data['total_players'] == 2


def test_question_selection_honors_photo_date_bounds(tmp_path: Path) -> None:
    immich = FakeImmichClient(
        [
            make_asset('old', captured='2010-01-01T10:11:12Z'),
            make_asset('in-range', captured='2024-01-14T10:11:12Z'),
            make_asset('new', captured='2026-01-01T10:11:12Z'),
        ]
    )
    client = build_client(
        tmp_path,
        immich,
        fetch_photos_date_lower_bound=date(2020, 1, 1),
        fetch_photos_date_upper_bound=date(2024, 12, 31),
    )
    match_id = start_match(client)

    response = client.post('/api/question', json={'match_id': match_id, 'played_asset_ids': []})
    assert response.status_code == 200
    assert response.json()['asset_id'] == 'in-range'


def test_albums_default_to_owned_only(client: TestClient, immich: FakeImmichClient) -> None:
    response = client.get('/api/albums', params={'library_name': 'family'})

    assert response.status_code == 200
    assert immich.last_include_shared_albums is False


def test_ui_config_exposes_layout_parameters(client: TestClient) -> None:
    response = client.get('/api/ui-config')

    assert response.status_code == 200
    body = response.json()
    assert body['quiz_image_max_height_px'] == 420


def test_albums_can_include_shared_when_requested(client: TestClient, immich: FakeImmichClient) -> None:
    response = client.get('/api/albums', params={'library_name': 'family', 'include_shared_albums': 'true'})

    assert response.status_code == 200
    assert immich.last_include_shared_albums is True


def test_albums_default_can_be_enabled_by_settings(tmp_path: Path) -> None:
    immich = FakeImmichClient()
    client = build_client(tmp_path, immich, include_shared_albums=True)

    response = client.get('/api/albums', params={'library_name': 'family'})

    assert response.status_code == 200
    assert immich.last_include_shared_albums is True


def test_albums_query_param_overrides_settings_default(tmp_path: Path) -> None:
    immich = FakeImmichClient()
    client = build_client(tmp_path, immich, include_shared_albums=True)

    response = client.get('/api/albums', params={'library_name': 'family', 'include_shared_albums': 'false'})

    assert response.status_code == 200
    assert immich.last_include_shared_albums is False


def test_answer_response_hides_the_solution(client: TestClient) -> None:
    match_id = start_match(client)
    question = client.post('/api/question', json={'match_id': match_id, 'played_asset_ids': []}).json()

    payload = answer_question(client, match_id, question['question_id'])['body']

    assert 'actual_latitude' not in payload
    assert 'actual_date' not in payload
    assert 'location_score' not in payload
    assert payload['round_complete'] is True
    assert payload['round_number'] == 1


def test_round_result_reveals_every_player(tmp_path: Path) -> None:
    immich = FakeImmichClient([make_asset(f'asset-{index}') for index in range(10)])
    client = build_client(tmp_path, immich)
    match_id = start_match(client, players=['Alice', 'Bob'], round_count=5)

    first = client.post('/api/question', json={'match_id': match_id, 'played_asset_ids': []}).json()
    assert answer_question(client, match_id, first['question_id'])['body']['round_complete'] is False

    second = client.post('/api/question', json={'match_id': match_id, 'played_asset_ids': []}).json()
    assert answer_question(client, match_id, second['question_id'])['body']['round_complete'] is True

    reveal = client.post('/api/round/result', json={'match_id': match_id, 'round_number': 1})
    assert reveal.status_code == 200
    body = reveal.json()

    assert body['actual_date'] == '2024-01-14'
    assert body['actual_year'] == 2024
    assert body['actual_month'] == 1
    assert [result['player_name'] for result in body['results']] == ['Alice', 'Bob']
    assert all(result['location_score'] == 100 for result in body['results'])
    assert all(result['date_score'] == 100 for result in body['results'])
    assert all(result['round_score'] == 200 for result in body['results'])
    assert all(result['date_diff_days'] == 0 for result in body['results'])
    assert all(result['date_diff_months'] == 0 for result in body['results'])


def test_round_result_is_blocked_until_every_player_answered(tmp_path: Path) -> None:
    immich = FakeImmichClient([make_asset(f'asset-{index}') for index in range(10)])
    client = build_client(tmp_path, immich)
    match_id = start_match(client, players=['Alice', 'Bob'], round_count=5)

    question = client.post('/api/question', json={'match_id': match_id, 'played_asset_ids': []}).json()
    answer_question(client, match_id, question['question_id'])

    response = client.post('/api/round/result', json={'match_id': match_id, 'round_number': 1})
    assert response.status_code == 409


def test_round_result_rejects_future_rounds(client: TestClient) -> None:
    match_id = start_match(client, round_count=5)
    assert client.post('/api/round/result', json={'match_id': match_id, 'round_number': 4}).status_code == 409
    assert client.post('/api/round/result', json={'match_id': match_id, 'round_number': 9}).status_code == 404


def test_timed_out_answers_are_flagged(client: TestClient) -> None:
    match_id = start_match(client, round_count=5)
    question = client.post('/api/question', json={'match_id': match_id, 'played_asset_ids': []}).json()

    client.post(
        '/api/answer',
        json={
            'match_id': match_id,
            'question_id': question['question_id'],
            'guessed_latitude': None,
            'guessed_longitude': None,
            'guessed_year': 2024,
            'guessed_month': 1,
            'timed_out': True,
        },
    )

    result = client.post('/api/round/result', json={'match_id': match_id, 'round_number': 1}).json()
    entry = result['results'][0]
    assert entry['timed_out'] is True
    assert entry['location_score'] == 0
    assert entry['distance_km'] is None


def test_month_guess_scores_days_from_the_month_boundary(client: TestClient) -> None:
    match_id = start_match(client, round_count=5)
    question = client.post('/api/question', json={'match_id': match_id, 'played_asset_ids': []}).json()

    client.post(
        '/api/answer',
        json={
            'match_id': match_id,
            'question_id': question['question_id'],
            'guessed_latitude': -27.5969,
            'guessed_longitude': -48.5495,
            'guessed_year': 2023,
            'guessed_month': 11,
        },
    )

    result = client.post('/api/round/result', json={'match_id': match_id, 'round_number': 1}).json()
    entry = result['results'][0]
    # Actual date 2024-01-14 is after the guessed month, so the error runs from 2023-11-30.
    assert entry['date_diff_days'] == 45
    assert entry['date_diff_months'] == 2
    assert entry['date_diff_years_part'] == 0
    assert entry['date_diff_months_part'] == 1
    assert entry['date_diff_days_part'] == 15
    assert entry['date_score'] == 91


def test_any_day_inside_the_guessed_month_is_a_perfect_date_score(client: TestClient) -> None:
    match_id = start_match(client, round_count=5)
    question = client.post('/api/question', json={'match_id': match_id, 'played_asset_ids': []}).json()

    client.post(
        '/api/answer',
        json={
            'match_id': match_id,
            'question_id': question['question_id'],
            'guessed_latitude': -27.5969,
            'guessed_longitude': -48.5495,
            'guessed_year': 2024,
            'guessed_month': 1,
        },
    )

    result = client.post('/api/round/result', json={'match_id': match_id, 'round_number': 1}).json()
    entry = result['results'][0]
    assert entry['date_diff_days'] == 0
    assert entry['date_score'] == 100


def test_custom_scoring_env_parameters_affect_round_and_summary(tmp_path: Path) -> None:
    immich = FakeImmichClient([make_asset('asset-1')])
    client = build_client(
        tmp_path,
        immich,
        score_max_points=80,
        location_score_decay_km=500.0,
        date_score_decay_days=300.0,
    )
    match_id = start_match(client, round_count=5)
    question = client.post('/api/question', json={'match_id': match_id, 'played_asset_ids': []}).json()

    client.post(
        '/api/answer',
        json={
            'match_id': match_id,
            'question_id': question['question_id'],
            'guessed_latitude': -27.5969,
            'guessed_longitude': -48.5495,
            'guessed_year': 2024,
            'guessed_month': 1,
        },
    )

    result = client.post('/api/round/result', json={'match_id': match_id, 'round_number': 1})
    assert result.status_code == 200
    entry = result.json()['results'][0]
    assert entry['location_score'] == 80
    assert entry['date_score'] == 80
    assert entry['round_score'] == 160

    summary = client.get(f'/api/match/{match_id}/summary').json()
    assert summary['players'][0]['max_possible_score'] == 800


def test_match_summary_ranks_players_and_names_a_winner(tmp_path: Path) -> None:
    immich = FakeImmichClient([make_asset(f'asset-{index}') for index in range(10)])
    client = build_client(tmp_path, immich)
    match_id = start_match(client, players=['Alice', 'Bob'], round_count=5)

    for _ in range(10):
        question = client.post('/api/question', json={'match_id': match_id, 'played_asset_ids': []}).json()
        if question['player_name'] == 'Alice':
            answer_question(client, match_id, question['question_id'])
        else:
            client.post(
                '/api/answer',
                json={
                    'match_id': match_id,
                    'question_id': question['question_id'],
                    'guessed_latitude': 48.85,
                    'guessed_longitude': 2.35,
                    'guessed_year': 2010,
                    'guessed_month': 6,
                },
            )

    summary = client.get(f'/api/match/{match_id}/summary').json()

    assert summary['finished'] is True
    assert summary['winners'] == ['Alice']
    assert summary['players'][0]['player_name'] == 'Alice'
    assert summary['players'][0]['rank'] == 1
    assert summary['players'][0]['is_winner'] is True
    assert summary['players'][0]['total_score'] == 1000
    assert summary['players'][0]['accuracy_pct'] == 100.0
    assert summary['players'][1]['rank'] == 2
    assert summary['players'][1]['is_winner'] is False


def test_repeated_question_request_returns_same_question(client: TestClient, immich: FakeImmichClient) -> None:
    immich.assets = [make_asset(f'asset-{index}') for index in range(10)]
    match_id = start_match(client)

    first = client.post('/api/question', json={'match_id': match_id, 'played_asset_ids': []}).json()
    second = client.post('/api/question', json={'match_id': match_id, 'played_asset_ids': []}).json()

    assert first['question_id'] == second['question_id']
    assert first['asset_id'] == second['asset_id']
    assert immich.search_calls == 1


def test_answer_replay_is_rejected(tmp_path: Path) -> None:
    immich = FakeImmichClient([make_asset(f'asset-{index}') for index in range(10)])
    client = build_client(tmp_path, immich)
    match_id = start_match(client, round_count=5)

    last_question_id = ''
    for _ in range(5):
        question = client.post('/api/question', json={'match_id': match_id, 'played_asset_ids': []}).json()
        last_question_id = question['question_id']
        assert answer_question(client, match_id, last_question_id)['status'] == 200

    assert answer_question(client, match_id, last_question_id)['status'] == 409

    entries = client.get('/api/leaderboard').json()
    assert len(entries) == 1
    assert entries[0]['total_score'] == 1000


def test_duplicate_assets_never_repeat_even_if_client_lies(tmp_path: Path) -> None:
    immich = FakeImmichClient([make_asset(f'asset-{index}') for index in range(6)])
    client = build_client(tmp_path, immich)
    match_id = start_match(client, round_count=5)

    seen: list[str] = []
    for _ in range(5):
        question = client.post('/api/question', json={'match_id': match_id, 'played_asset_ids': []}).json()
        seen.append(question['asset_id'])
        answer_question(client, match_id, question['question_id'])

    assert len(set(seen)) == 5


def test_all_players_in_a_round_share_the_same_photo(tmp_path: Path) -> None:
    immich = FakeImmichClient([make_asset(f'asset-{index}') for index in range(20)])
    client = build_client(tmp_path, immich)
    match_id = start_match(client, players=['Alice', 'Bob', 'Cara'], round_count=5)

    rounds: dict[int, set[str]] = {}
    round_assets: list[str] = []

    for _ in range(15):
        question = client.post('/api/question', json={'match_id': match_id, 'played_asset_ids': []}).json()
        rounds.setdefault(question['player_round_number'], set()).add(question['asset_id'])
        round_assets.append(question['asset_id'])
        answer_question(client, match_id, question['question_id'])

    # Every player in a round sees exactly one shared photo.
    assert all(len(assets) == 1 for assets in rounds.values())
    # Each round still uses a different photo.
    assert len(rounds) == 5
    assert len({next(iter(assets)) for assets in rounds.values()}) == 5
    assert len(round_assets) == 15


def test_players_rotate_within_a_round(tmp_path: Path) -> None:
    immich = FakeImmichClient([make_asset(f'asset-{index}') for index in range(20)])
    client = build_client(tmp_path, immich)
    match_id = start_match(client, players=['Alice', 'Bob'], round_count=5)

    order: list[str] = []
    for _ in range(4):
        question = client.post('/api/question', json={'match_id': match_id, 'played_asset_ids': []}).json()
        order.append(question['player_name'])
        answer_question(client, match_id, question['question_id'])

    assert order == ['Alice', 'Bob', 'Alice', 'Bob']


def test_media_rejects_asset_outside_any_match(client: TestClient) -> None:
    response = client.get('/api/media/asset-1?library=family')
    assert response.status_code == 404


def test_media_serves_registered_asset(client: TestClient) -> None:
    match_id = start_match(client)
    question = client.post('/api/question', json={'match_id': match_id, 'played_asset_ids': []}).json()

    response = client.get(f'/api/media/{question["asset_id"]}?library=family')
    assert response.status_code == 200
    assert response.headers['content-type'].startswith('image/jpeg')
    assert response.content == b'fake-jpg'


def test_album_name_is_resolved_server_side(client: TestClient) -> None:
    match_id = start_match(client, album_id='album-1', album_name='Spoofed Album')
    question = client.post('/api/question', json={'match_id': match_id, 'played_asset_ids': []}).json()
    assert question['album_name'] == 'Holidays'


def test_unknown_album_id_is_rejected(client: TestClient) -> None:
    response = client.post('/api/game/setup', json=setup_payload(album_id='does-not-exist'))
    assert response.status_code == 400


def test_preflight_checks_eligible_asset_count(tmp_path: Path) -> None:
    immich = FakeImmichClient(
        [
            make_asset('photo1', latitude=-27.5, longitude=-48.5, captured='2024-01-01T10:00:00Z'),
            make_asset('photo2', latitude=-27.5, longitude=-48.5, captured='2024-01-02T10:00:00Z'),
            make_asset('no-gps', latitude=None, longitude=None, captured='2024-01-03T10:00:00Z'),
        ]
    )
    client = build_client(tmp_path, immich)

    # 10 rounds requested, but only 2 photos are eligible when location_mode=True
    payload = setup_payload(round_count=10, location_mode=True, date_mode=True)
    res = client.post('/api/game/preflight', json=payload)
    assert res.status_code == 200
    body = res.json()
    assert body['ok'] is False
    assert body['eligible_count'] == 2
    assert body['required'] == 10
    assert 'location' in body['active_filters']
    assert 'date' in body['active_filters']

    # 5 rounds requested, with 5 eligible photos -> ok is True
    immich_enough = FakeImmichClient(
        [make_asset(f'photo_{i}', latitude=-27.5, longitude=-48.5, captured='2024-01-01T10:00:00Z') for i in range(5)]
    )
    client_enough = build_client(
        tmp_path,
        immich_enough,
        fetch_photos_date_lower_bound=date(2020, 1, 1),
        fetch_photos_date_upper_bound=date(2024, 12, 31),
    )
    payload_enough = setup_payload(round_count=5, location_mode=True, date_mode=True)
    res_enough = client_enough.post('/api/game/preflight', json=payload_enough)
    assert res_enough.status_code == 200
    body_enough = res_enough.json()
    assert body_enough['ok'] is True
    assert body_enough['min_date'] == '2020-01-01'
    assert body_enough['max_date'] == '2024-12-31'
    assert 'date_range' in body_enough['active_filters']


def test_preflight_prevents_repeated_player_names(client: TestClient) -> None:
    payload = setup_payload(players=['Alice', 'alice'])
    res = client.post('/api/game/preflight', json=payload)
    assert res.status_code == 422
    assert 'Player names must be unique' in res.text

    payload_exact = setup_payload(players=['Bob', 'Bob'])
    res_exact = client.post('/api/game/preflight', json=payload_exact)
    assert res_exact.status_code == 422
    assert 'Player names must be unique' in res_exact.text

    payload_ok = setup_payload(players=['Alice', 'Bob'])
    res_ok = client.post('/api/game/preflight', json=payload_ok)
    assert res_ok.status_code == 200


def test_game_setup_prevents_repeated_player_names(client: TestClient) -> None:
    payload = setup_payload(players=['Player 1', ' player 1 '])
    res = client.post('/api/game/setup', json=payload)
    assert res.status_code == 422
    assert 'Player names must be unique' in res.text


def test_security_headers(client: TestClient) -> None:
    res = client.get('/api/health')
    assert res.status_code == 200
    assert res.headers['X-Content-Type-Options'] == 'nosniff'
    assert res.headers['X-Frame-Options'] == 'DENY'
    assert res.headers['Referrer-Policy'] == 'strict-origin-when-cross-origin'


def test_session_store_cleanup(client: TestClient) -> None:
    match_id = start_match(client)
    store = client.app.state.session_store
    match_state = store.get_match(match_id)

    # Artificially set last_activity_at to 3 hours ago
    match_state.last_activity_at = match_state.created_at - 10000

    cleaned = store.cleanup_expired_matches(ttl_seconds=7200)
    assert cleaned == 1
    assert match_id not in store._matches


def test_audio_playground_endpoint(client: TestClient) -> None:
    res = client.get('/audio-playground')
    assert res.status_code == 200
    assert 'text/html' in res.headers['content-type']
    assert 'Audio Testing Playground' in res.text
    assert 'playTick()' in res.text
    assert 'playBuzzer()' in res.text
    assert 'playChime()' in res.text


def test_album_shuffle_multi_round_game(tmp_path: Path) -> None:
    assets = [make_asset(f'asset-{i}', captured=f'2024-01-{i + 1:02d}T10:00:00Z') for i in range(30)]
    immich = FakeImmichClient(assets)
    client = build_client(tmp_path, immich)

    payload = setup_payload(game_mode='album_shuffle', round_count=5, players=['Player 1'])
    setup_res = client.post('/api/game/setup', json=payload)
    assert setup_res.status_code == 200
    match_id = setup_res.json()['match_id']

    played: list[str] = []
    for r in range(1, 6):
        q_res = client.post('/api/question', json={'match_id': match_id, 'played_asset_ids': played})
        assert q_res.status_code == 200
        q_data = q_res.json()
        assert q_data['game_mode'] == 'album_shuffle'

        a_res = client.post(
            '/api/answer',
            json={
                'match_id': match_id,
                'question_id': q_data['question_id'],
                'album_shuffle_answers': [
                    {'photo_id': p['photo_id'], 'assigned_pin_id': 'A', 'assigned_timeline_index': idx}
                    for idx, p in enumerate(q_data['batch_photos'])
                ],
            },
        )
        assert a_res.status_code == 200
        a_data = a_res.json()
        assert a_data['round_number'] == r
        assert a_data['match_finished'] is (r == 5)
        played.extend([p['photo_id'] for p in q_data['batch_photos']])


def test_batch_validation_distance_and_time_constraints() -> None:
    from datetime import datetime, timezone

    from src.game.selector import is_asset_valid_for_batch
    from src.immich.client import AssetAnswer
    from src.storage.session import RoundAsset

    sel_ans = AssetAnswer(
        latitude=48.8584,
        longitude=2.2945,
        capture_datetime=datetime(2024, 5, 10, 14, 0, 0, tzinfo=timezone.utc),
    )
    sel_asset = RoundAsset(asset_id='asset-1', answer=sel_ans)

    # Candidate at same location (< 100m) -> invalid
    same_loc = AssetAnswer(
        latitude=48.85841,
        longitude=2.29451,
        capture_datetime=datetime(2024, 5, 11, 14, 0, 0, tzinfo=timezone.utc),
    )
    assert is_asset_valid_for_batch(same_loc, [sel_asset], location_mode=True, date_mode=True) is False

    # Candidate at same time (< 60s) -> invalid
    same_time = AssetAnswer(
        latitude=40.7128,
        longitude=-74.0060,
        capture_datetime=datetime(2024, 5, 10, 14, 0, 30, tzinfo=timezone.utc),
    )
    assert is_asset_valid_for_batch(same_time, [sel_asset], location_mode=True, date_mode=True) is False

    # Candidate far in distance (NY) and far in time (1 day) -> valid
    valid_cand = AssetAnswer(
        latitude=40.7128,
        longitude=-74.0060,
        capture_datetime=datetime(2024, 5, 11, 14, 0, 0, tzinfo=timezone.utc),
    )
    assert is_asset_valid_for_batch(valid_cand, [sel_asset], location_mode=True, date_mode=True) is True


def test_album_shuffle_timed_out_answers_receive_zero_points(tmp_path: Path) -> None:
    assets = [make_asset(f'asset-{i}', captured=f'2024-01-{i + 1:02d}T10:00:00Z') for i in range(10)]
    immich = FakeImmichClient(assets)
    client = build_client(tmp_path, immich)

    payload = setup_payload(game_mode='album_shuffle', round_count=5, players=['Player 1'])
    setup_res = client.post('/api/game/setup', json=payload)
    match_id = setup_res.json()['match_id']

    q_res = client.post('/api/question', json={'match_id': match_id, 'played_asset_ids': []})
    q_data = q_res.json()

    a_res = client.post(
        '/api/answer',
        json={
            'match_id': match_id,
            'question_id': q_data['question_id'],
            'album_shuffle_answers': [],
            'timed_out': True,
        },
    )
    assert a_res.status_code == 200

    result = client.post('/api/round/result', json={'match_id': match_id, 'round_number': 1}).json()
    entry = result['results'][0]
    assert entry['timed_out'] is True
    assert entry['location_score'] == 0
    assert entry['date_score'] == 0
    assert entry['round_score'] == 0


def test_album_shuffle_timed_out_with_answers_receives_points(tmp_path: Path) -> None:
    assets = [make_asset(f'asset-{i}', captured=f'2024-01-{i + 1:02d}T10:00:00Z') for i in range(10)]
    immich = FakeImmichClient(assets)
    client = build_client(tmp_path, immich)

    payload = setup_payload(game_mode='album_shuffle', round_count=5, players=['Player 1'])
    setup_res = client.post('/api/game/setup', json=payload)
    match_id = setup_res.json()['match_id']

    q_res = client.post('/api/question', json={'match_id': match_id, 'played_asset_ids': []})
    q_data = q_res.json()
    batch_photos = q_data['batch_photos']

    # Submit correct chronological order for photos with timed_out=True
    answers = []
    for idx, p in enumerate(batch_photos):
        answers.append({
            'photo_id': p['photo_id'],
            'assigned_pin_id': None,
            'assigned_timeline_index': idx,
        })

    a_res = client.post(
        '/api/answer',
        json={
            'match_id': match_id,
            'question_id': q_data['question_id'],
            'album_shuffle_answers': answers,
            'timed_out': True,
        },
    )
    assert a_res.status_code == 200

    result = client.post('/api/round/result', json={'match_id': match_id, 'round_number': 1}).json()
    entry = result['results'][0]
    assert entry['timed_out'] is True
    assert entry['date_score'] > 0



def test_is_asset_valid_for_batch_rejects_missing_or_zero_coordinates_in_location_mode() -> None:
    from datetime import datetime, timezone

    from src.game.selector import is_asset_valid_for_batch
    from src.immich.client import AssetAnswer

    no_coords = AssetAnswer(
        latitude=None,
        longitude=None,
        capture_datetime=datetime(2024, 5, 10, 14, 0, 0, tzinfo=timezone.utc),
    )
    assert is_asset_valid_for_batch(no_coords, [], location_mode=True, date_mode=True) is False
    assert is_asset_valid_for_batch(no_coords, [], location_mode=False, date_mode=True) is True

    zero_coords = AssetAnswer(
        latitude=0.0,
        longitude=0.0,
        capture_datetime=datetime(2024, 5, 10, 14, 0, 0, tzinfo=timezone.utc),
    )
    assert is_asset_valid_for_batch(zero_coords, [], location_mode=True, date_mode=True) is False
    assert is_asset_valid_for_batch(zero_coords, [], location_mode=False, date_mode=True) is True


def test_batch_pins_omitted_when_location_mode_is_false(tmp_path: Path) -> None:
    assets = [make_asset(f'asset-{i}', captured=f'2024-01-{i + 1:02d}T10:00:00Z') for i in range(10)]
    immich = FakeImmichClient(assets)
    client = build_client(tmp_path, immich)

    payload = setup_payload(
        game_mode='album_shuffle',
        location_mode=False,
        date_mode=True,
        round_count=5,
        players=['Player 1'],
    )
    setup_res = client.post('/api/game/setup', json=payload)
    match_id = setup_res.json()['match_id']

    q_res = client.post('/api/question', json={'match_id': match_id, 'played_asset_ids': []})
    q_data = q_res.json()

    assert q_data['batch_pins'] is None
    assert len(q_data['batch_photos']) == 5


def test_question_reselects_asset_when_cached_asset_marked_played(tmp_path: Path) -> None:
    assets = [
        make_asset('asset-1', captured='2024-01-01T10:00:00Z'),
        make_asset('asset-2', captured='2024-01-02T10:00:00Z'),
    ]
    immich = FakeImmichClient(assets)
    client = build_client(tmp_path, immich)

    match_id = start_match(client, players=['Alice'])

    # First fetch gets an asset
    q1 = client.post('/api/question', json={'match_id': match_id, 'played_asset_ids': []}).json()
    asset1 = q1['asset_id']

    # Submitting same match_id & round_index with asset1 marked as played forces re-selection
    q2 = client.post('/api/question', json={'match_id': match_id, 'played_asset_ids': [asset1]}).json()
    asset2 = q2['asset_id']

    assert asset2 != asset1


def test_all_players_in_same_round_receive_same_photo_even_with_played_asset_ids(tmp_path: Path) -> None:
    assets = [
        make_asset('asset-1', captured='2024-01-01T10:00:00Z'),
        make_asset('asset-2', captured='2024-01-02T10:00:00Z'),
    ]
    immich = FakeImmichClient(assets)
    client = build_client(tmp_path, immich)

    match_id = start_match(client, players=['Alice', 'Bob'])

    # Alice fetches question (Round 0) -> gets asset-1
    q_alice = client.post('/api/question', json={'match_id': match_id, 'played_asset_ids': []}).json()
    assert q_alice['asset_id'] == 'asset-1'
    assert q_alice['player_name'] == 'Alice'

    # Alice submits answer for Round 0
    answer_question(client, match_id, q_alice['question_id'])

    # Bob fetches question for Round 0, passing played_asset_ids=['asset-1'] (since Alice played asset-1)
    q_bob = client.post('/api/question', json={'match_id': match_id, 'played_asset_ids': ['asset-1']}).json()
    assert q_bob['player_name'] == 'Bob'
    # Bob MUST receive asset-1 for Round 0
    assert q_bob['asset_id'] == 'asset-1'


def test_album_shuffle_reselects_batch_when_asset_marked_played(tmp_path: Path) -> None:
    assets = [make_asset(f'asset-{i}', captured=f'2024-01-{i + 1:02d}T10:00:00Z') for i in range(15)]
    immich = FakeImmichClient(assets)
    client = build_client(tmp_path, immich)

    payload = setup_payload(
        game_mode='album_shuffle',
        location_mode=False,
        date_mode=True,
        round_count=1,
        players=['Player 1'],
    )
    setup_res = client.post('/api/game/setup', json=payload)
    match_id = setup_res.json()['match_id']

    q1 = client.post('/api/question', json={'match_id': match_id, 'played_asset_ids': []}).json()
    failed_photo_id = q1['batch_photos'][0]['photo_id']

    # Retry same round with failed_photo_id in played_asset_ids
    q2 = client.post('/api/question', json={'match_id': match_id, 'played_asset_ids': [failed_photo_id]}).json()
    new_photo_ids = [p['photo_id'] for p in q2['batch_photos']]

    assert failed_photo_id not in new_photo_ids


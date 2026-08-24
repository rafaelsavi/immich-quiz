from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path

from conftest import FakeImmichClient, build_client, make_asset, setup_payload
from fastapi.testclient import TestClient

from src.game.selector import calculate_match_bounds, is_asset_valid_for_batch
from src.immich.client import AssetAnswer
from src.storage.metadata import MetadataStore
from src.storage.session import RoundAsset


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
        date_lower_bound=date(2020, 1, 1),
        date_upper_bound=date(2024, 12, 31),
    )
    match_id = start_match(client)

    response = client.post('/api/question', json={'match_id': match_id, 'played_asset_ids': []})
    assert response.status_code == 200
    assert response.json()['asset_id'] == 'in-range'


def test_albums_fetches_all_albums(client: TestClient) -> None:
    response = client.get('/api/albums', params={'libraries': ['family']})

    assert response.status_code == 200
    assert len(response.json()['albums']) >= 1
    assert response.json()['albums'][0]['name'] == 'Holidays'


def test_ui_config_exposes_layout_parameters(client: TestClient) -> None:
    response = client.get('/api/ui-config')

    assert response.status_code == 200
    body = response.json()
    assert body['language'] == 'EN'
    assert body['score_max_points'] == 100


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
    assert entry['location_score'] == 100
    assert entry['date_score'] == 100
    assert entry['round_score'] == 200

    summary = client.get(f'/api/match/{match_id}/summary').json()
    assert summary['players'][0]['max_possible_score'] == 1000


def test_match_summary_ranks_players_and_names_a_winner(tmp_path: Path) -> None:
    immich = FakeImmichClient(
        [
            make_asset(
                f'asset-{index}',
                latitude=-27.5969 + index * 0.05,
                longitude=-48.5495 + index * 0.05,
                captured=f'2024-01-{index + 1:02d}T10:00:00Z',
            )
            for index in range(10)
        ]
    )
    client = build_client(tmp_path, immich)
    match_id = start_match(client, players=['Alice', 'Bob'], round_count=5)
    asset_map = {a['id']: a for a in immich.assets}

    for _ in range(10):
        question = client.post('/api/question', json={'match_id': match_id, 'played_asset_ids': []}).json()
        if question['player_name'] == 'Alice':
            asset = asset_map[question['asset_id']]
            client.post(
                '/api/answer',
                json={
                    'match_id': match_id,
                    'question_id': question['question_id'],
                    'guessed_latitude': asset['exifInfo']['latitude'],
                    'guessed_longitude': asset['exifInfo']['longitude'],
                    'guessed_year': 2024,
                    'guessed_month': 1,
                },
            )
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
    assert summary['filter_summary'] == 'Full Library'
    assert summary['is_custom_filtered'] is False


def test_match_summary_with_custom_filters(tmp_path: Path) -> None:
    immich = FakeImmichClient(
        [
            make_asset(
                f'asset-{index}',
                latitude=-27.5969 + index * 0.05,
                longitude=-48.5495 + index * 0.05,
                captured=f'2024-01-{index + 1:02d}T10:00:00Z',
            )
            for index in range(5)
        ]
    )
    client = build_client(tmp_path, immich)
    match_id = start_match(client, albums=['album-1'], round_count=5)

    for _ in range(5):
        q = client.post('/api/question', json={'match_id': match_id, 'played_asset_ids': []}).json()
        client.post(
            '/api/answer',
            json={
                'match_id': match_id,
                'question_id': q['question_id'],
                'guessed_latitude': -27.59,
                'guessed_longitude': -48.54,
                'guessed_year': 2024,
                'guessed_month': 1,
            },
        )

    summary = client.get(f'/api/match/{match_id}/summary').json()
    assert summary['finished'] is True
    assert summary['is_custom_filtered'] is True
    assert summary['filter_summary'] == 'Holidays'
    assert summary['filter_tooltip'] == 'Album: Holidays'


def test_repeated_question_request_returns_same_question(client: TestClient) -> None:
    match_id = start_match(client)

    first = client.post('/api/question', json={'match_id': match_id, 'played_asset_ids': []}).json()
    second = client.post('/api/question', json={'match_id': match_id, 'played_asset_ids': []}).json()

    assert first['question_id'] == second['question_id']
    assert first['asset_id'] == second['asset_id']


def test_answer_replay_is_rejected(tmp_path: Path) -> None:
    immich = FakeImmichClient(
        [
            make_asset(
                f'asset-{index}',
                latitude=-27.5969 + index * 0.05,
                longitude=-48.5495 + index * 0.05,
                captured=f'2024-01-{index + 1:02d}T10:00:00Z',
            )
            for index in range(10)
        ]
    )
    client = build_client(tmp_path, immich)
    match_id = start_match(client, round_count=5)
    asset_map = {a['id']: a for a in immich.assets}

    last_question_id = ''
    for _ in range(5):
        question = client.post('/api/question', json={'match_id': match_id, 'played_asset_ids': []}).json()
        last_question_id = question['question_id']
        asset = asset_map[question['asset_id']]
        res = client.post(
            '/api/answer',
            json={
                'match_id': match_id,
                'question_id': last_question_id,
                'guessed_latitude': asset['exifInfo']['latitude'],
                'guessed_longitude': asset['exifInfo']['longitude'],
                'guessed_year': 2024,
                'guessed_month': 1,
            },
        )
        assert res.status_code == 200

    assert answer_question(client, match_id, last_question_id)['status'] == 409

    entries = client.get('/api/leaderboard').json()
    assert len(entries) == 1
    assert entries[0]['total_score'] == 1000

    filtered_albums = client.get('/api/leaderboard').json()
    assert len(filtered_albums) == 1
    assert filtered_albums[0]['config']['albums'] == []

    empty_albums = client.get('/api/leaderboard?albums=non-existent-id').json()
    assert len(empty_albums) == 0

    # Non-matching min_date
    empty_date = client.get('/api/leaderboard?min_date=2024-01-01').json()
    assert len(empty_date) == 0

    # Non-matching countries/cities/person_ids
    empty_countries = client.get('/api/leaderboard?countries=France').json()
    assert len(empty_countries) == 0

    empty_cities = client.get('/api/leaderboard?cities=Paris').json()
    assert len(empty_cities) == 0

    empty_people = client.get('/api/leaderboard?people=p1&people_mode=ANY').json()
    assert len(empty_people) == 0


def test_duplicate_assets_never_repeat_even_if_client_lies(tmp_path: Path) -> None:
    immich = FakeImmichClient(
        [
            make_asset(
                f'asset-{index}',
                latitude=-27.5969 + index * 0.05,
                longitude=-48.5495 + index * 0.05,
                captured=f'2024-01-{index + 1:02d}T10:00:00Z',
            )
            for index in range(6)
        ]
    )
    client = build_client(tmp_path, immich)
    match_id = start_match(client, round_count=5)

    seen: list[str] = []
    for _ in range(5):
        question = client.post('/api/question', json={'match_id': match_id, 'played_asset_ids': []}).json()
        seen.append(question['asset_id'])
        answer_question(client, match_id, question['question_id'])

    assert len(set(seen)) == 5


def test_all_players_in_a_round_share_the_same_photo(tmp_path: Path) -> None:
    immich = FakeImmichClient(
        [
            make_asset(
                f'asset-{index}',
                latitude=-27.5969 + index * 0.05,
                longitude=-48.5495 + index * 0.05,
                captured=f'2024-01-{index + 1:02d}T10:00:00Z',
            )
            for index in range(20)
        ]
    )
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
    immich = FakeImmichClient(
        [
            make_asset(
                f'asset-{index}',
                latitude=-27.5969 + index * 0.05,
                longitude=-48.5495 + index * 0.05,
                captured=f'2024-01-{index + 1:02d}T10:00:00Z',
            )
            for index in range(20)
        ]
    )
    client = build_client(tmp_path, immich)
    match_id = start_match(client, players=['Alice', 'Bob'], round_count=5)

    order: list[str] = []
    for _ in range(4):
        question = client.post('/api/question', json={'match_id': match_id, 'played_asset_ids': []}).json()
        order.append(question['player_name'])
        answer_question(client, match_id, question['question_id'])

    assert order == ['Alice', 'Bob', 'Alice', 'Bob']


def test_media_rejects_asset_outside_any_match(client: TestClient) -> None:
    response = client.get('/api/media/asset-1')
    assert response.status_code == 404


def test_media_serves_registered_asset(client: TestClient) -> None:
    match_id = start_match(client)
    question = client.post('/api/question', json={'match_id': match_id, 'played_asset_ids': []}).json()

    response = client.get(f'/api/media/{question["asset_id"]}')
    assert response.status_code == 200
    assert response.headers['content-type'].startswith('image/jpeg')
    assert response.content == b'fake-jpg'


def test_album_names_are_resolved_server_side(client: TestClient) -> None:
    # 1. Resolving album by ID ('album-1')
    match_id_by_id = start_match(client, albums=['album-1'])
    summary_by_id = client.get(f'/api/match/{match_id_by_id}/summary').json()
    assert summary_by_id['album_names'] == ['Holidays']

    # 2. Resolving album by Name ('Holidays')
    match_id_by_name = start_match(client, albums=['Holidays'])
    summary_by_name = client.get(f'/api/match/{match_id_by_name}/summary').json()
    assert summary_by_name['album_names'] == ['Holidays']


def test_unknown_album_id_is_rejected(client: TestClient) -> None:
    response = client.post('/api/game/setup', json=setup_payload(albums=['does-not-exist']))
    assert response.status_code == 400


def test_preflight_checks_eligible_asset_count(tmp_path: Path) -> None:
    immich = FakeImmichClient(
        [
            make_asset('photo1', latitude=-27.5, longitude=-48.5, captured='2024-01-01T10:00:00Z'),
            make_asset('photo2', latitude=-27.6, longitude=-48.6, captured='2024-01-02T10:00:00Z'),
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
        [
            make_asset(
                f'photo_{i}',
                latitude=-27.5 + i * 0.05,
                longitude=-48.5 + i * 0.05,
                captured=f'2024-01-0{i + 1}T10:00:00Z',
            )
            for i in range(5)
        ]
    )
    client_enough = build_client(
        tmp_path,
        immich_enough,
        date_lower_bound=date(2020, 1, 1),
        date_upper_bound=date(2024, 12, 31),
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
    assets = [
        make_asset(
            f'asset-{i}',
            latitude=-27.5969 + i * 0.05,
            longitude=-48.5495 + i * 0.05,
            captured=f'2024-01-{i + 1:02d}T10:00:00Z',
        )
        for i in range(30)
    ]
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
    assets = [
        make_asset(
            f'asset-{i}',
            latitude=-27.5969 + i * 0.05,
            longitude=-48.5495 + i * 0.05,
            captured=f'2024-01-{i + 1:02d}T10:00:00Z',
        )
        for i in range(10)
    ]
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
    assets = [
        make_asset(
            f'asset-{i}',
            latitude=-27.5969 + i * 0.05,
            longitude=-48.5495 + i * 0.05,
            captured=f'2024-01-{i + 1:02d}T10:00:00Z',
        )
        for i in range(10)
    ]
    immich = FakeImmichClient(assets)
    client = build_client(tmp_path, immich)

    payload = setup_payload(game_mode='album_shuffle', round_count=5, players=['Player 1'])
    setup_res = client.post('/api/game/setup', json=payload)
    match_id = setup_res.json()['match_id']

    q_res = client.post('/api/question', json={'match_id': match_id, 'played_asset_ids': []})
    q_data = q_res.json()
    batch_photos = q_data['batch_photos']

    asset_date_map = {a['id']: a['fileCreatedAt'] for a in assets}
    sorted_photos = sorted(batch_photos, key=lambda p: asset_date_map[p['photo_id']], reverse=False)
    photo_rank_map = {p['photo_id']: r for r, p in enumerate(sorted_photos)}

    # Submit correct chronological order for photos with timed_out=True
    answers = [
        {
            'photo_id': p['photo_id'],
            'assigned_pin_id': None,
            'assigned_timeline_index': photo_rank_map[p['photo_id']],
        }
        for p in batch_photos
    ]

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
    assert entry['date_score'] == 100


def test_album_shuffle_exact_sequence_placement_date_score(tmp_path: Path) -> None:
    assets = [
        make_asset(
            f'asset-{i}',
            latitude=-27.5969 + i * 0.05,
            longitude=-48.5495 + i * 0.05,
            captured=f'2024-01-{i + 1:02d}T10:00:00Z',
        )
        for i in range(10)
    ]
    immich = FakeImmichClient(assets)
    client = build_client(tmp_path, immich)

    payload = setup_payload(game_mode='album_shuffle', round_count=5, players=['Player 1'])
    setup_res = client.post('/api/game/setup', json=payload)
    match_id = setup_res.json()['match_id']

    q_res = client.post('/api/question', json={'match_id': match_id, 'played_asset_ids': []})
    q_data = q_res.json()
    batch_photos = q_data['batch_photos']

    asset_date_map = {a['id']: a['fileCreatedAt'] for a in assets}
    sorted_photos = sorted(batch_photos, key=lambda p: asset_date_map[p['photo_id']], reverse=False)
    true_rank_map = {p['photo_id']: r for r, p in enumerate(sorted_photos)}

    # Submit exact sequence placement (all photos in correct slots) -> 100 points
    answers_perfect = [
        {'photo_id': p['photo_id'], 'assigned_pin_id': None, 'assigned_timeline_index': true_rank_map[p['photo_id']]}
        for p in batch_photos
    ]
    a_res = client.post(
        '/api/answer',
        json={'match_id': match_id, 'question_id': q_data['question_id'], 'album_shuffle_answers': answers_perfect},
    )
    assert a_res.status_code == 200
    res = client.post('/api/round/result', json={'match_id': match_id, 'round_number': 1}).json()
    assert res['results'][0]['date_score'] == 100


def test_is_asset_valid_for_batch_rejects_missing_or_zero_coordinates_in_location_mode() -> None:
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
    assert len(q_data['batch_photos']) == 3

    # Answer and fetch round result in Date-Only Album Shuffle mode
    answers = [
        {'photo_id': p['photo_id'], 'assigned_pin_id': None, 'assigned_timeline_index': i}
        for i, p in enumerate(q_data['batch_photos'])
    ]
    a_res = client.post(
        '/api/answer',
        json={'match_id': match_id, 'question_id': q_data['question_id'], 'album_shuffle_answers': answers},
    )
    assert a_res.status_code == 200
    res = client.post('/api/round/result', json={'match_id': match_id, 'round_number': 1})
    assert res.status_code == 200
    res_data = res.json()
    assert res_data['batch_reveal'] is not None
    assert len(res_data['batch_reveal']) == 3
    for item in res_data['batch_reveal']:
        assert item['true_pin_id'] is None


def test_question_reselects_asset_when_cached_asset_marked_played(tmp_path: Path) -> None:
    assets = [
        make_asset('asset-1', latitude=-27.5969, longitude=-48.5495, captured='2024-01-01T10:00:00Z'),
        make_asset('asset-2', latitude=-27.6500, longitude=-48.6000, captured='2024-01-02T10:00:00Z'),
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
        make_asset('asset-1', latitude=-27.5969, longitude=-48.5495, captured='2024-01-01T10:00:00Z'),
        make_asset('asset-2', latitude=-27.6500, longitude=-48.6000, captured='2024-01-02T10:00:00Z'),
    ]
    immich = FakeImmichClient(assets)
    client = build_client(tmp_path, immich)

    match_id = start_match(client, players=['Alice', 'Bob'])

    # Alice fetches question (Round 0)
    q_alice = client.post('/api/question', json={'match_id': match_id, 'played_asset_ids': []}).json()
    alice_asset_id = q_alice['asset_id']
    assert q_alice['player_name'] == 'Alice'

    # Alice submits answer for Round 0
    answer_question(client, match_id, q_alice['question_id'])

    # Bob fetches question for Round 0, passing played_asset_ids=[alice_asset_id]
    q_bob = client.post('/api/question', json={'match_id': match_id, 'played_asset_ids': [alice_asset_id]}).json()
    assert q_bob['player_name'] == 'Bob'
    # Bob MUST receive the same asset as Alice for Round 0
    assert q_bob['asset_id'] == alice_asset_id


def test_album_shuffle_reselects_batch_when_asset_marked_played(tmp_path: Path) -> None:
    assets = [make_asset(f'asset-{i}', captured=f'2024-01-{i + 1:02d}T10:00:00Z') for i in range(15)]
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

    q1 = client.post('/api/question', json={'match_id': match_id, 'played_asset_ids': []}).json()
    failed_photo_id = q1['batch_photos'][0]['photo_id']

    # Retry same round with failed_photo_id in played_asset_ids
    q2 = client.post('/api/question', json={'match_id': match_id, 'played_asset_ids': [failed_photo_id]}).json()
    new_photo_ids = [p['photo_id'] for p in q2['batch_photos']]

    assert failed_photo_id not in new_photo_ids


def test_setup_returns_smart_map_bounds_for_regional_album(tmp_path: Path) -> None:
    assets = [
        make_asset('photo-1', latitude=43.7696, longitude=11.2558),  # Florence
        make_asset('photo-2', latitude=43.7228, longitude=10.4017),  # Pisa (~70 km away)
        make_asset('photo-3', latitude=43.3188, longitude=11.3308),  # Siena (~50 km away)
    ]
    immich = FakeImmichClient(assets)
    client = build_client(tmp_path, immich)

    payload = setup_payload(
        game_mode='pinpoint',
        location_mode=True,
        date_mode=True,
    )
    res = client.post('/api/game/setup', json=payload)
    assert res.status_code == 200
    data = res.json()
    assert 'map_bounds' in data
    assert data['map_bounds'] is not None
    bounds = data['map_bounds']
    assert bounds['min_lat'] <= 43.3188
    assert bounds['max_lat'] >= 43.7696
    assert bounds['min_lng'] <= 10.4017
    assert bounds['max_lng'] >= 11.3308


def test_setup_smart_map_zoom_disabled_when_location_mode_false(tmp_path: Path) -> None:
    assets = [make_asset('photo-1', latitude=43.7696, longitude=11.2558)]
    immich = FakeImmichClient(assets)
    client = build_client(tmp_path, immich)

    payload = setup_payload(
        game_mode='pinpoint',
        location_mode=False,
        date_mode=True,
    )
    res = client.post('/api/game/setup', json=payload)
    assert res.status_code == 200
    assert res.json()['map_bounds'] is None


def test_setup_smart_map_zoom_disabled_for_album_shuffle(tmp_path: Path) -> None:
    assets = [make_asset(f'photo-{i}', latitude=43.76 + i * 0.01, longitude=11.25 + i * 0.01) for i in range(15)]
    immich = FakeImmichClient(assets)
    client = build_client(tmp_path, immich)

    payload = setup_payload(
        game_mode='album_shuffle',
        location_mode=True,
        date_mode=True,
    )
    res = client.post('/api/game/setup', json=payload)
    assert res.status_code == 200
    assert res.json()['map_bounds'] is None


def test_calculate_match_bounds_single_location() -> None:
    pool = [AssetAnswer(latitude=48.8584, longitude=2.2945)]  # Eiffel Tower
    bounds = calculate_match_bounds(pool)
    assert bounds is not None
    assert bounds.min_lat == 48.8584
    assert bounds.max_lat == 48.8584
    assert bounds.min_lng == 2.2945
    assert bounds.max_lng == 2.2945


def test_calculate_match_bounds_global_fallback() -> None:
    pool = [
        AssetAnswer(latitude=48.8584, longitude=2.2945),  # Paris
        AssetAnswer(latitude=-33.8688, longitude=151.2093),  # Sydney
        AssetAnswer(latitude=-22.9068, longitude=-43.1729),  # Rio
    ]
    bounds = calculate_match_bounds(pool, max_span_km=5000.0)
    assert bounds is None


def test_calculate_match_bounds_empty_and_invalid() -> None:
    assert calculate_match_bounds([]) is None
    assert calculate_match_bounds([AssetAnswer(latitude=None, longitude=None)]) is None
    assert calculate_match_bounds([AssetAnswer(latitude=0.0, longitude=0.0)]) is None


def test_calculate_match_bounds_multiple_locations() -> None:
    answers = [
        AssetAnswer(latitude=48.8584, longitude=2.2945),
        AssetAnswer(latitude=48.8606, longitude=2.3376),
    ]
    bounds = calculate_match_bounds(
        answers,
        max_span_km=1000.0,
    )
    assert bounds is not None
    assert bounds.min_lat == 48.8584
    assert bounds.max_lat == 48.8606


def test_ui_config_returns_runtime_metadata(tmp_path: Path) -> None:
    client = build_client(tmp_path, FakeImmichClient([]))
    res = client.get('/api/ui-config')
    assert res.status_code == 200
    data = res.json()
    assert data['language'] == 'EN'
    assert data['score_max_points'] == 100
    assert 'version' in data


def test_preflight_and_setup_respect_dynamic_partner_and_shared_flags(tmp_path: Path) -> None:
    from src.storage.db import DatabaseManager

    db = DatabaseManager(tmp_path / 'metadata.db')
    meta_store = MetadataStore(db)

    # Insert 1 owned asset, 1 partner asset, 1 shared asset
    meta_store.upsert_assets_batch(
        'family',
        [
            {
                'id': 'owned-1',
                'file_type': 'IMAGE',
                'latitude': 10.0,
                'longitude': 20.0,
                'capture_datetime': '2023-01-01T12:00:00',
                'is_shared': 0,
                'is_partner': 0,
            },
            {
                'id': 'partner-1',
                'file_type': 'IMAGE',
                'latitude': 10.0,
                'longitude': 20.0,
                'capture_datetime': '2023-01-02T12:00:00',
                'is_shared': 0,
                'is_partner': 1,
            },
            {
                'id': 'shared-1',
                'file_type': 'IMAGE',
                'latitude': 10.0,
                'longitude': 20.0,
                'capture_datetime': '2023-01-03T12:00:00',
                'is_shared': 1,
                'is_partner': 0,
            },
        ],
        [],
        [],
    )

    immich = FakeImmichClient([])
    client = build_client(tmp_path, immich)

    # 1. By default (include_shared=False), only owned-1 is eligible (count = 1)
    res = client.post(
        '/api/game/preflight',
        json={
            'libraries': ['family'],
            'round_count': 5,
            'location_mode': True,
            'date_mode': True,
            'include_shared': False,
        },
    )
    assert res.status_code == 200
    assert res.json()['eligible_count'] == 1

    # 2. Enabling include_shared yields all 3 assets (count = 3)
    res = client.post(
        '/api/game/preflight',
        json={
            'libraries': ['family'],
            'round_count': 5,
            'location_mode': True,
            'date_mode': True,
            'include_shared': True,
        },
    )
    assert res.status_code == 200
    assert res.json()['eligible_count'] == 3


def test_question_endpoint_records_times_played(tmp_path: Path) -> None:
    asset = make_asset('q-test-1', latitude=48.8584, longitude=2.2945, captured='2024-01-01T12:00:00Z')
    immich = FakeImmichClient([asset])
    client = build_client(tmp_path, immich)

    # Populate metadata.db with this asset
    meta_store: MetadataStore = client.app.state.metadata_store
    meta_store.upsert_assets_batch(
        'family',
        [
            {
                'id': 'q-test-1',
                'is_shared': 0,
                'is_partner': 0,
                'file_type': 'IMAGE',
                'latitude': 48.8584,
                'longitude': 2.2945,
                'capture_datetime': '2024-01-01T12:00:00',
            }
        ],
        [],
        [],
    )

    # Setup match
    payload = setup_payload(players=['Player 1'], round_count=5, library_name='family')
    setup_res = client.post('/api/game/setup', json=payload)
    assert setup_res.status_code == 200
    match_id = setup_res.json()['match_id']

    # Initial play count is 0
    row_before = meta_store._db.fetch_one("SELECT times_played FROM assets WHERE id = 'q-test-1'")
    assert row_before['times_played'] == 0

    # Fetch question for round 1
    q_res = client.post('/api/question', json={'match_id': match_id, 'played_asset_ids': []})
    assert q_res.status_code == 200
    assert q_res.json()['asset_id'] == 'q-test-1'

    # Verify play count is incremented to 1
    row_after = meta_store._db.fetch_one("SELECT times_played, last_played_at FROM assets WHERE id = 'q-test-1'")
    assert row_after['times_played'] == 1
    assert row_after['last_played_at'] is not None


def test_finished_match_persists_four_table_relational_schema(tmp_path: Path) -> None:
    immich = FakeImmichClient(
        [
            make_asset(f'asset-{i}', latitude=48.0 + i, longitude=2.0 + i, captured=f'2023-0{i}-15T12:00:00Z')
            for i in range(1, 6)
        ]
    )
    client = build_client(tmp_path, immich)
    match_id = start_match(client, players=['Alice', 'Bob'], round_count=5)

    # 5 rounds * 2 players = 10 turns
    for r_idx in range(5):
        for p_name in ['Alice', 'Bob']:
            q = client.post('/api/question', json={'match_id': match_id, 'played_asset_ids': []}).json()
            assert q['player_name'] == p_name
            ans = client.post(
                '/api/answer',
                json={
                    'match_id': match_id,
                    'question_id': q['question_id'],
                    'guessed_latitude': 48.0 + r_idx,
                    'guessed_longitude': 2.0 + r_idx,
                    'guessed_year': 2023,
                    'guessed_month': r_idx + 1,
                    'time_taken_seconds': 10.0,
                },
            )
            assert ans.status_code == 200
            if r_idx == 4 and p_name == 'Bob':
                assert ans.json()['match_finished'] is True

    # Check SQLite database persistence
    db = client.app.state.leaderboard_store._db
    matches = db.fetch_all('SELECT * FROM matches WHERE match_id = ?', (match_id,))
    assert len(matches) == 1
    assert matches[0]['play_mode'] == 'local'
    assert matches[0]['rounds'] == 5

    entries = db.fetch_all('SELECT * FROM match_entries WHERE match_id = ? ORDER BY player_name', (match_id,))
    assert len(entries) == 2
    assert entries[0]['player_name'] == 'Alice'
    assert entries[0]['total_time_seconds'] == 50.0  # 5 * 10.0
    assert entries[1]['player_name'] == 'Bob'
    assert entries[1]['total_time_seconds'] == 50.0

    guesses = db.fetch_all(
        'SELECT * FROM match_round_guesses WHERE match_id = ? ORDER BY round_index, player_name',
        (match_id,),
    )
    assert len(guesses) == 10  # 5 rounds * 2 players
    assert guesses[0]['player_name'] == 'Alice'
    assert guesses[0]['round_index'] == 0
    assert guesses[0]['photo_index'] == 0
    assert guesses[0]['time_taken_seconds'] == 10.0
    assert guesses[0]['location_points'] is not None
    assert guesses[0]['date_points'] is not None


def test_multiple_albums_across_libraries_gameplay(tmp_path: Path) -> None:
    """Test full match setup and question selection with multiple albums across libraries."""
    immich = FakeImmichClient()
    client = build_client(
        tmp_path,
        immich,
        immich_libraries={'lib1': 'key1', 'lib2': 'key2'},
        auto_seed=False,
    )
    meta_store = client.app.state.metadata_store  # type: ignore

    meta_store.upsert_albums('lib1', [{'id': 'alb-1', 'name': 'Album 1'}])
    meta_store.upsert_albums('lib2', [{'id': 'alb-2', 'name': 'Album 2'}])

    assets1 = [
        {
            'id': 'a-1',
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
            'id': 'a-2',
            'is_shared': 0,
            'is_partner': 0,
            'file_type': 'IMAGE',
            'latitude': 20.0,
            'longitude': 20.0,
            'country': 'Brazil',
            'city': 'Sao Paulo',
            'capture_datetime': '2023-02-01T12:00:00',
        },
        {
            'id': 'a-3',
            'is_shared': 0,
            'is_partner': 0,
            'file_type': 'IMAGE',
            'latitude': 25.0,
            'longitude': 25.0,
            'country': 'Brazil',
            'city': 'Curitiba',
            'capture_datetime': '2023-02-15T12:00:00',
        },
    ]
    assets2 = [
        {
            'id': 'a-4',
            'is_shared': 0,
            'is_partner': 0,
            'file_type': 'IMAGE',
            'latitude': 30.0,
            'longitude': 30.0,
            'country': 'France',
            'city': 'Paris',
            'capture_datetime': '2023-03-01T12:00:00',
        },
        {
            'id': 'a-5',
            'is_shared': 0,
            'is_partner': 0,
            'file_type': 'IMAGE',
            'latitude': 40.0,
            'longitude': 40.0,
            'country': 'France',
            'city': 'Lyon',
            'capture_datetime': '2023-04-01T12:00:00',
        },
        {
            'id': 'a-6',
            'is_shared': 0,
            'is_partner': 0,
            'file_type': 'IMAGE',
            'latitude': 45.0,
            'longitude': 45.0,
            'country': 'France',
            'city': 'Nice',
            'capture_datetime': '2023-05-01T12:00:00',
        },
    ]
    meta_store.upsert_assets_batch('lib1', assets1, [], [('a-1', 'alb-1'), ('a-2', 'alb-1'), ('a-3', 'alb-1')])
    meta_store.upsert_assets_batch('lib2', assets2, [], [('a-4', 'alb-2'), ('a-5', 'alb-2'), ('a-6', 'alb-2')])

    # Start match selecting both libraries and both albums
    res = client.post(
        '/api/game/setup',
        json={
            'players': ['Alice'],
            'round_count': 5,
            'round_length': '1m',
            'location_mode': True,
            'date_mode': True,
            'game_mode': 'pinpoint',
            'libraries': ['lib1', 'lib2'],
            'albums': ['Album 1', 'Album 2'],
        },
    )
    assert res.status_code == 200
    match_id = res.json()['match_id']

    # Draw questions - verify only assets from alb-1 and alb-2 are drawn
    drawn_ids = []
    for _ in range(5):
        q_res = client.post('/api/question', json={'match_id': match_id, 'played_asset_ids': drawn_ids})
        assert q_res.status_code == 200
        q = q_res.json()
        assert q['asset_id'] in {'a-1', 'a-2', 'a-3', 'a-4', 'a-5', 'a-6'}
        drawn_ids.append(q['asset_id'])
        # Answer to advance
        client.post(
            '/api/answer',
            json={
                'match_id': match_id,
                'question_id': q['question_id'],
                'guessed_latitude': 10.0,
                'guessed_longitude': 10.0,
            },
        )

    assert len(set(drawn_ids)) == 5

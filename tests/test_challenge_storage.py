from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from src.models import (
    AlbumShuffleAnswerItem,
    ChallengeAnswerRequest,
    ChallengeCreateRequest,
    ChallengeExpirationOption,
    RoundLength,
)
from src.storage.challenge import ChallengeStore
from src.storage.db import DatabaseManager
from src.storage.leaderboard import LeaderboardStore


def test_challenge_store_creation_and_retrieval(tmp_path: Path) -> None:
    db_path = tmp_path / 'leaderboard.db'
    db = DatabaseManager(db_path)
    # Initialize schema via LeaderboardStore
    LeaderboardStore(db)

    store = ChallengeStore(db)

    config = {
        'game_mode': 'pinpoint',
        'round_count': 5,
        'round_length': '1m',
        'location_mode': True,
        'date_mode': True,
        'location_decay_km': 42.5,
        'date_decay_days': 180.0,
        'map_bounds': {'min_lat': 10.0, 'max_lat': 20.0, 'min_lng': 30.0, 'max_lng': 40.0},
        'filter_summary': 'Family Vacation • 5 Rounds',
    }

    res = store.create_challenge(
        creator_name='Rafael',
        libraries=['family'],
        config=config,
        asset_ids=['a1', 'a2', 'a3', 'a4', 'a5'],
        title='Summer 2024 Challenge',
        expires_in_hours=24,
    )

    assert res['challenge_id'].startswith('ch_')
    assert len(res['capability_token']) > 10
    assert res['title'] == 'Summer 2024 Challenge'
    assert res['creator_name'] == 'Rafael'
    assert res['libraries'] == ['family']
    assert res['asset_ids'] == ['a1', 'a2', 'a3', 'a4', 'a5']
    assert res['is_active'] is True
    assert res['expires_at'] is not None

    # Fetch by capability token
    fetched = store.get_challenge_by_token(res['capability_token'])
    assert fetched is not None
    assert fetched['challenge_id'] == res['challenge_id']
    assert fetched['title'] == 'Summer 2024 Challenge'
    assert fetched['config']['location_decay_km'] == 42.5
    assert fetched['config']['date_decay_days'] == 180.0
    assert fetched['libraries'] == ['family']
    assert fetched['asset_ids'] == ['a1', 'a2', 'a3', 'a4', 'a5']

    # Fetch by ID
    by_id = store.get_challenge_by_id(res['challenge_id'])
    assert by_id is not None
    assert by_id['capability_token'] == res['capability_token']


def test_challenge_expiration_and_deactivation(tmp_path: Path) -> None:
    db_path = tmp_path / 'leaderboard.db'
    db = DatabaseManager(db_path)
    LeaderboardStore(db)
    store = ChallengeStore(db)

    # 1. Expired challenge
    expired = store.create_challenge(
        creator_name='Admin',
        libraries=None,
        config={'game_mode': 'pinpoint', 'round_count': 5},
        asset_ids=['a1'],
        expires_in_hours=1,
    )
    # Manually backdate expires_at
    past_iso = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    with db.connection() as conn:
        conn.execute(
            'UPDATE challenges SET expires_at = ? WHERE challenge_id = ?',
            (past_iso, expired['challenge_id']),
        )

    assert store.get_challenge_by_token(expired['capability_token']) is None
    assert store.is_asset_in_active_challenge('a1') is False

    # 2. Deactivated challenge
    active_ch = store.create_challenge(
        creator_name='Admin',
        libraries=['main'],
        config={'game_mode': 'pinpoint', 'round_count': 5},
        asset_ids=['a2'],
        expires_in_hours=None,  # Never expires
    )
    assert store.get_challenge_by_token(active_ch['capability_token']) is not None
    assert store.is_asset_in_active_challenge('a2') is True

    # Deactivate
    ok = store.deactivate_challenge(active_ch['challenge_id'])
    assert ok is True
    assert store.get_challenge_by_token(active_ch['capability_token']) is None
    assert store.is_asset_in_active_challenge('a2') is False


def test_player_session_lifecycle_and_resumption(tmp_path: Path) -> None:
    db_path = tmp_path / 'leaderboard.db'
    db = DatabaseManager(db_path)
    LeaderboardStore(db)
    store = ChallengeStore(db)

    ch = store.create_challenge(
        creator_name='Host',
        libraries=None,
        config={'game_mode': 'pinpoint', 'round_count': 3},
        asset_ids=['a1', 'a2', 'a3'],
    )

    # Start new session
    session1 = store.get_or_resume_player_session(ch['challenge_id'], 'Alice')
    assert session1['player_name'] == 'Alice'
    assert session1['current_round'] == 0
    assert session1['total_score'] == 0
    assert session1['completed_at'] is None
    token = session1['session_token']

    # Retrieve by token
    retrieved = store.get_player_session(token)
    assert retrieved is not None
    assert retrieved['player_name'] == 'Alice'

    # Advance round 0 -> round 1
    store.advance_session(
        token,
        round_index=0,
        location_points=85,
        date_points=90,
        round_score=175,
        time_taken_seconds=11.2,
        is_final=False,
    )

    after_r0 = store.get_player_session(token)
    assert after_r0 is not None
    assert after_r0['current_round'] == 1
    assert after_r0['location_score'] == 85
    assert after_r0['date_score'] == 90
    assert after_r0['total_score'] == 175
    assert after_r0['total_time_seconds'] == 11.2

    # Attempt to start again with same name -> resumes existing session
    resumed = store.get_or_resume_player_session(ch['challenge_id'], 'Alice')
    assert resumed['session_token'] == token
    assert resumed['current_round'] == 1
    assert resumed['total_score'] == 175

    # Advance round 1 -> 2
    store.advance_session(
        token,
        round_index=1,
        location_points=100,
        date_points=100,
        round_score=200,
        time_taken_seconds=9.5,
        is_final=False,
    )

    # Advance final round 2 -> 3 (is_final=True)
    store.advance_session(
        token,
        round_index=2,
        location_points=50,
        date_points=50,
        round_score=100,
        time_taken_seconds=12.0,
        is_final=True,
    )

    final_session = store.get_player_session(token)
    assert final_session is not None
    assert final_session['current_round'] == 3
    assert final_session['total_score'] == 475
    assert final_session['total_time_seconds'] == pytest.approx(32.7)
    assert final_session['completed_at'] is not None


def test_challenge_standings_and_fog_of_war(tmp_path: Path) -> None:
    db_path = tmp_path / 'leaderboard.db'
    db = DatabaseManager(db_path)
    lb_store = LeaderboardStore(db)
    ch_store = ChallengeStore(db)

    ch = ch_store.create_challenge(
        creator_name='Admin',
        libraries=['main'],
        config={
            'game_mode': 'pinpoint',
            'round_count': 3,
            'round_length': '1m',
            'location_mode': True,
            'date_mode': True,
            'location_decay_km': 40.0,
            'date_decay_days': 150.0,
            'filter_summary': 'Summer Tour • 3 Rounds',
        },
        asset_ids=['p1', 'p2', 'p3'],
    )
    ch_id = ch['challenge_id']

    # Alice starts and finishes all 3 rounds
    s_alice = ch_store.get_or_resume_player_session(ch_id, 'Alice')
    # Round 0: 180 pts, 10s
    lb_store.record_challenge_round_guess(
        match_id=s_alice['match_id'],
        challenge_id=ch_id,
        player_name='Alice',
        round_index=0,
        asset_id='p1',
        guess_latitude=10.0,
        guess_longitude=10.0,
        actual_latitude=10.0,
        actual_longitude=10.0,
        actual_city='City1',
        actual_country='Country1',
        location_points=90,
        date_points=90,
        round_score=180,
        time_taken_seconds=10.0,
    )
    ch_store.advance_session(
        s_alice['session_token'],
        round_index=0,
        location_points=90,
        date_points=90,
        round_score=180,
        time_taken_seconds=10.0,
    )

    # Round 1: 190 pts, 8s
    lb_store.record_challenge_round_guess(
        match_id=s_alice['match_id'],
        challenge_id=ch_id,
        player_name='Alice',
        round_index=1,
        asset_id='p2',
        location_points=95,
        date_points=95,
        round_score=190,
        time_taken_seconds=8.0,
    )
    ch_store.advance_session(
        s_alice['session_token'],
        round_index=1,
        location_points=95,
        date_points=95,
        round_score=190,
        time_taken_seconds=8.0,
    )

    # Round 2: 200 pts, 7s
    lb_store.record_challenge_round_guess(
        match_id=s_alice['match_id'],
        challenge_id=ch_id,
        player_name='Alice',
        round_index=2,
        asset_id='p3',
        location_points=100,
        date_points=100,
        round_score=200,
        time_taken_seconds=7.0,
    )
    ch_store.advance_session(
        s_alice['session_token'],
        round_index=2,
        location_points=100,
        date_points=100,
        round_score=200,
        time_taken_seconds=7.0,
        is_final=True,
    )

    # Finalize Alice's match in leaderboard
    lb_store.finalize_challenge_player_match(
        match_id=s_alice['match_id'],
        challenge_id=ch_id,
        config=ch['config'],
        player_name='Alice',
        location_score=285,
        date_score=285,
        total_score=570,
        total_rounds=3,
        total_time_seconds=25.0,
        libraries=ch['libraries'],
    )

    # Bob starts and only completes round 0 (150 pts, 12s)
    s_bob = ch_store.get_or_resume_player_session(ch_id, 'Bob')
    lb_store.record_challenge_round_guess(
        match_id=s_bob['match_id'],
        challenge_id=ch_id,
        player_name='Bob',
        round_index=0,
        asset_id='p1',
        location_points=75,
        date_points=75,
        round_score=150,
        time_taken_seconds=12.0,
    )
    ch_store.advance_session(
        s_bob['session_token'],
        round_index=0,
        location_points=75,
        date_points=75,
        round_score=150,
        time_taken_seconds=12.0,
    )

    # Participant count
    assert lb_store.get_challenge_participant_count(ch_id) == 2

    # 1. Fog of War: Bob queries standings having only completed Round 0 (max_round=0)
    # Standings must ONLY include scores up to Round 0
    standings_r0 = lb_store.get_challenge_standings(ch_id, max_round=0)
    assert len(standings_r0) == 2
    # Alice had 180 in Round 0 (rank 1)
    assert standings_r0[0].player_name == 'Alice'
    assert standings_r0[0].total_score == 180
    assert standings_r0[0].rank == 1
    assert standings_r0[0].completed_rounds == 1
    # Bob had 150 in Round 0 (rank 2)
    assert standings_r0[1].player_name == 'Bob'
    assert standings_r0[1].total_score == 150
    assert standings_r0[1].rank == 2
    assert standings_r0[1].completed_rounds == 1

    # Fog of War for guesses: Bob queries guesses up to Round 0
    guesses_r0 = lb_store.get_challenge_round_guesses(ch_id, max_round=0)
    assert len(guesses_r0) == 2
    assert {g.round_index for g in guesses_r0} == {0}

    # 2. Full standings (max_round=None)
    full_standings = lb_store.get_challenge_standings(ch_id, max_round=None)
    assert len(full_standings) == 2
    assert full_standings[0].player_name == 'Alice'
    assert full_standings[0].total_score == 570
    assert full_standings[0].is_finished is True
    assert full_standings[0].rank == 1
    assert full_standings[0].is_winner is True

    assert full_standings[1].player_name == 'Bob'
    assert full_standings[1].total_score == 150
    assert full_standings[1].is_finished is False
    assert full_standings[1].rank == 2
    assert full_standings[1].is_winner is False

    # Full guesses (max_round=None)
    all_guesses = lb_store.get_challenge_round_guesses(ch_id, max_round=None)
    # Alice has 3 guesses, Bob has 1 guess -> total 4
    assert len(all_guesses) == 4


def test_challenge_models_validation() -> None:
    # 1. ChallengeCreateRequest
    req = ChallengeCreateRequest(
        creator_name='Rafael',
        title='Roadtrip',
        round_count=10,
        round_length=RoundLength.minute_1,
        location_mode=True,
        date_mode=True,
        expires_in_hours=48,
    )
    assert req.creator_name == 'Rafael'
    assert req.expires_in_hours == 48

    # 2. ChallengeAnswerRequest validation
    # Valid pinpoint answer
    ans_pin = ChallengeAnswerRequest(
        round_index=0,
        guessed_latitude=48.85,
        guessed_longitude=2.29,
        guessed_year=2023,
        guessed_month=6,
        time_taken_seconds=8.5,
    )
    assert ans_pin.guessed_latitude == 48.85
    assert ans_pin.guessed_month == 6

    # Incomplete coordinate pair raises ValidationError
    with pytest.raises(ValidationError):
        ChallengeAnswerRequest(
            round_index=0,
            guessed_latitude=48.85,
            guessed_longitude=None,
            time_taken_seconds=5.0,
        )

    # Incomplete date pair raises ValidationError
    with pytest.raises(ValidationError):
        ChallengeAnswerRequest(
            round_index=0,
            guessed_year=2023,
            guessed_month=None,
            time_taken_seconds=5.0,
        )

    # Valid album shuffle answer
    ans_shuffle = ChallengeAnswerRequest(
        round_index=0,
        album_shuffle_answers=[
            AlbumShuffleAnswerItem(photo_id='p1', assigned_pin_id='A', assigned_timeline_index=0),
            AlbumShuffleAnswerItem(photo_id='p2', assigned_pin_id='B', assigned_timeline_index=1),
        ],
        time_taken_seconds=15.0,
    )
    assert len(ans_shuffle.album_shuffle_answers) == 2

    # 3. Expiration Enum
    assert ChallengeExpirationOption.TWENTY_FOUR_HOURS.value == '24h'
    assert ChallengeExpirationOption.NEVER.value == 'never'


def test_challenge_album_shuffle_standings_time_calculation(tmp_path: Path) -> None:
    """Verify that get_challenge_standings calculates total elapsed time accurately without multiplying by photos."""
    db_path = tmp_path / 'leaderboard.db'
    db = DatabaseManager(db_path)
    leaderboard_store = LeaderboardStore(db)
    challenge_store = ChallengeStore(db)

    config = {
        'game_mode': 'album_shuffle',
        'round_count': 2,
        'round_length': '1m',
        'location_mode': True,
        'date_mode': True,
    }

    ch = challenge_store.create_challenge(
        creator_name='Host',
        libraries=None,
        config=config,
        asset_ids=['p1', 'p2', 'p3', 'p4', 'p5', 'p6'],
    )
    ch_id = ch['challenge_id']

    session = challenge_store.get_or_resume_player_session(ch_id, 'Player1')

    # Record 3 photos for round 0, each taking 12.0 seconds for the round turn
    for photo_idx, pid in enumerate(['p1', 'p2', 'p3']):
        leaderboard_store.record_challenge_round_guess(
            match_id=session['match_id'],
            challenge_id=ch_id,
            player_name='Player1',
            round_index=0,
            photo_index=photo_idx,
            game_mode='album_shuffle',
            asset_id=pid,
            round_score=33,
            location_points=16,
            date_points=17,
            time_taken_seconds=12.0,
        )

    # Standings at round 0 must report 12.0s, NOT 36.0s (3 * 12.0)
    standings = leaderboard_store.get_challenge_standings(ch_id, max_round=0)
    assert len(standings) == 1
    assert standings[0].total_time_seconds == pytest.approx(12.0)
    assert standings[0].total_score == 99
    assert standings[0].completed_rounds == 1

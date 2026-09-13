from datetime import date
from pathlib import Path

from src.models import (
    BaseGameConfig,
    GameMode,
    GameSetupRequest,
    PeopleMode,
    PlayMode,
    RoundLength,
)
from src.storage.challenge import PLAYER_COLORS
from src.storage.leaderboard import LeaderboardStore, _deterministic_player_color


def _create_sample_matches(store: LeaderboardStore) -> None:
    config = BaseGameConfig(
        libraries=['main'],
        round_count=5,
        round_length=RoundLength.minute_1,
        location_mode=True,
        date_mode=True,
        game_mode=GameMode.pinpoint,
        people=[],
        people_mode=PeopleMode.ANY,
        countries=[],
        cities=[],
        min_date=date(2023, 1, 1),
        max_date=date(2023, 12, 31),
    )
    setup = GameSetupRequest(players=['Alice', 'Bob'], **config.model_dump())

    # Match 1: Alice wins with high accuracy
    round_guesses_m1 = [
        # Round 1
        {
            'match_id': 'match-1',
            'player_name': 'Alice',
            'round_index': 0,
            'photo_index': 0,
            'asset_id': 'asset-1',
            'guess_latitude': 48.8566,
            'guess_longitude': 2.3522,
            'actual_latitude': 48.8560,
            'actual_longitude': 2.3520,
            'distance_km': 0.1,
            'location_points': 98,
            'guess_date': '2023-06-15',
            'actual_date': '2023-06-15',
            'date_diff_days': 0,
            'date_points': 100,
            'round_score': 198,
            'time_taken_seconds': 5.2,
            'timed_out': 0,
            'is_correct_location': 1,
            'is_correct_date_order': 1,
        },
        {
            'match_id': 'match-1',
            'player_name': 'Bob',
            'round_index': 0,
            'photo_index': 0,
            'asset_id': 'asset-1',
            'guess_latitude': 40.7128,
            'guess_longitude': -74.0060,
            'actual_latitude': 48.8560,
            'actual_longitude': 2.3520,
            'distance_km': 5800.0,
            'location_points': 10,
            'guess_date': '2020-01-01',
            'actual_date': '2023-06-15',
            'date_diff_days': 1261,
            'date_points': 20,
            'round_score': 30,
            'time_taken_seconds': 14.8,
            'timed_out': 0,
            'is_correct_location': 0,
            'is_correct_date_order': 0,
        },
        # Round 2
        {
            'match_id': 'match-1',
            'player_name': 'Alice',
            'round_index': 1,
            'photo_index': 0,
            'asset_id': 'asset-2',
            'guess_latitude': 35.6762,
            'guess_longitude': 139.6503,
            'actual_latitude': 35.6760,
            'actual_longitude': 139.6500,
            'distance_km': 0.3,
            'location_points': 95,
            'guess_date': '2023-08-10',
            'actual_date': '2023-08-12',
            'date_diff_days': 2,
            'date_points': 95,
            'round_score': 190,
            'time_taken_seconds': 7.1,
            'timed_out': 0,
            'is_correct_location': 1,
            'is_correct_date_order': 1,
        },
        {
            'match_id': 'match-1',
            'player_name': 'Bob',
            'round_index': 1,
            'photo_index': 0,
            'asset_id': 'asset-2',
            'guess_latitude': 35.0,
            'guess_longitude': 139.0,
            'actual_latitude': 35.6760,
            'actual_longitude': 139.6500,
            'distance_km': 95.0,
            'location_points': 65,
            'guess_date': '2023-08-01',
            'actual_date': '2023-08-12',
            'date_diff_days': 11,
            'date_points': 70,
            'round_score': 135,
            'time_taken_seconds': 11.0,
            'timed_out': 0,
            'is_correct_location': 1,
            'is_correct_date_order': 1,
        },
    ]

    store.append_match(
        match_id='match-1',
        config=setup,
        player_scores={
            'Alice': {'total': 388, 'location': 193, 'date': 195},
            'Bob': {'total': 165, 'location': 75, 'date': 90},
        },
        round_guesses=round_guesses_m1,
        play_mode=PlayMode.local,
    )

    # Match 2: Bob vs Charlie in Unshuffle
    shuffle_config = BaseGameConfig(
        libraries=['main'],
        round_count=3,
        round_length=RoundLength.minute_2,
        location_mode=True,
        date_mode=True,
        game_mode=GameMode.unshuffle,
        people=[],
        people_mode=PeopleMode.ANY,
        countries=[],
        cities=[],
        min_date=None,
        max_date=None,
    )
    shuffle_setup = GameSetupRequest(players=['Bob', 'Charlie'], **shuffle_config.model_dump())

    round_guesses_m2 = [
        {
            'match_id': 'match-2',
            'player_name': 'Bob',
            'round_index': 0,
            'photo_index': 0,
            'asset_id': 'asset-3',
            'guess_latitude': 51.5074,
            'guess_longitude': -0.1278,
            'actual_latitude': 51.5070,
            'actual_longitude': -0.1270,
            'distance_km': 0.2,
            'location_points': 95,
            'guess_date': '2023-05-01',
            'actual_date': '2023-05-01',
            'date_diff_days': 0,
            'date_points': 100,
            'round_score': 195,
            'time_taken_seconds': 9.5,
            'timed_out': 0,
            'is_correct_location': 1,
            'is_correct_date_order': 1,
        },
        {
            'match_id': 'match-2',
            'player_name': 'Charlie',
            'round_index': 0,
            'photo_index': 0,
            'asset_id': 'asset-3',
            'guess_latitude': None,
            'guess_longitude': None,
            'actual_latitude': 51.5070,
            'actual_longitude': -0.1270,
            'distance_km': None,
            'location_points': 0,
            'guess_date': None,
            'actual_date': '2023-05-01',
            'date_diff_days': None,
            'date_points': 0,
            'round_score': 0,
            'time_taken_seconds': 120.0,
            'timed_out': 1,
            'is_correct_location': 0,
            'is_correct_date_order': 0,
        },
    ]

    store.append_match(
        match_id='match-2',
        config=shuffle_setup,
        player_scores={
            'Bob': {'total': 195, 'location': 95, 'date': 100},
            'Charlie': {'total': 0, 'location': 0, 'date': 0},
        },
        round_guesses=round_guesses_m2,
        play_mode=PlayMode.challenge,
    )


def test_deterministic_player_color() -> None:
    color1 = _deterministic_player_color('Alice')
    color2 = _deterministic_player_color('Alice')
    assert color1 == color2
    assert color1.startswith('#')
    # Custom color overrides deterministic
    assert _deterministic_player_color('Alice', '#123456') == '#123456'


def test_get_known_player_names(tmp_path: Path) -> None:
    db_path = tmp_path / 'leaderboard.db'
    store = LeaderboardStore(db_path)
    _create_sample_matches(store)

    # Empty query returns all known players
    suggestions = store.get_known_player_names()
    names = [s.player_name for s in suggestions]
    assert 'Alice' in names
    assert 'Bob' in names
    assert 'Charlie' in names
    assert len(suggestions) == 3

    # Filtered query
    ali_suggestions = store.get_known_player_names(query='ali')
    assert len(ali_suggestions) == 1
    assert ali_suggestions[0].player_name == 'Alice'

    # Bob played 2 matches
    bob_sugg = [s for s in suggestions if s.player_name == 'Bob'][0]
    assert bob_sugg.match_count == 2


def test_get_all_players_directory(tmp_path: Path) -> None:
    db_path = tmp_path / 'leaderboard.db'
    store = LeaderboardStore(db_path)
    _create_sample_matches(store)

    players = store.get_all_players_directory(sort_by='matches')
    assert len(players) == 3
    # Bob has 2 matches, Alice and Charlie have 1
    assert players[0].player_name == 'Bob'
    assert players[0].matches_played == 2
    assert players[0].matches_won == 1
    assert players[0].win_rate_pct == 50.0

    # Sort by win rate (Alice 100%, Bob 50%, Charlie 0%)
    win_sorted = store.get_all_players_directory(sort_by='win_rate')
    assert win_sorted[0].player_name == 'Alice'
    assert win_sorted[0].win_rate_pct == 100.0

    # Search filter
    filtered = store.get_all_players_directory(search='Char')
    assert len(filtered) == 1
    assert filtered[0].player_name == 'Charlie'


def test_get_player_profile(tmp_path: Path) -> None:
    db_path = tmp_path / 'leaderboard.db'
    store = LeaderboardStore(db_path)
    _create_sample_matches(store)

    # Nonexistent player
    assert store.get_player_profile('UnknownPlayer') is None

    # Alice Profile
    profile = store.get_player_profile('Alice')
    assert profile is not None
    assert profile.player.player_name == 'Alice'
    assert profile.player.career_points == 388
    assert profile.player.matches_played == 1
    assert profile.player.matches_won == 1
    assert profile.player.win_rate_pct == 100.0
    assert profile.player.podiums_count == 1
    assert profile.player.peak_match_accuracy_pct == 38.8

    # Analytics
    analytics = profile.analytics
    assert analytics.best_distance_km == 0.1
    assert analytics.perfect_location_rounds_count == 0  # <100 points
    assert analytics.exact_year_month_pct == 100.0
    assert analytics.perfect_date_rounds_count == 1  # Round 1 date points = 100
    assert analytics.avg_response_time_seconds > 0
    assert analytics.fastest_response_time_seconds == 5.2

    # Accuracy tiers: Alice had 2 rounds with location points 98 and 95 (both Top Tier 90-100%)
    loc_tiers = {t.tier_key: t for t in analytics.location_tiers}
    assert loc_tiers['top'].count == 2
    assert loc_tiers['top'].percentage == 100.0
    assert loc_tiers['great'].count == 0
    assert loc_tiers['moderate'].count == 0
    assert loc_tiers['low'].count == 0

    # Mode mastery
    assert analytics.mode_mastery is not None
    mode_map = {m.game_mode: m for m in analytics.mode_mastery}
    assert mode_map['pinpoint'].matches_played == 1
    assert mode_map['unshuffle'].matches_played == 0

    # Recent matches
    assert len(profile.recent_matches) == 1
    assert profile.recent_matches[0]['match_id'] == 'match-1'
    assert profile.recent_matches[0]['rank'] == 1


def test_list_matches_history(tmp_path: Path) -> None:
    db_path = tmp_path / 'leaderboard.db'
    store = LeaderboardStore(db_path)
    _create_sample_matches(store)

    all_matches = store.list_matches_history()
    assert len(all_matches) == 2

    # Filter by game_mode
    pinpoint_matches = store.list_matches_history(game_mode='pinpoint')
    assert len(pinpoint_matches) == 1
    assert pinpoint_matches[0].match_id == 'match-1'

    # Filter by play_mode
    challenge_matches = store.list_matches_history(play_mode='challenge')
    assert len(challenge_matches) == 1
    assert challenge_matches[0].match_id == 'match-2'

    # Filter by player
    alice_matches = store.list_matches_history(player_name='Alice')
    assert len(alice_matches) == 1
    assert alice_matches[0].match_id == 'match-1'

    bob_matches = store.list_matches_history(player_name='Bob')
    assert len(bob_matches) == 2


def test_get_match_replay(tmp_path: Path) -> None:
    db_path = tmp_path / 'leaderboard.db'
    store = LeaderboardStore(db_path)
    _create_sample_matches(store)

    # Nonexistent match
    assert store.get_match_replay('nonexistent') is None

    # Match 1 replay
    replay = store.get_match_replay('match-1')
    assert replay is not None
    assert replay.match_id == 'match-1'
    assert replay.game_mode == 'pinpoint'
    assert replay.rounds == 5
    assert replay.config is not None
    assert replay.config.round_count == 5
    assert replay.config.location_mode is True
    assert replay.config.date_mode is True
    assert replay.config.min_date == date(2023, 1, 1)
    assert replay.config.max_date == date(2023, 12, 31)
    assert len(replay.rounds_data) == 2

    # Round 1
    r1 = replay.rounds_data[0]
    assert r1.round_number == 1
    assert r1.asset_id == 'asset-1'
    assert len(r1.player_guesses) == 2

    guesses_by_name = {g.player_name: g for g in r1.player_guesses}
    assert 'Alice' in guesses_by_name
    assert 'Bob' in guesses_by_name
    # Player 1 (Alice) must have PLAYER_COLORS[0], Player 2 (Bob) must have PLAYER_COLORS[1]
    assert guesses_by_name['Alice'].player_color == PLAYER_COLORS[0]
    assert guesses_by_name['Bob'].player_color == PLAYER_COLORS[1]
    assert guesses_by_name['Alice'].round_score == 198
    assert guesses_by_name['Alice'].cumulative_score == 198
    assert guesses_by_name['Bob'].round_score == 30
    assert guesses_by_name['Bob'].cumulative_score == 30

    # Also verify players roster summary in replay
    players_by_name = {p.player_name: p for p in replay.players}
    assert players_by_name['Alice'].player_color == PLAYER_COLORS[0]
    assert players_by_name['Bob'].player_color == PLAYER_COLORS[1]

    # Round 2 cumulative score accumulation & consistent colors
    r2 = replay.rounds_data[1]
    guesses_r2 = {g.player_name: g for g in r2.player_guesses}
    assert guesses_r2['Alice'].player_color == PLAYER_COLORS[0]
    assert guesses_r2['Bob'].player_color == PLAYER_COLORS[1]
    assert guesses_r2['Alice'].round_score == 190
    assert guesses_r2['Alice'].cumulative_score == 198 + 190  # 388
    assert guesses_r2['Bob'].round_score == 135
    assert guesses_r2['Bob'].cumulative_score == 30 + 135  # 165


def test_get_match_replay_legacy_missing_player_color(tmp_path: Path) -> None:
    """Ensure older matches where player_color was NULL still reconstruct standard sequence."""
    db_path = tmp_path / 'leaderboard.db'
    store = LeaderboardStore(db_path)
    _create_sample_matches(store)

    # Simulate legacy database entries where player_color column is NULL
    with store.db.connection() as conn:
        conn.execute("UPDATE match_entries SET player_color = NULL WHERE match_id = 'match-1'")

    replay = store.get_match_replay('match-1')
    assert replay is not None
    r1 = replay.rounds_data[0]
    guesses = {g.player_name: g for g in r1.player_guesses}
    assert guesses['Alice'].player_color == PLAYER_COLORS[0]
    assert guesses['Bob'].player_color == PLAYER_COLORS[1]

    players = {p.player_name: p for p in replay.players}
    assert players['Alice'].player_color == PLAYER_COLORS[0]
    assert players['Bob'].player_color == PLAYER_COLORS[1]


def test_get_match_replay_challenge_multiplayer(tmp_path: Path) -> None:
    """Verify that a challenge match replay aggregates all challenge participant sessions and guesses."""
    db_path = tmp_path / 'leaderboard.db'
    store = LeaderboardStore(db_path)

    ch_id = 'test-ch-1'
    config = {'game_mode': 'pinpoint', 'location_mode': True, 'date_mode': True, 'round_length': '1m'}

    # 1. Insert challenge and sessions
    with store.db.connection() as conn:
        conn.execute(
            """
            INSERT INTO challenges (
                challenge_id, capability_token, title, creator_name,
                config_json, asset_ids_json, is_active, created_at
            )
            VALUES (?, 'cap-1', 'Test Challenge', 'Host', '{}', '["photo-1"]', 1, '2026-03-01T12:00:00')
            """,
            (ch_id,),
        )
        conn.execute(
            """
            INSERT INTO challenge_sessions (
                session_token, match_id, challenge_id, player_name,
                current_round, location_score, date_score, total_score,
                started_at, player_color
            )
            VALUES ('tok-1', 'm-ch-1', ?, 'Alice', 1, 100, 100, 200, '2026-03-01T12:00:00', '#ff0000')
            """,
            (ch_id,),
        )
        conn.execute(
            """
            INSERT INTO challenge_sessions (
                session_token, match_id, challenge_id, player_name,
                current_round, location_score, date_score, total_score,
                started_at, player_color
            )
            VALUES ('tok-2', 'm-ch-2', ?, 'Bob', 1, 80, 80, 160, '2026-03-01T12:05:00', '#00ff00')
            """,
            (ch_id,),
        )

    # 2. Record completions using official helper
    store.finalize_challenge_player_match(
        match_id='m-ch-1',
        challenge_id=ch_id,
        player_name='Alice',
        total_rounds=1,
        total_score=200,
        location_score=100,
        date_score=100,
        config=config,
    )
    store.finalize_challenge_player_match(
        match_id='m-ch-2',
        challenge_id=ch_id,
        player_name='Bob',
        total_rounds=1,
        total_score=160,
        location_score=80,
        date_score=80,
        config=config,
    )

    # 3. Add round guesses
    with store.db.connection() as conn:
        conn.execute(
            """
            INSERT INTO match_round_guesses (
                match_id, player_name, round_index, photo_index, game_mode,
                asset_id, actual_latitude, actual_longitude, actual_date,
                guess_latitude, guess_longitude, round_score, submitted_at
            )
            VALUES (
                'm-ch-1', 'Alice', 0, 0, 'pinpoint',
                'photo-1', 48.85, 2.35, '2023-01-01',
                48.86, 2.36, 200, '2026-03-01T12:01:00'
            )
            """
        )
        conn.execute(
            """
            INSERT INTO match_round_guesses (
                match_id, player_name, round_index, photo_index, game_mode,
                asset_id, actual_latitude, actual_longitude, actual_date,
                guess_latitude, guess_longitude, round_score, submitted_at
            )
            VALUES (
                'm-ch-2', 'Bob', 0, 0, 'pinpoint',
                'photo-1', 48.85, 2.35, '2023-01-01',
                48.90, 2.40, 160, '2026-03-01T12:06:00'
            )
            """
        )

    # 1. Query by session match_id
    replay = store.get_match_replay('m-ch-1')
    assert replay is not None
    assert len(replay.players) == 2
    assert replay.winners == ['Alice']
    assert len(replay.rounds_data[0].player_guesses) == 2

    # 2. Query by challenge_id
    replay_ch = store.get_match_replay(ch_id)
    assert replay_ch is not None
    assert len(replay_ch.players) == 2
    assert replay_ch.winners == ['Alice']
    assert len(replay_ch.rounds_data[0].player_guesses) == 2


def test_multiple_challenge_sessions_do_not_duplicate_player_stats(tmp_path: Path) -> None:
    """Verify that players with multiple challenge sessions do not have inflated stats or invalid win rates."""
    db_path = tmp_path / 'leaderboard.db'
    store = LeaderboardStore(db_path)
    _create_sample_matches(store)

    # Insert multiple challenge sessions for 'Alice' across multiple challenges
    with store.db.connection() as conn:
        for i in range(1, 4):
            ch_id = f'ch-multi-{i}'
            conn.execute(
                """
                INSERT INTO challenges (
                    challenge_id, capability_token, title, creator_name,
                    config_json, asset_ids_json, is_active, created_at
                )
                VALUES (?, ?, ?, 'Alice', '{}', '["p1"]', 1, '2026-03-01T12:00:00')
                """,
                (ch_id, f'tok-{i}', f'Challenge {i}'),
            )
            conn.execute(
                """
                INSERT INTO challenge_sessions (
                    session_token, match_id, challenge_id, player_name,
                    current_round, location_score, date_score, total_score,
                    started_at, player_color
                )
                VALUES (?, ?, ?, 'Alice', 1, 100, 100, 200, '2026-03-01T12:00:00', '#ff0000')
                """,
                (f'tok-alice-{i}', f'm-ch-multi-{i}', ch_id),
            )

    # Directory query must not crash with Pydantic ValidationError and must retain accurate numbers
    directory = store.get_all_players_directory()
    alice = next((p for p in directory if p.player_name == 'Alice'), None)
    assert alice is not None
    # Alice played 1 sample match in _create_sample_matches and won it
    assert alice.matches_played == 1
    assert alice.matches_won == 1
    assert alice.win_rate_pct == 100.0

    # Profile query must not multiply stats
    profile = store.get_player_profile('Alice')
    assert profile is not None
    assert profile.player.matches_played == 1
    assert profile.player.matches_won == 1
    assert profile.player.win_rate_pct == 100.0
    assert profile.player.podiums_count == 1
    assert profile.player.avatar_color == '#f25f5c'

    # Known player names autocomplete must also succeed
    suggestions = store.get_known_player_names('Alice')
    assert len(suggestions) == 1
    assert suggestions[0].match_count == 1
    assert suggestions[0].avatar_color == '#f25f5c'


def test_consolidated_challenge_replays_and_metadata(tmp_path: Path) -> None:
    """Verify that multiple player sessions for a challenge appear as a single catalog item

    with aggregated players/winners and accurate filters from challenges table.
    """
    import json

    store = LeaderboardStore(tmp_path / 'test_challenge_replay.db')
    ch_id = 'ch-consolidated-100'

    with store.db.connection() as conn:
        conn.execute(
            """
            INSERT INTO challenges (
                challenge_id, capability_token, title, creator_name,
                libraries_json, config_json, asset_ids_json, is_active, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, 1, '2026-09-13T10:00:00Z')
            """,
            (
                ch_id,
                'cap-tok-100',
                'Roadtrip Challenge',
                'HostRafael',
                json.dumps(['FamilyVault']),
                json.dumps(
                    {
                        'round_count': 3,
                        'round_length': '1m',
                        'game_mode': 'pinpoint',
                        'album_names': ['Roadtrip 2024'],
                        'libraries': ['FamilyVault'],
                        'location_mode': True,
                        'date_mode': True,
                        'filter_summary': 'FamilyVault • Roadtrip 2024',
                    }
                ),
                json.dumps(['photo-1', 'photo-2', 'photo-3']),
            ),
        )

        # Player 1 (Alice) session
        conn.execute(
            """
            INSERT INTO challenge_sessions (
                session_token, match_id, challenge_id, player_name,
                current_round, location_score, date_score, total_score,
                started_at, completed_at, player_color
            ) VALUES (?, ?, ?, ?, 3, 250, 250, 500, '2026-09-13T10:05:00Z', '2026-09-13T10:10:00Z', '#ff0000')
            """,
            ('tok-alice-100', 'm-alice-100', ch_id, 'Alice'),
        )
        # Player 2 (Bob) session
        conn.execute(
            """
            INSERT INTO challenge_sessions (
                session_token, match_id, challenge_id, player_name,
                current_round, location_score, date_score, total_score,
                started_at, completed_at, player_color
            ) VALUES (?, ?, ?, ?, 3, 150, 150, 300, '2026-09-13T10:15:00Z', '2026-09-13T10:20:00Z', '#0000ff')
            """,
            ('tok-bob-100', 'm-bob-100', ch_id, 'Bob'),
        )

    # Record round guesses for both players
    store.record_challenge_round_guess(
        match_id='m-alice-100',
        challenge_id=ch_id,
        player_name='Alice',
        round_index=0,
        asset_id='photo-1',
        guess_latitude=10.0,
        guess_longitude=20.0,
        actual_latitude=10.0,
        actual_longitude=20.0,
        round_score=200,
        is_correct_location=1,
        time_taken_seconds=5.0,
    )
    store.record_challenge_round_guess(
        match_id='m-bob-100',
        challenge_id=ch_id,
        player_name='Bob',
        round_index=0,
        asset_id='photo-1',
        guess_latitude=12.0,
        guess_longitude=22.0,
        actual_latitude=10.0,
        actual_longitude=20.0,
        round_score=100,
        is_correct_location=0,
        time_taken_seconds=8.0,
    )

    # Record finished match entries for both players
    with store.db.connection() as conn:
        conn.execute(
            """
            INSERT INTO match_entries (
                match_id, player_name, player_color, location_score, date_score,
                total_score, max_possible_score, accuracy_pct, rank, is_winner, total_time_seconds
            ) VALUES
            ('m-alice-100', 'Alice', '#ff0000', 250, 250, 500, 600, 83.3, 1, 1, 15.0),
            ('m-bob-100', 'Bob', '#0000ff', 150, 150, 300, 600, 50.0, 1, 1, 25.0)
            """
        )

    # 1. Verify list_matches_history consolidation
    history = store.list_matches_history(limit=10)
    assert len(history) == 1
    item = history[0]

    assert item.match_id == ch_id
    assert item.challenge_id == ch_id
    assert item.challenge_title == 'Roadtrip Challenge'
    assert item.challenge_creator == 'HostRafael'
    assert item.player_count == 2
    assert set(item.players) == {'Alice', 'Bob'}
    assert item.top_score == 500
    assert item.winners == ['Alice']

    # 2. Verify get_match_replay via challenge_id
    replay_by_ch = store.get_match_replay(ch_id)
    assert replay_by_ch is not None
    assert replay_by_ch.challenge_id == ch_id
    assert replay_by_ch.challenge_title == 'Roadtrip Challenge'
    assert replay_by_ch.challenge_creator == 'HostRafael'
    assert replay_by_ch.config.libraries == ['FamilyVault']
    assert replay_by_ch.config.album_names == ['Roadtrip 2024']
    assert len(replay_by_ch.players) == 2
    assert replay_by_ch.winners == ['Alice']

    # 3. Verify get_match_replay via a participant's session match_id
    replay_by_session = store.get_match_replay('m-bob-100')
    assert replay_by_session is not None
    assert replay_by_session.challenge_id == ch_id
    assert replay_by_session.challenge_title == 'Roadtrip Challenge'
    assert replay_by_session.challenge_creator == 'HostRafael'
    assert replay_by_session.config.libraries == ['FamilyVault']
    assert replay_by_session.config.album_names == ['Roadtrip 2024']
    assert len(replay_by_session.players) == 2

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

    # Match 2: Bob vs Charlie in Album Shuffle
    shuffle_config = BaseGameConfig(
        libraries=['main'],
        round_count=3,
        round_length=RoundLength.minute_2,
        location_mode=True,
        date_mode=True,
        game_mode=GameMode.album_shuffle,
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
    assert mode_map['album_shuffle'].matches_played == 0

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

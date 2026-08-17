from datetime import date
from pathlib import Path

from src.models import GameMode, PeopleMode, PlayMode, RoundLength
from src.storage.db import DatabaseManager
from src.storage.leaderboard import LeaderboardStore, format_filter_summary


def test_leaderboard_schema_initialization(tmp_path: Path) -> None:
    db_path = tmp_path / 'leaderboard.db'
    store = LeaderboardStore(db_path)
    assert store.list_entries() == []

    db = DatabaseManager(db_path)
    tables = db.fetch_all("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    table_names = [t['name'] for t in tables]
    assert 'challenges' in table_names
    assert 'matches' in table_names
    assert 'match_entries' in table_names
    assert 'match_round_guesses' in table_names


def test_format_filter_summary() -> None:
    # Full library (no filters)
    is_custom, summary = format_filter_summary()
    assert is_custom == 0
    assert summary == 'Full Library'

    # Filter with album
    is_custom, summary = format_filter_summary(album_name='Europe 2023')
    assert is_custom == 1
    assert summary == 'Europe 2023'

    # Filter with countries & dates
    is_custom, summary = format_filter_summary(
        countries=['Italy', 'France'],
        min_date=date(2022, 1, 1),
        max_date=date(2023, 12, 31),
    )
    assert is_custom == 1
    assert 'Italy, France' in summary
    assert '2022/01 - 2023/12' in summary


def test_leaderboard_append_and_retrieve_rich_entry(tmp_path: Path) -> None:
    db_path = tmp_path / 'leaderboard.db'
    store = LeaderboardStore(db_path)

    round_guesses = [
        {
            'match_id': 'm1',
            'player_name': 'Alice',
            'round_index': 0,
            'photo_index': 0,
            'asset_id': 'a1',
            'guess_latitude': 35.68,
            'guess_longitude': 139.69,
            'actual_latitude': 35.689,
            'actual_longitude': 139.691,
            'distance_km': 1.2,
            'location_points': 90,
            'guess_date': '2023-01-01',
            'actual_date': '2023-01-15',
            'date_diff_days': 14,
            'date_points': 85,
            'round_score': 175,
            'time_taken_seconds': 12.5,
        }
    ]

    store.append_match(
        match_id='m1',
        library_name='family',
        album_name='-',
        rounds_played=5,
        round_length=RoundLength.minute_1,
        location_mode=True,
        date_mode=True,
        game_mode=GameMode.pinpoint,
        player_scores={'Alice': {'location': 400, 'date': 450, 'total': 850}},
        album_ids=[],
        person_ids=['p1', 'p2'],
        people_mode=PeopleMode.ALL,
        countries=['Japan'],
        cities=['Tokyo'],
        min_date=date(2023, 1, 1),
        max_date=date(2023, 12, 31),
        play_mode=PlayMode.local,
        duration_seconds=45.0,
        player_times={'Alice': 12.5},
        round_guesses=round_guesses,
    )

    entries = store.list_entries()
    assert len(entries) == 1
    entry = entries[0]

    assert entry.match_id == 'm1'
    assert entry.player_name == 'Alice'
    assert entry.total_score == 850
    assert entry.location_score == 400
    assert entry.date_score == 450
    assert entry.max_possible_score == 1000  # 5 rounds * 2 goals * 100
    assert entry.accuracy_pct == 85.0
    assert entry.rank == 1
    assert entry.is_winner is True
    assert entry.is_custom_filtered is True
    assert 'Japan' in entry.filter_summary
    assert 'Tokyo' in entry.filter_summary

    # Check direct db rows in matches and match_round_guesses
    db = DatabaseManager(db_path)
    match_row = db.fetch_one('SELECT * FROM matches WHERE match_id = ?', ('m1',))
    assert match_row is not None
    assert match_row['duration_seconds'] == 45.0
    assert match_row['play_mode'] == 'local'

    guesses = db.fetch_all('SELECT * FROM match_round_guesses WHERE match_id = ?', ('m1',))
    assert len(guesses) == 1
    assert guesses[0]['asset_id'] == 'a1'
    assert guesses[0]['photo_index'] == 0
    assert guesses[0]['time_taken_seconds'] == 12.5


def test_leaderboard_multiplayer_ranking_and_winner(tmp_path: Path) -> None:
    db_path = tmp_path / 'leaderboard.db'
    store = LeaderboardStore(db_path)

    store.append_match(
        match_id='m-multi',
        library_name='family',
        album_name='-',
        rounds_played=10,
        round_length=RoundLength.minute_1,
        location_mode=True,
        date_mode=False,
        game_mode=GameMode.pinpoint,
        player_scores={
            'Bob': {'location': 700, 'total': 700},
            'Alice': {'location': 900, 'total': 900},
            'Charlie': {'location': 700, 'total': 700},
            'David': {'location': 500, 'total': 500},
        },
    )

    entries = store.list_entries(limit=10)
    assert len(entries) == 4

    # Alice should be rank 1 and winner
    assert entries[0].player_name == 'Alice'
    assert entries[0].rank == 1
    assert entries[0].is_winner is True
    assert entries[0].total_score == 900

    # Bob and Charlie tie for rank 2
    assert entries[1].player_name in {'Bob', 'Charlie'}
    assert entries[1].rank == 2
    assert entries[1].is_winner is False

    assert entries[2].player_name in {'Bob', 'Charlie'}
    assert entries[2].rank == 2
    assert entries[2].is_winner is False

    # David is rank 4
    assert entries[3].player_name == 'David'
    assert entries[3].rank == 4
    assert entries[3].is_winner is False


def test_leaderboard_filtering(tmp_path: Path) -> None:
    db_path = tmp_path / 'leaderboard.db'
    store = LeaderboardStore(db_path)

    # Standard Match
    store.append_match(
        match_id='m1',
        library_name='family',
        album_name='-',
        rounds_played=10,
        round_length=RoundLength.minute_1,
        location_mode=True,
        date_mode=True,
        game_mode=GameMode.pinpoint,
        player_scores={'Alice': {'total': 800}},
    )

    # Filtered Match (Custom)
    store.append_match(
        match_id='m2',
        library_name='family',
        album_name='Holidays',
        rounds_played=5,
        round_length=RoundLength.seconds_30,
        location_mode=False,
        date_mode=True,
        game_mode=GameMode.album_shuffle,
        player_scores={'Bob': {'total': 400}},
        album_ids=['alb-1'],
        countries=['France'],
    )

    # Filter by rounds and round_length
    res = store.list_entries(rounds=10, round_length=RoundLength.minute_1)
    assert len(res) == 1
    assert res[0].match_id == 'm1'

    # Filter by game_mode
    res = store.list_entries(game_mode=GameMode.album_shuffle)
    assert len(res) == 1
    assert res[0].match_id == 'm2'

    # Filter by player_name
    res = store.list_entries(player_name='Alice')
    assert len(res) == 1
    assert res[0].player_name == 'Alice'

    # Filter by custom filter flag (standard vs custom)
    standard_entries = store.list_entries(is_custom_filtered=False)
    assert len(standard_entries) == 1
    assert standard_entries[0].match_id == 'm1'

    custom_entries = store.list_entries(is_custom_filtered=True)
    assert len(custom_entries) == 1
    assert custom_entries[0].match_id == 'm2'


def test_leaderboard_album_shuffle_round_guesses(tmp_path: Path) -> None:
    db_path = tmp_path / 'leaderboard.db'
    store = LeaderboardStore(db_path)

    # 1 round with 3 batch photos
    round_guesses = [
        {
            'match_id': 'm-shuffle',
            'player_name': 'Bob',
            'round_index': 0,
            'photo_index': 0,
            'asset_id': 'photo-1',
            'guess_latitude': 48.85,
            'guess_longitude': 2.29,
            'actual_latitude': 48.858,
            'actual_longitude': 2.294,
            'round_score': 100,
            'time_taken_seconds': 18.0,
        },
        {
            'match_id': 'm-shuffle',
            'player_name': 'Bob',
            'round_index': 0,
            'photo_index': 1,
            'asset_id': 'photo-2',
            'guess_latitude': 35.68,
            'guess_longitude': 139.69,
            'actual_latitude': 35.689,
            'actual_longitude': 139.691,
            'round_score': 0,
            'time_taken_seconds': 18.0,
        },
        {
            'match_id': 'm-shuffle',
            'player_name': 'Bob',
            'round_index': 0,
            'photo_index': 2,
            'asset_id': 'photo-3',
            'guess_latitude': 40.71,
            'guess_longitude': -74.00,
            'actual_latitude': 40.712,
            'actual_longitude': -74.006,
            'round_score': 0,
            'time_taken_seconds': 18.0,
        },
    ]

    store.append_match(
        match_id='m-shuffle',
        library_name='vacation',
        album_name='Trip 2024',
        rounds_played=1,
        round_length=RoundLength.minute_1,
        location_mode=True,
        date_mode=False,
        game_mode=GameMode.album_shuffle,
        player_scores={'Bob': {'location': 100, 'total': 100}},
        player_times={'Bob': 18.0},
        duration_seconds=20.0,
        round_guesses=round_guesses,
    )

    db = DatabaseManager(db_path)
    guesses = db.fetch_all(
        'SELECT * FROM match_round_guesses WHERE match_id = ? ORDER BY photo_index',
        ('m-shuffle',),
    )
    assert len(guesses) == 3
    assert [g['photo_index'] for g in guesses] == [0, 1, 2]
    assert [g['asset_id'] for g in guesses] == ['photo-1', 'photo-2', 'photo-3']

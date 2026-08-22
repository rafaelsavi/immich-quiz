from datetime import date
from pathlib import Path

from src.models import (
    BaseGameConfig,
    GameMode,
    LeaderboardQuery,
    PeopleMode,
    PlayMode,
    RoundLength,
)
from src.storage.db import DatabaseManager
from src.storage.leaderboard import LeaderboardStore


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

    match_cols = [c['name'] for c in db.fetch_all('PRAGMA table_info(matches)')]
    assert 'libraries_json' in match_cols
    assert 'album_ids_json' in match_cols
    assert 'album_names_json' in match_cols


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

    config = BaseGameConfig(
        libraries=['family'],
        round_count=5,
        round_length=RoundLength.minute_1,
        location_mode=True,
        date_mode=True,
        game_mode=GameMode.pinpoint,
        person_ids=['p1', 'p2'],
        people_mode=PeopleMode.ALL,
        countries=['Japan'],
        cities=['Tokyo'],
        min_date=date(2023, 1, 1),
        max_date=date(2023, 12, 31),
    )

    store.append_match(
        match_id='m1',
        config=config,
        player_scores={'Alice': {'location': 400, 'date': 450, 'total': 850}},
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
    assert entry.config.libraries == ['family']

    # Test min_date and max_date filtering (loose mode)
    date_filtered = store.list_entries(
        LeaderboardQuery(min_date=date(2023, 1, 1), max_date=date(2023, 12, 31), exact_filter_match=False)
    )
    assert len(date_filtered) == 1
    assert date_filtered[0].match_id == 'm1'

    date_non_matching = store.list_entries(LeaderboardQuery(min_date=date(2024, 1, 1), exact_filter_match=False))
    assert len(date_non_matching) == 0

    # Test countries, cities, person_ids, people_mode filtering (loose mode)
    country_filtered = store.list_entries(LeaderboardQuery(countries=['Japan'], exact_filter_match=False))
    assert len(country_filtered) == 1
    assert store.list_entries(LeaderboardQuery(countries=['France'], exact_filter_match=False)) == []

    city_filtered = store.list_entries(LeaderboardQuery(cities=['Tokyo'], exact_filter_match=False))
    assert len(city_filtered) == 1
    assert store.list_entries(LeaderboardQuery(cities=['Paris'], exact_filter_match=False)) == []

    person_filtered = store.list_entries(
        LeaderboardQuery(person_ids=['p1', 'p2'], people_mode=PeopleMode.ALL, exact_filter_match=False)
    )
    assert len(person_filtered) == 1
    assert store.list_entries(LeaderboardQuery(person_ids=['p3'], exact_filter_match=False)) == []
    assert (
        store.list_entries(
            LeaderboardQuery(person_ids=['p1', 'p2'], people_mode=PeopleMode.ANY, exact_filter_match=False)
        )
        == []
    )

    # Check direct db rows in matches and match_round_guesses
    db = DatabaseManager(db_path)
    match_row = db.fetch_one('SELECT * FROM matches WHERE match_id = ?', ('m1',))
    assert match_row is not None
    assert match_row['duration_seconds'] == 45.0
    assert match_row['play_mode'] == 'local'
    assert match_row['libraries_json'] == '["family"]'

    guesses = db.fetch_all('SELECT * FROM match_round_guesses WHERE match_id = ?', ('m1',))
    assert len(guesses) == 1
    assert guesses[0]['asset_id'] == 'a1'
    assert guesses[0]['photo_index'] == 0
    assert guesses[0]['time_taken_seconds'] == 12.5


def test_leaderboard_multiplayer_ranking_and_winner(tmp_path: Path) -> None:
    db_path = tmp_path / 'leaderboard.db'
    store = LeaderboardStore(db_path)

    config = BaseGameConfig(
        libraries=['family'],
        round_count=10,
        round_length=RoundLength.minute_1,
        location_mode=True,
        date_mode=False,
        game_mode=GameMode.pinpoint,
    )

    store.append_match(
        match_id='m-multi',
        config=config,
        player_scores={
            'Bob': {'location': 700, 'total': 700},
            'Alice': {'location': 900, 'total': 900},
            'Charlie': {'location': 700, 'total': 700},
            'David': {'location': 500, 'total': 500},
        },
    )

    entries = store.list_entries(LeaderboardQuery(limit=10))
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
        config=BaseGameConfig(
            libraries=['family'],
            round_count=10,
            round_length=RoundLength.minute_1,
            location_mode=True,
            date_mode=True,
            game_mode=GameMode.pinpoint,
        ),
        player_scores={'Alice': {'total': 800}},
    )

    # Filtered Match (Custom)
    store.append_match(
        match_id='m2',
        config=BaseGameConfig(
            libraries=['family'],
            album_names=['Holidays'],
            album_ids=['alb-1'],
            round_count=5,
            round_length=RoundLength.seconds_30,
            location_mode=False,
            date_mode=True,
            game_mode=GameMode.album_shuffle,
            countries=['France'],
        ),
        player_scores={'Bob': {'total': 400}},
    )

    # Filter by rounds and round_length
    res = store.list_entries(LeaderboardQuery(rounds=10, round_length=RoundLength.minute_1))
    assert len(res) == 1
    assert res[0].match_id == 'm1'

    # Filter by game_mode
    res = store.list_entries(LeaderboardQuery(game_mode=GameMode.album_shuffle))
    assert len(res) == 1
    assert res[0].match_id == 'm2'

    # Filter by player_name
    res = store.list_entries(LeaderboardQuery(player_name='Alice'))
    assert len(res) == 1
    assert res[0].player_name == 'Alice'

    # Filter by album_ids
    custom_entries = store.list_entries(LeaderboardQuery(album_ids=['alb-1'], exact_filter_match=False))
    assert len(custom_entries) == 1
    assert custom_entries[0].match_id == 'm2'


def test_leaderboard_album_shuffle_round_guesses(tmp_path: Path) -> None:
    db_path = tmp_path / 'leaderboard.db'
    store = LeaderboardStore(db_path)

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

    config = BaseGameConfig(
        libraries=['vacation'],
        album_names=['Trip 2024'],
        round_count=5,
        round_length=RoundLength.minute_1,
        location_mode=True,
        date_mode=False,
        game_mode=GameMode.album_shuffle,
    )

    store.append_match(
        match_id='m-shuffle',
        config=config,
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


def test_leaderboard_custom_filter_isolation(tmp_path: Path) -> None:
    db_path = tmp_path / 'leaderboard.db'
    store = LeaderboardStore(db_path)

    # 1. Full Library match
    store.append_match(
        match_id='m-full',
        config=BaseGameConfig(libraries=['main'], round_count=5),
        player_scores={'Alice': {'total': 800}},
    )

    # 2. Country Japan only
    store.append_match(
        match_id='m-japan',
        config=BaseGameConfig(libraries=['main'], round_count=5, countries=['Japan']),
        player_scores={'Alice': {'total': 850}},
    )

    # 3. City Paris only
    store.append_match(
        match_id='m-paris',
        config=BaseGameConfig(libraries=['main'], round_count=5, cities=['Paris']),
        player_scores={'Alice': {'total': 900}},
    )

    # 4. People ["p1"] only
    store.append_match(
        match_id='m-person',
        config=BaseGameConfig(libraries=['main'], round_count=5, person_ids=['p1'], people_mode=PeopleMode.ANY),
        player_scores={'Alice': {'total': 950}},
    )

    # 5. Date range only
    store.append_match(
        match_id='m-dates',
        config=BaseGameConfig(
            libraries=['main'], round_count=5, min_date=date(2022, 1, 1), max_date=date(2022, 12, 31)
        ),
        player_scores={'Alice': {'total': 700}},
    )

    # 6. Japan + Tokyo
    store.append_match(
        match_id='m-japan-tokyo',
        config=BaseGameConfig(libraries=['main'], round_count=5, countries=['Japan'], cities=['Tokyo']),
        player_scores={'Alice': {'total': 600}},
    )

    # Assertions:
    # Query Full Library -> should strictly isolate Full Library match only
    full_res = store.list_entries(LeaderboardQuery(libraries=['main']))
    assert len(full_res) == 1
    assert full_res[0].match_id == 'm-full'

    # Test via LeaderboardQuery.from_config
    query_full = LeaderboardQuery.from_config(BaseGameConfig(libraries=['main'], round_count=5))
    full_from_q = store.list_entries(query_full)
    assert len(full_from_q) == 1
    assert full_from_q[0].match_id == 'm-full'

    # Query Country Japan only -> isolates m-japan (excludes m-japan-tokyo because city is not set)
    japan_res = store.list_entries(LeaderboardQuery(libraries=['main'], countries=['Japan']))
    assert len(japan_res) == 1
    assert japan_res[0].match_id == 'm-japan'

    # Query City Paris only
    paris_res = store.list_entries(LeaderboardQuery(libraries=['main'], cities=['Paris']))
    assert len(paris_res) == 1
    assert paris_res[0].match_id == 'm-paris'

    # Query Person p1 only
    person_res = store.list_entries(LeaderboardQuery(libraries=['main'], person_ids=['p1']))
    assert len(person_res) == 1
    assert person_res[0].match_id == 'm-person'

    # Query Date Range only
    date_res = store.list_entries(
        LeaderboardQuery(libraries=['main'], min_date=date(2022, 1, 1), max_date=date(2022, 12, 31))
    )
    assert len(date_res) == 1
    assert date_res[0].match_id == 'm-dates'

    # Query Japan + Tokyo
    combo_res = store.list_entries(LeaderboardQuery(libraries=['main'], countries=['Japan'], cities=['Tokyo']))
    assert len(combo_res) == 1
    assert combo_res[0].match_id == 'm-japan-tokyo'

    # Query non-existent Country
    france_res = store.list_entries(LeaderboardQuery(libraries=['main'], countries=['France']))
    assert len(france_res) == 0


def test_leaderboard_round_count_condensing(tmp_path: Path) -> None:
    """Ensure round count is ignored and condensed in leaderboard queries when rounds is not specified."""
    db_path = tmp_path / 'leaderboard.db'
    store = LeaderboardStore(db_path)

    # 1. 5-round match (90% accuracy: 900 / 1000)
    store.append_match(
        match_id='m-5',
        config=BaseGameConfig(libraries=['family'], round_count=5),
        player_scores={'Alice': {'total': 900}},
    )

    # 2. 10-round match (85% accuracy: 1700 / 2000)
    store.append_match(
        match_id='m-10',
        config=BaseGameConfig(libraries=['family'], round_count=10),
        player_scores={'Bob': {'total': 1700}},
    )

    # 3. 20-round match (95% accuracy: 3800 / 4000)
    store.append_match(
        match_id='m-20',
        config=BaseGameConfig(libraries=['family'], round_count=20),
        player_scores={'Charlie': {'total': 3800}},
    )

    # Default query (rounds=None): all 3 matches are condensed together and ranked by accuracy_pct
    all_condensed = store.list_entries(LeaderboardQuery(libraries=['family']))
    assert len(all_condensed) == 3
    # Ranking by accuracy: Charlie (95%) -> Alice (90%) -> Bob (85%)
    assert [e.player_name for e in all_condensed] == ['Charlie', 'Alice', 'Bob']
    assert [e.accuracy_pct for e in all_condensed] == [95.0, 90.0, 85.0]

    # Explicit rounds=10 query: only Bob's 10-round game is returned
    rounds_10 = store.list_entries(LeaderboardQuery(rounds=10, libraries=['family']))
    assert len(rounds_10) == 1
    assert rounds_10[0].player_name == 'Bob'


def test_leaderboard_include_shared_and_album_ids_isolation(tmp_path: Path) -> None:
    db_path = tmp_path / 'leaderboard.db'
    store = LeaderboardStore(db_path)

    store.append_match(
        match_id='m-standard',
        config=BaseGameConfig(libraries=['main'], round_count=5, include_shared=False),
        player_scores={'Alice': {'total': 800}},
    )

    store.append_match(
        match_id='m-shared',
        config=BaseGameConfig(libraries=['main'], round_count=5, include_shared=True),
        player_scores={'Bob': {'total': 850}},
    )

    store.append_match(
        match_id='m-album-1',
        config=BaseGameConfig(libraries=['main'], album_names=['Vacation'], album_ids=['alb-1'], round_count=5),
        player_scores={'Charlie': {'total': 900}},
    )

    # Standard (include_shared=False)
    standard_res = store.list_entries(LeaderboardQuery(libraries=['main'], include_shared=False))
    assert len(standard_res) == 1
    assert standard_res[0].match_id == 'm-standard'
    assert standard_res[0].config.include_shared is False

    # Shared (include_shared=True)
    shared_res = store.list_entries(LeaderboardQuery(libraries=['main'], include_shared=True))
    assert len(shared_res) == 1
    assert shared_res[0].match_id == 'm-shared'
    assert shared_res[0].config.include_shared is True

    # Album ID alb-1
    album_res = store.list_entries(LeaderboardQuery(libraries=['main'], album_ids=['alb-1']))
    assert len(album_res) == 1
    assert album_res[0].match_id == 'm-album-1'
    assert album_res[0].config.album_ids == ['alb-1']


def test_leaderboard_challenge_and_room_fields(tmp_path: Path) -> None:
    db_path = tmp_path / 'leaderboard.db'
    store = LeaderboardStore(db_path)
    db = DatabaseManager(db_path)

    # 1. Verify table columns exist in SQLite schema
    challenge_cols = [c['name'] for c in db.fetch_all('PRAGMA table_info(challenges)')]
    assert 'title' in challenge_cols
    assert 'capability_token' in challenge_cols
    assert 'libraries_json' in challenge_cols

    match_cols = [c['name'] for c in db.fetch_all('PRAGMA table_info(matches)')]
    assert 'room_id' in match_cols
    assert 'room_name' in match_cols
    assert 'challenge_id' in match_cols
    assert 'play_mode' in match_cols
    assert 'libraries_json' in match_cols

    # 2. Insert a challenge seed with a title
    with db.connection() as conn:
        conn.execute(
            """
            INSERT INTO challenges (
                challenge_id, capability_token, title, creator_name,
                libraries_json, config_json, asset_ids_json, created_at, expires_at, is_active
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL, 1)
            """,
            (
                'ch_test1',
                'cap_token_123',
                'Summer 2024 Roadtrip',
                'Rafael',
                '["family"]',
                '{}',
                '[]',
                '2026-08-17T12:00:00Z',
            ),
        )

    # 3. Append a match that links to the challenge
    store.append_match(
        match_id='m-challenge-1',
        config=BaseGameConfig(libraries=['family'], round_count=5),
        play_mode=PlayMode.challenge,
        challenge_id='ch_test1',
        player_scores={'Alice': {'total': 950}},
    )

    # 4. Append a match that occurred in a live room
    store.append_match(
        match_id='m-room-1',
        config=BaseGameConfig(libraries=['family'], round_count=5),
        play_mode=PlayMode.room,
        room_id='rm_uuid_456',
        room_name="Rafael's Lounge",
        player_scores={'Bob': {'total': 880}},
    )

    # 5. Query and assert LeaderboardEntry fields
    entries = store.list_entries(LeaderboardQuery(libraries=['family']))
    assert len(entries) == 2

    # Check challenge entry (Alice)
    alice_entry = next(e for e in entries if e.player_name == 'Alice')
    assert alice_entry.play_mode == PlayMode.challenge
    assert alice_entry.challenge_id == 'ch_test1'
    assert alice_entry.challenge_title == 'Summer 2024 Roadtrip'
    assert alice_entry.room_id is None

    # Check room entry (Bob)
    bob_entry = next(e for e in entries if e.player_name == 'Bob')
    assert bob_entry.play_mode == PlayMode.room
    assert bob_entry.room_id == 'rm_uuid_456'
    assert bob_entry.room_name == "Rafael's Lounge"
    assert bob_entry.challenge_title is None


def test_leaderboard_multi_library_json_storage_and_query(tmp_path: Path) -> None:
    db_path = tmp_path / 'leaderboard.db'
    store = LeaderboardStore(db_path)

    # Multi-library match
    store.append_match(
        match_id='m-multi-lib',
        config=BaseGameConfig(libraries=['family', 'vacation'], round_count=5),
        player_scores={'Alice': {'total': 800}},
    )

    db = DatabaseManager(db_path)
    match_row = db.fetch_one('SELECT * FROM matches WHERE match_id = ?', ('m-multi-lib',))
    assert match_row is not None
    assert match_row['libraries_json'] == '["family", "vacation"]'

    # Query with exact libraries list
    res_exact = store.list_entries(LeaderboardQuery(libraries=['family', 'vacation']))
    assert len(res_exact) == 1
    assert res_exact[0].match_id == 'm-multi-lib'
    assert res_exact[0].config.libraries == ['family', 'vacation']

    # Query with single library that doesn't match multi-library match
    res_single = store.list_entries(LeaderboardQuery(libraries=['family']))
    assert len(res_single) == 0


def test_leaderboard_multi_album_storage_and_query(tmp_path: Path) -> None:
    db_path = tmp_path / 'leaderboard.db'
    store = LeaderboardStore(db_path)

    # Multi-album match
    config = BaseGameConfig(
        libraries=['main'],
        album_ids=['alb-1', 'alb-2'],
        album_names=['Trip 1', 'Trip 2'],
        round_count=5,
    )
    store.append_match(
        match_id='m-multi-album',
        config=config,
        player_scores={'Alice': {'total': 800}},
    )

    db = DatabaseManager(db_path)
    row = db.fetch_one('SELECT * FROM matches WHERE match_id = ?', ('m-multi-album',))
    assert row is not None
    assert row['album_ids_json'] == '["alb-1", "alb-2"]'
    assert row['album_names_json'] == '["Trip 1", "Trip 2"]'

    # Query with exact album IDs via LeaderboardQuery
    q = LeaderboardQuery.from_config(config)
    res = store.list_entries(q)
    assert len(res) == 1
    assert res[0].match_id == 'm-multi-album'
    assert res[0].config.album_ids == ['alb-1', 'alb-2']

    # Query with subset of album IDs -> should return 0 in exact match mode
    q_subset = LeaderboardQuery(libraries=['main'], album_ids=['alb-1'])
    assert len(store.list_entries(q_subset)) == 0

    # Query in loose mode -> should find the match if album_ids not set or exact_filter_match=False
    res_loose = store.list_entries(LeaderboardQuery(libraries=['main'], exact_filter_match=False))
    assert len(res_loose) == 1


def test_leaderboard_player_count_and_play_mode_filters(tmp_path: Path) -> None:
    db_path = tmp_path / 'leaderboard.db'
    store = LeaderboardStore(db_path)

    # 1. Local match with 2 players
    store.append_match(
        match_id='m-local-2p',
        config=BaseGameConfig(libraries=['main'], round_count=5),
        player_scores={'Alice': {'total': 800}, 'Bob': {'total': 700}},
        play_mode=PlayMode.local,
    )

    db = DatabaseManager(db_path)
    # Insert challenge seed to satisfy FK constraint
    with db.connection() as conn:
        conn.execute(
            """
            INSERT INTO challenges (
                challenge_id, capability_token, title, creator_name,
                libraries_json, config_json, asset_ids_json, created_at, expires_at, is_active
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL, 1)
            """,
            ('ch_summer_2025', 'token_summer', 'Summer 2025', 'Admin', '["main"]', '{}', '[]', '2025-06-01T00:00:00Z'),
        )

    # 2. Challenge match with 1 player
    store.append_match(
        match_id='m-challenge-1p',
        config=BaseGameConfig(libraries=['main'], round_count=5),
        player_scores={'Charlie': {'total': 900}},
        play_mode=PlayMode.challenge,
        challenge_id='ch_summer_2025',
    )

    db = DatabaseManager(db_path)
    row_local = db.fetch_one('SELECT player_count, play_mode FROM matches WHERE match_id = ?', ('m-local-2p',))
    assert row_local is not None
    assert row_local['player_count'] == 2
    assert row_local['play_mode'] == 'local'

    row_ch = db.fetch_one(
        'SELECT player_count, play_mode, challenge_id FROM matches WHERE match_id = ?', ('m-challenge-1p',)
    )
    assert row_ch is not None
    assert row_ch['player_count'] == 1
    assert row_ch['play_mode'] == 'challenge'
    assert row_ch['challenge_id'] == 'ch_summer_2025'

    # Filter by play_mode
    res_ch = store.list_entries(LeaderboardQuery(play_mode=PlayMode.challenge, exact_filter_match=False))
    assert len(res_ch) == 1
    assert res_ch[0].player_name == 'Charlie'
    assert res_ch[0].play_mode == PlayMode.challenge
    assert res_ch[0].rounds == 5
    assert res_ch[0].game_mode == GameMode.pinpoint

    # Filter by challenge_id
    res_ch_id = store.list_entries(LeaderboardQuery(challenge_id='ch_summer_2025', exact_filter_match=False))
    assert len(res_ch_id) == 1
    assert res_ch_id[0].match_id == 'm-challenge-1p'

    # Filter by date range (today)
    today = date.today()
    res_today = store.list_entries(LeaderboardQuery(played_after=today, played_before=today, exact_filter_match=False))
    assert len(res_today) == 3  # Alice, Bob, Charlie


def test_leaderboard_album_shuffle_round_guesses_fidelity(tmp_path: Path) -> None:
    db_path = tmp_path / 'leaderboard.db'
    store = LeaderboardStore(db_path)

    # Album Shuffle 3-photo batch round guesses
    round_guesses = [
        {
            'match_id': 'm-shuffle',
            'player_name': 'Alice',
            'round_index': 0,
            'photo_index': 0,
            'game_mode': 'album_shuffle',
            'asset_id': 'photo-1',
            'guess_latitude': 48.8566,
            'guess_longitude': 2.3522,
            'actual_latitude': 48.8584,
            'actual_longitude': 2.2945,
            'distance_km': 4.25,
            'location_points': 33,
            'guess_date': None,
            'actual_date': '2023-05-10',
            'date_diff_days': None,
            'date_points': 33,
            'round_score': 66,
            'is_correct_location': 1,
            'is_correct_date_order': 1,
            'time_taken_seconds': 8.5,
        },
        {
            'match_id': 'm-shuffle',
            'player_name': 'Alice',
            'round_index': 0,
            'photo_index': 1,
            'game_mode': 'album_shuffle',
            'asset_id': 'photo-2',
            'guess_latitude': 40.7128,
            'guess_longitude': -74.0060,
            'actual_latitude': 48.8584,
            'actual_longitude': 2.2945,
            'distance_km': 5837.2,
            'location_points': 0,
            'guess_date': None,
            'actual_date': '2023-06-15',
            'date_diff_days': None,
            'date_points': 0,
            'round_score': 0,
            'is_correct_location': 0,
            'is_correct_date_order': 0,
            'time_taken_seconds': 8.5,
        },
        {
            'match_id': 'm-shuffle',
            'player_name': 'Alice',
            'round_index': 0,
            'photo_index': 2,
            'game_mode': 'album_shuffle',
            'asset_id': 'photo-3',
            'guess_latitude': 51.5074,
            'guess_longitude': -0.1278,
            'actual_latitude': 51.5074,
            'actual_longitude': -0.1278,
            'distance_km': 0.0,
            'location_points': 33,
            'guess_date': None,
            'actual_date': '2023-07-20',
            'date_diff_days': None,
            'date_points': 33,
            'round_score': 66,
            'is_correct_location': 1,
            'is_correct_date_order': 1,
            'time_taken_seconds': 8.5,
        },
    ]

    config = BaseGameConfig(
        libraries=['main'],
        round_count=5,
        game_mode=GameMode.album_shuffle,
    )

    store.append_match(
        match_id='m-shuffle',
        config=config,
        player_scores={'Alice': {'location': 66, 'date': 66, 'total': 132}},
        round_guesses=round_guesses,
    )

    db = DatabaseManager(db_path)
    guesses = db.fetch_all(
        'SELECT photo_index, game_mode, round_score, is_correct_location, is_correct_date_order, distance_km '
        'FROM match_round_guesses WHERE match_id = ? ORDER BY photo_index ASC',
        ('m-shuffle',),
    )
    assert len(guesses) == 3

    # Photo 0
    assert guesses[0]['photo_index'] == 0
    assert guesses[0]['game_mode'] == 'album_shuffle'
    assert guesses[0]['round_score'] == 66
    assert guesses[0]['is_correct_location'] == 1
    assert guesses[0]['is_correct_date_order'] == 1
    assert round(guesses[0]['distance_km'], 2) == 4.25

    # Photo 1
    assert guesses[1]['photo_index'] == 1
    assert guesses[1]['game_mode'] == 'album_shuffle'
    assert guesses[1]['round_score'] == 0
    assert guesses[1]['is_correct_location'] == 0
    assert guesses[1]['is_correct_date_order'] == 0

    # Photo 2
    assert guesses[2]['photo_index'] == 2
    assert guesses[2]['game_mode'] == 'album_shuffle'
    assert guesses[2]['round_score'] == 66
    assert guesses[2]['is_correct_location'] == 1
    assert guesses[2]['is_correct_date_order'] == 1
    assert guesses[2]['distance_km'] == 0.0

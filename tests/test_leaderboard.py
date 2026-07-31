from pathlib import Path

from src.storage.leaderboard import CSV_HEADER, LeaderboardStore


def test_leaderboard_file_header(tmp_path: Path) -> None:
    csv_path = tmp_path / 'leaderboard.csv'
    store = LeaderboardStore(csv_path)
    header = csv_path.read_text(encoding='utf-8').splitlines()[0]
    assert header == ','.join(CSV_HEADER)
    assert store.list_entries() == []


def test_leaderboard_config_stored_as_flat_columns(tmp_path: Path) -> None:
    csv_path = tmp_path / 'leaderboard.csv'
    store = LeaderboardStore(csv_path)

    store.append_match(
        match_id='m1',
        library_name='family',
        album_name='-',
        rounds_played=5,
        round_length='1m',
        location_mode=False,
        date_mode=True,
        player_scores={'Alice': {'location': 0, 'date': 350, 'total': 350}},
    )

    entries = store.list_entries()
    assert len(entries) == 1
    entry = entries[0]
    assert entry.total_score == 350
    assert entry.config['rounds'] == 5
    assert entry.config['round_length'] == '1m'
    assert entry.config['location_mode'] is False
    assert entry.config['date_mode'] is True
    assert entry.config['library'] == 'family'
    assert entry.config['album'] == '-'


def test_leaderboard_filter_by_config(tmp_path: Path) -> None:
    csv_path = tmp_path / 'leaderboard.csv'
    store = LeaderboardStore(csv_path)

    store.append_match(
        match_id='m1',
        library_name='family',
        album_name='-',
        rounds_played=10,
        round_length='1m',
        location_mode=True,
        date_mode=True,
        player_scores={'Alice': {'location': 200, 'date': 300, 'total': 500}},
    )
    store.append_match(
        match_id='m2',
        library_name='family',
        album_name='Holidays',
        rounds_played=5,
        round_length='30s',
        location_mode=False,
        date_mode=True,
        player_scores={'Bob': {'location': 0, 'date': 150, 'total': 150}},
    )

    # Filter to match m1's config
    filtered = store.list_entries(
        rounds=10, round_length='1m', location_mode=True, date_mode=True, library='family', album='-'
    )
    assert len(filtered) == 1
    assert filtered[0].match_id == 'm1'

    # Filter to match m2's config
    filtered = store.list_entries(
        rounds=5, round_length='30s', location_mode=False, date_mode=True, library='family', album='Holidays'
    )
    assert len(filtered) == 1
    assert filtered[0].match_id == 'm2'

    # No filter — return both
    all_entries = store.list_entries()
    assert len(all_entries) == 2

"""Automated test suite for Player Stats, Directory, Profile, Match History and Replays REST API."""

from __future__ import annotations

from pathlib import Path

from conftest import FakeImmichClient, build_client

from tests.storage.test_player_stats import _create_sample_matches


def test_player_names_autocomplete_api(tmp_path: Path) -> None:
    immich = FakeImmichClient([])
    client = build_client(tmp_path, immich)
    store = client.app.state.leaderboard_store
    _create_sample_matches(store)

    # All known names
    res = client.get('/api/players/names')
    assert res.status_code == 200
    names_data = res.json()
    assert len(names_data) >= 3
    name_list = [p['player_name'] for p in names_data]
    assert 'Alice' in name_list
    assert 'Bob' in name_list
    assert 'Charlie' in name_list

    # Search filter
    res_filtered = client.get('/api/players/names?q=ali')
    assert res_filtered.status_code == 200
    filtered = res_filtered.json()
    assert len(filtered) == 1
    assert filtered[0]['player_name'] == 'Alice'
    assert filtered[0]['match_count'] == 1

    # Limit check
    res_limit = client.get('/api/players/names?limit=1')
    assert res_limit.status_code == 200
    assert len(res_limit.json()) == 1


def test_players_directory_api(tmp_path: Path) -> None:
    immich = FakeImmichClient([])
    client = build_client(tmp_path, immich)
    store = client.app.state.leaderboard_store
    _create_sample_matches(store)

    # Default sort by matches
    res = client.get('/api/players')
    assert res.status_code == 200
    players = res.json()
    assert len(players) == 3

    # Bob played 2 matches, Alice and Charlie played 1
    assert players[0]['player_name'] == 'Bob'
    assert players[0]['matches_played'] == 2

    # Verify summary fields
    alice = next(p for p in players if p['player_name'] == 'Alice')
    assert alice['matches_played'] == 1
    assert alice['matches_won'] == 1
    assert alice['win_rate_pct'] == 100.0
    assert alice['career_points'] == 388
    assert 'avatar_color' in alice
    assert alice['avatar_color'].startswith('#')

    # Sort by win_rate
    res_wr = client.get('/api/players?sort_by=win_rate')
    assert res_wr.status_code == 200
    wr_players = res_wr.json()
    assert wr_players[0]['win_rate_pct'] >= wr_players[-1]['win_rate_pct']

    # Sort by points
    res_pts = client.get('/api/players?sort_by=points')
    assert res_pts.status_code == 200
    pts_players = res_pts.json()
    assert pts_players[0]['career_points'] >= pts_players[-1]['career_points']

    # Filter by search
    res_search = client.get('/api/players?search=Charlie')
    assert res_search.status_code == 200
    search_players = res_search.json()
    assert len(search_players) == 1
    assert search_players[0]['player_name'] == 'Charlie'


def test_player_profile_api(tmp_path: Path) -> None:
    immich = FakeImmichClient([])
    client = build_client(tmp_path, immich)
    store = client.app.state.leaderboard_store
    _create_sample_matches(store)

    # 1. Existing player profile
    res = client.get('/api/players/Alice/profile')
    assert res.status_code == 200
    data = res.json()

    # Core performance metrics
    player = data['player']
    assert player['player_name'] == 'Alice'
    assert player['matches_played'] == 1
    assert player['matches_won'] == 1
    assert player['win_rate_pct'] == 100.0
    assert player['career_points'] == 388
    assert player['avg_accuracy_pct'] == 38.8
    assert player['peak_match_accuracy_pct'] == 38.8

    # Analytics
    analytics = data['analytics']
    assert analytics['best_distance_km'] == 0.1
    assert analytics['perfect_location_rounds_count'] == 0
    assert analytics['exact_year_month_pct'] == 100.0
    assert analytics['exact_year_pct'] == 100.0
    assert analytics['perfect_date_rounds_count'] == 1

    # Location & Date Tiers
    loc_tiers = analytics['location_tiers']
    assert len(loc_tiers) == 4
    top_loc = next(t for t in loc_tiers if t['tier_key'] == 'top')
    assert top_loc['count'] == 2
    assert top_loc['percentage'] == 100.0

    # Game mode mastery
    modes = {m['game_mode']: m for m in analytics['mode_mastery']}
    assert 'pinpoint' in modes
    assert modes['pinpoint']['matches_played'] == 1
    assert modes['pinpoint']['wins'] == 1
    assert 'album_shuffle' in modes
    assert modes['album_shuffle']['matches_played'] == 0

    # Recent matches list
    recent = data['recent_matches']
    assert len(recent) == 1
    assert recent[0]['match_id'] == 'match-1'
    assert recent[0]['is_winner'] is True

    # 2. 404 for unknown player
    res_404 = client.get('/api/players/NonExistentPlayer/profile')
    assert res_404.status_code == 404
    assert 'not found' in res_404.json()['detail'].lower()


def test_matches_history_api(tmp_path: Path) -> None:
    immich = FakeImmichClient([])
    client = build_client(tmp_path, immich)
    store = client.app.state.leaderboard_store
    _create_sample_matches(store)

    # 1. Unfiltered
    res = client.get('/api/matches')
    assert res.status_code == 200
    matches = res.json()
    assert len(matches) == 2

    # Verify MatchHistoryItem shape
    m1 = next(m for m in matches if m['match_id'] == 'match-1')
    assert m1['game_mode'] == 'pinpoint'
    assert 'Alice' in m1['winners']
    assert m1['top_score'] == 388

    # 2. Filter by game_mode
    res_pinpoint = client.get('/api/matches?game_mode=pinpoint')
    assert res_pinpoint.status_code == 200
    pinpoint_matches = res_pinpoint.json()
    assert len(pinpoint_matches) == 1
    assert pinpoint_matches[0]['match_id'] == 'match-1'

    # 3. Filter by player
    res_player = client.get('/api/matches?player=Charlie')
    assert res_player.status_code == 200
    charlie_matches = res_player.json()
    assert len(charlie_matches) == 1
    assert charlie_matches[0]['match_id'] == 'match-2'

    # 4. Limit & offset
    res_paging = client.get('/api/matches?limit=1&offset=1')
    assert res_paging.status_code == 200
    assert len(res_paging.json()) == 1


def test_match_replay_api(tmp_path: Path) -> None:
    immich = FakeImmichClient([])
    client = build_client(tmp_path, immich)
    store = client.app.state.leaderboard_store
    _create_sample_matches(store)

    # 1. Existing match replay
    res = client.get('/api/match/match-1/replay')
    assert res.status_code == 200
    data = res.json()

    assert data['match_id'] == 'match-1'
    assert data['game_mode'] == 'pinpoint'
    assert data['rounds'] == 5
    assert len(data['players']) == 2
    assert len(data['rounds_data']) == 2

    # Check round 1 replay data
    round_0 = data['rounds_data'][0]
    assert round_0['round_number'] == 1
    assert round_0['actual_latitude'] == 48.8560
    assert round_0['actual_longitude'] == 2.3520
    assert round_0['actual_date'] == '2023-06-15'

    # Check player guesses in round 1
    guesses = {g['player_name']: g for g in round_0['player_guesses']}
    assert 'Alice' in guesses
    assert 'Bob' in guesses
    assert guesses['Alice']['distance_km'] == 0.1
    assert guesses['Alice']['cumulative_score'] == 198
    assert guesses['Bob']['distance_km'] == 5800.0
    assert guesses['Bob']['cumulative_score'] == 30

    # 2. Non-existent match replay 404
    res_404 = client.get('/api/match/non-existent-match/replay')
    assert res_404.status_code == 404
    assert 'not found' in res_404.json()['detail'].lower()

"""SQLite leaderboard storage, match history tracking, and ranking query engine."""

from __future__ import annotations

import contextlib
import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from src.app_logging import LOGGER_STORAGE, get_logger
from src.models import (
    BaseGameConfig,
    GameMode,
    GameSetupRequest,
    LeaderboardEntry,
    LeaderboardQuery,
    MatchConfig,
    MatchSummaryPlayer,
    MatchSummaryResponse,
    PeopleMode,
    PlayMode,
    RoundLength,
    SupportedLanguage,
)
from src.scoring import accuracy_pct, max_possible_score
from src.storage.db import DatabaseManager

logger = get_logger(LOGGER_STORAGE)

LEADERBOARD_SCHEMA_SQL = """
-- 1. Challenges (Match Seeds for Async & Live Multiplayer)
CREATE TABLE IF NOT EXISTS challenges (
    challenge_id       TEXT PRIMARY KEY,
    capability_token   TEXT UNIQUE NOT NULL,
    title              TEXT,                          -- e.g. "Summer Roadtrip 2024" (NULL = auto-generate)
    creator_name       TEXT NOT NULL,
    libraries_json     TEXT,
    config_json        TEXT NOT NULL,
    asset_ids_json     TEXT NOT NULL,
    created_at         TEXT NOT NULL,
    expires_at         TEXT,                          -- ISO8601 UTC or NULL for Never
    is_active          INTEGER NOT NULL
);

-- 2. Matches (Every finished local, challenge, or room game)
CREATE TABLE IF NOT EXISTS matches (
    match_id           TEXT PRIMARY KEY,
    challenge_id       TEXT,
    room_id            TEXT,                          -- Secure Room Session UUID (if live multiplayer)
    room_name          TEXT,                          -- e.g. "Rafael's Lounge" (optional display name)
    play_mode          TEXT NOT NULL,                 -- 'local', 'challenge', 'room'
    played_at          TEXT NOT NULL,
    libraries_json     TEXT,
    game_mode          TEXT NOT NULL,
    rounds             INTEGER NOT NULL,
    round_length       TEXT NOT NULL,
    player_count       INTEGER NOT NULL,
    location_mode      INTEGER NOT NULL,
    date_mode          INTEGER NOT NULL,
    album_names_json   TEXT,
    album_ids_json     TEXT,
    person_ids_json    TEXT,
    people_mode        TEXT DEFAULT 'ANY',
    countries_json     TEXT,
    cities_json        TEXT,
    min_date           TEXT,
    max_date           TEXT,
    include_shared     INTEGER NOT NULL,
    is_custom_filtered INTEGER NOT NULL,
    filter_summary     TEXT,
    duration_seconds   REAL,
    FOREIGN KEY(challenge_id) REFERENCES challenges(challenge_id) ON DELETE SET NULL
);

-- 3. Match Entries (Player totals, ranks, and response times)
CREATE TABLE IF NOT EXISTS match_entries (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    match_id           TEXT NOT NULL,
    player_name        TEXT NOT NULL,
    location_score     INTEGER,
    date_score         INTEGER,
    total_score        INTEGER NOT NULL,
    max_possible_score INTEGER NOT NULL,
    accuracy_pct       REAL NOT NULL,
    rank               INTEGER NOT NULL,
    is_winner          INTEGER NOT NULL,
    total_time_seconds REAL,                          -- Sum of active question response times
    FOREIGN KEY(match_id) REFERENCES matches(match_id) ON DELETE CASCADE
);

-- 4. Match Round Guesses (Per-photo coordinates, dates, and times)
CREATE TABLE IF NOT EXISTS match_round_guesses (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    match_id           TEXT NOT NULL,
    player_name        TEXT NOT NULL,
    round_index        INTEGER NOT NULL,              -- 0-indexed
    photo_index        INTEGER NOT NULL,              -- 0-indexed (0 for pinpoint; 0, 1, 2 for album shuffle)
    game_mode          TEXT NOT NULL,
    asset_id           TEXT NOT NULL,
    guess_latitude     REAL,
    guess_longitude    REAL,
    actual_latitude    REAL,
    actual_longitude   REAL,
    actual_city        TEXT,
    actual_country     TEXT,
    distance_km        REAL,
    location_points    INTEGER,
    guess_date         TEXT,                          -- 'YYYY-MM-DD'
    actual_date        TEXT,                          -- 'YYYY-MM-DD'
    date_diff_days     INTEGER,
    date_points        INTEGER,
    round_score        INTEGER NOT NULL,              -- sum of location_points + date_points for this photo
    is_correct_location   INTEGER,                    -- 1 if correct, 0 if wrong, NULL for pinpoint
    is_correct_date_order INTEGER,                    -- 1 if correct, 0 if wrong, NULL for pinpoint
    time_taken_seconds REAL,                          -- Time spent answering this specific turn/question
    submitted_at       TEXT NOT NULL,
    FOREIGN KEY(match_id) REFERENCES matches(match_id) ON DELETE CASCADE
);

-- Indices for rapid querying and filtering
CREATE INDEX IF NOT EXISTS idx_matches_played_at ON matches(played_at DESC);
CREATE INDEX IF NOT EXISTS idx_matches_challenge_id ON matches(challenge_id);
CREATE INDEX IF NOT EXISTS idx_matches_room_id ON matches(room_id);
CREATE INDEX IF NOT EXISTS idx_matches_play_mode ON matches(play_mode);
CREATE INDEX IF NOT EXISTS idx_matches_filter_scope ON matches(
    rounds, round_length, location_mode, date_mode, game_mode, is_custom_filtered
);
CREATE INDEX IF NOT EXISTS idx_match_entries_match_id ON match_entries(match_id);
CREATE INDEX IF NOT EXISTS idx_match_entries_player ON match_entries(player_name);
CREATE INDEX IF NOT EXISTS idx_match_entries_accuracy ON match_entries(accuracy_pct DESC, total_score DESC);
CREATE INDEX IF NOT EXISTS idx_match_round_guesses_match ON match_round_guesses(match_id);
CREATE INDEX IF NOT EXISTS idx_challenges_capability ON challenges(capability_token);
"""


def _canonicalize_filter_list(items: list[str] | None) -> str | None:
    """Sort and serialize string list to JSON or return None if empty."""
    if not items:
        return None
    cleaned = [str(x).strip() for x in items if str(x).strip()]
    return json.dumps(sorted(cleaned)) if cleaned else None


def _parse_json_list(val: str | None) -> list[str]:
    """Parse JSON array string to Python list of strings."""
    return json.loads(val) if val else []


def _build_round_history_from_guesses(
    guess_rows: list[dict[str, Any]],
    match_row: dict[str, Any],
) -> list[dict[str, Any]]:
    """Reconstruct round history and album shuffle batch reveal data from stored guess records.

    Returns a list of round objects for match summary replay:
    - Single photo mode (`pinpoint`):
        {round_number, media_url, actual_latitude, actual_longitude,
         actual_year, actual_month, location_mode, game_mode}
    - Batch photo mode (`album_shuffle`):
        Includes above fields plus `batch_reveal`:
        [{photo_id, true_pin_id ('A', 'B', ...), actual_latitude,
          actual_longitude, actual_year, actual_month}, ...]
    """
    if not guess_rows:
        return []

    rounds_by_idx: dict[int, list[dict[str, Any]]] = {}
    for gr in guess_rows:
        r_idx = int(gr['round_index'])
        rounds_by_idx.setdefault(r_idx, []).append(gr)

    round_history: list[dict[str, Any]] = []
    game_mode = match_row['game_mode']
    location_mode = bool(match_row['location_mode'])

    for r_idx in sorted(rounds_by_idx.keys()):
        r_guesses = rounds_by_idx[r_idx]
        first_g = r_guesses[0]

        act_dt = _parse_iso_date(first_g.get('actual_date'))
        round_entry: dict[str, Any] = {
            'round_number': r_idx + 1,
            'media_url': f'/api/media/{first_g["asset_id"]}' if first_g.get('asset_id') else None,
            'actual_latitude': first_g.get('actual_latitude'),
            'actual_longitude': first_g.get('actual_longitude'),
            'actual_date': first_g.get('actual_date'),
            'actual_year': act_dt.year if act_dt else None,
            'actual_month': act_dt.month if act_dt else None,
            'actual_city': first_g.get('actual_city'),
            'actual_country': first_g.get('actual_country'),
            'location_mode': location_mode,
            'game_mode': game_mode,
        }

        if game_mode == 'album_shuffle':
            unique_photos: dict[str, dict[str, Any]] = {}
            for g in r_guesses:
                p_id = g['asset_id']
                if p_id not in unique_photos:
                    p_dt = _parse_iso_date(g.get('actual_date'))
                    p_idx_raw = g.get('photo_index')
                    p_idx = int(p_idx_raw) if p_idx_raw is not None else 0
                    unique_photos[p_id] = {
                        'photo_id': p_id,
                        'true_pin_id': chr(65 + p_idx),
                        'actual_latitude': g.get('actual_latitude'),
                        'actual_longitude': g.get('actual_longitude'),
                        'actual_date': g.get('actual_date'),
                        'actual_year': p_dt.year if p_dt else None,
                        'actual_month': p_dt.month if p_dt else None,
                        'actual_city': g.get('actual_city'),
                        'actual_country': g.get('actual_country'),
                    }
            round_entry['batch_reveal'] = list(unique_photos.values())

        round_history.append(round_entry)

    return round_history


def _parse_iso_date(val: str | None) -> date | None:
    """Parse ISO date string to Python date object or return None."""
    if not val:
        return None
    with contextlib.suppress(Exception):
        return date.fromisoformat(val)
    return None


def _parse_iso_datetime(val: str | None) -> datetime:
    """Parse ISO datetime string to Python datetime object or fallback to UTC now."""
    if val:
        with contextlib.suppress(Exception):
            return datetime.fromisoformat(val)
    return datetime.now(timezone.utc)


class LeaderboardStore:
    """Manages persistent match history, player leaderboards, and detailed round guesses in SQLite."""

    def __init__(self, db_path: Path | DatabaseManager) -> None:
        if isinstance(db_path, DatabaseManager):
            self._db = db_path
        else:
            self._db = DatabaseManager(db_path)
        self._init_db()

    def _init_db(self) -> None:
        self._db.execute_script(LEADERBOARD_SCHEMA_SQL)

    def append_match(
        self,
        match_id: str,
        config: BaseGameConfig | GameSetupRequest,
        player_scores: dict[str, dict[str, int]],
        *,
        play_mode: PlayMode = PlayMode.local,
        challenge_id: str | None = None,
        room_id: str | None = None,
        room_name: str | None = None,
        duration_seconds: float | None = None,
        player_times: dict[str, float] | None = None,
        round_guesses: list[dict[str, Any]] | None = None,
    ) -> None:
        """Persist a completed match with match metadata, player entries, and detailed guesses."""
        played_at = datetime.now(timezone.utc).isoformat()
        is_custom, summary = config.format_filter_summary()

        max_score = max_possible_score(
            config.round_count,
            config.location_mode,
            config.date_mode,
        )

        # Rank players by score descending
        ordered_players = sorted(
            player_scores.keys(),
            key=lambda p: (-player_scores[p].get('total', 0), p.lower()),
        )
        best_total = player_scores[ordered_players[0]].get('total', 0) if ordered_players else 0

        libraries_json = _canonicalize_filter_list(config.libraries)
        album_names_json = _canonicalize_filter_list(config.album_names)
        album_ids_json = _canonicalize_filter_list(config.albums)
        person_ids_json = _canonicalize_filter_list(config.people)
        countries_json = _canonicalize_filter_list(config.countries)
        cities_json = _canonicalize_filter_list(config.cities)

        with self._db.connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO matches (
                    match_id, challenge_id, room_id, room_name, play_mode, played_at,
                    libraries_json, game_mode,
                    rounds, round_length, player_count, location_mode, date_mode,
                    album_names_json, album_ids_json, person_ids_json, people_mode,
                    countries_json, cities_json, min_date, max_date,
                    include_shared, is_custom_filtered, filter_summary, duration_seconds
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    match_id,
                    challenge_id,
                    room_id,
                    room_name,
                    play_mode.value,
                    played_at,
                    libraries_json,
                    config.game_mode.value,
                    config.round_count,
                    config.round_length.value,
                    len(player_scores),
                    1 if config.location_mode else 0,
                    1 if config.date_mode else 0,
                    album_names_json,
                    album_ids_json,
                    person_ids_json,
                    config.people_mode.value,
                    countries_json,
                    cities_json,
                    config.min_date.isoformat() if config.min_date else None,
                    config.max_date.isoformat() if config.max_date else None,
                    1 if config.include_shared else 0,
                    is_custom,
                    summary,
                    duration_seconds,
                ),
            )

            rank = 0
            previous_total: int | None = None
            for idx, player in enumerate(ordered_players):
                scores = player_scores[player]
                total = scores.get('total', 0)
                if previous_total is None or total != previous_total:
                    rank = idx + 1
                    previous_total = total

                is_winner = 1 if total == best_total else 0
                acc_pct = accuracy_pct(total, max_score)
                loc_score = scores.get('location') if config.location_mode else None
                dt_score = scores.get('date') if config.date_mode else None
                total_time = player_times.get(player) if player_times else None

                conn.execute(
                    """
                    INSERT INTO match_entries (
                        match_id, player_name, location_score, date_score,
                        total_score, max_possible_score, accuracy_pct,
                        rank, is_winner, total_time_seconds
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        match_id,
                        player,
                        loc_score,
                        dt_score,
                        total,
                        max_score,
                        acc_pct,
                        rank,
                        is_winner,
                        total_time,
                    ),
                )

            # Insert round guesses if provided
            if round_guesses:
                for rg in round_guesses:
                    conn.execute(
                        """
                        INSERT INTO match_round_guesses (
                            match_id, player_name, round_index, photo_index,
                            game_mode, asset_id, guess_latitude, guess_longitude,
                            actual_latitude, actual_longitude, actual_city, actual_country,
                            distance_km, location_points, guess_date, actual_date,
                            date_diff_days, date_points, round_score,
                            is_correct_location, is_correct_date_order,
                            time_taken_seconds, submitted_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            rg.get('match_id', match_id),
                            rg.get('player_name', ordered_players[0] if ordered_players else 'Player'),
                            rg.get('round_index', 0),
                            rg.get('photo_index', 0),
                            rg.get('game_mode', config.game_mode.value),
                            rg.get('asset_id', ''),
                            rg.get('guess_latitude'),
                            rg.get('guess_longitude'),
                            rg.get('actual_latitude'),
                            rg.get('actual_longitude'),
                            rg.get('actual_city'),
                            rg.get('actual_country'),
                            rg.get('distance_km'),
                            rg.get('location_points'),
                            rg.get('guess_date'),
                            rg.get('actual_date'),
                            rg.get('date_diff_days'),
                            rg.get('date_points'),
                            rg.get('round_score', 0),
                            rg.get('is_correct_location'),
                            rg.get('is_correct_date_order'),
                            rg.get('time_taken_seconds'),
                            rg.get('submitted_at', played_at),
                        ),
                    )

        winners = [p for p in ordered_players if player_scores[p].get('total', 0) == best_total]
        logger.info(
            '🏆 Match %s recorded to leaderboard: %d player(s), winner(s)=%s (best score: %d/%d)',
            match_id,
            len(ordered_players),
            winners,
            best_total,
            max_score,
        )

    def list_entries(
        self,
        query: LeaderboardQuery | None = None,
    ) -> list[LeaderboardEntry]:
        """Query and return sorted leaderboard entries matching the provided filter parameters."""
        q = query or LeaderboardQuery()

        clauses: list[str] = []
        params: list[Any] = []

        # Standard game setup fields
        if q.rounds is not None:
            clauses.append('m.rounds = ?')
            params.append(q.rounds)
        if q.round_length is not None:
            clauses.append('m.round_length = ?')
            params.append(q.round_length.value)
        if q.location_mode is not None:
            clauses.append('m.location_mode = ?')
            params.append(1 if q.location_mode else 0)
        if q.date_mode is not None:
            clauses.append('m.date_mode = ?')
            params.append(1 if q.date_mode else 0)
        if q.game_mode is not None:
            clauses.append('m.game_mode = ?')
            params.append(q.game_mode.value)

        if q.player_name is not None and q.player_name != '':
            clauses.append('e.player_name = ?')
            params.append(q.player_name)
        if q.play_mode is not None:
            clauses.append('m.play_mode = ?')
            params.append(q.play_mode.value)
        if q.challenge_id is not None:
            clauses.append('m.challenge_id = ?')
            params.append(q.challenge_id)
        if q.played_after is not None:
            clauses.append('m.played_at >= ?')
            params.append(f'{q.played_after.isoformat()}T00:00:00')
        if q.played_before is not None:
            clauses.append('m.played_at <= ?')
            params.append(f'{q.played_before.isoformat()}T23:59:59.999')
        if q.is_custom_filtered is not None:
            clauses.append('m.is_custom_filtered = ?')
            params.append(1 if q.is_custom_filtered else 0)

        # Check if caller specified any filter scope dimension
        has_filter_scope = bool(
            q.libraries
            or q.albums
            or q.countries
            or q.cities
            or q.people
            or q.min_date
            or q.max_date
            or q.include_shared
        )

        if q.exact_filter_match and has_filter_scope:
            # Exact preset isolation: all filter dimensions are strictly constrained
            libs_json = _canonicalize_filter_list(q.libraries)
            if libs_json:
                clauses.append('m.libraries_json = ?')
                params.append(libs_json)
            else:
                clauses.append('m.libraries_json IS NULL')

            aid_json = _canonicalize_filter_list(q.albums)
            if aid_json:
                clauses.append('m.album_ids_json = ?')
                params.append(aid_json)
            else:
                clauses.append('m.album_ids_json IS NULL')

            c_json = _canonicalize_filter_list(q.countries)
            if c_json:
                clauses.append('m.countries_json = ?')
                params.append(c_json)
            else:
                clauses.append('m.countries_json IS NULL')

            ci_json = _canonicalize_filter_list(q.cities)
            if ci_json:
                clauses.append('m.cities_json = ?')
                params.append(ci_json)
            else:
                clauses.append('m.cities_json IS NULL')

            p_json = _canonicalize_filter_list(q.people)
            if p_json:
                clauses.append('m.person_ids_json = ?')
                params.append(p_json)
                if q.people_mode is not None and len(_parse_json_list(p_json)) > 1:
                    clauses.append('m.people_mode = ?')
                    params.append(q.people_mode.value)
            else:
                clauses.append('m.person_ids_json IS NULL')

            if q.min_date is not None:
                clauses.append('m.min_date = ?')
                params.append(q.min_date.isoformat())
            else:
                clauses.append('m.min_date IS NULL')

            if q.max_date is not None:
                clauses.append('m.max_date = ?')
                params.append(q.max_date.isoformat())
            else:
                clauses.append('m.max_date IS NULL')

            if q.include_shared:
                clauses.append('m.include_shared = 1')
            else:
                clauses.append('(m.include_shared IS NULL OR m.include_shared = 0)')
        else:
            # Loose querying: only add conditions for explicitly provided filters
            libs_json = _canonicalize_filter_list(q.libraries)
            if libs_json:
                clauses.append('m.libraries_json = ?')
                params.append(libs_json)

            aid_json = _canonicalize_filter_list(q.albums)
            if aid_json:
                clauses.append('m.album_ids_json = ?')
                params.append(aid_json)

            if q.countries:
                c_json = _canonicalize_filter_list(q.countries)
                if c_json:
                    clauses.append('m.countries_json = ?')
                    params.append(c_json)

            if q.cities:
                ci_json = _canonicalize_filter_list(q.cities)
                if ci_json:
                    clauses.append('m.cities_json = ?')
                    params.append(ci_json)

            if q.people:
                p_json = _canonicalize_filter_list(q.people)
                if p_json:
                    clauses.append('m.person_ids_json = ?')
                    params.append(p_json)
                    if q.people_mode is not None:
                        clauses.append('m.people_mode = ?')
                        params.append(q.people_mode.value)

            if q.min_date is not None:
                clauses.append('m.min_date = ?')
                params.append(q.min_date.isoformat())

            if q.max_date is not None:
                clauses.append('m.max_date = ?')
                params.append(q.max_date.isoformat())

            if q.include_shared:
                clauses.append('m.include_shared = ?')
                params.append(1 if q.include_shared else 0)

        where_sql = f'WHERE {" AND ".join(clauses)}' if clauses else ''
        limit_sql = f'LIMIT {int(q.limit)}' if q.limit is not None and q.limit > 0 else ''

        sql = f"""
        SELECT
            e.match_id,
            m.played_at,
            e.player_name,
            e.location_score,
            e.date_score,
            e.total_score,
            e.max_possible_score,
            e.accuracy_pct,
            e.rank,
            e.is_winner,
            e.total_time_seconds,
            m.rounds,
            m.round_length,
            m.location_mode,
            m.date_mode,
            m.game_mode,
            m.libraries_json,
            m.album_names_json,
            m.album_ids_json,
            m.person_ids_json,
            m.people_mode,
            m.countries_json,
            m.cities_json,
            m.min_date,
            m.max_date,
            m.include_shared,
            m.is_custom_filtered,
            m.filter_summary,
            m.duration_seconds,
            m.play_mode,
            m.challenge_id,
            m.room_id,
            m.room_name,
            c.title AS challenge_title
        FROM match_entries e
        JOIN matches m ON e.match_id = m.match_id
        LEFT JOIN challenges c ON m.challenge_id = c.challenge_id
        {where_sql}
        ORDER BY e.accuracy_pct DESC, e.total_score DESC, m.played_at DESC, e.rank ASC
        {limit_sql}
        """

        rows = self._db.fetch_all(sql, params)
        entries: list[LeaderboardEntry] = []

        for row in rows:
            config = MatchConfig(
                round_count=row['rounds'],
                round_length=RoundLength(row['round_length']),
                location_mode=bool(row['location_mode']),
                date_mode=bool(row['date_mode']),
                game_mode=GameMode(row['game_mode']),
                libraries=_parse_json_list(row['libraries_json']),
                albums=_parse_json_list(row['album_ids_json']),
                people=_parse_json_list(row['person_ids_json']),
                album_names=_parse_json_list(row['album_names_json']),
                people_mode=PeopleMode(row['people_mode']) if row['people_mode'] else PeopleMode.ANY,
                countries=_parse_json_list(row['countries_json']),
                cities=_parse_json_list(row['cities_json']),
                min_date=_parse_iso_date(row.get('min_date')),
                max_date=_parse_iso_date(row.get('max_date')),
                include_shared=bool(row['include_shared']),
            )

            entries.append(
                LeaderboardEntry(
                    match_id=row['match_id'],
                    played_at=_parse_iso_datetime(row.get('played_at')),
                    player_name=row['player_name'],
                    total_score=row['total_score'],
                    max_possible_score=row['max_possible_score'],
                    accuracy_pct=float(row['accuracy_pct']),
                    rank=int(row['rank']),
                    is_winner=bool(row['is_winner']),
                    game_mode=GameMode(row['game_mode']),
                    rounds=int(row['rounds']),
                    play_mode=PlayMode(row['play_mode']),
                    is_custom_filtered=bool(row['is_custom_filtered']),
                    config=config,
                    location_score=row['location_score'],
                    date_score=row['date_score'],
                    total_time_seconds=row['total_time_seconds'],
                    duration_seconds=row['duration_seconds'],
                    filter_summary=row['filter_summary'],
                    challenge_id=row['challenge_id'],
                    challenge_title=row['challenge_title'],
                    room_id=row['room_id'],
                    room_name=row['room_name'],
                )
            )

        return entries

    def is_asset_recorded(self, asset_id: str) -> bool:
        """Check if an asset was used in any recorded match."""
        row = self._db.fetch_one(
            'SELECT 1 FROM match_round_guesses WHERE asset_id = ? LIMIT 1',
            (asset_id,),
        )
        return row is not None

    def get_match_summary(self, match_id: str, language: str | None = None) -> MatchSummaryResponse | None:
        """Retrieve full match replay data and podium summary from SQLite."""
        match_row = self._db.fetch_one('SELECT * FROM matches WHERE match_id = ?', (match_id,))
        if not match_row:
            return None

        entry_rows = self._db.fetch_all(
            'SELECT * FROM match_entries WHERE match_id = ? ORDER BY rank ASC, player_name ASC',
            (match_id,),
        )
        winners = [r['player_name'] for r in entry_rows if r['is_winner']]

        players = [
            MatchSummaryPlayer(
                player_name=r['player_name'],
                location_score=r['location_score'],
                date_score=r['date_score'],
                total_score=r['total_score'],
                max_possible_score=r['max_possible_score'],
                accuracy_pct=r['accuracy_pct'],
                rank=r['rank'],
                is_winner=bool(r['is_winner']),
            )
            for r in entry_rows
        ]

        guess_rows = self._db.fetch_all(
            'SELECT * FROM match_round_guesses WHERE match_id = ? '
            'ORDER BY round_index ASC, photo_index ASC, player_name ASC',
            (match_id,),
        )
        round_history = _build_round_history_from_guesses(guess_rows, match_row)

        filter_tooltip = None
        if match_row['is_custom_filtered']:
            lang_enum = SupportedLanguage.from_str(language) if language else SupportedLanguage.EN
            setup_obj = GameSetupRequest(
                round_count=int(match_row['rounds']),
                players=[p.player_name for p in players] if players else ['Player 1'],
                game_mode=GameMode(match_row['game_mode']),
                libraries=_parse_json_list(match_row['libraries_json']),
                album_names=_parse_json_list(match_row['album_names_json']),
                countries=_parse_json_list(match_row['countries_json']),
                cities=_parse_json_list(match_row['cities_json']),
                min_date=_parse_iso_date(match_row.get('min_date')),
                max_date=_parse_iso_date(match_row.get('max_date')),
                include_shared=bool(match_row['include_shared']),
            )
            filter_tooltip = setup_obj.format_filter_tooltip(language=lang_enum)

        return MatchSummaryResponse(
            match_id=match_row['match_id'],
            rounds_played=int(match_row['rounds']),
            location_mode=bool(match_row['location_mode']),
            date_mode=bool(match_row['date_mode']),
            game_mode=GameMode(match_row['game_mode']),
            libraries=_parse_json_list(match_row['libraries_json']),
            album_names=_parse_json_list(match_row['album_names_json']),
            finished=True,
            winners=winners,
            players=players,
            filter_summary=match_row['filter_summary'],
            filter_tooltip=filter_tooltip,
            is_custom_filtered=bool(match_row['is_custom_filtered']),
            round_history=round_history if round_history else None,
        )

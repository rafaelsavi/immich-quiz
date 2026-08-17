from __future__ import annotations

import json
import logging
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from src.models import GameMode, LeaderboardEntry, PeopleMode, PlayMode, RoundLength
from src.scoring import accuracy_pct, max_possible_score
from src.storage.db import DatabaseManager

logger = logging.getLogger(__name__)

LEADERBOARD_SCHEMA_SQL = """
-- 1. Challenges (Match Seeds for Async & Live Multiplayer)
CREATE TABLE IF NOT EXISTS challenges (
    challenge_id       TEXT PRIMARY KEY,
    capability_token   TEXT UNIQUE NOT NULL,
    creator_name       TEXT NOT NULL,
    library_name       TEXT NOT NULL,
    config_json        TEXT NOT NULL,
    asset_ids_json     TEXT NOT NULL,
    created_at         TEXT NOT NULL,
    expires_at         TEXT,                          -- ISO8601 UTC or NULL for Never
    is_active          INTEGER NOT NULL DEFAULT 1
);

-- 2. Matches (Every finished local, challenge, or room game)
CREATE TABLE IF NOT EXISTS matches (
    match_id           TEXT PRIMARY KEY,
    challenge_id       TEXT,
    play_mode          TEXT NOT NULL DEFAULT 'local',  -- 'local', 'challenge', 'room'
    played_at          TEXT NOT NULL,
    library_name       TEXT NOT NULL,
    game_mode          TEXT NOT NULL,
    rounds             INTEGER NOT NULL,
    round_length       TEXT NOT NULL,
    location_mode      INTEGER NOT NULL,
    date_mode          INTEGER NOT NULL,
    album_name         TEXT,
    album_ids_json     TEXT,
    person_ids_json    TEXT,
    people_mode        TEXT DEFAULT 'ANY',
    countries_json     TEXT,
    cities_json        TEXT,
    min_date           TEXT,
    max_date           TEXT,
    is_custom_filtered INTEGER NOT NULL DEFAULT 0,
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
    rank               INTEGER NOT NULL DEFAULT 1,
    is_winner          INTEGER NOT NULL DEFAULT 0,
    total_time_seconds REAL,                          -- Sum of active question response times
    FOREIGN KEY(match_id) REFERENCES matches(match_id) ON DELETE CASCADE
);

-- 4. Match Round Guesses (Per-photo coordinates, dates, and times)
CREATE TABLE IF NOT EXISTS match_round_guesses (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    match_id           TEXT NOT NULL,
    player_name        TEXT NOT NULL,
    round_index        INTEGER NOT NULL,              -- 0-indexed
    photo_index        INTEGER NOT NULL DEFAULT 0,    -- 0-indexed (0 for pinpoint; 0, 1, 2 for album shuffle)
    asset_id           TEXT NOT NULL,
    guess_latitude     REAL,
    guess_longitude    REAL,
    actual_latitude    REAL,
    actual_longitude   REAL,
    distance_km        REAL,
    location_points    INTEGER,
    guess_date         TEXT,                          -- YYYY-MM-DD
    actual_date        TEXT,                          -- YYYY-MM-DD
    date_diff_days     INTEGER,
    date_points        INTEGER,
    round_score        INTEGER NOT NULL,
    time_taken_seconds REAL,                          -- Active seconds on question screen
    submitted_at       TEXT NOT NULL,
    FOREIGN KEY(match_id) REFERENCES matches(match_id) ON DELETE CASCADE
);

-- Optimized Indexes
CREATE INDEX IF NOT EXISTS idx_matches_played_at   ON matches(played_at DESC);
CREATE INDEX IF NOT EXISTS idx_matches_library     ON matches(library_name);
CREATE INDEX IF NOT EXISTS idx_matches_challenge   ON matches(challenge_id);
CREATE INDEX IF NOT EXISTS idx_matches_play_mode   ON matches(play_mode);

CREATE INDEX IF NOT EXISTS idx_entries_match       ON match_entries(match_id);
CREATE INDEX IF NOT EXISTS idx_entries_player      ON match_entries(player_name);
CREATE INDEX IF NOT EXISTS idx_entries_ranking     ON match_entries(accuracy_pct DESC, total_score DESC);

CREATE INDEX IF NOT EXISTS idx_guesses_match_round ON match_round_guesses(match_id, round_index, photo_index);
CREATE INDEX IF NOT EXISTS idx_guesses_player      ON match_round_guesses(player_name);
CREATE INDEX IF NOT EXISTS idx_guesses_asset       ON match_round_guesses(asset_id);

CREATE INDEX IF NOT EXISTS idx_challenges_token    ON challenges(capability_token);
CREATE INDEX IF NOT EXISTS idx_challenges_expires  ON challenges(expires_at);
"""


def format_filter_summary(
    *,
    album_name: str | None = None,
    album_ids: list[str] | None = None,
    countries: list[str] | None = None,
    cities: list[str] | None = None,
    person_ids: list[str] | None = None,
    min_date: date | None = None,
    max_date: date | None = None,
) -> tuple[int, str]:
    """Return (is_custom_filtered, summary_str) based on active filter parameters."""
    parts: list[str] = []

    if album_ids or (album_name and album_name != '-'):
        parts.append(album_name if album_name and album_name != '-' else f'{len(album_ids or [])} albums')
    if countries:
        parts.append(', '.join(countries) if len(countries) <= 2 else f'{len(countries)} countries')
    if cities:
        parts.append(', '.join(cities) if len(cities) <= 2 else f'{len(cities)} cities')
    if person_ids:
        parts.append(f'{len(person_ids)} people' if len(person_ids) > 1 else '1 person')
    if min_date or max_date:
        if min_date and max_date:
            parts.append(f'{min_date.strftime("%Y/%m")} - {max_date.strftime("%Y/%m")}')
        elif min_date:
            parts.append(f'from {min_date.strftime("%Y/%m")}')
        elif max_date:
            parts.append(f'until {max_date.strftime("%Y/%m")}')

    if not parts:
        return 0, 'Full Library'
    return 1, ' • '.join(parts)


class LeaderboardStore:
    def __init__(
        self,
        db: DatabaseManager | Path,
    ) -> None:
        if isinstance(db, Path):
            self._db = DatabaseManager(db)
        else:
            self._db = db
        self._init_schema()

    def _init_schema(self) -> None:
        self._db.execute_script(LEADERBOARD_SCHEMA_SQL)

    def append_match(
        self,
        match_id: str,
        library_name: str,
        album_name: str,
        rounds_played: int,
        round_length: RoundLength,
        location_mode: bool,
        date_mode: bool,
        game_mode: GameMode,
        player_scores: dict[str, dict[str, int]],
        *,
        album_ids: list[str] | None = None,
        person_ids: list[str] | None = None,
        people_mode: PeopleMode = PeopleMode.ANY,
        countries: list[str] | None = None,
        cities: list[str] | None = None,
        min_date: date | None = None,
        max_date: date | None = None,
        play_mode: PlayMode = PlayMode.local,
        challenge_id: str | None = None,
        duration_seconds: float | None = None,
        player_times: dict[str, float] | None = None,
        round_guesses: list[dict[str, Any]] | None = None,
    ) -> None:
        played_at = datetime.now(timezone.utc).isoformat()
        is_custom, summary = format_filter_summary(
            album_name=album_name,
            album_ids=album_ids,
            countries=countries,
            cities=cities,
            person_ids=person_ids,
            min_date=min_date,
            max_date=max_date,
        )

        max_score = max_possible_score(
            rounds_played,
            location_mode,
            date_mode,
        )

        # Rank players by score descending
        ordered_players = sorted(
            player_scores.keys(),
            key=lambda p: (-player_scores[p].get('total', 0), p.lower()),
        )
        best_total = player_scores[ordered_players[0]].get('total', 0) if ordered_players else 0

        with self._db.connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO matches (
                    match_id, challenge_id, play_mode, played_at, library_name, game_mode,
                    rounds, round_length, location_mode, date_mode,
                    album_name, album_ids_json, person_ids_json, people_mode,
                    countries_json, cities_json, min_date, max_date,
                    is_custom_filtered, filter_summary, duration_seconds
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    match_id,
                    challenge_id,
                    play_mode.value,
                    played_at,
                    library_name,
                    game_mode.value,
                    rounds_played,
                    round_length.value,
                    1 if location_mode else 0,
                    1 if date_mode else 0,
                    album_name or '-',
                    json.dumps(album_ids) if album_ids else None,
                    json.dumps(person_ids) if person_ids else None,
                    people_mode.value,
                    json.dumps(countries) if countries else None,
                    json.dumps(cities) if cities else None,
                    min_date.isoformat() if min_date else None,
                    max_date.isoformat() if max_date else None,
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
                loc_score = scores.get('location') if location_mode else None
                dt_score = scores.get('date') if date_mode else None
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

            if round_guesses:
                for rg in round_guesses:
                    conn.execute(
                        """
                        INSERT INTO match_round_guesses (
                            match_id, player_name, round_index, photo_index,
                            asset_id, guess_latitude, guess_longitude,
                            actual_latitude, actual_longitude, distance_km,
                            location_points, guess_date, actual_date,
                            date_diff_days, date_points, round_score,
                            time_taken_seconds, submitted_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            rg.get('match_id', match_id),
                            rg['player_name'],
                            rg['round_index'],
                            rg.get('photo_index', 0),
                            rg['asset_id'],
                            rg.get('guess_latitude'),
                            rg.get('guess_longitude'),
                            rg.get('actual_latitude'),
                            rg.get('actual_longitude'),
                            rg.get('distance_km'),
                            rg.get('location_points'),
                            rg.get('guess_date'),
                            rg.get('actual_date'),
                            rg.get('date_diff_days'),
                            rg.get('date_points'),
                            rg.get('round_score', 0),
                            rg.get('time_taken_seconds'),
                            rg.get('submitted_at', played_at),
                        ),
                    )

    def list_entries(
        self,
        *,
        rounds: int | None = None,
        round_length: RoundLength | None = None,
        location_mode: bool | None = None,
        date_mode: bool | None = None,
        game_mode: GameMode | None = None,
        library: str | None = None,
        albums: str | None = None,
        player_name: str | None = None,
        is_custom_filtered: bool | None = None,
        limit: int | None = None,
    ) -> list[LeaderboardEntry]:
        clauses: list[str] = []
        params: list[Any] = []

        if rounds is not None:
            clauses.append('m.rounds = ?')
            params.append(rounds)
        if round_length is not None:
            clauses.append('m.round_length = ?')
            params.append(round_length.value)
        if location_mode is not None:
            clauses.append('m.location_mode = ?')
            params.append(1 if location_mode else 0)
        if date_mode is not None:
            clauses.append('m.date_mode = ?')
            params.append(1 if date_mode else 0)
        if game_mode is not None:
            clauses.append('m.game_mode = ?')
            params.append(game_mode.value)
        if library is not None and library != '':
            clauses.append('m.library_name = ?')
            params.append(library)
        if albums is not None and albums != '':
            clauses.append('m.album_name = ?')
            params.append(albums)
        if player_name is not None and player_name != '':
            clauses.append('e.player_name = ?')
            params.append(player_name)
        if is_custom_filtered is not None:
            clauses.append('m.is_custom_filtered = ?')
            params.append(1 if is_custom_filtered else 0)

        where_sql = f'WHERE {" AND ".join(clauses)}' if clauses else ''
        limit_sql = f'LIMIT {int(limit)}' if limit is not None and limit > 0 else ''

        query = f"""
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
            m.library_name,
            m.album_name,
            m.album_ids_json,
            m.person_ids_json,
            m.people_mode,
            m.countries_json,
            m.cities_json,
            m.min_date,
            m.max_date,
            m.is_custom_filtered,
            m.filter_summary,
            m.duration_seconds
        FROM match_entries e
        JOIN matches m ON e.match_id = m.match_id
        {where_sql}
        ORDER BY m.played_at DESC, e.rank ASC
        {limit_sql}
        """

        rows = self._db.fetch_all(query, params)
        entries: list[LeaderboardEntry] = []

        for row in rows:
            album_ids = json.loads(row['album_ids_json']) if row['album_ids_json'] else []
            person_ids = json.loads(row['person_ids_json']) if row['person_ids_json'] else []
            countries = json.loads(row['countries_json']) if row['countries_json'] else []
            cities = json.loads(row['cities_json']) if row['cities_json'] else []

            config = {
                'rounds': row['rounds'],
                'round_length': row['round_length'],
                'location_mode': bool(row['location_mode']),
                'date_mode': bool(row['date_mode']),
                'game_mode': row['game_mode'],
                'library': row['library_name'],
                'albums': row['album_name'] or '-',
                'album_ids': album_ids,
                'person_ids': person_ids,
                'people_mode': row['people_mode'] or 'ANY',
                'countries': countries,
                'cities': cities,
                'min_date': row['min_date'],
                'max_date': row['max_date'],
            }

            entries.append(
                LeaderboardEntry(
                    match_id=row['match_id'],
                    played_at=datetime.fromisoformat(row['played_at']),
                    player_name=row['player_name'],
                    location_score=row['location_score'],
                    date_score=row['date_score'],
                    total_score=row['total_score'],
                    max_possible_score=row['max_possible_score'],
                    accuracy_pct=float(row['accuracy_pct']),
                    rank=int(row['rank']),
                    is_winner=bool(row['is_winner']),
                    filter_summary=row['filter_summary'],
                    is_custom_filtered=bool(row['is_custom_filtered']),
                    config=config,
                )
            )

        return entries

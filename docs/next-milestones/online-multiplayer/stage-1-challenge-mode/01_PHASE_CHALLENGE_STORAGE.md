# Phase 1: Challenge Storage & Data Models

> **Prerequisites**: Ensure the completed Day-1 4-table schema is in place. Read [`00_OVERVIEW.md`](../00_OVERVIEW.md) first.

## Goal

1. Implement `ChallengeStore` in `src/storage/challenge.py` for creating, querying, and managing challenge seeds and player session tokens.
2. Extend `LeaderboardStore` in `src/storage/leaderboard.py` to query challenge standings, participant counts, and per-round guesses under Fog of War.
3. Add challenge-related Pydantic models to `src/models.py`.

---

## 1. Schema DDL (Clean Day-1 Architecture)

The unified 4-table DDL is established in `src/storage/leaderboard.py`:

```sql
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
    is_active          INTEGER NOT NULL DEFAULT 1
);

-- 2. Matches (Every finished local, challenge, or room game)
CREATE TABLE IF NOT EXISTS matches (
    match_id           TEXT PRIMARY KEY,
    challenge_id       TEXT,
    room_id            TEXT,                          -- Secure Room Session UUID (if live multiplayer)
    room_name          TEXT,                          -- e.g. "Rafael's Lounge" (optional display name)
    play_mode          TEXT NOT NULL DEFAULT 'local',  -- 'local', 'challenge', 'room'
    played_at          TEXT NOT NULL,
    libraries_json     TEXT,
    game_mode          TEXT NOT NULL,
    rounds             INTEGER NOT NULL,
    round_length       TEXT NOT NULL,
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
    include_shared     INTEGER NOT NULL DEFAULT 0,
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
```

---

## 2. File: `src/storage/challenge.py`

Create `ChallengeStore` with the following implementation:

```python
from __future__ import annotations

import json
import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from src.storage.db import DatabaseManager

logger = logging.getLogger(__name__)


class ChallengeStore:
    def __init__(self, db: DatabaseManager) -> None:
        self._db = db
        # In-memory session token mapping: session_token -> session_dict
        self._sessions: dict[str, dict[str, Any]] = {}

    def create_challenge(
        self,
        creator_name: str,
        library_name: str,
        config: dict[str, Any],
        asset_ids: list[str],
        title: str | None = None,
        expires_in_hours: int | None = 24,
    ) -> dict[str, Any]:
        challenge_id = f'ch_{uuid4().hex[:12]}'
        capability_token = secrets.token_urlsafe(16)
        created_at = datetime.now(timezone.utc)
        expires_at = (created_at + timedelta(hours=expires_in_hours)).isoformat() if expires_in_hours else None

        with self._db.connection() as conn:
            conn.execute(
                """
                INSERT INTO challenges (
                    challenge_id, capability_token, title, creator_name, library_name,
                    config_json, asset_ids_json, created_at, expires_at, is_active
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
                """,
                (
                    challenge_id,
                    capability_token,
                    title,
                    creator_name,
                    library_name,
                    json.dumps(config),
                    json.dumps(asset_ids),
                    created_at.isoformat(),
                    expires_at,
                ),
            )

        return {
            'challenge_id': challenge_id,
            'capability_token': capability_token,
            'title': title,
            'creator_name': creator_name,
            'library_name': library_name,
            'config': config,
            'asset_ids': asset_ids,
            'created_at': created_at.isoformat(),
            'expires_at': expires_at,
            'is_active': True,
        }

    def get_challenge_by_token(self, capability_token: str) -> dict[str, Any] | None:
        row = self._db.fetch_one(
            'SELECT * FROM challenges WHERE capability_token = ?',
            (capability_token,),
        )
        if not row:
            return None

        # Check expiration
        if row['expires_at']:
            exp = datetime.fromisoformat(row['expires_at'])
            if datetime.now(timezone.utc) > exp:
                return None  # Expired

        if not row['is_active']:
            return None

        return {
            'challenge_id': row['challenge_id'],
            'capability_token': row['capability_token'],
            'creator_name': row['creator_name'],
            'library_name': row['library_name'],
            'config': json.loads(row['config_json']),
            'asset_ids': json.loads(row['asset_ids_json']),
            'created_at': row['created_at'],
            'expires_at': row['expires_at'],
            'is_active': bool(row['is_active']),
        }

    def create_player_session(
        self,
        challenge_id: str,
        capability_token: str,
        player_name: str,
    ) -> dict[str, Any]:
        """Create an active attempt session token for a player."""
        session_token = secrets.token_urlsafe(24)
        match_id = f'ch_match_{uuid4().hex[:12]}'
        session_data = {
            'session_token': session_token,
            'match_id': match_id,
            'challenge_id': challenge_id,
            'capability_token': capability_token,
            'player_name': player_name,
            'current_round': 0,
            'started_at': datetime.now(timezone.utc).isoformat(),
            'completed_rounds': 0,
            'total_score': 0,
            'total_time_seconds': 0.0,
        }
        self._sessions[session_token] = session_data
        return session_data

    def get_player_session(self, session_token: str) -> dict[str, Any] | None:
        return self._sessions.get(session_token)

    def is_asset_in_active_challenge(self, asset_id: str) -> bool:
        """Verify if an asset is registered to any currently active challenge (for /media proxying)."""
        now_iso = datetime.now(timezone.utc).isoformat()
        rows = self._db.fetch_all(
            """
            SELECT asset_ids_json FROM challenges
            WHERE is_active = 1 AND (expires_at IS NULL OR expires_at > ?)
            """,
            (now_iso,),
        )
        for row in rows:
            asset_ids = json.loads(row['asset_ids_json'])
            if asset_id in asset_ids:
                return True
        return False
```

---

## 3. Pydantic Models in `src/models.py`

```python
# --- Challenge & Async Multiplayer Models ---


class ChallengeExpirationOption(str, Enum):
    ONE_HOUR = '1h'
    SIX_HOURS = '6h'
    TWENTY_FOUR_HOURS = '24h'
    FORTY_EIGHT_HOURS = '48h'
    SEVEN_DAYS = '7d'
    NEVER = 'never'


class ChallengeCreateRequest(BaseGameConfig):
    creator_name: str = Field(min_length=1, max_length=50)
    expires_in_hours: int | None = Field(default=24, ge=1, le=8760)  # None = Never


class ChallengeCreateResponse(BaseModel):
    challenge_id: str
    capability_token: str
    play_url: str
    creator_name: str
    libraries: list[str] = Field(default_factory=list)
    rounds: int
    expires_at: datetime | None


class ChallengeDetailResponse(BaseModel):
    challenge_id: str
    capability_token: str
    creator_name: str
    libraries: list[str] = Field(default_factory=list)
    rounds: int
    round_length: str
    location_mode: bool
    date_mode: bool
    game_mode: str
    filter_summary: str
    created_at: datetime
    expires_at: datetime | None
    total_participants: int


class ChallengeStartRequest(BaseModel):
    player_name: str = Field(min_length=1, max_length=50)


class ChallengeStartResponse(BaseModel):
    session_token: str
    match_id: str
    player_name: str
    total_rounds: int
    current_round: int


class ChallengeQuestionResponse(BaseModel):
    round_index: int
    total_rounds: int
    asset_id: str
    game_mode: str
    location_mode: bool
    date_mode: bool
    round_length: str


class ChallengeAnswerRequest(BaseModel):
    round_index: int
    guess_latitude: float | None = None
    guess_longitude: float | None = None
    guess_date: str | None = None
    time_taken_seconds: float = Field(ge=0.0)


class ChallengeRoundGuessData(BaseModel):
    player_name: str
    round_index: int
    guess_latitude: float | None = None
    guess_longitude: float | None = None
    actual_latitude: float | None = None
    actual_longitude: float | None = None
    distance_km: float | None = None
    location_points: int | None = None
    guess_date: str | None = None
    actual_date: str | None = None
    date_diff_days: int | None = None
    date_points: int | None = None
    round_score: int
    time_taken_seconds: float


class ChallengeLeaderboardEntry(BaseModel):
    player_name: str
    total_score: int
    max_possible_score: int
    accuracy_pct: float
    rank: int
    is_winner: bool
    total_time_seconds: float
    completed_rounds: int
    awards: list[str] = Field(default_factory=list)


class ChallengeLeaderboardResponse(BaseModel):
    challenge_id: str
    up_to_round: int
    is_game_over: bool
    leaderboard: list[ChallengeLeaderboardEntry]
    round_guesses: list[ChallengeRoundGuessData]
```

---

## Acceptance Criteria

1. Running `pytest` validates that `LEADERBOARD_SCHEMA_SQL` initializes without errors.
2. `ChallengeStore.create_challenge()` persists challenge configuration with custom `expires_in_hours`.
3. Expired challenges return `None` when queried via `get_challenge_by_token()`.
4. `is_asset_in_active_challenge()` correctly validates asset accessibility for `/media/` proxying.

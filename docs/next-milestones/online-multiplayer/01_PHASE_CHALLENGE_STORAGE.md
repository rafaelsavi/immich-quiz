# Phase 1: Challenge Storage & Data Models

> **Prerequisites**: Read `00_OVERVIEW.md` first.

## Goal

1. Implement the clean 4-table SQLite schema in `src/storage/leaderboard.py` (or `src/storage/challenge.py`).
2. Add `ChallengeStore` for creating, querying, and managing challenge seeds and player attempt records.
3. Add challenge-related Pydantic models to `src/models.py`.

---

## 1. Schema DDL (Clean Day-1 Architecture)

Update `LEADERBOARD_SCHEMA_SQL` in `src/storage/leaderboard.py` with the unified 4-table DDL:

```sql
-- 1. Challenges (Match Seeds for Async & Live Multiplayer)
CREATE TABLE IF NOT EXISTS challenges (
    challenge_id TEXT PRIMARY KEY,
    capability_token TEXT UNIQUE NOT NULL,
    creator_name TEXT NOT NULL,
    library_name TEXT NOT NULL,
    config_json TEXT NOT NULL,
    asset_ids_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    expires_at TEXT,                          -- ISO8601 UTC or NULL for Never
    is_active INTEGER NOT NULL DEFAULT 1
);

-- 2. Matches (Every finished local, challenge, or room game)
CREATE TABLE IF NOT EXISTS matches (
    match_id TEXT PRIMARY KEY,
    challenge_id TEXT,
    play_mode TEXT NOT NULL DEFAULT 'local',  -- 'local', 'challenge', 'room'
    played_at TEXT NOT NULL,
    library_name TEXT NOT NULL,
    game_mode TEXT NOT NULL,
    rounds INTEGER NOT NULL,
    round_length TEXT NOT NULL,
    location_mode INTEGER NOT NULL,
    date_mode INTEGER NOT NULL,
    album_name TEXT,
    album_ids_json TEXT,
    person_ids_json TEXT,
    people_mode TEXT DEFAULT 'ANY',
    countries_json TEXT,
    cities_json TEXT,
    min_date TEXT,
    max_date TEXT,
    is_custom_filtered INTEGER NOT NULL DEFAULT 0,
    filter_summary TEXT,
    duration_seconds REAL,
    FOREIGN KEY(challenge_id) REFERENCES challenges(challenge_id) ON DELETE SET NULL
);

-- 3. Match Entries (Player totals, ranks, and awards)
CREATE TABLE IF NOT EXISTS match_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    match_id TEXT NOT NULL,
    player_name TEXT NOT NULL,
    location_score INTEGER,
    date_score INTEGER,
    total_score INTEGER NOT NULL,
    max_possible_score INTEGER NOT NULL,
    accuracy_pct REAL NOT NULL,
    rank INTEGER NOT NULL DEFAULT 1,
    is_winner INTEGER NOT NULL DEFAULT 0,
    total_time_seconds REAL,                  -- Sum of active question response times
    awards_json TEXT,
    FOREIGN KEY(match_id) REFERENCES matches(match_id) ON DELETE CASCADE
);

-- 4. Match Round Guesses (Per-round coordinates, dates, and times)
CREATE TABLE IF NOT EXISTS match_round_guesses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    match_id TEXT NOT NULL,
    player_name TEXT NOT NULL,
    round_index INTEGER NOT NULL,             -- 0-indexed
    asset_id TEXT NOT NULL,
    guess_latitude REAL,
    guess_longitude REAL,
    actual_latitude REAL,
    actual_longitude REAL,
    distance_km REAL,
    location_points INTEGER,
    guess_date TEXT,                          -- YYYY-MM-DD
    actual_date TEXT,                         -- YYYY-MM-DD
    date_diff_days INTEGER,
    date_points INTEGER,
    round_score INTEGER NOT NULL,
    time_taken_seconds REAL,                  -- Active seconds on question screen
    submitted_at TEXT NOT NULL,
    FOREIGN KEY(match_id) REFERENCES matches(match_id) ON DELETE CASCADE
);

-- Optimized Indexes
CREATE INDEX IF NOT EXISTS idx_matches_played_at ON matches(played_at DESC);
CREATE INDEX IF NOT EXISTS idx_matches_library ON matches(library_name);
CREATE INDEX IF NOT EXISTS idx_matches_challenge ON matches(challenge_id);
CREATE INDEX IF NOT EXISTS idx_matches_play_mode ON matches(play_mode);

CREATE INDEX IF NOT EXISTS idx_entries_match ON match_entries(match_id);
CREATE INDEX IF NOT EXISTS idx_entries_player ON match_entries(player_name);
CREATE INDEX IF NOT EXISTS idx_entries_ranking ON match_entries(accuracy_pct DESC, total_score DESC);

CREATE INDEX IF NOT EXISTS idx_guesses_match_round ON match_round_guesses(match_id, round_index);
CREATE INDEX IF NOT EXISTS idx_guesses_player ON match_round_guesses(player_name);
CREATE INDEX IF NOT EXISTS idx_guesses_asset ON match_round_guesses(asset_id);

CREATE INDEX IF NOT EXISTS idx_challenges_token ON challenges(capability_token);
CREATE INDEX IF NOT EXISTS idx_challenges_expires ON challenges(expires_at);
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

    def create_challenge(
        self,
        creator_name: str,
        library_name: str,
        config: dict[str, Any],
        asset_ids: list[str],
        expires_in_hours: int | None = 24,
    ) -> dict[str, Any]:
        challenge_id = f"ch_{uuid4().hex[:12]}"
        capability_token = secrets.token_urlsafe(16)
        created_at = datetime.now(timezone.utc)
        expires_at = (created_at + timedelta(hours=expires_in_hours)).isoformat() if expires_in_hours else None

        with self._db.connection() as conn:
            conn.execute(
                """
                INSERT INTO challenges (
                    challenge_id, capability_token, creator_name, library_name,
                    config_json, asset_ids_json, created_at, expires_at, is_active
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
                """,
                (
                    challenge_id,
                    capability_token,
                    creator_name,
                    library_name,
                    json.dumps(config),
                    json.dumps(asset_ids),
                    created_at.isoformat(),
                    expires_at,
                ),
            )

        return {
            "challenge_id": challenge_id,
            "capability_token": capability_token,
            "creator_name": creator_name,
            "library_name": library_name,
            "config": config,
            "asset_ids": asset_ids,
            "created_at": created_at.isoformat(),
            "expires_at": expires_at,
            "is_active": True,
        }

    def get_challenge_by_token(self, capability_token: str) -> dict[str, Any] | None:
        row = self._db.fetch_one(
            "SELECT * FROM challenges WHERE capability_token = ?",
            (capability_token,),
        )
        if not row:
            return None

        # Check expiration
        if row["expires_at"]:
            exp = datetime.fromisoformat(row["expires_at"])
            if datetime.now(timezone.utc) > exp:
                return None  # Expired

        if not row["is_active"]:
            return None

        return {
            "challenge_id": row["challenge_id"],
            "capability_token": row["capability_token"],
            "creator_name": row["creator_name"],
            "library_name": row["library_name"],
            "config": json.loads(row["config_json"]),
            "asset_ids": json.loads(row["asset_ids_json"]),
            "created_at": row["created_at"],
            "expires_at": row["expires_at"],
            "is_active": bool(row["is_active"]),
        }

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
            asset_ids = json.loads(row["asset_ids_json"])
            if asset_id in asset_ids:
                return True
        return False
```

---

## 3. Pydantic Models to Append to `src/models.py`

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
    library_name: str
    rounds: int
    expires_at: datetime | None


class ChallengeDetailResponse(BaseModel):
    challenge_id: str
    capability_token: str
    creator_name: str
    library_name: str
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

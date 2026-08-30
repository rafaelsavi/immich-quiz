"""Storage layer for challenge seeds, capability tokens, and persistent player sessions."""

from __future__ import annotations

import json
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from src.app_logging import LOGGER_STORAGE, get_logger
from src.storage.db import DatabaseManager

logger = get_logger(LOGGER_STORAGE)


class ChallengeStore:
    """Storage layer for challenge seeds, capability tokens, and persistent player sessions."""

    def __init__(self, db: DatabaseManager) -> None:
        self._db = db

    def create_challenge(
        self,
        creator_name: str,
        libraries: list[str] | None,
        config: dict[str, Any],
        asset_ids: list[str],
        title: str | None = None,
        expires_in_hours: int | None = 24,
    ) -> dict[str, Any]:
        """Create a deterministic challenge seed with a capability URL token."""
        challenge_id = f'ch_{uuid4().hex[:12]}'
        capability_token = secrets.token_urlsafe(16)
        created_at = datetime.now(timezone.utc)
        expires_at = (created_at + timedelta(hours=expires_in_hours)).isoformat() if expires_in_hours else None

        with self._db.connection() as conn:
            conn.execute(
                """
                INSERT INTO challenges (
                    challenge_id, capability_token, title, creator_name, libraries_json,
                    config_json, asset_ids_json, created_at, expires_at, is_active
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
                """,
                (
                    challenge_id,
                    capability_token,
                    title,
                    creator_name,
                    json.dumps(sorted(libraries)) if libraries else None,
                    json.dumps(config),
                    json.dumps(asset_ids),
                    created_at.isoformat(),
                    expires_at,
                ),
            )

        logger.info(
            'Challenge %s created by %r (%d assets, expires=%s)',
            challenge_id,
            creator_name,
            len(asset_ids),
            expires_at or 'never',
        )

        return {
            'challenge_id': challenge_id,
            'capability_token': capability_token,
            'title': title,
            'creator_name': creator_name,
            'libraries': libraries or [],
            'config': config,
            'asset_ids': asset_ids,
            'created_at': created_at.isoformat(),
            'expires_at': expires_at,
            'is_active': True,
        }

    def get_challenge_by_token(self, capability_token: str) -> dict[str, Any] | None:
        """Look up challenge by capability token, returning None if expired or inactive."""
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
            'title': row['title'],
            'creator_name': row['creator_name'],
            'libraries': json.loads(row['libraries_json']) if row['libraries_json'] else [],
            'config': json.loads(row['config_json']),
            'asset_ids': json.loads(row['asset_ids_json']),
            'created_at': row['created_at'],
            'expires_at': row['expires_at'],
            'is_active': bool(row['is_active']),
        }

    def get_challenge_by_id(self, challenge_id: str) -> dict[str, Any] | None:
        """Look up challenge by challenge_id."""
        row = self._db.fetch_one(
            'SELECT * FROM challenges WHERE challenge_id = ?',
            (challenge_id,),
        )
        if not row:
            return None

        return {
            'challenge_id': row['challenge_id'],
            'capability_token': row['capability_token'],
            'title': row['title'],
            'creator_name': row['creator_name'],
            'libraries': json.loads(row['libraries_json']) if row['libraries_json'] else [],
            'config': json.loads(row['config_json']),
            'asset_ids': json.loads(row['asset_ids_json']),
            'created_at': row['created_at'],
            'expires_at': row['expires_at'],
            'is_active': bool(row['is_active']),
        }

    def get_or_resume_player_session(
        self,
        challenge_id: str,
        player_name: str,
    ) -> dict[str, Any]:
        """Resume an existing session or create a new one for the player.

        Uses UNIQUE(challenge_id, player_name) constraint — if a player has an
        existing session (complete or in-progress), it is returned for resume.
        """
        existing = self._db.fetch_one(
            'SELECT * FROM challenge_sessions WHERE challenge_id = ? AND player_name = ?',
            (challenge_id, player_name),
        )
        if existing:
            logger.info(
                'Resuming session for %r in challenge %s (round %d)',
                player_name,
                challenge_id,
                existing['current_round'],
            )
            return dict(existing)

        session_token = secrets.token_urlsafe(24)
        match_id = f'ch_match_{uuid4().hex[:12]}'
        started_at = datetime.now(timezone.utc).isoformat()

        with self._db.connection() as conn:
            conn.execute(
                """
                INSERT INTO challenge_sessions (
                    session_token, match_id, challenge_id, player_name,
                    current_round, location_score, date_score, total_score,
                    total_time_seconds, started_at
                ) VALUES (?, ?, ?, ?, 0, 0, 0, 0, 0.0, ?)
                """,
                (session_token, match_id, challenge_id, player_name, started_at),
            )

        logger.info('Created new session for %r in challenge %s', player_name, challenge_id)

        return {
            'session_token': session_token,
            'match_id': match_id,
            'challenge_id': challenge_id,
            'player_name': player_name,
            'current_round': 0,
            'location_score': 0,
            'date_score': 0,
            'total_score': 0,
            'total_time_seconds': 0.0,
            'started_at': started_at,
            'completed_at': None,
        }

    def get_player_session(self, session_token: str) -> dict[str, Any] | None:
        """Retrieve a player session by its token from persistent storage."""
        row = self._db.fetch_one(
            'SELECT * FROM challenge_sessions WHERE session_token = ?',
            (session_token,),
        )
        return dict(row) if row else None

    def advance_session(
        self,
        session_token: str,
        *,
        round_index: int,
        location_points: int,
        date_points: int,
        round_score: int,
        time_taken_seconds: float,
        is_final: bool = False,
    ) -> None:
        """Advance session state after a round submission."""
        completed_at = datetime.now(timezone.utc).isoformat() if is_final else None
        with self._db.connection() as conn:
            conn.execute(
                """
                UPDATE challenge_sessions SET
                    current_round = ?,
                    location_score = location_score + ?,
                    date_score = date_score + ?,
                    total_score = total_score + ?,
                    total_time_seconds = total_time_seconds + ?,
                    completed_at = COALESCE(?, completed_at)
                WHERE session_token = ?
                """,
                (
                    round_index + 1,
                    location_points,
                    date_points,
                    round_score,
                    time_taken_seconds,
                    completed_at,
                    session_token,
                ),
            )

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

    def deactivate_challenge(self, challenge_id: str) -> bool:
        """Mark a challenge as inactive (admin revocation)."""
        with self._db.connection() as conn:
            cursor = conn.execute(
                'UPDATE challenges SET is_active = 0 WHERE challenge_id = ?',
                (challenge_id,),
            )
            return cursor.rowcount > 0

    def list_challenges(
        self,
        limit: int = 100,
        include_inactive: bool = True,
    ) -> list[dict[str, Any]]:
        """List challenges ordered by creation time descending."""
        where_clause = '' if include_inactive else 'WHERE is_active = 1'
        rows = self._db.fetch_all(
            f'SELECT * FROM challenges {where_clause} ORDER BY created_at DESC LIMIT ?',
            (limit,),
        )
        results = []
        for row in rows:
            results.append(
                {
                    'challenge_id': row['challenge_id'],
                    'capability_token': row['capability_token'],
                    'title': row['title'],
                    'creator_name': row['creator_name'],
                    'libraries': json.loads(row['libraries_json']) if row['libraries_json'] else [],
                    'config': json.loads(row['config_json']),
                    'asset_ids': json.loads(row['asset_ids_json']),
                    'created_at': row['created_at'],
                    'expires_at': row['expires_at'],
                    'is_active': bool(row['is_active']),
                }
            )
        return results

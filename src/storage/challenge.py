"""Storage layer for challenge seeds, capability tokens, and persistent player sessions."""

from __future__ import annotations

import json
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from src.app_logging import LOGGER_STORAGE, get_logger
from src.storage.db import DatabaseManager

logger = get_logger(LOGGER_STORAGE)


def _row_to_challenge_dict(row: dict[str, Any] | Any) -> dict[str, Any]:
    """Map a challenges table database row to a standardized dictionary."""
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


PLAYER_COLORS: list[str] = [
    '#f25f5c',
    '#0f7c7f',
    '#7048e8',
    '#f7b267',
    '#2f80ed',
    '#e0338d',
    '#3aa655',
    '#8d5524',
    '#17a2b8',
    '#fd7e14',
    '#6f42c1',
    '#20c997',
    '#d63384',
    '#4d96ff',
    '#ff6b6b',
    '#198754',
]


class ChallengeStore:
    """Storage layer for challenge seeds, capability tokens, and persistent player sessions."""

    def __init__(self, db: DatabaseManager) -> None:
        self._db = db

    def get_challenge_participants(self, challenge_id: str) -> list[str]:
        """Return ordered list of player names who have started this challenge."""
        rows = self._db.fetch_all(
            'SELECT player_name FROM challenge_sessions WHERE challenge_id = ? ORDER BY started_at ASC',
            (challenge_id,),
        )
        return [r['player_name'] for r in rows]

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

    def get_challenge_by_token(
        self,
        capability_token: str,
        include_inactive: bool = False,
    ) -> dict[str, Any] | None:
        """Look up challenge by capability token.

        Returns None if expired or inactive (unless include_inactive=True).
        """
        row = self._db.fetch_one(
            'SELECT * FROM challenges WHERE capability_token = ?',
            (capability_token,),
        )
        if not row:
            return None

        if not include_inactive:
            # Check expiration
            if row['expires_at']:
                exp = datetime.fromisoformat(row['expires_at'])
                if datetime.now(timezone.utc) > exp:
                    return None  # Expired

            if not row['is_active']:
                return None

        return _row_to_challenge_dict(row)

    def get_challenge_by_id(self, challenge_id: str) -> dict[str, Any] | None:
        """Look up challenge by challenge_id."""
        row = self._db.fetch_one(
            'SELECT * FROM challenges WHERE challenge_id = ?',
            (challenge_id,),
        )
        if not row:
            return None

        return _row_to_challenge_dict(row)

    def get_or_resume_player_session(
        self,
        challenge_id: str,
        player_name: str,
        player_color: str | None = None,
    ) -> dict[str, Any]:
        """Resume an existing session or create a new one for the player.

        Uses UNIQUE(challenge_id, player_name) constraint — if a player has an
        existing session (complete or in-progress), it is returned for resume.
        Assigns a persistent individual icon color based on join order.
        """
        existing = self._db.fetch_one(
            'SELECT * FROM challenge_sessions WHERE challenge_id = ? AND player_name = ?',
            (challenge_id, player_name),
        )
        if existing:
            session_dict = dict(existing)
            color = session_dict.get('player_color')
            if not color:
                all_sessions = self._db.fetch_all(
                    'SELECT session_token FROM challenge_sessions WHERE challenge_id = ? ORDER BY started_at ASC',
                    (challenge_id,),
                )
                idx = next(
                    (i for i, s in enumerate(all_sessions) if s['session_token'] == session_dict['session_token']),
                    0,
                )
                color = PLAYER_COLORS[idx % len(PLAYER_COLORS)]
                with self._db.connection() as conn:
                    conn.execute(
                        'UPDATE challenge_sessions SET player_color = ? WHERE session_token = ?',
                        (color, session_dict['session_token']),
                    )
                session_dict['player_color'] = color

            logger.info(
                'Resuming session for %r in challenge %s (round %d, color %s)',
                player_name,
                challenge_id,
                existing['current_round'],
                session_dict.get('player_color'),
            )
            return session_dict

        existing_sessions = self._db.fetch_all(
            'SELECT session_token FROM challenge_sessions WHERE challenge_id = ? ORDER BY started_at ASC',
            (challenge_id,),
        )
        participant_index = len(existing_sessions)
        assigned_color = (
            player_color.strip()
            if player_color and player_color.strip().startswith('#')
            else PLAYER_COLORS[participant_index % len(PLAYER_COLORS)]
        )

        session_token = secrets.token_urlsafe(24)
        match_id = f'ch_match_{uuid4().hex[:12]}'
        started_at = datetime.now(timezone.utc).isoformat()

        try:
            with self._db.connection() as conn:
                conn.execute(
                    """
                    INSERT INTO challenge_sessions (
                        session_token, match_id, challenge_id, player_name,
                        current_round, location_score, date_score, total_score,
                        total_time_seconds, started_at, player_color
                    ) VALUES (?, ?, ?, ?, 0, 0, 0, 0, 0.0, ?, ?)
                    """,
                    (session_token, match_id, challenge_id, player_name, started_at, assigned_color),
                )
        except sqlite3.IntegrityError:
            existing = self._db.fetch_one(
                'SELECT * FROM challenge_sessions WHERE challenge_id = ? AND player_name = ?',
                (challenge_id, player_name),
            )
            if existing:
                return dict(existing)
            raise

        logger.info(
            'Created new session for %r in challenge %s (index %d, color %s)',
            player_name,
            challenge_id,
            participant_index,
            assigned_color,
        )

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
            'player_color': assigned_color,
            'participant_index': participant_index,
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
        row = self._db.fetch_one(
            """
            SELECT 1 FROM challenges, json_each(challenges.asset_ids_json)
            WHERE challenges.is_active = 1
              AND (challenges.expires_at IS NULL OR challenges.expires_at > ?)
              AND json_each.value = ?
            LIMIT 1
            """,
            (now_iso, asset_id),
        )
        return row is not None

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
        return [_row_to_challenge_dict(row) for row in rows]

"""SQLite database connection manager and helper utilities."""

from __future__ import annotations

import sqlite3
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from src.app_logging import LOGGER_STORAGE, get_logger

logger = get_logger(LOGGER_STORAGE)


class DatabaseManager:
    """Manages SQLite database connection, initialization, and configuration."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self._ensure_dir()
        self._init_db()

    def _ensure_dir(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def _init_db(self) -> None:
        with self.connection() as conn:
            conn.execute('PRAGMA journal_mode=WAL;')
            conn.execute('PRAGMA synchronous=NORMAL;')
            conn.execute('PRAGMA foreign_keys=ON;')
            conn.execute('PRAGMA busy_timeout=5000;')

    @contextmanager
    def connection(self) -> Generator[sqlite3.Connection]:
        """Context manager yielding a SQLite connection with foreign keys and row factory."""
        conn = sqlite3.connect(self.db_path, timeout=10.0)
        conn.row_factory = sqlite3.Row
        conn.execute('PRAGMA foreign_keys=ON;')
        conn.execute('PRAGMA synchronous=NORMAL;')
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def execute_script(self, script: str) -> None:
        """Execute a multi-statement SQL script in a transaction."""
        with self.connection() as conn:
            conn.executescript(script)

    def fetch_all(self, sql: str, params: tuple[Any, ...] | list[Any] = ()) -> list[dict[str, Any]]:
        """Execute a query and return all matching rows as dictionaries."""
        with self.connection() as conn:
            cursor = conn.execute(sql, params)
            return [dict(row) for row in cursor.fetchall()]

    def fetch_one(self, sql: str, params: tuple[Any, ...] | list[Any] = ()) -> dict[str, Any] | None:
        """Execute a query and return the first matching row as a dictionary or None."""
        with self.connection() as conn:
            cursor = conn.execute(sql, params)
            row = cursor.fetchone()
            return dict(row) if row is not None else None

    def fetch_val(self, sql: str, params: tuple[Any, ...] | list[Any] = ()) -> Any:
        """Execute a query and return the single scalar value of the first column or None."""
        with self.connection() as conn:
            cursor = conn.execute(sql, params)
            row = cursor.fetchone()
            return row[0] if row is not None else None

    def checkpoint(self, mode: str = 'TRUNCATE') -> None:
        """Checkpoint the WAL journal back into the database file.

        Modes supported: PASSIVE, FULL, RESTART, TRUNCATE.
        """
        valid_modes = {'PASSIVE', 'FULL', 'RESTART', 'TRUNCATE'}
        normalized_mode = mode.strip().upper()
        if normalized_mode not in valid_modes:
            normalized_mode = 'TRUNCATE'
        try:
            with self.connection() as conn:
                conn.execute(f'PRAGMA wal_checkpoint({normalized_mode});')
                logger.debug('WAL checkpoint (%s) executed for %s', normalized_mode, self.db_path.name)
        except Exception as exc:
            logger.warning('Failed to checkpoint WAL for %s: %s', self.db_path.name, exc)

    def optimize(self) -> None:
        """Run PRAGMA optimize to update SQLite query planner statistics."""
        try:
            with self.connection() as conn:
                conn.execute('PRAGMA optimize;')
                logger.debug('PRAGMA optimize executed for %s', self.db_path.name)
        except Exception as exc:
            logger.warning('Failed to run PRAGMA optimize for %s: %s', self.db_path.name, exc)

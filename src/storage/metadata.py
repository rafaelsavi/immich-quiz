"""SQLite photo metadata cache, faceted indexing, and query evaluation engine."""

from __future__ import annotations

import contextlib
import logging
from dataclasses import dataclass, replace
from datetime import date, datetime
from typing import Any

from src.config import AppSettings
from src.immich.client import AssetAnswer
from src.models import (
    BaseGameConfig,
    CityOption,
    DateRangeOption,
    FacetCounts,
    LibraryFiltersResponse,
    PeopleMode,
    PersonOption,
    SyncMode,
    SyncStage,
    SyncStatus,
)
from src.storage.db import DatabaseManager

logger = logging.getLogger(__name__)

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS sync_state (
    library_name TEXT PRIMARY KEY,
    last_sync_at TEXT,
    last_full_sync_at TEXT,
    last_immich_updated_at TEXT,
    sync_status TEXT DEFAULT 'idle',
    sync_mode TEXT DEFAULT 'full',
    sync_stage TEXT DEFAULT 'idle',
    sync_error TEXT,
    total_assets INTEGER DEFAULT 0,
    synced_assets INTEGER DEFAULT 0,
    last_sync_duration_seconds REAL
);

CREATE TABLE IF NOT EXISTS assets (
    id TEXT NOT NULL,
    library_name TEXT NOT NULL,
    is_shared INTEGER NOT NULL DEFAULT 0,
    is_partner INTEGER NOT NULL DEFAULT 0,
    file_type TEXT NOT NULL DEFAULT 'IMAGE',
    latitude REAL,
    longitude REAL,
    country TEXT,
    state TEXT,
    city TEXT,
    capture_datetime TEXT,
    immich_updated_at TEXT,
    times_played INTEGER NOT NULL DEFAULT 0,
    last_played_at TEXT,
    PRIMARY KEY(id, library_name)
);

CREATE INDEX IF NOT EXISTS idx_assets_lib_country ON assets(library_name, country);
CREATE INDEX IF NOT EXISTS idx_assets_lib_state ON assets(library_name, state);
CREATE INDEX IF NOT EXISTS idx_assets_lib_city ON assets(library_name, city);
CREATE INDEX IF NOT EXISTS idx_assets_lib_datetime ON assets(library_name, capture_datetime);
CREATE INDEX IF NOT EXISTS idx_assets_lib_coords ON assets(library_name, latitude, longitude);
CREATE INDEX IF NOT EXISTS idx_assets_lib_updated ON assets(library_name, immich_updated_at);
CREATE INDEX IF NOT EXISTS idx_assets_lib_times_played ON assets(library_name, times_played);
CREATE INDEX IF NOT EXISTS idx_assets_lib_shared_partner ON assets(library_name, is_shared, is_partner);

CREATE TABLE IF NOT EXISTS people (
    id TEXT NOT NULL,
    library_name TEXT NOT NULL,
    name TEXT NOT NULL,
    PRIMARY KEY(id, library_name)
);

CREATE TABLE IF NOT EXISTS asset_people (
    asset_id TEXT NOT NULL,
    person_id TEXT NOT NULL,
    library_name TEXT NOT NULL,
    PRIMARY KEY(asset_id, person_id, library_name),
    FOREIGN KEY(asset_id, library_name) REFERENCES assets(id, library_name) ON DELETE CASCADE,
    FOREIGN KEY(person_id, library_name) REFERENCES people(id, library_name) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_asset_people_person ON asset_people(library_name, person_id);
CREATE INDEX IF NOT EXISTS idx_asset_people_asset_lib ON asset_people(asset_id, library_name);

CREATE TABLE IF NOT EXISTS albums (
    id TEXT NOT NULL,
    library_name TEXT NOT NULL,
    name TEXT NOT NULL,
    is_shared INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY(id, library_name)
);

CREATE TABLE IF NOT EXISTS asset_albums (
    asset_id TEXT NOT NULL,
    album_id TEXT NOT NULL,
    library_name TEXT NOT NULL,
    PRIMARY KEY(asset_id, album_id, library_name),
    FOREIGN KEY(asset_id, library_name) REFERENCES assets(id, library_name) ON DELETE CASCADE,
    FOREIGN KEY(album_id, library_name) REFERENCES albums(id, library_name) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_asset_albums_album ON asset_albums(library_name, album_id);
CREATE INDEX IF NOT EXISTS idx_asset_albums_asset_lib ON asset_albums(asset_id, library_name);

CREATE TABLE IF NOT EXISTS tags (
    id TEXT NOT NULL,
    library_name TEXT NOT NULL,
    name TEXT NOT NULL,
    PRIMARY KEY(id, library_name)
);
CREATE INDEX IF NOT EXISTS idx_tags_lib_name ON tags(library_name, name);

CREATE TABLE IF NOT EXISTS asset_tags (
    asset_id TEXT NOT NULL,
    tag_id TEXT NOT NULL,
    library_name TEXT NOT NULL,
    PRIMARY KEY(asset_id, tag_id, library_name),
    FOREIGN KEY(asset_id, library_name) REFERENCES assets(id, library_name) ON DELETE CASCADE,
    FOREIGN KEY(tag_id, library_name) REFERENCES tags(id, library_name) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_asset_tags_tag ON asset_tags(library_name, tag_id);
CREATE INDEX IF NOT EXISTS idx_asset_tags_asset_lib ON asset_tags(asset_id, library_name);
"""


@dataclass(frozen=True)
class AssetFilterCriteria:
    """Unified query filter parameters combining user match settings with server safeguards."""

    library_names: tuple[str, ...] = ()
    location_mode: bool = False
    date_mode: bool = False
    min_date: date | None = None
    max_date: date | None = None
    countries: tuple[str, ...] = ()
    cities: tuple[str, ...] = ()
    person_ids: tuple[str, ...] = ()
    people_mode: PeopleMode = PeopleMode.ANY
    album_ids: tuple[str, ...] = ()
    include_shared: bool = False
    # Layer 1 Config Safeguards
    country_whitelist: frozenset[str] = frozenset()
    country_blacklist: frozenset[str] = frozenset()
    city_whitelist: frozenset[str] = frozenset()
    city_blacklist: frozenset[str] = frozenset()
    people_whitelist: frozenset[str] = frozenset()
    people_blacklist: frozenset[str] = frozenset()
    tag_whitelist: frozenset[str] = frozenset()
    tag_blacklist: frozenset[str] = frozenset()

    def __post_init__(self) -> None:
        if self.min_date is not None and self.max_date is not None and self.min_date > self.max_date:
            raise ValueError('min_date cannot be greater than max_date')

    @classmethod
    def from_setup(cls, setup: BaseGameConfig, settings: AppSettings | None = None) -> AssetFilterCriteria:
        """Create unified filter criteria combining user setup and global settings."""
        eff_min = setup.min_date
        eff_max = setup.max_date
        if settings is not None:
            if settings.date_lower_bound:
                eff_min = max(filter(None, [settings.date_lower_bound, eff_min]), default=None)
            if settings.date_upper_bound:
                eff_max = min(filter(None, [settings.date_upper_bound, eff_max]), default=None)

        libs = tuple(setup.libraries) if setup.libraries else ()
        return cls(
            library_names=libs,
            location_mode=setup.location_mode,
            date_mode=setup.date_mode,
            min_date=eff_min,
            max_date=eff_max,
            countries=tuple(setup.countries) if setup.countries else (),
            cities=tuple(setup.cities) if setup.cities else (),
            person_ids=tuple(setup.person_ids) if setup.person_ids else (),
            people_mode=setup.people_mode,
            album_ids=tuple(setup.album_ids) if setup.album_ids else (),
            include_shared=setup.include_shared,
            country_whitelist=settings.country_whitelist if settings else frozenset(),
            country_blacklist=settings.country_blacklist if settings else frozenset(),
            city_whitelist=settings.city_whitelist if settings else frozenset(),
            city_blacklist=settings.city_blacklist if settings else frozenset(),
            people_whitelist=settings.people_whitelist if settings else frozenset(),
            people_blacklist=settings.people_blacklist if settings else frozenset(),
            tag_whitelist=settings.tag_whitelist if settings else frozenset(),
            tag_blacklist=settings.tag_blacklist if settings else frozenset(),
        )


class MetadataStore:
    """Manages SQLite-based metadata storage, indexing, and unified filtering for Immich Quiz."""

    def __init__(self, db: DatabaseManager) -> None:
        self._db = db
        self.init_schema()

    def init_schema(self) -> None:
        """Initialize metadata database schema tables and indices."""
        self._db.execute_script(SCHEMA_SQL)

    def has_synced_assets(self, libraries: list[str] | tuple[str, ...] | None = None) -> bool:
        """Check if any photo assets are indexed for the given libraries (or across all if None)."""
        if not libraries:
            count = self._db.fetch_val('SELECT COUNT(*) FROM assets')
            return bool(count and count > 0)
        placeholders = ', '.join('?' for _ in libraries)
        count = self._db.fetch_val(
            f'SELECT COUNT(*) FROM assets WHERE library_name IN ({placeholders})',
            tuple(libraries),
        )
        return bool(count and count > 0)

    def get_asset_library(self, asset_id: str) -> str | None:
        """Look up a library_name that indexed a given asset ID."""
        row = self._db.fetch_one('SELECT library_name FROM assets WHERE id = ? LIMIT 1', (asset_id,))
        return str(row['library_name']) if row and row.get('library_name') else None

    def get_sync_state(self, library_name: str) -> dict[str, Any]:
        """Fetch current sync progress and state record for a library."""
        row = self._db.fetch_one(
            'SELECT * FROM sync_state WHERE library_name = ?',
            (library_name,),
        )
        if row:
            return row
        return {
            'library_name': library_name,
            'last_sync_at': None,
            'last_full_sync_at': None,
            'last_immich_updated_at': None,
            'sync_status': SyncStatus.idle.value,
            'sync_mode': SyncMode.full.value,
            'sync_stage': SyncStage.idle.value,
            'sync_error': None,
            'total_assets': 0,
            'synced_assets': 0,
            'last_sync_duration_seconds': None,
        }

    def get_all_sync_states(self) -> list[dict[str, Any]]:
        """Fetch sync state records for all configured libraries."""
        return self._db.fetch_all('SELECT * FROM sync_state ORDER BY library_name')

    def set_sync_state(
        self,
        library_name: str,
        *,
        status: SyncStatus,
        total_assets: int | None = None,
        synced_assets: int | None = None,
        sync_stage: SyncStage | None = None,
        error: str | None = None,
        last_sync_at: str | None = None,
        last_full_sync_at: str | None = None,
        last_immich_updated_at: str | None = None,
        sync_mode: SyncMode | None = None,
        last_sync_duration_seconds: float | None = None,
    ) -> None:
        """Update or insert sync state and progress information for a library."""
        with self._db.connection() as conn:
            existing = conn.execute(
                """
                SELECT total_assets, synced_assets, last_sync_at, last_full_sync_at,
                       last_immich_updated_at, sync_mode, sync_stage, last_sync_duration_seconds
                FROM sync_state WHERE library_name = ?
                """,
                (library_name,),
            ).fetchone()

            tot = total_assets if total_assets is not None else (existing['total_assets'] if existing else 0)
            sync_cnt = synced_assets if synced_assets is not None else (existing['synced_assets'] if existing else 0)
            if isinstance(sync_stage, SyncStage):
                stage = sync_stage.value
            elif sync_stage is not None:
                stage = str(sync_stage)
            else:
                stage = existing['sync_stage'] if existing else SyncStage.idle.value

            last_sync = last_sync_at if last_sync_at is not None else (existing['last_sync_at'] if existing else None)
            last_full = (
                last_full_sync_at
                if last_full_sync_at is not None
                else (existing['last_full_sync_at'] if existing else None)
            )
            last_updated = (
                last_immich_updated_at
                if last_immich_updated_at is not None
                else (existing['last_immich_updated_at'] if existing else None)
            )
            if isinstance(sync_mode, SyncMode):
                mode = sync_mode.value
            elif sync_mode is not None:
                mode = str(sync_mode)
            else:
                mode = existing['sync_mode'] if existing else SyncMode.full.value
            duration = (
                last_sync_duration_seconds
                if last_sync_duration_seconds is not None
                else (existing['last_sync_duration_seconds'] if existing else None)
            )

            conn.execute(
                """
                INSERT INTO sync_state (
                    library_name, last_sync_at, last_full_sync_at, last_immich_updated_at,
                    sync_status, sync_mode, sync_stage, sync_error,
                    total_assets, synced_assets, last_sync_duration_seconds
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(library_name) DO UPDATE SET
                    last_sync_at = excluded.last_sync_at,
                    last_full_sync_at = excluded.last_full_sync_at,
                    last_immich_updated_at = excluded.last_immich_updated_at,
                    sync_status = excluded.sync_status,
                    sync_mode = excluded.sync_mode,
                    sync_stage = excluded.sync_stage,
                    sync_error = excluded.sync_error,
                    total_assets = excluded.total_assets,
                    synced_assets = excluded.synced_assets,
                    last_sync_duration_seconds = excluded.last_sync_duration_seconds
                """,
                (
                    library_name,
                    last_sync,
                    last_full,
                    last_updated,
                    status.value,
                    mode,
                    stage,
                    error,
                    tot,
                    sync_cnt,
                    duration,
                ),
            )

    def get_indexed_album_ids(self, library_name: str) -> set[str]:
        """Return the set of album IDs already indexed for this library."""
        rows = self._db.fetch_all('SELECT id FROM albums WHERE library_name = ?', (library_name,))
        return {str(r['id']) for r in rows}

    def upsert_people(self, library_name: str, people: list[dict[str, str]]) -> None:
        """Insert or update recognized people metadata for a library."""
        rows = [
            (str(p.get('id', '')).strip(), library_name, str(p.get('name', '')).strip())
            for p in people
            if str(p.get('id', '')).strip() and str(p.get('name', '')).strip()
        ]
        if not rows:
            return
        with self._db.connection() as conn:
            conn.executemany(
                """
                INSERT INTO people (id, library_name, name)
                VALUES (?, ?, ?)
                ON CONFLICT(id, library_name) DO UPDATE SET
                    name = excluded.name
                """,
                rows,
            )

    def upsert_albums(self, library_name: str, albums: list[dict[str, Any]]) -> None:
        """Insert or update album metadata for a library."""
        rows = []
        for a in albums:
            aid = str(a.get('id', '')).strip()
            name = str(a.get('name', '') or a.get('albumName', '')).strip()
            is_shared = 1 if bool(a.get('isShared') or a.get('shared')) else 0
            if aid and name:
                rows.append((aid, library_name, name, is_shared))
        if not rows:
            return
        with self._db.connection() as conn:
            conn.executemany(
                """
                INSERT INTO albums (id, library_name, name, is_shared)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(id, library_name) DO UPDATE SET
                    name = excluded.name,
                    is_shared = excluded.is_shared
                """,
                rows,
            )

    def prune_missing_albums(self, library_name: str, active_album_ids: set[str]) -> int:
        """Remove albums that no longer exist on the Immich server."""
        if not active_album_ids:
            return 0
        with self._db.connection() as conn:
            conn.execute('CREATE TEMP TABLE temp_active_album_ids (id TEXT PRIMARY KEY);')
            conn.executemany(
                'INSERT INTO temp_active_album_ids (id) VALUES (?);',
                [(aid,) for aid in active_album_ids],
            )
            cursor = conn.execute(
                """
                DELETE FROM albums
                WHERE library_name = ?
                  AND id NOT IN (SELECT id FROM temp_active_album_ids)
                """,
                (library_name,),
            )
            deleted_count = cursor.rowcount
            conn.execute('DROP TABLE temp_active_album_ids;')
            return deleted_count

    def upsert_tags(self, library_name: str, tags: list[dict[str, str]]) -> None:
        """Insert or update user tag metadata for a library."""
        rows = [
            (str(t.get('id', '')).strip(), library_name, str(t.get('name', '')).strip())
            for t in tags
            if str(t.get('id', '')).strip() and str(t.get('name', '')).strip()
        ]
        if not rows:
            return
        with self._db.connection() as conn:
            conn.executemany(
                """
                INSERT INTO tags (id, library_name, name)
                VALUES (?, ?, ?)
                ON CONFLICT(id, library_name) DO UPDATE SET
                    name = excluded.name
                """,
                rows,
            )

    def link_album_assets(
        self,
        library_name: str,
        junction_inserts: list[tuple[str, str]],
        shared_asset_updates: list[tuple[str,]] | None = None,
        *,
        clear_album_ids: set[str] | None = None,
    ) -> None:
        """Insert album junction records and optionally update shared flags in bulk for a library."""
        with self._db.connection() as conn:
            if clear_album_ids:
                conn.executemany(
                    'DELETE FROM asset_albums WHERE library_name = ? AND album_id = ?',
                    [(library_name, aid) for aid in clear_album_ids],
                )
            if junction_inserts:
                conn.executemany(
                    """
                    INSERT OR IGNORE INTO asset_albums (asset_id, album_id, library_name)
                    SELECT a.id, alb.id, ?
                    FROM assets a, albums alb
                    WHERE a.id = ? AND alb.id = ? AND a.library_name = ? AND alb.library_name = ?
                    """,
                    [(library_name, aid, albid, library_name, library_name) for aid, albid in junction_inserts],
                )
            if shared_asset_updates:
                conn.executemany(
                    'UPDATE assets SET is_shared = 1, is_partner = 0 WHERE id = ? AND library_name = ?',
                    [(aid[0], library_name) for aid in shared_asset_updates],
                )

    def count_library_assets(self, library_name: str) -> int:
        """Count total assets currently indexed for a library."""
        return (
            self._db.fetch_val(
                'SELECT COUNT(*) FROM assets WHERE library_name = ?',
                (library_name,),
            )
            or 0
        )

    def upsert_assets_batch(
        self,
        library_name: str,
        assets: list[dict[str, Any]],
        asset_people: list[tuple[str, str]],
        asset_albums: list[tuple[str, str]],
        asset_tags: list[tuple[str, str]] | None = None,
    ) -> None:
        """Insert or update batch of asset records along with people/album/tag junction rows."""
        if not assets:
            return

        asset_rows = []
        asset_ids = []
        for a in assets:
            aid = a['id']
            asset_ids.append(aid)
            country_val = a.get('country')
            state_val = a.get('state')
            city_val = a.get('city')
            country_clean = str(country_val).strip() if country_val else None
            if country_clean and country_clean.lower() in ('none', 'null', 'undefined', ''):
                country_clean = None
            state_clean = str(state_val).strip() if state_val else None
            if state_clean and state_clean.lower() in ('none', 'null', 'undefined', ''):
                state_clean = None
            city_clean = str(city_val).strip() if city_val else None
            if city_clean and city_clean.lower() in ('none', 'null', 'undefined', ''):
                city_clean = None

            asset_rows.append(
                (
                    aid,
                    library_name,
                    a['is_shared'],
                    a['is_partner'],
                    a.get('file_type', 'IMAGE'),
                    a.get('latitude'),
                    a.get('longitude'),
                    country_clean,
                    state_clean,
                    city_clean,
                    a.get('capture_datetime'),
                    a.get('immich_updated_at'),
                )
            )

        with self._db.connection() as conn:
            conn.executemany(
                """
                INSERT INTO assets (
                    id, library_name, is_shared, is_partner, file_type,
                    latitude, longitude, country, state, city, capture_datetime,
                    immich_updated_at, times_played, last_played_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, NULL)
                ON CONFLICT(id, library_name) DO UPDATE SET
                    is_shared = excluded.is_shared,
                    is_partner = excluded.is_partner,
                    file_type = excluded.file_type,
                    latitude = excluded.latitude,
                    longitude = excluded.longitude,
                    country = excluded.country,
                    state = excluded.state,
                    city = excluded.city,
                    capture_datetime = excluded.capture_datetime,
                    immich_updated_at = excluded.immich_updated_at
                """,
                asset_rows,
            )

            # Clear stale junction records for this batch of assets in this library
            id_tuples = [(aid, library_name) for aid in asset_ids]
            conn.executemany('DELETE FROM asset_people WHERE asset_id = ? AND library_name = ?', id_tuples)
            conn.executemany('DELETE FROM asset_albums WHERE asset_id = ? AND library_name = ?', id_tuples)
            conn.executemany('DELETE FROM asset_tags WHERE asset_id = ? AND library_name = ?', id_tuples)

            if asset_people:
                conn.executemany(
                    """
                    INSERT OR IGNORE INTO asset_people (asset_id, person_id, library_name)
                    SELECT a.id, p.id, ?
                    FROM assets a, people p
                    WHERE a.id = ? AND p.id = ? AND a.library_name = ? AND p.library_name = ?
                    """,
                    [(library_name, aid, pid, library_name, library_name) for aid, pid in asset_people],
                )

            if asset_albums:
                conn.executemany(
                    """
                    INSERT OR IGNORE INTO asset_albums (asset_id, album_id, library_name)
                    SELECT a.id, alb.id, ?
                    FROM assets a, albums alb
                    WHERE a.id = ? AND alb.id = ? AND a.library_name = ? AND alb.library_name = ?
                    """,
                    [(library_name, aid, albid, library_name, library_name) for aid, albid in asset_albums],
                )

            if asset_tags:
                conn.executemany(
                    """
                    INSERT OR IGNORE INTO asset_tags (asset_id, tag_id, library_name)
                    SELECT a.id, t.id, ?
                    FROM assets a, tags t
                    WHERE a.id = ? AND t.id = ? AND a.library_name = ? AND t.library_name = ?
                    """,
                    [(library_name, aid, tid, library_name, library_name) for aid, tid in asset_tags],
                )

    def prune_missing_assets(self, library_name: str, active_asset_ids: set[str]) -> int:
        """Remove assets for a library that no longer exist on the Immich server."""
        if not active_asset_ids:
            return 0
        with self._db.connection() as conn:
            # Create a temporary table of active IDs for fast set difference
            conn.execute('CREATE TEMP TABLE temp_active_ids (id TEXT PRIMARY KEY);')
            conn.executemany(
                'INSERT INTO temp_active_ids (id) VALUES (?);',
                [(aid,) for aid in active_asset_ids],
            )
            cursor = conn.execute(
                """
                DELETE FROM assets
                WHERE library_name = ?
                  AND id NOT IN (SELECT id FROM temp_active_ids)
                """,
                (library_name,),
            )
            deleted_count = cursor.rowcount
            conn.execute('DROP TABLE temp_active_ids;')
            return deleted_count

    def mark_asset_invalid(self, asset_id: str) -> None:
        """Delete or invalidate a missing/corrupt asset on-the-fly during gameplay."""
        with self._db.connection() as conn:
            conn.execute('DELETE FROM assets WHERE id = ?', (asset_id,))

    def record_asset_played(self, asset_id: str, played_at: datetime | None = None) -> None:
        """Increment play count and record timestamp for a played asset."""
        self.record_assets_played([asset_id], played_at=played_at)

    def record_assets_played(self, asset_ids: list[str], played_at: datetime | None = None) -> None:
        """Increment play count and record timestamp for multiple played assets."""
        if not asset_ids:
            return
        ts = (played_at or datetime.now()).isoformat()
        with self._db.connection() as conn:
            conn.executemany(
                """
                UPDATE assets
                SET times_played = times_played + 1,
                    last_played_at = ?
                WHERE id = ?
                """,
                [(ts, aid) for aid in asset_ids],
            )

    def _build_filter_clauses(
        self,
        criteria: AssetFilterCriteria,
        ignore_location_mode: bool = False,
        ignore_date_mode: bool = False,
    ) -> tuple[str, list[Any]]:
        """Construct unified SQL WHERE clauses and parameters matching exact quiz filter semantics."""
        clauses: list[str] = ["a.file_type != 'VIDEO'"]
        params: list[Any] = []
        if criteria.library_names:
            placeholders = ', '.join('?' for _ in criteria.library_names)
            clauses.append(f'a.library_name IN ({placeholders})')
            params.extend(criteria.library_names)

        # -------------------------------------------------------------------
        # LAYER 1: Hard Server Configuration Safeguards (Always Enforced)
        # -------------------------------------------------------------------

        # 1. Location mode: non-zero lat/lon
        if criteria.location_mode and not ignore_location_mode:
            clauses.append(
                'a.latitude IS NOT NULL AND a.longitude IS NOT NULL AND NOT ('
                'abs(a.latitude) < 1e-6 AND abs(a.longitude) < 1e-6'
                ')'
            )

        # 2. Date mode: capture datetime required
        if criteria.date_mode and not ignore_date_mode:
            clauses.append('a.capture_datetime IS NOT NULL')

        # 3. Date bounds (ISO8601 string comparison)
        if criteria.min_date:
            clauses.append('a.capture_datetime >= ?')
            params.append(f'{criteria.min_date.isoformat()}T00:00:00')
        if criteria.max_date:
            clauses.append('a.capture_datetime <= ?')
            params.append(f'{criteria.max_date.isoformat()}T23:59:59.999')

        # 4. Country blacklist (exclude matching countries)
        if criteria.country_blacklist:
            placeholders = ', '.join('?' for _ in criteria.country_blacklist)
            clauses.append(f'(a.country IS NULL OR LOWER(a.country) NOT IN ({placeholders}))')
            params.extend(c.lower() for c in criteria.country_blacklist)

        # 5. City blacklist (exclude matching cities)
        if criteria.city_blacklist:
            placeholders = ', '.join('?' for _ in criteria.city_blacklist)
            clauses.append(f'(a.city IS NULL OR LOWER(a.city) NOT IN ({placeholders}))')
            params.extend(c.lower() for c in criteria.city_blacklist)

        # 6. People blacklist (exclude matching people by name or ID)
        if criteria.people_blacklist:
            name_placeholders = ', '.join('?' for _ in criteria.people_blacklist)
            id_placeholders = ', '.join('?' for _ in criteria.people_blacklist)
            clauses.append(
                f"""NOT EXISTS (
                    SELECT 1
                    FROM asset_people ap
                    JOIN people p ON ap.person_id = p.id AND ap.library_name = p.library_name
                    WHERE ap.asset_id = a.id AND ap.library_name = a.library_name
                      AND (LOWER(p.name) IN ({name_placeholders}) OR LOWER(ap.person_id) IN ({id_placeholders}))
                )"""
            )
            params.extend(p.lower() for p in criteria.people_blacklist)
            params.extend(p.lower() for p in criteria.people_blacklist)

        # 7. Country whitelist baseline (if active and user didn't specify countries)
        if criteria.country_whitelist and not criteria.countries:
            placeholders = ', '.join('?' for _ in criteria.country_whitelist)
            clauses.append(f'(a.country IS NOT NULL AND LOWER(a.country) IN ({placeholders}))')
            params.extend(c.lower() for c in criteria.country_whitelist)

        # 8. City whitelist baseline (if active and user didn't specify cities)
        if criteria.city_whitelist and not criteria.cities:
            placeholders = ', '.join('?' for _ in criteria.city_whitelist)
            clauses.append(f'(a.city IS NOT NULL AND LOWER(a.city) IN ({placeholders}))')
            params.extend(c.lower() for c in criteria.city_whitelist)

        # 9. People whitelist baseline (if active and user didn't specify people)
        # Excludes photos containing non-whitelisted recognized people (photos where ANY attached person
        # matches neither a whitelisted name nor ID), while allowing photos with no tagged people.
        if criteria.people_whitelist and not criteria.person_ids:
            name_placeholders = ', '.join('?' for _ in criteria.people_whitelist)
            id_placeholders = ', '.join('?' for _ in criteria.people_whitelist)
            clauses.append(
                f"""NOT EXISTS (
                    SELECT 1
                    FROM asset_people ap
                    JOIN people p ON ap.person_id = p.id AND ap.library_name = p.library_name
                    WHERE ap.asset_id = a.id AND ap.library_name = a.library_name
                      AND (LOWER(p.name) NOT IN ({name_placeholders})
                           AND LOWER(ap.person_id) NOT IN ({id_placeholders}))
                )"""
            )
            params.extend(p.lower() for p in criteria.people_whitelist)
            params.extend(p.lower() for p in criteria.people_whitelist)

        # 10. Tag blacklist (exclude matching tags by name or ID)
        if criteria.tag_blacklist:
            tag_name_placeholders = ', '.join('?' for _ in criteria.tag_blacklist)
            tag_id_placeholders = ', '.join('?' for _ in criteria.tag_blacklist)
            clauses.append(
                f"""NOT EXISTS (
                    SELECT 1
                    FROM asset_tags at
                    JOIN tags t ON at.tag_id = t.id AND at.library_name = t.library_name
                    WHERE at.asset_id = a.id AND at.library_name = a.library_name
                      AND (LOWER(t.name) IN ({tag_name_placeholders}) OR LOWER(at.tag_id) IN ({tag_id_placeholders}))
                )"""
            )
            params.extend(t.lower() for t in criteria.tag_blacklist)
            params.extend(t.lower() for t in criteria.tag_blacklist)

        # 11. Tag whitelist (only include assets with at least one whitelisted tag by name or ID)
        if criteria.tag_whitelist:
            tag_name_placeholders = ', '.join('?' for _ in criteria.tag_whitelist)
            tag_id_placeholders = ', '.join('?' for _ in criteria.tag_whitelist)
            clauses.append(
                f"""EXISTS (
                    SELECT 1
                    FROM asset_tags at
                    JOIN tags t ON at.tag_id = t.id AND at.library_name = t.library_name
                    WHERE at.asset_id = a.id AND at.library_name = a.library_name
                      AND (LOWER(t.name) IN ({tag_name_placeholders}) OR LOWER(at.tag_id) IN ({tag_id_placeholders}))
                )"""
            )
            params.extend(t.lower() for t in criteria.tag_whitelist)
            params.extend(t.lower() for t in criteria.tag_whitelist)

        # -------------------------------------------------------------------
        # LAYER 2: User Match Setup Rules (Applied on top)
        # -------------------------------------------------------------------

        # 10. Ownership flags
        has_selected_albums = bool(criteria.album_ids)
        if not has_selected_albums and not criteria.include_shared:
            clauses.append(
                'a.is_shared = 0 AND a.is_partner = 0 AND NOT EXISTS ('
                'SELECT 1 FROM asset_albums aa '
                'JOIN albums alb ON aa.album_id = alb.id AND aa.library_name = alb.library_name '
                'WHERE aa.asset_id = a.id AND aa.library_name = a.library_name AND alb.is_shared = 1'
                ')'
            )

        # 11. User countries filter (case-insensitive)
        if criteria.countries:
            placeholders = ', '.join('?' for _ in criteria.countries)
            clauses.append(f'LOWER(a.country) IN ({placeholders})')
            params.extend(c.lower() for c in criteria.countries)

        # 12. User cities filter (case-insensitive)
        if criteria.cities:
            city_placeholders = ', '.join('?' for _ in criteria.cities)
            clauses.append(f'LOWER(a.city) IN ({city_placeholders})')
            params.extend(c.lower() for c in criteria.cities)

        # 13. User people filter (ANY union vs ALL intersection) — supports both ID and Name matching
        if criteria.person_ids:
            p_targets = list(criteria.person_ids)
            if criteria.people_mode == PeopleMode.ALL and len(p_targets) > 1:
                for target in p_targets:
                    clauses.append(
                        """EXISTS (
                            SELECT 1
                            FROM asset_people ap
                            JOIN people p ON ap.person_id = p.id AND ap.library_name = p.library_name
                            WHERE ap.asset_id = a.id
                              AND ap.library_name = a.library_name
                              AND (
                                  p.name COLLATE NOCASE = ?
                                  OR ap.person_id = ?
                                  OR p.name IN (SELECT name FROM people WHERE id = ?)
                              )
                        )"""
                    )
                    params.extend([target, target, target])
            else:
                placeholders = ', '.join('?' for _ in p_targets)
                clauses.append(
                    f"""EXISTS (
                        SELECT 1
                        FROM asset_people ap
                        JOIN people p ON ap.person_id = p.id AND ap.library_name = p.library_name
                        WHERE ap.asset_id = a.id
                          AND ap.library_name = a.library_name
                          AND p.name IN (
                              SELECT name FROM people
                              WHERE id IN ({placeholders}) OR name COLLATE NOCASE IN ({placeholders})
                          )
                    )"""
                )
                params.extend(p_targets)
                params.extend(p_targets)

        # 14. User albums filter (OR union) — supports both ID and Name matching
        if criteria.album_ids:
            alb_targets = list(criteria.album_ids)
            placeholders = ', '.join('?' for _ in alb_targets)
            clauses.append(
                f"""EXISTS (
                    SELECT 1
                    FROM asset_albums aa
                    JOIN albums alb ON aa.album_id = alb.id AND aa.library_name = alb.library_name
                    WHERE aa.asset_id = a.id
                      AND aa.library_name = a.library_name
                      AND alb.name IN (
                          SELECT name FROM albums
                          WHERE id IN ({placeholders}) OR name COLLATE NOCASE IN ({placeholders})
                      )
                )"""
            )
            params.extend(alb_targets)
            params.extend(alb_targets)

        where_sql = ' AND '.join(f'({c})' for c in clauses)
        return where_sql, params

    def count_eligible_assets(self, criteria: AssetFilterCriteria) -> int:
        """Count eligible assets matching the unified filter criteria in < 3ms."""
        where_sql, params = self._build_filter_clauses(criteria)
        sql = f'SELECT COUNT(DISTINCT a.id) FROM assets a WHERE {where_sql}'
        count = self._db.fetch_val(sql, params)
        return int(count) if count is not None else 0

    def get_asset_counts(self, criteria: AssetFilterCriteria) -> dict[str, int]:
        """Compute total, GPS, Date, and mode-eligible asset counts in a single fast query."""
        where_sql, params = self._build_filter_clauses(
            criteria,
            ignore_location_mode=True,
            ignore_date_mode=True,
        )
        gps_condition = (
            'a.latitude IS NOT NULL AND a.longitude IS NOT NULL AND NOT ('
            'abs(a.latitude) < 1e-6 AND abs(a.longitude) < 1e-6'
            ')'
        )
        date_condition = 'a.capture_datetime IS NOT NULL'
        sql = f"""
            SELECT
                COUNT(DISTINCT a.id) AS total_count,
                COUNT(DISTINCT CASE WHEN {gps_condition} THEN a.id END) AS gps_count,
                COUNT(DISTINCT CASE WHEN {date_condition} THEN a.id END) AS date_count,
                COUNT(DISTINCT CASE WHEN {gps_condition} AND {date_condition} THEN a.id END) AS both_count
            FROM assets a
            WHERE {where_sql}
        """
        row = self._db.fetch_one(sql, params)
        if not row:
            return {'eligible_count': 0, 'total_count': 0, 'gps_count': 0, 'date_count': 0}

        total_cnt = int(row['total_count'] or 0)
        gps_cnt = int(row['gps_count'] or 0)
        date_cnt = int(row['date_count'] or 0)
        both_cnt = int(row['both_count'] or 0)

        if criteria.location_mode and criteria.date_mode:
            eligible = both_cnt
        elif criteria.location_mode:
            eligible = gps_cnt
        elif criteria.date_mode:
            eligible = date_cnt
        else:
            eligible = total_cnt

        return {
            'eligible_count': eligible,
            'total_count': total_cnt,
            'gps_count': gps_cnt,
            'date_count': date_cnt,
        }

    def fetch_candidate_assets(
        self,
        criteria: AssetFilterCriteria,
        limit: int = 250,
    ) -> dict[str, AssetAnswer]:
        """Fetch randomized candidate assets matching the unified filter criteria."""
        where_sql, params = self._build_filter_clauses(criteria)
        sql = f"""
            SELECT a.id, a.latitude, a.longitude, a.capture_datetime, a.city, a.state, a.country
            FROM assets a
            WHERE {where_sql}
            GROUP BY a.id
            ORDER BY MIN(a.times_played) ASC, RANDOM()
            LIMIT ?
        """
        rows = self._db.fetch_all(sql, (*params, limit))
        results: dict[str, AssetAnswer] = {}
        for r in rows:
            aid = str(r['id'])
            capture_dt: datetime | None = None
            if r.get('capture_datetime'):
                with contextlib.suppress(ValueError):
                    capture_dt = datetime.fromisoformat(str(r['capture_datetime']))

            results[aid] = AssetAnswer(
                latitude=float(r['latitude']) if r.get('latitude') is not None else None,
                longitude=float(r['longitude']) if r.get('longitude') is not None else None,
                capture_datetime=capture_dt,
                city=r.get('city'),
                state=r.get('state'),
                country=r.get('country'),
            )
        return results

    def get_filter_options(
        self,
        libraries: list[str] | tuple[str, ...] | None,
        settings: AppSettings,
    ) -> LibraryFiltersResponse:
        """Fetch all available filter options for one or more libraries (or all if None).

        Gated by environment date boundaries and whitelists/blacklists.
        """
        libs = [str(lib).strip() for lib in libraries if str(lib).strip()] if libraries else []

        clauses: list[str] = ["a.file_type != 'VIDEO'"]
        params: list[Any] = []
        if libs:
            placeholders = ', '.join('?' for _ in libs)
            clauses.append(f'a.library_name IN ({placeholders})')
            params.extend(libs)
        base_where = ' AND '.join(f'({c})' for c in clauses)

        # 1. Countries
        country_rows = self._db.fetch_all(
            f"""
            SELECT DISTINCT a.country
            FROM assets a
            WHERE {base_where}
              AND a.country IS NOT NULL
              AND TRIM(a.country) != ''
              AND LOWER(a.country) NOT IN ('none', 'null')
            ORDER BY a.country COLLATE NOCASE
            """,
            params,
        )
        raw_countries = [str(r['country']).strip() for r in country_rows if r.get('country')]
        if settings.country_whitelist and not raw_countries:
            raw_countries = [c.title() for c in settings.country_whitelist]

        filtered_countries = [
            c
            for c in raw_countries
            if (not settings.country_whitelist or c.lower() in settings.country_whitelist)
            and (not settings.country_blacklist or c.lower() not in settings.country_blacklist)
        ]
        filtered_countries.sort(key=str.lower)

        # 2. Cities (with country association)
        city_rows = self._db.fetch_all(
            f"""
            SELECT a.city, a.country, COUNT(DISTINCT a.id) as count
            FROM assets a
            WHERE {base_where}
              AND a.city IS NOT NULL
              AND TRIM(a.city) != ''
              AND LOWER(a.city) NOT IN ('none', 'null')
            GROUP BY a.city, a.country
            ORDER BY a.city COLLATE NOCASE
            """,
            params,
        )
        city_options: list[CityOption] = []
        for r in city_rows:
            c_name = str(r['city']).strip()
            c_country = str(r['country']).strip() if r.get('country') else None
            c_lower = c_name.lower()
            if (not settings.city_whitelist or c_lower in settings.city_whitelist) and (
                not settings.city_blacklist or c_lower not in settings.city_blacklist
            ):
                if c_country:
                    country_lower = c_country.lower()
                    if settings.country_whitelist and country_lower not in settings.country_whitelist:
                        continue
                    if settings.country_blacklist and country_lower in settings.country_blacklist:
                        continue
                elif settings.country_whitelist:
                    continue
                city_options.append(CityOption(name=c_name, country=c_country))

        # 3. People (deduplicated by name across libraries)
        people_rows = self._db.fetch_all(
            f"""
            SELECT p.name, MIN(p.id) as id
            FROM people p
            JOIN asset_people ap ON p.id = ap.person_id AND p.library_name = ap.library_name
            JOIN assets a ON ap.asset_id = a.id AND ap.library_name = a.library_name
            WHERE {base_where}
            GROUP BY p.name COLLATE NOCASE
            ORDER BY p.name COLLATE NOCASE
            """,
            params,
        )
        person_options: list[PersonOption] = []
        for r in people_rows:
            p_name = str(r['name']).strip()
            p_id = str(r['id']).strip()
            p_lower = p_name.lower()
            if (not settings.people_whitelist or p_lower in settings.people_whitelist) and (
                not settings.people_blacklist or p_lower not in settings.people_blacklist
            ):
                person_options.append(PersonOption(id=p_id, name=p_name))

        # 4. Date bounds
        bounds_row = self._db.fetch_one(
            f"""
            SELECT MIN(a.capture_datetime) as min_dt, MAX(a.capture_datetime) as max_dt
            FROM assets a
            WHERE {base_where}
              AND a.capture_datetime IS NOT NULL
              AND TRIM(a.capture_datetime) != ''
              AND LOWER(a.capture_datetime) NOT IN ('none', 'null')
            """,
            params,
        )
        min_month: str | None = None
        max_month: str | None = None
        if bounds_row:
            if bounds_row.get('min_dt') and len(str(bounds_row['min_dt'])) >= 7:
                min_month = str(bounds_row['min_dt'])[:7]
            if bounds_row.get('max_dt') and len(str(bounds_row['max_dt'])) >= 7:
                max_month = str(bounds_row['max_dt'])[:7]

        # Apply .env date lower/upper bounds as clamps if set
        if settings.date_lower_bound:
            env_min = settings.date_lower_bound.strftime('%Y-%m')
            min_month = max(min_month, env_min) if min_month is not None else env_min
        if settings.date_upper_bound:
            env_max = settings.date_upper_bound.strftime('%Y-%m')
            max_month = min(max_month, env_max) if max_month is not None else env_max

        return LibraryFiltersResponse(
            date_range=DateRangeOption(min_month=min_month, max_month=max_month),
            countries=filtered_countries,
            cities=city_options,
            people=person_options,
        )

    def get_person_names(self, person_ids: list[str]) -> dict[str, str]:
        """Look up person display names by ID from indexed metadata."""
        if not person_ids:
            return {}
        placeholders = ', '.join('?' for _ in person_ids)
        rows = self._db.fetch_all(
            f'SELECT DISTINCT id, name FROM people WHERE id IN ({placeholders})',
            person_ids,
        )
        return {str(r['id']).strip(): str(r['name']).strip() for r in rows if r.get('id') and r.get('name')}

    def get_facet_counts(self, criteria: AssetFilterCriteria) -> FacetCounts:
        """Compute matching photo counts for each facet option under current criteria.

        Facets are evaluated independently:
        - The count for each country is evaluated using criteria excluding user-selected countries.
        - The count for each city is evaluated using criteria excluding user-selected cities.
        - The count for each person option is evaluated using criteria excluding user-selected person_ids.
        - The count for each album option is evaluated using criteria excluding user-selected album_ids.
        """
        # 1. Countries
        country_crit = replace(criteria, countries=())
        c_where, c_params = self._build_filter_clauses(country_crit)
        country_rows = self._db.fetch_all(
            f"""
            SELECT a.country, COUNT(DISTINCT a.id) as count
            FROM assets a
            WHERE {c_where}
              AND a.country IS NOT NULL
              AND TRIM(a.country) != ''
              AND LOWER(a.country) NOT IN ('none', 'null')
            GROUP BY a.country
            """,
            c_params,
        )
        country_counts = {str(r['country']).strip(): int(r['count']) for r in country_rows if r.get('country')}

        # 2. Cities
        city_crit = replace(criteria, cities=())
        ct_where, ct_params = self._build_filter_clauses(city_crit)
        city_rows = self._db.fetch_all(
            f"""
            SELECT a.city, COUNT(DISTINCT a.id) as count
            FROM assets a
            WHERE {ct_where}
              AND a.city IS NOT NULL
              AND TRIM(a.city) != ''
              AND LOWER(a.city) NOT IN ('none', 'null')
            GROUP BY a.city
            """,
            ct_params,
        )
        city_counts = {str(r['city']).strip(): int(r['count']) for r in city_rows if r.get('city')}

        # 3. People (aggregated by name across libraries, populated by both name and ID)
        people_crit = replace(criteria, person_ids=())
        p_where, p_params = self._build_filter_clauses(people_crit)
        people_rows = self._db.fetch_all(
            f"""
            SELECT ap.person_id, p.name, COUNT(DISTINCT a.id) as count
            FROM assets a
            JOIN asset_people ap ON a.id = ap.asset_id AND a.library_name = ap.library_name
            JOIN people p ON ap.person_id = p.id AND ap.library_name = p.library_name
            WHERE {p_where}
            GROUP BY p.name COLLATE NOCASE
            """,
            p_params,
        )
        people_counts: dict[str, int] = {}
        for r in people_rows:
            cnt = int(r['count'])
            if r.get('name'):
                people_counts[str(r['name']).strip()] = cnt
            if r.get('person_id'):
                people_counts[str(r['person_id']).strip()] = cnt

        # 4. Albums (aggregated by name across libraries, populated by both name and ID)
        album_crit = replace(criteria, album_ids=())
        al_where, al_params = self._build_filter_clauses(album_crit)
        album_rows = self._db.fetch_all(
            f"""
            SELECT aa.album_id, alb.name, COUNT(DISTINCT a.id) as count
            FROM assets a
            JOIN asset_albums aa ON a.id = aa.asset_id AND a.library_name = aa.library_name
            JOIN albums alb ON aa.album_id = alb.id AND aa.library_name = alb.library_name
            WHERE {al_where}
            GROUP BY alb.name COLLATE NOCASE
            """,
            al_params,
        )
        album_counts: dict[str, int] = {}
        for r in album_rows:
            cnt = int(r['count'])
            if r.get('name'):
                album_counts[str(r['name']).strip()] = cnt
            if r.get('album_id'):
                album_counts[str(r['album_id']).strip()] = cnt

        return FacetCounts(
            countries=country_counts,
            cities=city_counts,
            people=people_counts,
            albums=album_counts,
        )

    def get_albums(
        self,
        library_names: list[str] | tuple[str, ...] | None = None,
        include_shared: bool = True,
    ) -> list[dict[str, Any]]:
        """Return distinct albums deduplicated by name across libraries, matching ownership constraints."""
        where_clauses: list[str] = []
        params: list[Any] = []

        if library_names:
            placeholders = ', '.join('?' for _ in library_names)
            where_clauses.append(f'library_name IN ({placeholders})')
            params.extend(library_names)

        if not include_shared:
            where_clauses.append('is_shared = 0')

        where_str = f'WHERE {" AND ".join(where_clauses)}' if where_clauses else ''
        album_rows = self._db.fetch_all(
            f"""
            SELECT MIN(id) as id, name
            FROM albums
            {where_str}
            GROUP BY name COLLATE NOCASE
            ORDER BY name COLLATE NOCASE
            """,
            params,
        )
        return [
            {'id': str(r['id']).strip(), 'name': str(r['name']).strip()}
            for r in album_rows
            if r.get('id') and r.get('name')
        ]

    def get_tags(
        self,
        libraries: list[str] | tuple[str, ...] | None = None,
        settings: AppSettings | None = None,
    ) -> list[dict[str, str]]:
        """Return indexed tags for one or more libraries (or all if None), optionally filtered by settings."""
        clauses = []
        params: list[Any] = []
        if libraries:
            placeholders = ', '.join('?' for _ in libraries)
            clauses.append(f'library_name IN ({placeholders})')
            params.extend(tuple(libraries))
        where_str = f'WHERE {" AND ".join(clauses)}' if clauses else ''
        sql = f'SELECT DISTINCT id, name FROM tags {where_str} ORDER BY name COLLATE NOCASE'
        rows = self._db.fetch_all(sql, tuple(params))
        tags: list[dict[str, str]] = []
        for r in rows:
            t_id = str(r['id'])
            t_name = str(r['name'])
            t_lower = t_name.lower()
            t_id_lower = t_id.lower()
            if settings:
                if settings.tag_whitelist and (
                    t_lower not in settings.tag_whitelist and t_id_lower not in settings.tag_whitelist
                ):
                    continue
                if settings.tag_blacklist and (
                    t_lower in settings.tag_blacklist or t_id_lower in settings.tag_blacklist
                ):
                    continue
            tags.append({'id': t_id, 'name': t_name})
        return tags

from __future__ import annotations

import contextlib
import logging
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from src.config import AppSettings
from src.immich.client import AssetAnswer
from src.models import CityOption, DateRangeOption, LibraryFiltersResponse, PersonOption
from src.storage.db import DatabaseManager

logger = logging.getLogger(__name__)

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS sync_state (
    library_name TEXT PRIMARY KEY,
    last_sync_at TEXT,
    sync_status TEXT DEFAULT 'idle',
    sync_error TEXT,
    total_assets INTEGER DEFAULT 0,
    synced_assets INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS assets (
    id TEXT PRIMARY KEY,
    library_name TEXT NOT NULL,
    is_shared INTEGER NOT NULL DEFAULT 0,
    is_partner INTEGER NOT NULL DEFAULT 0,
    file_type TEXT NOT NULL DEFAULT 'IMAGE',
    latitude REAL,
    longitude REAL,
    country TEXT,
    city TEXT,
    capture_datetime TEXT
);

CREATE INDEX IF NOT EXISTS idx_assets_lib_country ON assets(library_name, country);
CREATE INDEX IF NOT EXISTS idx_assets_lib_city ON assets(library_name, city);
CREATE INDEX IF NOT EXISTS idx_assets_lib_datetime ON assets(library_name, capture_datetime);
CREATE INDEX IF NOT EXISTS idx_assets_lib_coords ON assets(library_name, latitude, longitude);

CREATE TABLE IF NOT EXISTS people (
    id TEXT PRIMARY KEY,
    library_name TEXT NOT NULL,
    name TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS asset_people (
    asset_id TEXT NOT NULL,
    person_id TEXT NOT NULL,
    PRIMARY KEY(asset_id, person_id),
    FOREIGN KEY(asset_id) REFERENCES assets(id) ON DELETE CASCADE,
    FOREIGN KEY(person_id) REFERENCES people(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_asset_people_person ON asset_people(person_id);

CREATE TABLE IF NOT EXISTS albums (
    id TEXT PRIMARY KEY,
    library_name TEXT NOT NULL,
    name TEXT NOT NULL,
    is_shared INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS asset_albums (
    asset_id TEXT NOT NULL,
    album_id TEXT NOT NULL,
    PRIMARY KEY(asset_id, album_id),
    FOREIGN KEY(asset_id) REFERENCES assets(id) ON DELETE CASCADE,
    FOREIGN KEY(album_id) REFERENCES albums(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_asset_albums_album ON asset_albums(album_id);
"""


@dataclass(frozen=True)
class AssetFilterCriteria:
    library_name: str
    location_mode: bool = False
    date_mode: bool = False
    min_date: date | None = None
    max_date: date | None = None
    countries: tuple[str, ...] = ()
    cities: tuple[str, ...] = ()
    person_ids: tuple[str, ...] = ()
    people_mode: str = 'OR'
    album_ids: tuple[str, ...] = ()
    include_shared_albums: bool = False
    include_partner_assets: bool = False


class MetadataStore:
    """Manages SQLite-based metadata storage, indexing, and unified filtering for Immich Quiz."""

    def __init__(self, db: DatabaseManager) -> None:
        self._db = db
        self.init_schema()

    def init_schema(self) -> None:
        self._db.execute_script(SCHEMA_SQL)

    def has_synced_assets(self, library_name: str) -> bool:
        count = self._db.fetch_val(
            'SELECT COUNT(*) FROM assets WHERE library_name = ?',
            (library_name,),
        )
        return bool(count and count > 0)

    def get_sync_state(self, library_name: str) -> dict[str, Any]:
        row = self._db.fetch_one(
            'SELECT * FROM sync_state WHERE library_name = ?',
            (library_name,),
        )
        if row:
            return row
        return {
            'library_name': library_name,
            'last_sync_at': None,
            'sync_status': 'idle',
            'sync_error': None,
            'total_assets': 0,
            'synced_assets': 0,
        }

    def set_sync_state(
        self,
        library_name: str,
        *,
        status: str,
        total_assets: int | None = None,
        synced_assets: int | None = None,
        error: str | None = None,
        last_sync_at: str | None = None,
    ) -> None:
        with self._db.connection() as conn:
            existing = conn.execute(
                'SELECT total_assets, synced_assets, last_sync_at FROM sync_state WHERE library_name = ?',
                (library_name,),
            ).fetchone()

            tot = total_assets if total_assets is not None else (existing['total_assets'] if existing else 0)
            sync_cnt = synced_assets if synced_assets is not None else (existing['synced_assets'] if existing else 0)
            last_sync = last_sync_at if last_sync_at is not None else (existing['last_sync_at'] if existing else None)

            conn.execute(
                """
                INSERT INTO sync_state (
                    library_name, last_sync_at, sync_status, sync_error, total_assets, synced_assets
                )
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(library_name) DO UPDATE SET
                    last_sync_at = excluded.last_sync_at,
                    sync_status = excluded.sync_status,
                    sync_error = excluded.sync_error,
                    total_assets = excluded.total_assets,
                    synced_assets = excluded.synced_assets
                """,
                (library_name, last_sync, status, error, tot, sync_cnt),
            )

    def upsert_people(self, library_name: str, people: list[dict[str, str]]) -> None:
        with self._db.connection() as conn:
            for p in people:
                pid = str(p.get('id', '')).strip()
                name = str(p.get('name', '')).strip()
                if pid and name:
                    conn.execute(
                        """
                        INSERT INTO people (id, library_name, name)
                        VALUES (?, ?, ?)
                        ON CONFLICT(id) DO UPDATE SET
                            library_name = excluded.library_name,
                            name = excluded.name
                        """,
                        (pid, library_name, name),
                    )

    def upsert_albums(self, library_name: str, albums: list[dict[str, Any]]) -> None:
        with self._db.connection() as conn:
            for a in albums:
                aid = str(a.get('id', '')).strip()
                name = str(a.get('name', '') or a.get('albumName', '')).strip()
                is_shared = 1 if bool(a.get('isShared') or a.get('shared')) else 0
                if aid and name:
                    conn.execute(
                        """
                        INSERT INTO albums (id, library_name, name, is_shared)
                        VALUES (?, ?, ?, ?)
                        ON CONFLICT(id) DO UPDATE SET
                            library_name = excluded.library_name,
                            name = excluded.name,
                            is_shared = excluded.is_shared
                        """,
                        (aid, library_name, name, is_shared),
                    )

    def upsert_assets_batch(
        self,
        library_name: str,
        assets: list[dict[str, Any]],
        asset_people: list[tuple[str, str]],
        asset_albums: list[tuple[str, str]],
    ) -> None:
        with self._db.connection() as conn:
            for a in assets:
                country_val = a.get('country')
                city_val = a.get('city')
                country_clean = str(country_val).strip() if country_val else None
                if country_clean and country_clean.lower() in ('none', 'null', 'undefined', ''):
                    country_clean = None
                city_clean = str(city_val).strip() if city_val else None
                if city_clean and city_clean.lower() in ('none', 'null', 'undefined', ''):
                    city_clean = None

                conn.execute(
                    """
                    INSERT INTO assets (
                        id, library_name, is_shared, is_partner, file_type,
                        latitude, longitude, country, city, capture_datetime
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        library_name = excluded.library_name,
                        is_shared = excluded.is_shared,
                        is_partner = excluded.is_partner,
                        file_type = excluded.file_type,
                        latitude = excluded.latitude,
                        longitude = excluded.longitude,
                        country = excluded.country,
                        city = excluded.city,
                        capture_datetime = excluded.capture_datetime
                    """,
                    (
                        a['id'],
                        library_name,
                        a['is_shared'],
                        a['is_partner'],
                        a.get('file_type', 'IMAGE'),
                        a.get('latitude'),
                        a.get('longitude'),
                        country_clean,
                        city_clean,
                        a.get('capture_datetime'),
                    ),
                )

            for aid, pid in asset_people:
                conn.execute(
                    """
                    INSERT OR IGNORE INTO asset_people (asset_id, person_id)
                    SELECT ?, id FROM people WHERE id = ?
                    """,
                    (aid, pid),
                )

            for aid, album_id in asset_albums:
                conn.execute(
                    """
                    INSERT OR IGNORE INTO asset_albums (asset_id, album_id)
                    SELECT ?, id FROM albums WHERE id = ?
                    """,
                    (aid, album_id),
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

    def _build_filter_clauses(self, criteria: AssetFilterCriteria) -> tuple[str, list[Any]]:
        """Construct unified SQL WHERE clauses and parameters matching exact quiz filter semantics."""
        clauses: list[str] = ['a.library_name = ?', "a.file_type != 'VIDEO'"]
        params: list[Any] = [criteria.library_name]

        # 1. Location mode: non-zero lat/lon
        if criteria.location_mode:
            clauses.append(
                'a.latitude IS NOT NULL AND a.longitude IS NOT NULL AND NOT ('
                'abs(a.latitude) < 1e-6 AND abs(a.longitude) < 1e-6'
                ')'
            )

        # 2. Date mode: capture datetime required
        if criteria.date_mode:
            clauses.append('a.capture_datetime IS NOT NULL')

        # 3. Date bounds (ISO8601 string comparison)
        if criteria.min_date:
            clauses.append('a.capture_datetime >= ?')
            params.append(f'{criteria.min_date.isoformat()}T00:00:00')
        if criteria.max_date:
            clauses.append('a.capture_datetime <= ?')
            params.append(f'{criteria.max_date.isoformat()}T23:59:59.999')

        # 4. Ownership flags
        has_selected_albums = bool(criteria.album_ids)
        if not has_selected_albums:
            if not criteria.include_shared_albums and not criteria.include_partner_assets:
                clauses.append(
                    'a.is_shared = 0 AND a.is_partner = 0 AND a.id NOT IN ('
                    'SELECT aa.asset_id FROM asset_albums aa '
                    'JOIN albums alb ON aa.album_id = alb.id WHERE alb.is_shared = 1'
                    ')'
                )
            elif not criteria.include_shared_albums:
                clauses.append(
                    'a.is_shared = 0 AND a.id NOT IN ('
                    'SELECT aa.asset_id FROM asset_albums aa '
                    'JOIN albums alb ON aa.album_id = alb.id WHERE alb.is_shared = 1'
                    ')'
                )
            elif not criteria.include_partner_assets:
                clauses.append('a.is_partner = 0')

        # 5. Countries filter (case-insensitive)
        if criteria.countries:
            placeholders = ', '.join('?' for _ in criteria.countries)
            clauses.append(f'LOWER(a.country) IN ({placeholders})')
            params.extend(c.lower() for c in criteria.countries)

        # 6. Cities filter (case-insensitive)
        if criteria.cities:
            city_placeholders = ', '.join('?' for _ in criteria.cities)
            clauses.append(f'LOWER(a.city) IN ({city_placeholders})')
            params.extend(c.lower() for c in criteria.cities)

        # 7. People filter (OR union vs AND intersection)
        if criteria.person_ids:
            if criteria.people_mode.upper() == 'AND' and len(criteria.person_ids) > 1:
                placeholders = ', '.join('?' for _ in criteria.person_ids)
                clauses.append(
                    f"""a.id IN (
                        SELECT ap.asset_id
                        FROM asset_people ap
                        WHERE ap.person_id IN ({placeholders})
                        GROUP BY ap.asset_id
                        HAVING COUNT(DISTINCT ap.person_id) = ?
                    )"""
                )
                params.extend(criteria.person_ids)
                params.append(len(set(criteria.person_ids)))
            else:
                placeholders = ', '.join('?' for _ in criteria.person_ids)
                clauses.append(
                    f"""a.id IN (
                        SELECT ap.asset_id
                        FROM asset_people ap
                        WHERE ap.person_id IN ({placeholders})
                    )"""
                )
                params.extend(criteria.person_ids)

        # 8. Albums filter (OR union)
        if criteria.album_ids:
            placeholders = ', '.join('?' for _ in criteria.album_ids)
            clauses.append(
                f"""a.id IN (
                    SELECT aa.asset_id
                    FROM asset_albums aa
                    WHERE aa.album_id IN ({placeholders})
                )"""
            )
            params.extend(criteria.album_ids)

        where_sql = ' AND '.join(f'({c})' for c in clauses)
        return where_sql, params

    def count_eligible_assets(self, criteria: AssetFilterCriteria) -> int:
        """Count eligible assets matching the unified filter criteria in < 3ms."""
        where_sql, params = self._build_filter_clauses(criteria)
        sql = f'SELECT COUNT(DISTINCT a.id) FROM assets a WHERE {where_sql}'
        count = self._db.fetch_val(sql, params)
        return int(count) if count is not None else 0

    def fetch_candidate_assets(
        self,
        criteria: AssetFilterCriteria,
        limit: int = 250,
    ) -> dict[str, AssetAnswer]:
        """Fetch randomized candidate assets matching the unified filter criteria."""
        where_sql, params = self._build_filter_clauses(criteria)
        sql = f"""
            SELECT a.id, a.latitude, a.longitude, a.capture_datetime, a.city, a.country
            FROM assets a
            WHERE {where_sql}
            ORDER BY RANDOM()
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
                country=r.get('country'),
            )
        return results

    def get_filter_options(
        self,
        library_name: str,
        settings: AppSettings,
    ) -> LibraryFiltersResponse:
        """Fetch unique filter options from indexed SQLite metadata.

        Strictly gated by ownership settings and whitelists/blacklists.
        """
        clauses: list[str] = ['a.library_name = ?', "a.file_type != 'VIDEO'"]
        params: list[Any] = [library_name]

        if not settings.include_shared_albums and not settings.include_partner_assets:
            clauses.append(
                'a.is_shared = 0 AND a.is_partner = 0 AND a.id NOT IN ('
                'SELECT aa.asset_id FROM asset_albums aa '
                'JOIN albums alb ON aa.album_id = alb.id WHERE alb.is_shared = 1'
                ')'
            )
        elif not settings.include_shared_albums:
            clauses.append(
                'a.is_shared = 0 AND a.id NOT IN ('
                'SELECT aa.asset_id FROM asset_albums aa '
                'JOIN albums alb ON aa.album_id = alb.id WHERE alb.is_shared = 1'
                ')'
            )
        elif not settings.include_partner_assets:
            clauses.append('a.is_partner = 0')

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
            SELECT a.city, a.country, COUNT(*) as count
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
                city_options.append(CityOption(name=c_name, country=c_country))

        # 3. People
        people_rows = self._db.fetch_all(
            f"""
            SELECT DISTINCT p.id, p.name
            FROM people p
            JOIN asset_people ap ON p.id = ap.person_id
            JOIN assets a ON ap.asset_id = a.id
            WHERE {base_where}
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
        if settings.fetch_photos_date_lower_bound:
            env_min = settings.fetch_photos_date_lower_bound.strftime('%Y-%m')
            min_month = max(min_month, env_min) if min_month is not None else env_min
        if settings.fetch_photos_date_upper_bound:
            env_max = settings.fetch_photos_date_upper_bound.strftime('%Y-%m')
            max_month = min(max_month, env_max) if max_month is not None else env_max

        return LibraryFiltersResponse(
            date_range=DateRangeOption(min_month=min_month, max_month=max_month),
            countries=filtered_countries,
            cities=city_options,
            people=person_options,
        )

    def get_albums(self, library_name: str, include_shared_albums: bool = False) -> list[dict[str, str]]:
        """Return indexed albums for a library, respecting shared album visibility settings."""
        if include_shared_albums:
            rows = self._db.fetch_all(
                'SELECT id, name FROM albums WHERE library_name = ? ORDER BY name COLLATE NOCASE',
                (library_name,),
            )
        else:
            rows = self._db.fetch_all(
                'SELECT id, name FROM albums WHERE library_name = ? AND is_shared = 0 ORDER BY name COLLATE NOCASE',
                (library_name,),
            )
        return [{'id': str(r['id']), 'name': str(r['name'])} for r in rows]

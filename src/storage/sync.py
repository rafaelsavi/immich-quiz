from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

from src.immich.client import ImmichClient, ImmichClientError
from src.storage.metadata import MetadataStore

logger = logging.getLogger(__name__)


def _clean_str(val: Any) -> str | None:
    if val is None:
        return None
    s = str(val).strip()
    if not s or s.lower() in ('none', 'null', 'undefined'):
        return None
    return s


class SyncEngine:
    """Coordinates background synchronization between Immich and the local SQLite metadata index."""

    def __init__(
        self,
        immich: ImmichClient,
        metadata_store: MetadataStore,
        *,
        on_sync_complete: Callable[[str], None] | None = None,
    ) -> None:
        self._immich = immich
        self._metadata_store = metadata_store
        self._on_sync_complete = on_sync_complete
        self._active_sync_tasks: dict[str, asyncio.Task[None]] = {}
        self._sync_warnings: dict[str, str] = {}

    def is_syncing(self, library_name: str) -> bool:
        task = self._active_sync_tasks.get(library_name)
        return task is not None and not task.done()

    def get_sync_status(self, library_name: str) -> dict[str, Any]:
        state = self._metadata_store.get_sync_state(library_name)
        # If task has completed or failed, ensure status reflects accurately
        if state.get('sync_status') == 'syncing' and not self.is_syncing(library_name):
            state['sync_status'] = 'idle'
        if library_name in self._sync_warnings:
            state['warning'] = self._sync_warnings[library_name]
        return state

    def trigger_sync(self, library_name: str) -> asyncio.Task[None]:
        """Trigger an asynchronous background sync for a library if not already running."""
        if self.is_syncing(library_name):
            logger.info('Sync already in progress for library %s', library_name)
            return self._active_sync_tasks[library_name]

        task = asyncio.create_task(self.sync_library(library_name))
        self._active_sync_tasks[library_name] = task

        def _on_done(t: asyncio.Task[None]) -> None:
            self._active_sync_tasks.pop(library_name, None)
            try:
                t.result()
            except Exception as exc:
                logger.error('Background sync failed for library %s: %s', library_name, exc, exc_info=True)

        task.add_done_callback(_on_done)
        return task

    async def sync_library(self, library_name: str) -> None:
        """Perform full metadata synchronization for a specific library."""
        logger.info('Starting metadata sync for library: %s', library_name)
        self._metadata_store.set_sync_state(
            library_name,
            status='syncing',
            error=None,
            synced_assets=0,
        )

        try:
            self._sync_warnings.pop(library_name, None)
            key = self._immich._library_key(library_name)
            current_user_id = await self._immich._current_user_id(key)

            # 1. Fetch & store people
            raw_people = await self._immich._request_json('GET', '/people', key)
            people_list = (
                raw_people.get('people', raw_people)
                if isinstance(raw_people, dict)
                else (raw_people if isinstance(raw_people, list) else [])
            )
            people_data: list[dict[str, str]] = []
            for p in people_list:
                if isinstance(p, dict):
                    pid = str(p.get('id', '')).strip()
                    pname = str(p.get('name', '')).strip()
                    if pid and pname and not bool(p.get('isHidden', False)):
                        people_data.append({'id': pid, 'name': pname})
            self._metadata_store.upsert_people(library_name, people_data)
            known_person_ids = {p['id'] for p in people_data}

            # 2. Fetch & store albums
            raw_albums = await self._immich._request_json('GET', '/albums', key)
            albums_list = raw_albums if isinstance(raw_albums, list) else []
            albums_data: list[dict[str, Any]] = []
            album_asset_map: dict[str, set[str]] = {}  # asset_id -> set of album_ids
            shared_album_ids: set[str] = set()

            for alb in albums_list:
                if isinstance(alb, dict):
                    aid = str(alb.get('id', '')).strip()
                    aname = str(alb.get('albumName', '') or alb.get('name', '')).strip()
                    is_shared = ImmichClient._is_shared_album(alb, current_user_id)
                    if is_shared:
                        shared_album_ids.add(aid)
                    if aid and aname:
                        albums_data.append({'id': aid, 'name': aname, 'isShared': is_shared})

                        # Fetch album assets to populate album junction
                        try:
                            alb_detail = await self._immich._request_json('GET', f'/albums/{aid}', key)
                            alb_assets = self._immich._extract_asset_items(alb_detail)
                            if not alb_assets and alb.get('assetCount', 0) > 0:
                                search_alb = await self._immich._request_json(
                                    'POST',
                                    '/search/metadata',
                                    key,
                                    json={'albumIds': [aid], 'size': 1000},
                                )
                                alb_assets = self._immich._extract_asset_items(search_alb)

                            for item in alb_assets:
                                item_id = str(item.get('id', '') or item.get('assetId', '')).strip()
                                if item_id:
                                    if item_id not in album_asset_map:
                                        album_asset_map[item_id] = set()
                                    album_asset_map[item_id].add(aid)
                        except ImmichClientError as exc:
                            logger.warning('Failed to fetch assets for album %s: %s', aid, exc)

            self._metadata_store.upsert_albums(library_name, albums_data)
            known_album_ids = {a['id'] for a in albums_data}

            # 3. Paginate through all assets via /search/metadata
            page_size = 250
            page_num = 1
            seen_asset_ids: set[str] = set()
            total_reported: int | None = await self._immich.get_asset_count(library_name)
            if total_reported is None:
                msg = (
                    f"Immich /search/statistics did not return an asset count for library '{library_name}'. "
                    'Sync will proceed without total progress estimate.'
                )
                logger.warning(msg)
                self._sync_warnings[library_name] = msg

            while True:
                payload = {
                    'size': page_size,
                    'page': page_num,
                    'withExif': True,
                    'withPartners': True,
                    'isShared': True,
                    'withPeople': True,
                }
                raw_page = await self._immich._request_json('POST', '/search/metadata', key, json=payload)
                if total_reported is None:
                    extracted_total = self._immich._extract_total_assets(raw_page)
                    if extracted_total is not None and extracted_total > 0:
                        total_reported = extracted_total

                items = self._immich._extract_asset_items(raw_page)
                if not items:
                    break

                batch_assets: list[dict[str, Any]] = []
                batch_asset_people: list[tuple[str, str]] = []
                batch_asset_albums: list[tuple[str, str]] = []

                for item in items:
                    aid = str(item.get('id', '') or item.get('assetId', '')).strip()
                    if not aid:
                        continue
                    seen_asset_ids.add(aid)

                    # Determine ownership flags
                    owner_id = ImmichClient._extract_owner_id(item)
                    in_shared_album = bool(aid in album_asset_map and (album_asset_map[aid] & shared_album_ids))
                    has_shared_prop = bool(item.get('isShared') or item.get('shared'))
                    is_shared_flag = 1 if (has_shared_prop or in_shared_album) else 0
                    is_other_owner = bool(owner_id and current_user_id and owner_id != current_user_id)
                    is_partner_flag = 1 if (is_other_owner and not is_shared_flag) else 0

                    # Extract EXIF & location
                    exif = ImmichClient._exif(item)
                    lat: float | None = None
                    lon: float | None = None
                    raw_lat = exif.get('latitude')
                    raw_lon = exif.get('longitude')
                    if raw_lat is not None and raw_lon is not None:
                        try:
                            lat_val = float(raw_lat)
                            lon_val = float(raw_lon)
                            if not (lat_val == 0.0 and lon_val == 0.0):
                                lat = lat_val
                                lon = lon_val
                        except (ValueError, TypeError):
                            lat = None
                            lon = None

                    city = _clean_str(exif.get('city'))
                    country = _clean_str(exif.get('country'))

                    # Extract capture datetime (normalized to ISO8601 string)
                    capture_dt = ImmichClient.extract_capture_datetime(item)
                    capture_dt_str = capture_dt.isoformat() if capture_dt is not None else None

                    file_type = str(item.get('type', 'IMAGE')).upper()

                    batch_assets.append(
                        {
                            'id': aid,
                            'is_shared': is_shared_flag,
                            'is_partner': is_partner_flag,
                            'file_type': file_type,
                            'latitude': lat,
                            'longitude': lon,
                            'country': country,
                            'city': city,
                            'capture_datetime': capture_dt_str,
                        }
                    )

                    # Extract people (only keep named people present in the people table)
                    people = item.get('people') or item.get('faces') or []
                    if isinstance(people, list):
                        for p in people:
                            if isinstance(p, dict) and p.get('id'):
                                pid = str(p['id']).strip()
                                if pid and pid in known_person_ids:
                                    batch_asset_people.append((aid, pid))

                    # Attach album associations (only keep albums present in albums table)
                    if aid in album_asset_map:
                        for alb_id in album_asset_map[aid]:
                            if alb_id in known_album_ids:
                                batch_asset_albums.append((aid, alb_id))

                # Batch upsert into SQLite
                self._metadata_store.upsert_assets_batch(
                    library_name,
                    batch_assets,
                    batch_asset_people,
                    batch_asset_albums,
                )

                synced_count = len(seen_asset_ids)
                total_target = total_reported if (total_reported is not None and total_reported >= synced_count) else 0
                self._metadata_store.set_sync_state(
                    library_name,
                    status='syncing',
                    synced_assets=synced_count,
                    total_assets=total_target,
                )

                page_num += 1
                # Yield to the event loop so the server remains responsive during large syncs
                await asyncio.sleep(0.01)

            # 4. Link any album associations that might have been processed
            if album_asset_map:
                with self._metadata_store._db.connection() as conn:
                    for asset_id, album_ids in album_asset_map.items():
                        if asset_id in seen_asset_ids:
                            for album_id in album_ids:
                                if album_id in known_album_ids:
                                    conn.execute(
                                        """
                                        INSERT OR IGNORE INTO asset_albums (asset_id, album_id)
                                        SELECT ?, id FROM albums WHERE id = ?
                                        """,
                                        (asset_id, album_id),
                                    )
                            if album_ids & shared_album_ids:
                                conn.execute(
                                    'UPDATE assets SET is_shared = 1, is_partner = 0 WHERE id = ?',
                                    (asset_id,),
                                )

            # 5. Prune missing assets
            pruned_count = self._metadata_store.prune_missing_assets(library_name, seen_asset_ids)
            if pruned_count > 0:
                logger.info('Pruned %d deleted asset(s) from metadata index for %s', pruned_count, library_name)

            # 6. Mark sync complete
            now_iso = datetime.now(timezone.utc).isoformat()
            total_final = len(seen_asset_ids)
            self._metadata_store.set_sync_state(
                library_name,
                status='idle',
                last_sync_at=now_iso,
                synced_assets=total_final,
                total_assets=total_final,
                error=None,
            )
            logger.info('Successfully finished metadata sync for %s (%d assets)', library_name, total_final)

            if self._on_sync_complete is not None:
                try:
                    self._on_sync_complete(library_name)
                except Exception as cb_exc:
                    logger.warning('on_sync_complete callback failed for library %s: %s', library_name, cb_exc)

        except Exception as exc:
            logger.error('Error during metadata sync for %s: %s', library_name, exc, exc_info=True)
            self._metadata_store.set_sync_state(
                library_name,
                status='error',
                error=str(exc),
            )
            raise

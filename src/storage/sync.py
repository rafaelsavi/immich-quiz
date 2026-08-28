"""Background metadata synchronization coordinator between Immich API and local SQLite cache."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from typing import Any

from src.app_logging import LOGGER_SYNC, get_logger
from src.immich.client import ImmichClient, ImmichClientError
from src.models import SyncMode, SyncStage, SyncStatus
from src.storage.metadata import MetadataStore

logger = get_logger(LOGGER_SYNC)


def _clean_str(val: Any) -> str | None:
    """Normalize string value, stripping whitespace and filtering placeholder null values."""
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
        """Initialize SyncEngine with Immich client, metadata store, and optional completion callback."""
        self._immich = immich
        self._metadata_store = metadata_store
        self._on_sync_complete = on_sync_complete
        self._active_sync_tasks: dict[str, asyncio.Task[None]] = {}
        self._sync_warnings: dict[str, str] = {}

    def is_syncing(self, library_name: str) -> bool:
        """Check whether a background synchronization task is actively running for a library."""
        task = self._active_sync_tasks.get(library_name)
        return task is not None and not task.done()

    def is_any_syncing(self) -> bool:
        """Check whether any background synchronization task is actively running across all libraries."""
        return any(not t.done() for t in self._active_sync_tasks.values())

    def get_sync_status(self, available_libraries: list[str] | str | None = None) -> dict[str, Any]:
        """Fetch consolidated synchronization status dictionary for the given libraries."""
        return self.get_global_sync_status(available_libraries=available_libraries)

    def get_global_sync_status(self, available_libraries: list[str] | str | None = None) -> dict[str, Any]:
        """Compute aggregated progress, stage, error, and timestamp metrics across libraries."""
        if isinstance(available_libraries, str):
            libs = [available_libraries]
        elif available_libraries is not None:
            libs = list(available_libraries)
        elif hasattr(self._immich, 'list_libraries') and self._immich.list_libraries():
            libs = self._immich.list_libraries()
        else:
            all_states = self._metadata_store.get_all_sync_states()
            libs = [s['library_name'] for s in all_states] or list(self._active_sync_tasks.keys())
        states = [self._metadata_store.get_sync_state(lib) for lib in libs]

        total_assets = sum(s.get('total_assets', 0) or 0 for s in states)
        synced_assets = sum(s.get('synced_assets', 0) or 0 for s in states)
        is_syncing = self.is_any_syncing()

        # Determine overall sync status
        has_error = any(s.get('sync_status') == SyncStatus.error.value for s in states)
        never_synced = (
            all(not s.get('last_sync_at') and (s.get('synced_assets') or 0) == 0 for s in states) and not is_syncing
        )

        if is_syncing:
            status = SyncStatus.syncing
        elif has_error:
            status = SyncStatus.error
        elif never_synced:
            status = SyncStatus.never_synced
        else:
            status = SyncStatus.idle

        # Find active syncing library's stage and mode, or default to last completed
        active_stage = SyncStage.idle.value
        active_mode = SyncMode.full.value
        syncing_found = False
        for lib in libs:
            if self.is_syncing(lib):
                st = self._metadata_store.get_sync_state(lib)
                active_stage = st.get('sync_stage', SyncStage.idle.value)
                active_mode = st.get('sync_mode', SyncMode.full.value)
                syncing_found = True
                break

        most_recent = max(states, key=lambda s: s.get('last_sync_at') or '', default=None) if states else None
        if not syncing_found:
            active_stage = SyncStage.idle.value
            if most_recent and most_recent.get('sync_mode'):
                active_mode = most_recent['sync_mode']

        sync_dates = [str(s['last_sync_at']) for s in states if s.get('last_sync_at')]
        last_sync_at = max(sync_dates) if sync_dates else None

        full_sync_dates = [str(s['last_full_sync_at']) for s in states if s.get('last_full_sync_at')]
        last_full_sync_at = max(full_sync_dates) if full_sync_dates else None

        immich_dates = [str(s['last_immich_updated_at']) for s in states if s.get('last_immich_updated_at')]
        last_immich_updated_at = max(immich_dates) if immich_dates else None

        errors = [str(s['sync_error']) for s in states if s.get('sync_error')]
        sync_error = '; '.join(errors) if errors else None

        last_sync_duration = most_recent.get('last_sync_duration_seconds') if most_recent else None

        target_warning_libs = libs or list(self._sync_warnings.keys())
        warnings_dict = {lib: self._sync_warnings[lib] for lib in target_warning_libs if lib in self._sync_warnings}

        return {
            'libraries': libs,
            'is_syncing': is_syncing,
            'last_sync_at': last_sync_at,
            'last_full_sync_at': last_full_sync_at,
            'last_immich_updated_at': last_immich_updated_at,
            'sync_status': status.value if isinstance(status, SyncStatus) else status,
            'sync_mode': active_mode,
            'sync_stage': active_stage,
            'sync_error': sync_error,
            'total_assets': total_assets,
            'synced_assets': synced_assets,
            'last_sync_duration_seconds': last_sync_duration,
            'warnings': warnings_dict,
        }

    def trigger_sync_all(
        self,
        *,
        force_full: bool = False,
        available_libraries: list[str] | None = None,
    ) -> list[asyncio.Task[None]]:
        """Trigger background synchronization for all configured and available libraries."""
        libs = available_libraries if available_libraries is not None else self._immich.list_libraries()
        tasks = []
        for lib in libs:
            t = self.trigger_sync(lib, force_full=force_full)
            tasks.append(t)
        return tasks

    @staticmethod
    def is_sync_due(last_at_iso: str | None, interval_hours: int, now: datetime | None = None) -> bool:
        """Check if a sync is due given the ISO timestamp of the last run and the interval in hours."""
        if interval_hours <= 0:
            return False
        if not last_at_iso:
            return True
        try:
            last_dt = datetime.fromisoformat(last_at_iso)
            if last_dt.tzinfo is None:
                last_dt = last_dt.replace(tzinfo=timezone.utc)
            current_time = now or datetime.now(timezone.utc)
            return (current_time - last_dt) >= timedelta(hours=interval_hours)
        except (ValueError, TypeError):
            return True

    def check_and_trigger_scheduled_sync(
        self,
        library_name: str,
        *,
        delta_interval_hours: int,
        full_interval_hours: int,
        now: datetime | None = None,
    ) -> asyncio.Task[None] | None:
        """Evaluate sync intervals against database sync_state and trigger sync if due."""
        if self.is_syncing(library_name):
            return None

        state = self._metadata_store.get_sync_state(library_name)
        last_sync_at = state.get('last_sync_at')
        last_full_sync_at = state.get('last_full_sync_at')

        # Full sync takes precedence if due
        if self.is_sync_due(last_full_sync_at, full_interval_hours, now=now):
            logger.info('Triggering scheduled full metadata sync for library: %s', library_name)
            return self.trigger_sync(library_name, force_full=True)

        # Otherwise check if delta sync is due
        if self.is_sync_due(last_sync_at, delta_interval_hours, now=now):
            logger.info('Triggering scheduled delta metadata sync for library: %s', library_name)
            return self.trigger_sync(library_name, force_full=False)

        return None

    def trigger_sync(self, library_name: str, *, force_full: bool = False) -> asyncio.Task[None]:
        """Trigger an asynchronous background sync for a library if not already running."""
        if self.is_syncing(library_name):
            logger.info('Sync already in progress for library %s', library_name)
            return self._active_sync_tasks[library_name]

        task = asyncio.create_task(self.sync_library(library_name, force_full=force_full))
        self._active_sync_tasks[library_name] = task

        def _on_done(t: asyncio.Task[None]) -> None:
            self._active_sync_tasks.pop(library_name, None)
            try:
                t.result()
            except Exception as exc:
                logger.error('Background sync failed for library %s: %s', library_name, exc, exc_info=True)

        task.add_done_callback(_on_done)
        return task

    def _process_asset_item(
        self,
        item: dict[str, Any],
        *,
        current_user_id: str | None,
        album_asset_map: dict[str, set[str]],
        shared_album_ids: set[str],
        known_person_ids: set[str],
        known_album_ids: set[str],
        known_tag_ids: set[str],
    ) -> tuple[dict[str, Any] | None, list[tuple[str, str]], list[tuple[str, str]], list[tuple[str, str]]]:
        """Extract metadata, EXIF details, and junction relations from raw Immich asset JSON payload."""
        aid = str(item.get('id', '') or item.get('assetId', '')).strip()
        if not aid:
            return None, [], [], []

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
        state = _clean_str(exif.get('state'))
        country = _clean_str(exif.get('country'))

        capture_dt = ImmichClient.extract_capture_datetime(item)
        capture_dt_str = capture_dt.isoformat() if capture_dt is not None else None
        updated_at_str = _clean_str(item.get('updatedAt'))
        file_type = str(item.get('type', 'IMAGE')).upper()

        asset_dict = {
            'id': aid,
            'is_shared': is_shared_flag,
            'is_partner': is_partner_flag,
            'file_type': file_type,
            'latitude': lat,
            'longitude': lon,
            'country': country,
            'state': state,
            'city': city,
            'capture_datetime': capture_dt_str,
            'immich_updated_at': updated_at_str,
        }

        asset_people: list[tuple[str, str]] = []
        people = item.get('people') or item.get('faces') or []
        if isinstance(people, list):
            for p in people:
                if isinstance(p, dict) and p.get('id'):
                    pid = str(p['id']).strip()
                    if pid and pid in known_person_ids:
                        asset_people.append((aid, pid))

        asset_albums: list[tuple[str, str]] = []
        if aid in album_asset_map:
            for alb_id in album_asset_map[aid]:
                if alb_id in known_album_ids:
                    asset_albums.append((aid, alb_id))

        asset_tags: list[tuple[str, str]] = []
        item_tags = item.get('tags') or []
        if isinstance(item_tags, list):
            for t in item_tags:
                if isinstance(t, dict) and t.get('id'):
                    tid = str(t['id']).strip()
                    if tid and tid in known_tag_ids:
                        asset_tags.append((aid, tid))
                elif isinstance(t, str):
                    tid = t.strip()
                    if tid and tid in known_tag_ids:
                        asset_tags.append((aid, tid))

        return asset_dict, asset_people, asset_albums, asset_tags

    async def sync_library(self, library_name: str, *, force_full: bool = False) -> None:
        """Perform metadata synchronization (delta or full) for a specific library."""
        current_state = self._metadata_store.get_sync_state(library_name)
        has_synced = self._metadata_store.has_synced_assets([library_name])
        last_immich_updated_at = current_state.get('last_immich_updated_at')

        is_delta = (not force_full) and has_synced and bool(last_immich_updated_at)
        sync_mode = SyncMode.delta if is_delta else SyncMode.full

        logger.info('Starting %s metadata sync for library: %s', sync_mode.value, library_name)
        sync_start = time.monotonic()
        self._metadata_store.set_sync_state(
            library_name,
            status=SyncStatus.syncing,
            sync_mode=sync_mode,
            sync_stage=SyncStage.checking_updates if is_delta else SyncStage.initializing,
            error=None,
            synced_assets=0,
            total_assets=0,
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

            indexed_album_ids = self._metadata_store.get_indexed_album_ids(library_name)
            albums_to_fetch: list[tuple[str, int]] = []  # (album_id, asset_count)

            for alb in albums_list:
                if isinstance(alb, dict):
                    aid = str(alb.get('id', '')).strip()
                    aname = str(alb.get('albumName', '') or alb.get('name', '')).strip()
                    is_shared = ImmichClient._is_shared_album(alb, current_user_id)
                    if is_shared:
                        shared_album_ids.add(aid)
                    if aid and aname:
                        albums_data.append({'id': aid, 'name': aname, 'isShared': is_shared})

                        asset_count = int(alb.get('assetCount', 0) or 0)
                        if asset_count > 0:
                            alb_updated_at = _clean_str(alb.get('updatedAt'))
                            if not is_delta:
                                # Full sync: fetch all non-empty albums in parallel
                                albums_to_fetch.append((aid, asset_count))
                            else:
                                # Delta sync: only fetch if album is newly added or modified since last sync
                                is_new = aid not in indexed_album_ids
                                is_modified = bool(
                                    alb_updated_at
                                    and last_immich_updated_at
                                    and alb_updated_at > last_immich_updated_at
                                )
                                if is_new or is_modified:
                                    albums_to_fetch.append((aid, asset_count))

            self._metadata_store.upsert_albums(library_name, albums_data)
            known_album_ids = {a['id'] for a in albums_data}

            if not is_delta:
                self._metadata_store.prune_missing_albums(library_name, known_album_ids)

            # Concurrent album asset fetching (bounded concurrency pool of 15)
            if albums_to_fetch:
                self._metadata_store.set_sync_state(
                    library_name,
                    status=SyncStatus.syncing,
                    sync_mode=sync_mode,
                    sync_stage=SyncStage.fetching_albums if not is_delta else SyncStage.updating_albums,
                    total_assets=len(albums_to_fetch),
                    synced_assets=0,
                )
                album_semaphore = asyncio.Semaphore(15)

                async def _fetch_album_contents(alb_id: str, count: int) -> tuple[str, list[str]]:
                    async with album_semaphore:
                        try:
                            alb_detail = await self._immich._request_json('GET', f'/albums/{alb_id}', key)
                            alb_assets = self._immich._extract_asset_items(alb_detail)
                            if not alb_assets and count > 0:
                                search_alb = await self._immich._request_json(
                                    'POST',
                                    '/search/metadata',
                                    key,
                                    json={'albumIds': [alb_id], 'size': 1000},
                                )
                                alb_assets = self._immich._extract_asset_items(search_alb)

                            item_ids = [
                                str(item.get('id', '') or item.get('assetId', '')).strip()
                                for item in alb_assets
                                if str(item.get('id', '') or item.get('assetId', '')).strip()
                            ]
                            return alb_id, item_ids
                        except ImmichClientError as exc:
                            logger.warning('Failed to fetch assets for album %s: %s', alb_id, exc)
                            return alb_id, []

                fetched_results = await asyncio.gather(
                    *(_fetch_album_contents(alb_id, cnt) for alb_id, cnt in albums_to_fetch)
                )

                # Populate album_asset_map & update modified album junctions in SQLite
                modified_junction_inserts: list[tuple[str, str]] = []
                clear_album_ids: set[str] = set()
                for alb_id, item_ids in fetched_results:
                    if is_delta:
                        clear_album_ids.add(alb_id)
                    for item_id in item_ids:
                        if item_id not in album_asset_map:
                            album_asset_map[item_id] = set()
                        album_asset_map[item_id].add(alb_id)
                        if is_delta:
                            modified_junction_inserts.append((item_id, alb_id))

                if modified_junction_inserts or clear_album_ids:
                    self._metadata_store.link_album_assets(
                        library_name,
                        modified_junction_inserts,
                        clear_album_ids=clear_album_ids if is_delta else None,
                    )

            # 3. Fetch & store tags
            try:
                raw_tags = await self._immich._request_json('GET', '/tags', key)
                tags_list = raw_tags if isinstance(raw_tags, list) else []
                tags_data: list[dict[str, str]] = []
                for t in tags_list:
                    if isinstance(t, dict):
                        tid = str(t.get('id', '')).strip()
                        tname = str(t.get('name', '')).strip()
                        if tid and tname:
                            tags_data.append({'id': tid, 'name': tname})
                self._metadata_store.upsert_tags(library_name, tags_data)
                known_tag_ids = {t['id'] for t in tags_data}
            except Exception as exc:
                logger.warning('Failed to fetch tags for library %s: %s', library_name, exc)
                known_tag_ids = set()

            # 4. Asset search (Delta or Full)
            page_size = 250
            page_num = 1
            seen_asset_ids: set[str] = set()
            max_updated_at: str | None = last_immich_updated_at if is_delta else None
            total_reported: int | None = None

            if not is_delta:
                total_reported = await self._immich.get_asset_count(library_name)
                if total_reported is None:
                    msg = (
                        f"Immich /search/statistics did not return an asset count for library '{library_name}'. "
                        'Sync will proceed without total progress estimate.'
                    )
                    logger.warning(msg)
                    self._sync_warnings[library_name] = msg

                self._metadata_store.set_sync_state(
                    library_name,
                    status=SyncStatus.syncing,
                    sync_mode=sync_mode,
                    sync_stage=SyncStage.scanning_assets,
                    synced_assets=0,
                    total_assets=total_reported or 0,
                )
            else:
                self._metadata_store.set_sync_state(
                    library_name,
                    status=SyncStatus.syncing,
                    sync_mode=sync_mode,
                    sync_stage=SyncStage.checking_updates,
                    synced_assets=0,
                    total_assets=0,
                )

            while True:
                payload: dict[str, Any] = {
                    'size': page_size,
                    'page': page_num,
                    'withExif': True,
                    'withPartners': True,
                    'isShared': True,
                    'withPeople': True,
                    'withTags': True,
                }
                if is_delta and last_immich_updated_at:
                    payload['updatedAfter'] = last_immich_updated_at

                raw_page = await self._immich._request_json('POST', '/search/metadata', key, json=payload)
                if not is_delta and total_reported is None:
                    extracted_total = self._immich._extract_total_assets(raw_page)
                    if extracted_total is not None and extracted_total > 0:
                        total_reported = extracted_total

                items = self._immich._extract_asset_items(raw_page)
                if not items:
                    break

                batch_assets: list[dict[str, Any]] = []
                batch_asset_people: list[tuple[str, str]] = []
                batch_asset_albums: list[tuple[str, str]] = []
                batch_asset_tags: list[tuple[str, str]] = []

                for item in items:
                    asset_dict, a_people, a_albums, a_tags = self._process_asset_item(
                        item,
                        current_user_id=current_user_id,
                        album_asset_map=album_asset_map,
                        shared_album_ids=shared_album_ids,
                        known_person_ids=known_person_ids,
                        known_album_ids=known_album_ids,
                        known_tag_ids=known_tag_ids,
                    )
                    if not asset_dict:
                        continue

                    aid = asset_dict['id']
                    seen_asset_ids.add(aid)
                    batch_assets.append(asset_dict)
                    batch_asset_people.extend(a_people)
                    batch_asset_albums.extend(a_albums)
                    batch_asset_tags.extend(a_tags)

                    updated_str = asset_dict.get('immich_updated_at')
                    if updated_str and (max_updated_at is None or updated_str > max_updated_at):
                        max_updated_at = updated_str

                # Batch upsert into SQLite
                self._metadata_store.upsert_assets_batch(
                    library_name,
                    batch_assets,
                    batch_asset_people,
                    batch_asset_albums,
                    batch_asset_tags,
                )

                synced_count = len(seen_asset_ids)
                if not is_delta:
                    total_target = (
                        total_reported if (total_reported is not None and total_reported >= synced_count) else 0
                    )
                    self._metadata_store.set_sync_state(
                        library_name,
                        status=SyncStatus.syncing,
                        sync_mode=sync_mode,
                        sync_stage=SyncStage.indexing_assets,
                        synced_assets=synced_count,
                        total_assets=total_target,
                    )
                else:
                    self._metadata_store.set_sync_state(
                        library_name,
                        status=SyncStatus.syncing,
                        sync_mode=sync_mode,
                        sync_stage=SyncStage.updating_assets if synced_count > 0 else SyncStage.checking_updates,
                        synced_assets=synced_count,
                        total_assets=synced_count,
                    )

                page_num += 1
                await asyncio.sleep(0.01)

            # 5. Link any album associations that might have been processed
            if album_asset_map:
                junction_inserts: list[tuple[str, str]] = []
                shared_asset_updates: list[tuple[str,]] = []

                for asset_id, album_ids in album_asset_map.items():
                    for album_id in album_ids:
                        if album_id in known_album_ids:
                            junction_inserts.append((asset_id, album_id))
                    if album_ids & shared_album_ids:
                        shared_asset_updates.append((asset_id,))

                if junction_inserts or shared_asset_updates:
                    self._metadata_store.link_album_assets(
                        library_name,
                        junction_inserts,
                        shared_asset_updates=shared_asset_updates,
                    )

            # 6. Prune missing assets (only in full sync)
            if not is_delta:
                self._metadata_store.set_sync_state(
                    library_name,
                    status=SyncStatus.syncing,
                    sync_mode=sync_mode,
                    sync_stage=SyncStage.pruning,
                )
                pruned_count = self._metadata_store.prune_missing_assets(library_name, seen_asset_ids)
                if pruned_count > 0:
                    logger.info('Pruned %d deleted asset(s) from metadata index for %s', pruned_count, library_name)

            # 7. Mark sync complete
            self._metadata_store.set_sync_state(
                library_name,
                status=SyncStatus.syncing,
                sync_mode=sync_mode,
                sync_stage=SyncStage.finalizing,
            )
            now_iso = datetime.now(timezone.utc).isoformat()
            duration_sec = round(time.monotonic() - sync_start, 2)
            db_total = self._metadata_store.count_library_assets(library_name)

            last_full_at = now_iso if not is_delta else current_state.get('last_full_sync_at')
            self._metadata_store.set_sync_state(
                library_name,
                status=SyncStatus.idle,
                sync_stage=SyncStage.idle,
                last_sync_at=now_iso,
                last_full_sync_at=last_full_at,
                last_immich_updated_at=max_updated_at,
                sync_mode=sync_mode,
                last_sync_duration_seconds=duration_sec,
                synced_assets=db_total,
                total_assets=db_total,
                error=None,
            )
            logger.info(
                'Successfully finished %s metadata sync for %s (%d assets in db, %d updated in %.2fs)',
                sync_mode.value,
                library_name,
                db_total,
                len(seen_asset_ids),
                duration_sec,
            )

            if self._on_sync_complete is not None:
                try:
                    self._on_sync_complete(library_name)
                except Exception as cb_exc:
                    logger.warning('on_sync_complete callback failed for library %s: %s', library_name, cb_exc)

        except Exception as exc:
            logger.error('Error during metadata sync for %s: %s', library_name, exc, exc_info=True)
            self._metadata_store.set_sync_state(
                library_name,
                status=SyncStatus.error,
                sync_stage=SyncStage.idle,
                error=str(exc),
            )
            raise

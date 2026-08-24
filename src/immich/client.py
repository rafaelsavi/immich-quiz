"""Immich API client for remote metadata fetching, authentication, and thumbnail streaming."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import date, datetime
from types import TracebackType
from typing import Any

import httpx

from src.models import PeopleMode

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class ImmichClientError(RuntimeError):
    """Raised when an error occurs communicating with or authenticating to the Immich server."""


@dataclass
class AssetAnswer:
    """Ground truth geographic and temporal metadata for an indexed or candidate photo asset."""

    latitude: float | None
    longitude: float | None
    capture_datetime: datetime | None = None
    city: str | None = None
    state: str | None = None
    country: str | None = None

    def __post_init__(self) -> None:
        if self.latitude is not None and not (-90.0 <= self.latitude <= 90.0):
            raise ValueError(f'latitude must be between -90.0 and 90.0, got {self.latitude}')
        if self.longitude is not None and not (-180.0 <= self.longitude <= 180.0):
            raise ValueError(f'longitude must be between -180.0 and 180.0, got {self.longitude}')

    @property
    def capture_date(self) -> date | None:
        return self.capture_datetime.date() if self.capture_datetime is not None else None


class ImmichClient:
    """Asynchronous HTTP client for interacting with one or more Immich server libraries."""

    def __init__(
        self,
        server_url: str,
        library_keys: dict[str, str],
        timeout_seconds: int = 25,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        """Initialize client with Immich server URL, library API key map, and request timeout."""
        url = server_url.strip().rstrip('/')
        if not url.endswith('/api'):
            url = f'{url}/api'
        self._server_url = url
        self._library_keys = library_keys
        self._timeout = timeout_seconds
        self._client = client
        self._user_id_by_key: dict[str, str] = {}

    async def __aenter__(self) -> ImmichClient:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        await self.aclose()

    @property
    def _http(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self._timeout)
        return self._client

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    def list_libraries(self) -> list[str]:
        """Return sorted list of configured library names."""
        return sorted(self._library_keys.keys())

    async def validate_access(self, library_name: str) -> None:
        """Verify API key validity and access permissions for a specific library."""
        key = self._library_key(library_name)
        payload = {'size': 1, 'page': 1, 'withExif': True}
        await self._request_json('POST', '/search/metadata', key, json=payload)

    async def list_albums(self, library_name: str, include_shared: bool = False) -> list[dict[str, str]]:
        """Fetch and return all albums for a library, optionally filtering out shared albums."""
        key = self._library_key(library_name)
        raw = await self._request_json('GET', '/albums', key)
        items: list[dict[str, str]] = []
        raw_count = len(raw) if isinstance(raw, list) else 0
        if isinstance(raw, list):
            current_user_id: str | None = None
            if not include_shared:
                current_user_id = await self._current_user_id(key)
            for album in raw:
                if not isinstance(album, dict):
                    continue
                if not include_shared and self._is_shared_album(album, current_user_id):
                    continue
                album_id = str(album.get('id', '')).strip()
                album_name = str(album.get('albumName', '') or album.get('name', '')).strip()
                if album_id and album_name:
                    items.append({'id': album_id, 'name': album_name})
        items.sort(key=lambda item: (item['name'].lower(), item['id']))
        logger.info(
            'list_albums(%s): %d raw album(s) from Immich, %d returned (include_shared=%s)',
            library_name,
            raw_count,
            len(items),
            include_shared,
        )
        return items

    async def list_tags(self, library_name: str) -> list[dict[str, str]]:
        """Fetch and return all user tags for a library."""
        key = self._library_key(library_name)
        raw = await self._request_json('GET', '/tags', key)
        items: list[dict[str, str]] = []
        tags_list = raw if isinstance(raw, list) else []
        for tag in tags_list:
            if not isinstance(tag, dict):
                continue
            tag_id = str(tag.get('id', '')).strip()
            tag_name = str(tag.get('name', '')).strip()
            if tag_id and tag_name:
                items.append({'id': tag_id, 'name': tag_name})
        items.sort(key=lambda item: (item['name'].lower(), item['id']))
        return items

    async def get_asset_count(self, library_name: str) -> int | None:
        """Retrieve total photo/video asset count from Immich statistics endpoint."""
        key = self._library_key(library_name)
        try:
            stats = await self._request_json('POST', '/search/statistics', key, json={})
            if isinstance(stats, dict):
                total = stats.get('total')
                if isinstance(total, int) and total >= 0:
                    return total
                images = stats.get('images') or stats.get('photos') or 0
                videos = stats.get('videos') or 0
                if isinstance(images, int) and isinstance(videos, int) and (images + videos) >= 0:
                    return images + videos
            logger.warning(
                'Unexpected response structure from Immich /search/statistics for %s: %s',
                library_name,
                stats,
            )
        except ImmichClientError as exc:
            logger.warning(
                'Failed to fetch asset count from Immich /search/statistics for %s: %s',
                library_name,
                exc,
            )
        except Exception as exc:
            logger.warning(
                'Unexpected error in get_asset_count for %s: %s',
                library_name,
                exc,
            )

        return None

    @staticmethod
    def _extract_owner_id(item: dict[str, Any]) -> str:
        """Extract user or owner ID string from an album or asset JSON dictionary."""
        owner_id = item.get('ownerId')
        if owner_id is not None and str(owner_id).strip():
            return str(owner_id).strip()
        owner = item.get('owner')
        if isinstance(owner, dict) and owner.get('id') is not None:
            return str(owner['id']).strip()
        album_users = item.get('albumUsers')
        if isinstance(album_users, list):
            for u in album_users:
                if isinstance(u, dict) and u.get('role') == 'owner':
                    user_obj = u.get('user')
                    if isinstance(user_obj, dict) and user_obj.get('id'):
                        return str(user_obj['id']).strip()
                    if u.get('userId'):
                        return str(u['userId']).strip()
            if album_users and isinstance(album_users[0], dict):
                first = album_users[0]
                user_obj = first.get('user')
                if isinstance(user_obj, dict) and user_obj.get('id'):
                    return str(user_obj['id']).strip()
                if first.get('userId'):
                    return str(first['userId']).strip()
        user_val = item.get('user')
        if isinstance(user_val, dict) and user_val.get('id'):
            return str(user_val['id']).strip()
        user_id = item.get('userId')
        if user_id is not None and str(user_id).strip():
            return str(user_id).strip()
        return ''

    @staticmethod
    def _is_shared_album(album: dict[str, Any], current_user_id: str | None = None) -> bool:
        """Return True if the album was shared with the user by someone else."""
        owner_id = ImmichClient._extract_owner_id(album)
        if owner_id and current_user_id:
            return owner_id != current_user_id

        album_users = album.get('albumUsers')
        if isinstance(album_users, list) and current_user_id:
            for u in album_users:
                if isinstance(u, dict):
                    user_obj = u.get('user')
                    uid = str(
                        (user_obj.get('id') if isinstance(user_obj, dict) else None) or u.get('userId') or ''
                    ).strip()
                    if uid == current_user_id:
                        return u.get('role') != 'owner'

        if album.get('shared') is False or album.get('isShared') is False:
            return False

        if album.get('shared') is True or album.get('isShared') is True:
            return True

        return bool(album.get('sharedUsers') or album.get('sharedWith'))

    @staticmethod
    def _unwrap_asset(item: dict[str, Any]) -> dict[str, Any]:
        """Unwrap nested asset dictionary structure if returned inside an envelope."""
        if isinstance(item.get('asset'), dict) and (item['asset'].get('id') or item['asset'].get('assetId')):
            unwrapped = dict(item['asset'])
            for k, v in item.items():
                if k != 'asset' and k not in unwrapped:
                    unwrapped[k] = v
            return unwrapped
        return item

    @staticmethod
    def _extract_total_assets(raw: Any) -> int | None:
        """Extract total count integer from Immich metadata search response."""
        if not isinstance(raw, dict):
            return None

        totals: list[Any] = [raw.get('total'), raw.get('totalItems')]
        assets = raw.get('assets')
        if isinstance(assets, dict):
            totals.extend([assets.get('total'), assets.get('totalItems')])

        for value in totals:
            if isinstance(value, int) and value >= 0:
                return value
        return None

    @staticmethod
    def _extract_asset_items(raw: Any) -> list[dict[str, Any]]:
        """Extract list of asset dictionaries from various Immich API response formats."""
        items: list[dict[str, Any]] = []
        if isinstance(raw, list):
            items = [x for x in raw if isinstance(x, dict)]
        elif isinstance(raw, dict):
            if isinstance(raw.get('assets'), list):
                items = [x for x in raw['assets'] if isinstance(x, dict)]
            elif isinstance(raw.get('assets'), dict) and isinstance(raw['assets'].get('items'), list):
                items = [x for x in raw['assets']['items'] if isinstance(x, dict)]
            elif isinstance(raw.get('items'), list):
                items = [x for x in raw['items'] if isinstance(x, dict)]

        return [ImmichClient._unwrap_asset(item) for item in items]

    async def get_asset_bytes(self, library_name: str, asset_id: str) -> tuple[bytes, str]:
        """Download thumbnail preview bytes and content type for an asset."""
        key = self._library_key(library_name)
        preview = await self._request_raw('GET', f'/assets/{asset_id}/thumbnail?size=preview', key, accept='*/*')
        content_type = preview.headers.get('content-type', 'image/jpeg')
        return preview.content, content_type

    @staticmethod
    def _exif(asset: dict[str, Any]) -> dict[str, Any]:
        """Extract and normalize EXIF metadata dictionary from an asset payload."""
        exif = asset.get('exifInfo') or asset.get('exif')
        res = dict(exif) if isinstance(exif, dict) else {}
        for key in ('latitude', 'longitude', 'city', 'country', 'state', 'dateTimeOriginal'):
            if key not in res and key in asset and asset[key] is not None:
                res[key] = asset[key]
        return res

    @staticmethod
    def is_eligible_asset(
        asset: dict[str, Any],
        location_mode: bool,
        date_mode: bool,
        min_date: date | None = None,
        max_date: date | None = None,
        countries: tuple[str, ...] = (),
        cities: tuple[str, ...] = (),
        person_ids: tuple[str, ...] = (),
        people_mode: PeopleMode = PeopleMode.ANY,
        country_whitelist: frozenset[str] = frozenset(),
        country_blacklist: frozenset[str] = frozenset(),
        city_whitelist: frozenset[str] = frozenset(),
        city_blacklist: frozenset[str] = frozenset(),
        people_whitelist: frozenset[str] = frozenset(),
        people_blacklist: frozenset[str] = frozenset(),
        tag_whitelist: frozenset[str] = frozenset(),
        tag_blacklist: frozenset[str] = frozenset(),
    ) -> bool:
        """Check whether an asset satisfies location, date, and whitelist/blacklist constraints."""
        # 1. Reject videos
        if asset.get('type') == 'VIDEO':
            return False

        # 2. Location mode check (valid non-zero lat/lng)
        exif = ImmichClient._exif(asset)
        if location_mode:
            lat = exif.get('latitude')
            lon = exif.get('longitude')
            if lat is None or lon is None:
                return False
            try:
                lat_val = float(lat)
                lon_val = float(lon)
                if lat_val == 0.0 and lon_val == 0.0:
                    return False
            except (ValueError, TypeError):
                return False

        # 3. Date mode & min/max bounds check
        capture_dt = ImmichClient.extract_capture_datetime(asset)
        if date_mode and capture_dt is None:
            return False

        if min_date is not None or max_date is not None:
            if capture_dt is None:
                return False
            c_date = capture_dt.date()
            if min_date is not None and c_date < min_date:
                return False
            if max_date is not None and c_date > max_date:
                return False

        # Extract asset metadata for config safeguards
        asset_country = (exif.get('country') or '').strip().lower()
        asset_city = (exif.get('city') or '').strip().lower()

        asset_people = asset.get('people') or asset.get('faces') or []
        asset_person_ids = {str(p.get('id', '')).strip() for p in asset_people if isinstance(p, dict) and p.get('id')}
        asset_person_names = {
            str(p.get('name', '')).strip().lower() for p in asset_people if isinstance(p, dict) and p.get('name')
        }

        asset_tags = asset.get('tags') or []
        asset_tag_ids: set[str] = set()
        asset_tag_names: set[str] = set()
        if isinstance(asset_tags, list):
            for t in asset_tags:
                if isinstance(t, dict):
                    if tid := str(t.get('id', '')).strip():
                        asset_tag_ids.add(tid.lower())
                    if tname := str(t.get('name', '')).strip().lower():
                        asset_tag_names.add(tname)
                elif isinstance(t, str):
                    tid_or_name = t.strip()
                    if tid_or_name:
                        asset_tag_ids.add(tid_or_name.lower())
                        asset_tag_names.add(tid_or_name.lower())

        # -------------------------------------------------------------------
        # LAYER 1: Hard Server Configuration Safeguards (Always Enforced)
        # -------------------------------------------------------------------

        # Country blacklist
        if country_blacklist and asset_country and asset_country in {c.lower() for c in country_blacklist}:
            return False

        # City blacklist
        if city_blacklist and asset_city and asset_city in {c.lower() for c in city_blacklist}:
            return False

        # People blacklist (by name or by ID)
        if people_blacklist:
            for bl_item in people_blacklist:
                bl_lower = bl_item.lower()
                if bl_lower in asset_person_names or bl_item in asset_person_ids:
                    return False

        # Tag blacklist (by name or by ID)
        if tag_blacklist:
            tag_bl_lower = {w.lower() for w in tag_blacklist}
            if asset_tag_names.intersection(tag_bl_lower) or asset_tag_ids.intersection(tag_bl_lower):
                return False

        # Country whitelist baseline (when user didn't specify countries)
        if (
            country_whitelist
            and not countries
            and (not asset_country or asset_country not in {c.lower() for c in country_whitelist})
        ):
            return False

        # City whitelist baseline (when user didn't specify cities)
        if city_whitelist and not cities and (not asset_city or asset_city not in {c.lower() for c in city_whitelist}):
            return False

        # People whitelist baseline (when user didn't specify person_ids)
        if people_whitelist and not person_ids:
            wl_lower = {w.lower() for w in people_whitelist}
            for p_name in asset_person_names:
                if p_name and p_name not in wl_lower:
                    return False
            for pid in asset_person_ids:
                if pid and pid not in people_whitelist and not any(p_name in wl_lower for p_name in asset_person_names):
                    return False

        # Tag whitelist baseline
        if tag_whitelist:
            wl_lower = {w.lower() for w in tag_whitelist}
            if not (asset_tag_names.intersection(wl_lower) or asset_tag_ids.intersection(wl_lower)):
                return False

        # -------------------------------------------------------------------
        # LAYER 2: User Match Setup Rules (Applied on top)
        # -------------------------------------------------------------------

        # User Country check (if countries filter specified)
        if countries and (not asset_country or asset_country not in {c.lower() for c in countries}):
            return False

        # User City check (if cities filter specified)
        if cities:
            allowed_cities = {c.lower() for c in cities}
            if asset_city not in allowed_cities:
                return False

        # User Person check (if person_ids filter specified — supports both ID and Name matching)
        if person_ids:
            if people_mode == PeopleMode.ALL:
                for target in person_ids:
                    if not (target in asset_person_ids or target.lower() in asset_person_names):
                        return False
            else:
                target_ids = set(person_ids)
                target_names = {p.lower() for p in person_ids}
                if not (asset_person_ids.intersection(target_ids) or asset_person_names.intersection(target_names)):
                    return False

        return True

    @staticmethod
    def extract_answer(asset: dict[str, Any]) -> AssetAnswer:
        """Construct an AssetAnswer instance from asset metadata and EXIF dictionary."""
        exif = ImmichClient._exif(asset)

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

        capture_dt = ImmichClient.extract_capture_datetime(asset)
        city = str(exif.get('city', '')).strip() if exif.get('city') else None
        state = str(exif.get('state', '')).strip() if exif.get('state') else None
        country = str(exif.get('country', '')).strip() if exif.get('country') else None

        return AssetAnswer(
            latitude=lat,
            longitude=lon,
            capture_datetime=capture_dt,
            city=city,
            state=state,
            country=country,
        )

    @staticmethod
    def extract_capture_datetime(asset: dict[str, Any]) -> datetime | None:
        """Parse capture datetime from asset EXIF or file timestamp properties."""
        exif = ImmichClient._exif(asset)
        date_str = (
            exif.get('dateTimeOriginal')
            or asset.get('fileCreatedAt')
            or asset.get('localDateTime')
            or asset.get('createdAt')
        )
        if not date_str or not isinstance(date_str, str):
            return None

        s = date_str.strip()

        if len(s) >= 19 and s[4] == ':' and s[7] == ':':
            s = s[:4] + '-' + s[5:7] + '-' + s[8:]

        if s.endswith('Z'):
            s = s[:-1] + '+00:00'

        try:
            return datetime.fromisoformat(s)
        except ValueError:
            pass

        m = re.match(r'^(\d{4}-\d{2}-\d{2})', s)
        if m:
            try:
                return datetime.fromisoformat(m.group(1))
            except ValueError:
                pass

        return None

    def _library_key(self, library_name: str) -> str:
        """Retrieve API key for a library name or raise ImmichClientError."""
        key = self._library_keys.get(library_name)
        if not key:
            available = ', '.join(sorted(self._library_keys.keys()))
            raise ImmichClientError(f'Unknown library "{library_name}". Available libraries: {available}')
        return key

    async def _current_user_id(self, key: str) -> str | None:
        """Fetch and cache the current authenticated user's ID for an API key."""
        if key in self._user_id_by_key:
            return self._user_id_by_key[key]

        try:
            me = await self._request_json('GET', '/users/me', key)
            if isinstance(me, dict) and me.get('id'):
                user_id = str(me['id']).strip()
                self._user_id_by_key[key] = user_id
                return user_id
        except ImmichClientError as exc:
            logger.warning('Failed to fetch /users/me for key %s...: %s', key[:8], exc)

        return None

    async def _request_json(
        self,
        method: str,
        path: str,
        api_key: str,
        json: dict[str, Any] | None = None,
    ) -> Any:
        """Send HTTP request and parse JSON response with error handling."""
        res = await self._request_raw(method, path, api_key, json=json)
        try:
            return res.json()
        except ValueError as exc:
            raise ImmichClientError(f'Invalid JSON from Immich endpoint {path}') from exc

    async def _request_raw(
        self,
        method: str,
        path: str,
        api_key: str,
        json: dict[str, Any] | None = None,
        accept: str = 'application/json',
    ) -> httpx.Response:
        """Send raw HTTP request with API key authentication headers."""
        url = f'{self._server_url}{path}'
        headers = {
            'x-api-key': api_key,
            'Accept': accept,
        }
        try:
            res = await self._http.request(method, url, headers=headers, json=json)
        except httpx.RequestError as exc:
            raise ImmichClientError(f'Network error connecting to Immich: {exc}') from exc

        if res.status_code in {401, 403}:
            raise ImmichClientError(f'Authentication failed for library ({res.status_code})')
        if res.status_code >= 400:
            raise ImmichClientError(f'Immich API error {res.status_code} at {path}: {res.text[:300]}')

        return res

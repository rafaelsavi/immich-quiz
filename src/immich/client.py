from __future__ import annotations

import logging
import random
import re
from dataclasses import dataclass
from datetime import date, datetime
from types import TracebackType
from typing import Any

import httpx

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class ImmichClientError(RuntimeError):
    pass


@dataclass
class AssetAnswer:
    latitude: float | None
    longitude: float | None
    capture_datetime: datetime | None = None
    city: str | None = None
    country: str | None = None

    @property
    def capture_date(self) -> date | None:
        return self.capture_datetime.date() if self.capture_datetime is not None else None


@dataclass(frozen=True)
class SearchQuery:
    album_ids: tuple[str, ...] = ()
    include_shared_albums: bool = False
    include_partner_assets: bool = False
    min_date: date | None = None
    max_date: date | None = None

    @property
    def should_filter_by_owner(self) -> bool:
        if self.album_ids:
            return False
        return not (self.include_shared_albums and self.include_partner_assets)

    def build_payload(self, size: int, page: int | None = None) -> dict[str, Any]:
        payload: dict[str, Any] = {'size': size, 'withExif': True}
        if page is not None:
            payload['page'] = page
        if self.album_ids:
            payload['albumIds'] = list(self.album_ids)
        if self.include_partner_assets:
            payload['withPartners'] = True
        if self.include_shared_albums and not self.album_ids:
            payload['isShared'] = True
        if self.min_date:
            payload['createdAfter'] = f'{self.min_date.isoformat()}T00:00:00.000Z'
        if self.max_date:
            payload['createdBefore'] = f'{self.max_date.isoformat()}T23:59:59.999Z'
        return payload


class ImmichClient:
    def __init__(
        self,
        server_url: str,
        library_keys: dict[str, str],
        timeout_seconds: int = 25,
        client: httpx.AsyncClient | None = None,
    ) -> None:
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
        return sorted(self._library_keys.keys())

    async def validate_access(self, library_name: str) -> None:
        key = self._library_key(library_name)
        payload = {'size': 1, 'page': 1, 'withExif': True}
        await self._request_json('POST', '/search/metadata', key, json=payload)

    @staticmethod
    def _build_search_payload(
        size: int,
        album_ids: list[str] | None = None,
        *,
        query: SearchQuery | None = None,
        page: int | None = None,
        include_shared_albums: bool = False,
        include_partner_assets: bool = False,
        min_date: date | None = None,
        max_date: date | None = None,
    ) -> dict[str, Any]:
        if query is None:
            query = SearchQuery(
                album_ids=tuple(album_ids) if album_ids else (),
                include_shared_albums=include_shared_albums,
                include_partner_assets=include_partner_assets,
                min_date=min_date,
                max_date=max_date,
            )
        return query.build_payload(size, page=page)

    async def list_albums(self, library_name: str, include_shared_albums: bool = False) -> list[dict[str, str]]:
        key = self._library_key(library_name)
        raw = await self._request_json('GET', '/albums', key)
        items: list[dict[str, str]] = []
        raw_count = len(raw) if isinstance(raw, list) else 0
        if isinstance(raw, list):
            current_user_id: str | None = None
            for album in raw:
                if not isinstance(album, dict):
                    continue
                owner_id = self._album_owner_id(album)
                if owner_id and not include_shared_albums:
                    if current_user_id is None:
                        current_user_id = await self._current_user_id(key)
                    if owner_id != current_user_id:
                        continue
                album_id = str(album.get('id', '')).strip()
                album_name = str(album.get('albumName', '')).strip()
                if album_id and album_name:
                    items.append({'id': album_id, 'name': album_name})
        items.sort(key=lambda item: (item['name'].lower(), item['id']))
        logger.info(
            'list_albums(%s): %d raw album(s) from Immich, %d returned (include_shared=%s)',
            library_name,
            raw_count,
            len(items),
            include_shared_albums,
        )
        return items

    async def search_assets(
        self,
        library_name: str,
        album_ids: list[str] | None = None,
        *,
        query: SearchQuery | None = None,
        include_shared_albums: bool = False,
        include_partner_assets: bool = False,
        min_date: date | None = None,
        max_date: date | None = None,
        size: int = 250,
        page: int = 1,
    ) -> list[dict[str, Any]]:
        if query is None:
            query = SearchQuery(
                album_ids=tuple(album_ids) if album_ids else (),
                include_shared_albums=include_shared_albums,
                include_partner_assets=include_partner_assets,
                min_date=min_date,
                max_date=max_date,
            )
        key = self._library_key(library_name)
        payload = query.build_payload(size, page=page)

        raw = await self._request_json('POST', '/search/metadata', key, json=payload)
        items = self._extract_asset_items(raw)
        if not items or not query.should_filter_by_owner:
            return items
        current_user_id = await self._current_user_id(key)
        return self._filter_assets_by_owner(
            items,
            current_user_id=current_user_id,
            has_selected_albums=bool(query.album_ids),
            include_shared_albums=query.include_shared_albums,
            include_partner_assets=query.include_partner_assets,
        )

    async def search_random_assets(
        self,
        library_name: str,
        album_ids: list[str] | None = None,
        size: int = 250,
        include_shared_albums: bool = False,
        include_partner_assets: bool = False,
        *,
        query: SearchQuery | None = None,
        min_date: date | None = None,
        max_date: date | None = None,
    ) -> list[dict[str, Any]]:
        """Draw a randomized candidate pool."""
        if query is None:
            query = SearchQuery(
                album_ids=tuple(album_ids) if album_ids else (),
                include_shared_albums=include_shared_albums,
                include_partner_assets=include_partner_assets,
                min_date=min_date,
                max_date=max_date,
            )
        key = self._library_key(library_name)
        payload = query.build_payload(size)

        raw_items: list[dict[str, Any]] = []
        try:
            unique_assets: dict[str, dict[str, Any]] = {}
            for _ in range(3):
                raw = await self._request_json('POST', '/search/random', key, json=payload)
                self._merge_assets(unique_assets, self._extract_asset_items(raw))
                if len(unique_assets) >= size:
                    break
            if unique_assets:
                items = list(unique_assets.values())
                random.shuffle(items)
                raw_items = items[:size]
        except ImmichClientError:
            pass

        if not raw_items:
            raw_items = await self._search_assets_randomized_fallback(
                library_name,
                size,
                query=query,
            )

        if not raw_items or not query.should_filter_by_owner:
            return raw_items

        current_user_id = await self._current_user_id(key)
        return self._filter_assets_by_owner(
            raw_items,
            current_user_id=current_user_id,
            has_selected_albums=bool(query.album_ids),
            include_shared_albums=query.include_shared_albums,
            include_partner_assets=query.include_partner_assets,
        )

    async def _search_assets_randomized_fallback(
        self,
        library_name: str,
        size: int,
        query: SearchQuery,
    ) -> list[dict[str, Any]]:
        """Randomize metadata fallback by sampling multiple pages instead of page 1 only."""
        key = self._library_key(library_name)

        first_page_payload = query.build_payload(size, page=1)

        first_raw = await self._request_json('POST', '/search/metadata', key, json=first_page_payload)
        unique_assets: dict[str, dict[str, Any]] = {}
        self._merge_assets(unique_assets, self._extract_asset_items(first_raw))

        total = self._extract_total_assets(first_raw)
        if total is not None and total > size:
            total_pages = (total + size - 1) // size
            if total_pages > 1:
                extra_page_count = min(4, total_pages - 1)
                pages = random.sample(range(2, total_pages + 1), k=extra_page_count)
                for page in pages:
                    page_payload = query.build_payload(size, page=page)
                    raw = await self._request_json('POST', '/search/metadata', key, json=page_payload)
                    self._merge_assets(unique_assets, self._extract_asset_items(raw))

        items = list(unique_assets.values())
        random.shuffle(items)
        return items[:size]

    @staticmethod
    def _extract_owner_id(item: dict[str, Any]) -> str:
        owner_id = item.get('ownerId')
        if owner_id:
            return str(owner_id).strip()
        owner = item.get('owner')
        if isinstance(owner, dict) and owner.get('id'):
            return str(owner['id']).strip()
        return ''

    @staticmethod
    def _asset_owner_id(asset: dict[str, Any]) -> str:
        return ImmichClient._extract_owner_id(asset)

    @staticmethod
    def _filter_assets_by_owner(
        items: list[dict[str, Any]],
        *,
        current_user_id: str | None,
        has_selected_albums: bool = False,
        include_shared_albums: bool = False,
        include_partner_assets: bool = False,
    ) -> list[dict[str, Any]]:
        if has_selected_albums or (include_shared_albums and include_partner_assets):
            return items

        filtered: list[dict[str, Any]] = []
        for asset in items:
            owner_id = ImmichClient._asset_owner_id(asset)
            if not owner_id or owner_id == current_user_id:
                filtered.append(asset)
                continue

            is_shared = bool(asset.get('isShared'))
            if (
                is_shared
                and include_shared_albums
                or not is_shared
                and include_partner_assets
                or (include_shared_albums or include_partner_assets)
                and 'isShared' not in asset
            ):
                filtered.append(asset)

        return filtered

    @staticmethod
    def _merge_assets(target: dict[str, dict[str, Any]], items: list[dict[str, Any]]) -> None:
        for item in items:
            asset_id = str(item.get('id', '')).strip()
            if asset_id and asset_id not in target:
                target[asset_id] = item

    @staticmethod
    def _extract_total_assets(raw: Any) -> int | None:
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
        if isinstance(raw, list):
            return [x for x in raw if isinstance(x, dict)]
        if not isinstance(raw, dict):
            return []
        if isinstance(raw.get('assets'), dict) and isinstance(raw['assets'].get('items'), list):
            return [x for x in raw['assets']['items'] if isinstance(x, dict)]
        if isinstance(raw.get('items'), list):
            return [x for x in raw['items'] if isinstance(x, dict)]
        return []

    async def get_asset_bytes(self, library_name: str, asset_id: str) -> tuple[bytes, str]:
        key = self._library_key(library_name)
        preview = await self._request_raw('GET', f'/assets/{asset_id}/thumbnail?size=preview', key, accept='*/*')
        content_type = preview.headers.get('content-type', 'image/jpeg')
        return preview.content, content_type

    @staticmethod
    def _exif(asset: dict[str, Any]) -> dict[str, Any]:
        exif = asset.get('exifInfo')
        return exif if isinstance(exif, dict) else {}

    @staticmethod
    def is_eligible_asset(
        asset: dict[str, Any],
        location_mode: bool,
        date_mode: bool,
        min_date: date | None = None,
        max_date: date | None = None,
    ) -> bool:
        if asset.get('type') == 'VIDEO':
            return False

        if location_mode:
            exif = ImmichClient._exif(asset)
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

        return True

    @staticmethod
    def extract_answer(asset: dict[str, Any]) -> AssetAnswer:
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
        country = str(exif.get('country', '')).strip() if exif.get('country') else None

        return AssetAnswer(
            latitude=lat,
            longitude=lon,
            capture_datetime=capture_dt,
            city=city,
            country=country,
        )

    @staticmethod
    def extract_capture_datetime(asset: dict[str, Any]) -> datetime | None:
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
        key = self._library_keys.get(library_name)
        if not key:
            available = ', '.join(sorted(self._library_keys.keys()))
            raise ImmichClientError(f'Unknown library "{library_name}". Available libraries: {available}')
        return key

    async def _current_user_id(self, key: str) -> str | None:
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

    def _album_owner_id(self, album: dict[str, Any]) -> str:
        return ImmichClient._extract_owner_id(album)

    async def _request_json(
        self,
        method: str,
        path: str,
        api_key: str,
        json: dict[str, Any] | None = None,
    ) -> Any:
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
            raise ImmichClientError(f'Immich API error {res.status_code} at {path}')

        return res

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
    album_id: str | None = None
    include_shared_albums: bool = False
    include_partner_assets: bool = False
    min_date: date | None = None
    max_date: date | None = None

    @property
    def should_filter_by_owner(self) -> bool:
        if self.album_id:
            return False
        if self.include_shared_albums and self.include_partner_assets:
            return False
        return True

    def build_payload(self, size: int, page: int | None = None) -> dict[str, Any]:
        payload: dict[str, Any] = {'size': size, 'withExif': True}
        if page is not None:
            payload['page'] = page
        if self.album_id:
            payload['albumIds'] = [self.album_id]
        if self.include_partner_assets:
            payload['withPartners'] = True
        if self.include_shared_albums and not self.album_id:
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
        album_id: str | None = None,
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
                album_id=album_id,
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
                # Only filter when owner is *positively* identified as another user.
                # If owner_id is empty (API field name changed / unknown format),
                # include the album rather than silently drop it.
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
        album_id: str | None = None,
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
                album_id=album_id,
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
            album_id=query.album_id,
            include_shared_albums=query.include_shared_albums,
            include_partner_assets=query.include_partner_assets,
        )

    async def search_random_assets(
        self,
        library_name: str,
        album_id: str | None = None,
        size: int = 250,
        include_shared_albums: bool = False,
        include_partner_assets: bool = False,
        *,
        query: SearchQuery | None = None,
        min_date: date | None = None,
        max_date: date | None = None,
    ) -> list[dict[str, Any]]:
        """Draw a randomized candidate pool.

        Metadata search always returns the same first page, which makes matches
        repetitive. Immich's random search spreads selection across the whole
        library; fall back to metadata search if it is unavailable.
        """
        if query is None:
            query = SearchQuery(
                album_id=album_id,
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
            album_id=query.album_id,
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
        current_user_id: str,
        album_id: str | None,
        include_shared_albums: bool,
        include_partner_assets: bool,
    ) -> list[dict[str, Any]]:
        if album_id or (include_shared_albums and include_partner_assets):
            return items

        filtered: list[dict[str, Any]] = []
        for asset in items:
            owner_id = ImmichClient._asset_owner_id(asset)
            if not owner_id or owner_id == current_user_id:
                filtered.append(asset)
                continue

            if 'isShared' in asset:
                keep = include_shared_albums if asset['isShared'] else include_partner_assets
            else:
                keep = include_shared_albums or include_partner_assets

            if keep:
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
        min_capture_date: date | None = None,
        max_capture_date: date | None = None,
    ) -> bool:
        media_type = str(asset.get('type', '')).upper()
        if media_type != 'IMAGE':
            return False

        exif = ImmichClient._exif(asset)
        latitude = exif.get('latitude')
        longitude = exif.get('longitude')

        if location_mode:
            if not isinstance(latitude, (int, float)) or not isinstance(longitude, (int, float)):
                return False
            if abs(latitude) < 1e-6 and abs(longitude) < 1e-6:
                return False

        capture_date: date | None = None
        if date_mode or min_capture_date is not None or max_capture_date is not None:
            date_value = exif.get('dateTimeOriginal') or asset.get('fileCreatedAt')
            capture_date = ImmichClient._parse_capture_date(date_value)
            if date_mode and capture_date is None:
                return False

        if min_capture_date is not None or max_capture_date is not None:
            if capture_date is None:
                return False
            if min_capture_date is not None and capture_date < min_capture_date:
                return False
            if max_capture_date is not None and capture_date > max_capture_date:
                return False

        return True

    @staticmethod
    def extract_answer(asset: dict[str, Any]) -> AssetAnswer:
        exif = ImmichClient._exif(asset)
        latitude = exif.get('latitude') if isinstance(exif.get('latitude'), (int, float)) else None
        longitude = exif.get('longitude') if isinstance(exif.get('longitude'), (int, float)) else None
        if latitude is not None and longitude is not None and abs(latitude) < 1e-6 and abs(longitude) < 1e-6:
            latitude = None
            longitude = None

        date_value = exif.get('dateTimeOriginal') or asset.get('fileCreatedAt')
        capture_datetime = ImmichClient._parse_capture_datetime(date_value)

        return AssetAnswer(
            latitude=latitude,
            longitude=longitude,
            capture_datetime=capture_datetime,
            # Immich already reverse-geocodes assets, so reuse its labels.
            city=ImmichClient._clean_text(exif.get('city')),
            country=ImmichClient._clean_text(exif.get('country')),
        )

    @staticmethod
    def _clean_text(value: Any) -> str | None:
        if not isinstance(value, str):
            return None
        cleaned = value.strip()
        return cleaned or None

    @staticmethod
    def _parse_capture_datetime(value: Any) -> datetime | None:
        if not value or not isinstance(value, str):
            return None
        try:
            normalized = value.replace('Z', '+00:00')
            return datetime.fromisoformat(normalized)
        except ValueError:
            return None

    @staticmethod
    def _parse_capture_date(value: Any) -> date | None:
        dt = ImmichClient._parse_capture_datetime(value)
        return dt.date() if dt is not None else None

    def _library_key(self, library_name: str) -> str:
        key = self._library_keys.get(library_name)
        if not key:
            raise ImmichClientError(f'Unknown library: {library_name}')
        return key

    def _library_name_for_key(self, api_key: str) -> str | None:
        for library_name, configured_key in self._library_keys.items():
            if configured_key == api_key:
                return library_name
        return None

    @staticmethod
    def _api_key_hint(api_key: str) -> str:
        tail = api_key[-4:] if len(api_key) >= 4 else api_key
        return f'***{tail}'

    @staticmethod
    def _response_error_message(response: httpx.Response) -> str | None:
        try:
            payload = response.json()
        except ValueError:
            return None

        if isinstance(payload, dict):
            for field in ('message', 'error', 'detail'):
                value = payload.get(field)
                if isinstance(value, str) and value.strip():
                    return value.strip()
        return None

    @staticmethod
    def _missing_permission(message: str | None) -> str | None:
        if not message:
            return None
        match = re.search(r'Missing required permission:\s*([a-zA-Z0-9._-]+)', message)
        if match:
            return match.group(1)
        return None

    @staticmethod
    def _album_owner_id(album: dict[str, Any]) -> str:
        owner_id = ImmichClient._extract_owner_id(album)
        if owner_id:
            return owner_id

        album_users = album.get('albumUsers')
        if isinstance(album_users, list):
            for user in album_users:
                if isinstance(user, dict) and user.get('role') == 'owner':
                    u_id = user.get('user', {}).get('id')
                    if u_id:
                        return str(u_id).strip()

        logger.warning('Album %s does not have an owner', album.get('id'))
        return ''

    async def _current_user_id(self, api_key: str) -> str:
        cached = self._user_id_by_key.get(api_key)
        if cached:
            return cached

        raw = await self._request_json('GET', '/users/me', api_key)
        if not isinstance(raw, dict):
            raise ImmichClientError('Invalid /users/me response from Immich')

        user_id = str(raw.get('id', '')).strip()
        if not user_id:
            raise ImmichClientError('Immich /users/me response missing id')

        self._user_id_by_key[api_key] = user_id
        return user_id

    async def _request_json(self, method: str, path: str, api_key: str, json: dict[str, Any] | None = None) -> Any:
        response = await self._request_raw(method, path, api_key, json=json)
        try:
            return response.json()
        except ValueError as exc:
            preview = response.text[:250].replace('\n', ' ')
            raise ImmichClientError(f'Invalid JSON response from Immich ({response.status_code}): {preview}') from exc

    async def _request_raw(
        self,
        method: str,
        path: str,
        api_key: str,
        json: dict[str, Any] | None = None,
        accept: str = 'application/json',
    ) -> httpx.Response:
        headers = {'x-api-key': api_key, 'accept': accept}
        url = f'{self._server_url}{path}'
        response = await self._http.request(method=method, url=url, headers=headers, json=json)

        if response.status_code >= 400:
            library_name = self._library_name_for_key(api_key)
            library_label = f"library '{library_name}'" if library_name else 'a configured library'
            key_hint = self._api_key_hint(api_key)
            message = self._response_error_message(response)

            if response.status_code == 403 and path == '/users/me':
                permission = self._missing_permission(message)
                if permission:
                    raise ImmichClientError(
                        f'Immich denied access for {library_label} (API key {key_hint}). '
                        f"This key is missing required permission '{permission}' for /users/me. "
                    )
                raise ImmichClientError(
                    f'Immich denied access for {library_label} (API key {key_hint}) when calling /users/me.'
                )

            if message:
                raise ImmichClientError(
                    f'Immich API request failed for {library_label} (API key {key_hint}): '
                    f'{method} {path} returned {response.status_code}. {message}'
                )

            preview = response.text[:250].replace('\n', ' ')
            raise ImmichClientError(
                f'Immich API request failed for {library_label} (API key {key_hint}): '
                f'{method} {path} returned {response.status_code}. Response: {preview}'
            )
        return response

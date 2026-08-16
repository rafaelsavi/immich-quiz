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


@dataclass(frozen=True)
class PersonInfo:
    id: str
    name: str


@dataclass(frozen=True)
class CityInfo:
    name: str
    country: str | None = None


@dataclass(frozen=True)
class TimelineBounds:
    min_date: date | None
    max_date: date | None


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
    person_ids: tuple[str, ...] = ()
    people_mode: str = 'OR'  # 'OR' (any) | 'AND' (all together)
    countries: tuple[str, ...] = ()
    cities: tuple[str, ...] = ()
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
        if self.person_ids:
            payload['personIds'] = list(self.person_ids)
        if self.include_partner_assets or self.album_ids:
            payload['withPartners'] = True
        if self.include_shared_albums or self.album_ids:
            payload['isShared'] = True
        # Immich API accepts only a single string for 'country'/'city'.
        # Pass the value only when exactly one is selected; multi-value
        # filtering is handled post-fetch by is_eligible_asset.
        if self.countries and len(self.countries) == 1:
            payload['country'] = self.countries[0]
        if self.cities and len(self.cities) == 1:
            payload['city'] = self.cities[0]
        if self.min_date:
            payload['takenAfter'] = f'{self.min_date.isoformat()}T00:00:00.000Z'
        if self.max_date:
            payload['takenBefore'] = f'{self.max_date.isoformat()}T23:59:59.999Z'
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

    async def list_albums(self, library_name: str, include_shared_albums: bool = False) -> list[dict[str, str]]:
        key = self._library_key(library_name)
        raw = await self._request_json('GET', '/albums', key)
        items: list[dict[str, str]] = []
        raw_count = len(raw) if isinstance(raw, list) else 0
        if isinstance(raw, list):
            current_user_id: str | None = None
            if not include_shared_albums:
                current_user_id = await self._current_user_id(key)
            for album in raw:
                if not isinstance(album, dict):
                    continue
                if not include_shared_albums and self._is_shared_album(album, current_user_id):
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
            include_shared_albums,
        )
        return items

    async def list_people(
        self,
        library_name: str,
        whitelist: frozenset[str] = frozenset(),
        blacklist: frozenset[str] = frozenset(),
    ) -> list[PersonInfo]:
        key = self._library_key(library_name)
        raw = await self._request_json('GET', '/people', key)
        people_list = raw.get('people', raw) if isinstance(raw, dict) else (raw if isinstance(raw, list) else [])

        result: list[PersonInfo] = []
        for p in people_list:
            if not isinstance(p, dict):
                continue
            pid = str(p.get('id', '')).strip()
            name = str(p.get('name', '')).strip()
            is_hidden = bool(p.get('isHidden', False))

            if not pid or not name or is_hidden:
                continue

            name_lower = name.lower()
            if whitelist and name_lower not in whitelist:
                continue
            if blacklist and name_lower in blacklist:
                continue

            result.append(PersonInfo(id=pid, name=name))

        result.sort(key=lambda x: (x.name.lower(), x.id))
        return result

    async def get_timeline_bounds(self, library_name: str) -> TimelineBounds:
        key = self._library_key(library_name)
        try:
            buckets = await self._request_json('GET', '/timeline/buckets?size=MONTH', key)
            if not isinstance(buckets, list) or not buckets:
                return TimelineBounds(min_date=None, max_date=None)

            valid_dates: list[date] = []
            for b in buckets:
                if isinstance(b, dict) and b.get('timeBucket'):
                    raw_time = str(b['timeBucket']).split('T')[0]
                    try:
                        valid_dates.append(date.fromisoformat(raw_time))
                    except ValueError:
                        continue

            if not valid_dates:
                return TimelineBounds(min_date=None, max_date=None)

            return TimelineBounds(min_date=min(valid_dates), max_date=max(valid_dates))
        except ImmichClientError:
            return TimelineBounds(min_date=None, max_date=None)

    async def get_asset_count(self, library_name: str) -> int | None:
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

    async def list_countries(
        self,
        library_name: str,
        whitelist: frozenset[str] = frozenset(),
        blacklist: frozenset[str] = frozenset(),
    ) -> list[str]:
        key = self._library_key(library_name)
        countries: set[str] = set()
        try:
            explore = await self._request_json('GET', '/search/explore', key)
            if isinstance(explore, list):
                for item in explore:
                    # Immich returns fieldName as 'country' or 'exifInfo.country' depending on version
                    field = str(item.get('fieldName', ''))
                    if isinstance(item, dict) and field in {'country', 'exifInfo.country'}:
                        for val in item.get('items', []):
                            if isinstance(val, dict) and val.get('value'):
                                countries.add(str(val['value']).strip())
        except ImmichClientError:
            pass

        # If whitelist provided, seed from whitelist
        if whitelist and not countries:
            countries = {c.title() for c in whitelist}

        filtered = [
            c
            for c in countries
            if (not whitelist or c.lower() in whitelist) and (not blacklist or c.lower() not in blacklist)
        ]
        filtered.sort(key=str.lower)
        return filtered

    async def list_cities(
        self,
        library_name: str,
        whitelist: frozenset[str] = frozenset(),
        blacklist: frozenset[str] = frozenset(),
    ) -> list[CityInfo]:
        key = self._library_key(library_name)
        city_map: dict[str, str | None] = {}  # city_name -> country_name
        try:
            explore = await self._request_json('GET', '/search/explore', key)
            if isinstance(explore, list):
                for item in explore:
                    # Immich returns fieldName as 'city' or 'exifInfo.city'
                    field = str(item.get('fieldName', ''))
                    if isinstance(item, dict) and field in {'city', 'exifInfo.city'}:
                        for val in item.get('items', []):
                            if isinstance(val, dict) and val.get('value'):
                                c_name = str(val['value']).strip()
                                country = str(val.get('country', '')).strip() or None
                                city_map[c_name] = country
        except ImmichClientError:
            pass

        if whitelist and not city_map:
            city_map = {c.title(): None for c in whitelist}

        filtered = [
            CityInfo(name=c, country=country)
            for c, country in city_map.items()
            if (not whitelist or c.lower() in whitelist) and (not blacklist or c.lower() not in blacklist)
        ]
        filtered.sort(key=lambda item: item.name.lower())
        return filtered

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
        items = await self._execute_search_query(key, library_name, query, size, page=page, randomized=False)

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

    async def _fetch_album_assets(self, key: str, album_id: str) -> list[dict[str, Any]]:
        try:
            album_raw = await self._request_json('GET', f'/albums/{album_id}', key)
            return self._extract_asset_items(album_raw)
        except ImmichClientError:
            return []

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
        raw_items = await self._execute_search_query(key, library_name, query, size, page=1, randomized=True)

        if not raw_items or not query.should_filter_by_owner:
            random.shuffle(raw_items)
            return raw_items[:size]

        current_user_id = await self._current_user_id(key)
        filtered = self._filter_assets_by_owner(
            raw_items,
            current_user_id=current_user_id,
            has_selected_albums=bool(query.album_ids),
            include_shared_albums=query.include_shared_albums,
            include_partner_assets=query.include_partner_assets,
        )
        random.shuffle(filtered)
        return filtered[:size]

    async def _execute_search_query(
        self,
        key: str,
        library_name: str,
        query: SearchQuery,
        size: int,
        *,
        page: int = 1,
        randomized: bool = False,
    ) -> list[dict[str, Any]]:
        """Decompose multi-select criteria (people, albums, cities, countries) into individual queries.

        Immich's API requires individual queries for OR semantics across multi-selects:
        - People: 'OR' unions single-person queries; 'AND' intersects them.
        - Albums: unions single-album queries.
        - Cities: unions single-city queries.
        - Countries: unions single-country queries.
        """
        # 1. Multi-person filtering
        if query.person_ids and len(query.person_ids) > 1:
            if query.people_mode.upper() == 'AND':
                person_asset_maps: list[dict[str, dict[str, Any]]] = []
                for pid in query.person_ids:
                    sub_q = SearchQuery(
                        album_ids=query.album_ids,
                        person_ids=(pid,),
                        people_mode='OR',
                        countries=query.countries,
                        cities=query.cities,
                        include_shared_albums=query.include_shared_albums,
                        include_partner_assets=query.include_partner_assets,
                        min_date=query.min_date,
                        max_date=query.max_date,
                    )
                    items = await self._execute_search_query(
                        key, library_name, sub_q, size, page=page, randomized=randomized
                    )
                    p_map: dict[str, dict[str, Any]] = {}
                    for item in items:
                        aid = str(item.get('id', '') or item.get('assetId', '')).strip()
                        if aid:
                            p_map[aid] = item
                    person_asset_maps.append(p_map)
                if not person_asset_maps:
                    return []
                common_ids = set(person_asset_maps[0].keys())
                for p_map in person_asset_maps[1:]:
                    common_ids &= set(p_map.keys())
                first_map = person_asset_maps[0]
                return [first_map[aid] for aid in common_ids if aid in first_map]
            else:
                pool: dict[str, dict[str, Any]] = {}
                for pid in query.person_ids:
                    sub_q = SearchQuery(
                        album_ids=query.album_ids,
                        person_ids=(pid,),
                        people_mode='OR',
                        countries=query.countries,
                        cities=query.cities,
                        include_shared_albums=query.include_shared_albums,
                        include_partner_assets=query.include_partner_assets,
                        min_date=query.min_date,
                        max_date=query.max_date,
                    )
                    items = await self._execute_search_query(
                        key, library_name, sub_q, size, page=page, randomized=randomized
                    )
                    self._merge_assets(pool, items)
                return list(pool.values())

        # 2. Multi-album filtering (OR union)
        if query.album_ids and len(query.album_ids) > 1:
            pool = {}
            for aid in query.album_ids:
                sub_q = SearchQuery(
                    album_ids=(aid,),
                    person_ids=query.person_ids,
                    people_mode=query.people_mode,
                    countries=query.countries,
                    cities=query.cities,
                    include_shared_albums=query.include_shared_albums,
                    include_partner_assets=query.include_partner_assets,
                    min_date=query.min_date,
                    max_date=query.max_date,
                )
                items = await self._execute_search_query(
                    key, library_name, sub_q, size, page=page, randomized=randomized
                )
                self._merge_assets(pool, items)
            return list(pool.values())

        # 3. Multi-city filtering (OR union)
        if query.cities and len(query.cities) > 1:
            pool = {}
            for city in query.cities:
                sub_q = SearchQuery(
                    album_ids=query.album_ids,
                    person_ids=query.person_ids,
                    people_mode=query.people_mode,
                    countries=query.countries,
                    cities=(city,),
                    include_shared_albums=query.include_shared_albums,
                    include_partner_assets=query.include_partner_assets,
                    min_date=query.min_date,
                    max_date=query.max_date,
                )
                items = await self._execute_search_query(
                    key, library_name, sub_q, size, page=page, randomized=randomized
                )
                self._merge_assets(pool, items)
            return list(pool.values())

        # 4. Multi-country filtering (OR union, when cities not specified)
        if query.countries and len(query.countries) > 1 and not query.cities:
            pool = {}
            for country in query.countries:
                sub_q = SearchQuery(
                    album_ids=query.album_ids,
                    person_ids=query.person_ids,
                    people_mode=query.people_mode,
                    countries=(country,),
                    cities=query.cities,
                    include_shared_albums=query.include_shared_albums,
                    include_partner_assets=query.include_partner_assets,
                    min_date=query.min_date,
                    max_date=query.max_date,
                )
                items = await self._execute_search_query(
                    key, library_name, sub_q, size, page=page, randomized=randomized
                )
                self._merge_assets(pool, items)
            return list(pool.values())

        # Base case: Primitive query (at most 1 person, 1 album, 1 city, 1 country)
        if randomized:
            return await self._search_primitive_random_assets(key, library_name, query, size)
        return await self._search_primitive_metadata_assets(key, library_name, query, size, page=page)

    async def _search_primitive_metadata_assets(
        self,
        key: str,
        library_name: str,
        query: SearchQuery,
        size: int,
        page: int = 1,
    ) -> list[dict[str, Any]]:
        payload = query.build_payload(size, page=page)
        items: list[dict[str, Any]] = []
        try:
            raw = await self._request_json('POST', '/search/metadata', key, json=payload)
            items = self._extract_asset_items(raw)
        except ImmichClientError:
            pass

        if not items and query.album_ids:
            items = await self._fetch_album_assets(key, query.album_ids[0])

        return items

    async def _search_primitive_random_assets(
        self,
        key: str,
        library_name: str,
        query: SearchQuery,
        size: int,
    ) -> list[dict[str, Any]]:
        pool: dict[str, dict[str, Any]] = {}
        if query.min_date or query.max_date:
            items = await self._search_assets_year_bucketed(library_name, size, query=query)
            self._merge_assets(pool, items)
        else:
            payload = query.build_payload(size)
            try:
                for _ in range(3):
                    raw = await self._request_json('POST', '/search/random', key, json=payload)
                    self._merge_assets(pool, self._extract_asset_items(raw))
                    if len(pool) >= size:
                        break
            except ImmichClientError:
                pass

            if not pool:
                items = await self._search_assets_randomized_fallback(library_name, size, query=query)
                self._merge_assets(pool, items)

            if not pool and query.album_ids:
                items = await self._fetch_album_assets(key, query.album_ids[0])
                self._merge_assets(pool, items)

        return list(pool.values())

    async def _search_assets_year_bucketed(
        self,
        library_name: str,
        size: int,
        query: SearchQuery,
    ) -> list[dict[str, Any]]:
        """Sample assets evenly across years in the active date range."""
        key = self._library_key(library_name)
        today = date.today()
        min_year = query.min_date.year if query.min_date else 1900
        max_year = query.max_date.year if query.max_date else today.year
        total_years = max(1, max_year - min_year + 1)

        if total_years > 50:
            bucket_years = 5
        elif total_years > 20:
            bucket_years = 2
        else:
            bucket_years = 1

        num_buckets = max(1, (total_years + bucket_years - 1) // bucket_years)
        per_bucket = max(10, (size * 2 + num_buckets - 1) // num_buckets)

        unique_assets: dict[str, dict[str, Any]] = {}
        year = min_year
        while year <= max_year:
            bucket_end_year = min(year + bucket_years - 1, max_year)
            bucket_min = max(date(year, 1, 1), query.min_date or date.min)
            bucket_max = min(date(bucket_end_year, 12, 31), query.max_date or today)

            bucket_query = SearchQuery(
                album_ids=query.album_ids,
                person_ids=query.person_ids,
                people_mode=query.people_mode,
                countries=query.countries,
                cities=query.cities,
                include_shared_albums=query.include_shared_albums,
                include_partner_assets=query.include_partner_assets,
                min_date=bucket_min,
                max_date=bucket_max,
            )
            try:
                payload = bucket_query.build_payload(per_bucket, page=1)
                raw = await self._request_json('POST', '/search/metadata', key, json=payload)
                self._merge_assets(unique_assets, self._extract_asset_items(raw))
            except ImmichClientError as exc:
                logger.warning('Year-bucketed sampling failed for %d–%d: %s', year, bucket_end_year, exc)

            year += bucket_years

        items = list(unique_assets.values())
        random.shuffle(items)
        return items[:size]

    async def _search_assets_randomized_fallback(
        self,
        library_name: str,
        size: int,
        query: SearchQuery,
    ) -> list[dict[str, Any]]:
        """Randomize metadata fallback by sampling multiple pages instead of page 1 only.

        Used as a fallback when /search/random is unavailable. When a date range
        is active, prefer _search_assets_year_bucketed for better temporal spread.
        """
        key = self._library_key(library_name)

        first_page_payload = query.build_payload(size, page=1)

        unique_assets: dict[str, dict[str, Any]] = {}
        try:
            first_raw = await self._request_json('POST', '/search/metadata', key, json=first_page_payload)
            extracted = self._extract_asset_items(first_raw)
            self._merge_assets(unique_assets, extracted)

            total = self._extract_total_assets(first_raw)
            if total is not None and total > size:
                total_pages = (total + size - 1) // size
                if total_pages > 1:
                    extra_page_count = min(10, total_pages - 1)
                    pages = random.sample(range(2, total_pages + 1), k=extra_page_count)
                    for page in pages:
                        page_payload = query.build_payload(size, page=page)
                        raw = await self._request_json('POST', '/search/metadata', key, json=page_payload)
                        self._merge_assets(unique_assets, self._extract_asset_items(raw))
        except ImmichClientError as exc:
            logger.warning('/search/metadata fallback failed: %s', exc)

        items = list(unique_assets.values())
        random.shuffle(items)
        return items[:size]

    @staticmethod
    def _extract_owner_id(item: dict[str, Any]) -> str:
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
        """Return True if the album was shared with the user by someone else.

        Albums owned by the current user (whether private or shared with others)
        return False so they are retained when include_shared_albums is False.
        """
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
            owner_id = ImmichClient._extract_owner_id(asset)
            if not owner_id or (current_user_id and owner_id == current_user_id):
                filtered.append(asset)
                continue

            is_shared = bool(asset.get('isShared') or asset.get('shared'))
            if (
                is_shared
                and include_shared_albums
                or not is_shared
                and include_partner_assets
                or (include_shared_albums or include_partner_assets)
                and ('isShared' not in asset and 'shared' not in asset)
            ):
                filtered.append(asset)

        return filtered

    @staticmethod
    def _unwrap_asset(item: dict[str, Any]) -> dict[str, Any]:
        if isinstance(item.get('asset'), dict) and (item['asset'].get('id') or item['asset'].get('assetId')):
            unwrapped = dict(item['asset'])
            for k, v in item.items():
                if k != 'asset' and k not in unwrapped:
                    unwrapped[k] = v
            return unwrapped
        return item

    @staticmethod
    def _merge_assets(target: dict[str, dict[str, Any]], items: list[dict[str, Any]]) -> None:
        for raw_item in items:
            item = ImmichClient._unwrap_asset(raw_item)
            asset_id = str(item.get('id', '') or item.get('assetId', '')).strip()
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
        key = self._library_key(library_name)
        preview = await self._request_raw('GET', f'/assets/{asset_id}/thumbnail?size=preview', key, accept='*/*')
        content_type = preview.headers.get('content-type', 'image/jpeg')
        return preview.content, content_type

    @staticmethod
    def _exif(asset: dict[str, Any]) -> dict[str, Any]:
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
        people_mode: str = 'OR',
        country_whitelist: frozenset[str] = frozenset(),
        country_blacklist: frozenset[str] = frozenset(),
        city_whitelist: frozenset[str] = frozenset(),
        city_blacklist: frozenset[str] = frozenset(),
        people_whitelist: frozenset[str] = frozenset(),
        people_blacklist: frozenset[str] = frozenset(),
    ) -> bool:
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
        asset_person_ids = {
            str(p.get('id', '')).strip() for p in asset_people if isinstance(p, dict) and p.get('id')
        }
        asset_person_names = {
            str(p.get('name', '')).strip().lower() for p in asset_people if isinstance(p, dict) and p.get('name')
        }

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

        # Country whitelist baseline (when user didn't specify countries)
        if (
            country_whitelist
            and not countries
            and (not asset_country or asset_country not in {c.lower() for c in country_whitelist})
        ):
            return False

        # City whitelist baseline (when user didn't specify cities)
        if (
            city_whitelist
            and not cities
            and (not asset_city or asset_city not in {c.lower() for c in city_whitelist})
        ):
            return False

        # People whitelist baseline (when user didn't specify person_ids)
        # Excludes photos containing non-whitelisted recognized people, while allowing photos with no tagged people
        if people_whitelist and not person_ids:
            wl_lower = {w.lower() for w in people_whitelist}
            for p_name in asset_person_names:
                if p_name and p_name not in wl_lower:
                    return False
            for pid in asset_person_ids:
                if pid and pid not in people_whitelist and not any(p_name in wl_lower for p_name in asset_person_names):
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

        # User Person check (if person_ids filter specified)
        if person_ids:
            target_person_ids = set(person_ids)
            if people_mode.upper() == 'AND':
                # 'AND' mode: All selected people must be present in this photo
                if not target_person_ids.issubset(asset_person_ids):
                    return False
            else:
                # 'OR' mode: At least one selected person must be present in this photo
                if not asset_person_ids.intersection(target_person_ids):
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
            raise ImmichClientError(f'Immich API error {res.status_code} at {path}: {res.text[:300]}')

        return res

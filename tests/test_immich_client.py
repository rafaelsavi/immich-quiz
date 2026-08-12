from __future__ import annotations

import json
from datetime import date

import httpx
import pytest

from src.immich.client import ImmichClient, ImmichClientError


def build_client(handler) -> ImmichClient:
    transport = httpx.MockTransport(handler)
    return ImmichClient(
        'https://example.test/api',
        {'family': 'token'},
        client=httpx.AsyncClient(transport=transport),
    )


def test_immich_client_url_normalization() -> None:
    client1 = ImmichClient('https://example.test', {'family': 'token'})
    assert client1._server_url == 'https://example.test/api'

    client2 = ImmichClient('https://example.test/', {'family': 'token'})
    assert client2._server_url == 'https://example.test/api'

    client3 = ImmichClient('https://example.test/api/', {'family': 'token'})
    assert client3._server_url == 'https://example.test/api'


def asset(**overrides) -> dict:
    base = {
        'id': 'asset-1',
        'type': 'IMAGE',
        'exifInfo': {
            'latitude': 10.0,
            'longitude': 20.0,
            'dateTimeOriginal': '2024-01-14T10:11:12Z',
        },
        'fileCreatedAt': '2024-01-14T10:11:12Z',
    }
    base.update(overrides)
    return base


def test_video_assets_are_rejected() -> None:
    assert ImmichClient.is_eligible_asset(asset(type='VIDEO'), True, True) is False


def test_missing_coordinates_rejected_in_location_mode() -> None:
    no_coords = asset(exifInfo={'dateTimeOriginal': '2024-01-14T10:11:12Z'})
    assert ImmichClient.is_eligible_asset(no_coords, True, False) is False
    assert ImmichClient.is_eligible_asset(no_coords, False, True) is True


def test_zero_coordinates_rejected_in_location_mode() -> None:
    zeroed = asset(exifInfo={'latitude': 0, 'longitude': 0, 'dateTimeOriginal': '2024-01-14T10:11:12Z'})
    assert ImmichClient.is_eligible_asset(zeroed, True, False) is False

    ans = ImmichClient.extract_answer(zeroed)
    assert ans.latitude is None
    assert ans.longitude is None


def test_greenwich_and_equator_coordinates_accepted() -> None:
    greenwich = asset(exifInfo={'latitude': 51.4778, 'longitude': 0.0, 'dateTimeOriginal': '2024-01-14T10:11:12Z'})
    equator = asset(exifInfo={'latitude': 0.0, 'longitude': 37.9062, 'dateTimeOriginal': '2024-01-14T10:11:12Z'})
    assert ImmichClient.is_eligible_asset(greenwich, True, False) is True
    assert ImmichClient.is_eligible_asset(equator, True, False) is True
    ans_g = ImmichClient.extract_answer(greenwich)
    assert ans_g.latitude == 51.4778
    assert ans_g.longitude == 0.0


def test_unparseable_date_rejected_in_date_mode() -> None:
    bad_date = asset(exifInfo={'latitude': 10.0, 'longitude': 20.0, 'dateTimeOriginal': 'nope'}, fileCreatedAt=None)
    assert ImmichClient.is_eligible_asset(bad_date, False, True) is False
    assert ImmichClient.is_eligible_asset(bad_date, True, False) is True


def test_date_lower_bound_filters_older_assets() -> None:
    older = asset(exifInfo={'latitude': 10.0, 'longitude': 20.0, 'dateTimeOriginal': '2020-01-01T10:11:12Z'})
    assert ImmichClient.is_eligible_asset(older, False, False, min_capture_date=date(2021, 1, 1)) is False


def test_date_upper_bound_filters_newer_assets() -> None:
    newer = asset(exifInfo={'latitude': 10.0, 'longitude': 20.0, 'dateTimeOriginal': '2025-01-01T10:11:12Z'})
    assert ImmichClient.is_eligible_asset(newer, False, False, max_capture_date=date(2024, 12, 31)) is False


def test_date_bounds_require_parseable_date() -> None:
    bad_date = asset(exifInfo={'latitude': 10.0, 'longitude': 20.0, 'dateTimeOriginal': 'nope'}, fileCreatedAt=None)
    assert ImmichClient.is_eligible_asset(bad_date, False, False, min_capture_date=date(2021, 1, 1)) is False


def test_valid_asset_accepted() -> None:
    assert ImmichClient.is_eligible_asset(asset(), True, True) is True


def test_asset_within_date_bounds_is_accepted() -> None:
    assert (
        ImmichClient.is_eligible_asset(
            asset(),
            True,
            True,
            min_capture_date=date(2024, 1, 1),
            max_capture_date=date(2024, 12, 31),
        )
        is True
    )


def test_extract_answer_reads_exif() -> None:
    answer = ImmichClient.extract_answer(asset())
    assert answer.latitude == 10.0
    assert answer.longitude == 20.0
    assert answer.capture_date == date(2024, 1, 14)


async def test_media_uses_preview_thumbnail_not_original() -> None:
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen['url'] = str(request.url)
        return httpx.Response(200, content=b'\xff\xd8\xff\xe0JFIF-body', headers={'content-type': 'image/jpeg'})

    client = build_client(handler)
    content, content_type = await client.get_asset_bytes('family', 'asset-1')
    await client.aclose()

    assert '/assets/asset-1/thumbnail' in seen['url']
    assert 'original' not in seen['url']
    assert content_type == 'image/jpeg'
    assert b'Exif' not in content
    assert b'GPS' not in content


async def test_random_search_falls_back_to_metadata_search() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith('/users/me'):
            return httpx.Response(200, json={'id': 'me-user'})
        if request.url.path.endswith('/search/random'):
            return httpx.Response(404, json={'error': 'not found'})
        return httpx.Response(200, json={'assets': {'items': [asset()]}})

    client = build_client(handler)
    items = await client.search_random_assets('family')
    await client.aclose()

    assert len(items) == 1
    assert items[0]['id'] == 'asset-1'


async def test_random_search_fallback_samples_multiple_metadata_pages() -> None:
    seen_pages: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith('/users/me'):
            return httpx.Response(200, json={'id': 'me-user'})
        if request.url.path.endswith('/search/random'):
            return httpx.Response(404, json={'error': 'not found'})

        payload = json.loads(request.content.decode('utf-8'))
        page = int(payload.get('page', 1))
        seen_pages.append(page)

        if page == 1:
            return httpx.Response(200, json={'assets': {'items': [asset(id='page-1')], 'total': 500}})
        if page == 2:
            return httpx.Response(200, json={'assets': {'items': [asset(id='page-2')], 'total': 500}})
        return httpx.Response(200, json={'assets': {'items': [], 'total': 500}})

    client = build_client(handler)
    items = await client.search_random_assets('family')
    await client.aclose()

    assert {item['id'] for item in items} == {'page-1', 'page-2'}
    assert set(seen_pages) >= {1, 2}


async def test_unknown_library_raises() -> None:
    client = build_client(lambda request: httpx.Response(200, json=[]))
    with pytest.raises(ImmichClientError, match='Unknown library'):
        await client.list_albums('missing')
    await client.aclose()


async def test_list_albums_excludes_shared_albums() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith('/users/me'):
            return httpx.Response(200, json={'id': 'me-user'})
        if request.url.path.endswith('/albums'):
            return httpx.Response(
                200,
                json=[
                    {'id': 'album-1', 'albumName': 'Mine', 'ownerId': 'me-user'},
                    {'id': 'album-2', 'albumName': 'Shared', 'ownerId': 'other-user'},
                    {'id': 'album-3', 'albumName': 'Also Mine', 'owner': {'id': 'me-user'}},
                ],
            )
        return httpx.Response(404, json={'error': 'not found'})

    client = build_client(handler)
    albums = await client.list_albums('family')
    await client.aclose()

    assert albums == [
        {'id': 'album-3', 'name': 'Also Mine'},
        {'id': 'album-1', 'name': 'Mine'},
    ]


async def test_list_albums_returns_ascending_by_name() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith('/users/me'):
            return httpx.Response(200, json={'id': 'me-user'})
        if request.url.path.endswith('/albums'):
            return httpx.Response(
                200,
                json=[
                    {'id': 'album-1', 'albumName': 'Zebra', 'ownerId': 'me-user'},
                    {'id': 'album-2', 'albumName': 'Apple', 'ownerId': 'me-user'},
                    {'id': 'album-3', 'albumName': 'banana', 'ownerId': 'me-user'},
                ],
            )
        return httpx.Response(404, json={'error': 'not found'})

    client = build_client(handler)
    albums = await client.list_albums('family')
    await client.aclose()

    assert albums == [
        {'id': 'album-2', 'name': 'Apple'},
        {'id': 'album-3', 'name': 'banana'},
        {'id': 'album-1', 'name': 'Zebra'},
    ]


async def test_list_albums_includes_shared_albums_when_true() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith('/users/me'):
            return httpx.Response(200, json={'id': 'me-user'})
        if request.url.path.endswith('/albums'):
            return httpx.Response(
                200,
                json=[
                    {'id': 'album-1', 'albumName': 'Mine', 'ownerId': 'me-user'},
                    {'id': 'album-2', 'albumName': 'Shared', 'ownerId': 'other-user'},
                ],
            )
        return httpx.Response(404, json={'error': 'not found'})

    client = build_client(handler)
    albums = await client.list_albums('family', include_shared_albums=True)
    await client.aclose()

    assert albums == [
        {'id': 'album-1', 'name': 'Mine'},
        {'id': 'album-2', 'name': 'Shared'},
    ]


async def test_search_random_assets_payload_flags() -> None:
    payloads: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith('/users/me'):
            return httpx.Response(200, json={'id': 'me-user'})
        if request.url.path.endswith('/search/random'):
            data = json.loads(request.content.decode('utf-8'))
            payloads.append(data)
            return httpx.Response(200, json={'assets': {'items': [asset()]}})
        return httpx.Response(404, json={'error': 'not found'})

    client = build_client(handler)
    await client.search_random_assets('family', size=1, include_partner_assets=True, include_shared_albums=False)
    await client.search_random_assets('family', size=1, include_partner_assets=False, include_shared_albums=True)
    await client.aclose()

    assert len(payloads) == 2
    assert payloads[0].get('withPartners') is True
    assert 'isShared' not in payloads[0]

    assert 'withPartners' not in payloads[1]
    assert payloads[1].get('isShared') is True


async def test_search_random_assets_owner_filtering_both_false() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith('/users/me'):
            return httpx.Response(200, json={'id': 'me-user'})
        if request.url.path.endswith('/search/random'):
            return httpx.Response(
                200,
                json={
                    'assets': {
                        'items': [
                            asset(id='my-photo', ownerId='me-user'),
                            asset(id='shared-photo', ownerId='other-user', isShared=True),
                            asset(id='partner-photo', ownerId='partner-user', isShared=False),
                        ]
                    }
                },
            )
        return httpx.Response(404, json={'error': 'not found'})

    client = build_client(handler)
    items = await client.search_random_assets('family', include_shared_albums=False, include_partner_assets=False)
    await client.aclose()

    assert [item['id'] for item in items] == ['my-photo']


async def test_search_random_assets_owner_filtering_include_partner() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith('/users/me'):
            return httpx.Response(200, json={'id': 'me-user'})
        if request.url.path.endswith('/search/random'):
            return httpx.Response(
                200,
                json={
                    'assets': {
                        'items': [
                            asset(id='my-photo', ownerId='me-user'),
                            asset(id='shared-photo', ownerId='other-user', isShared=True),
                            asset(id='partner-photo', ownerId='partner-user', isShared=False),
                        ]
                    }
                },
            )
        return httpx.Response(404, json={'error': 'not found'})

    client = build_client(handler)
    items = await client.search_random_assets('family', include_shared_albums=False, include_partner_assets=True)
    await client.aclose()

    assert set(item['id'] for item in items) == {'my-photo', 'partner-photo'}


async def test_search_random_assets_owner_filtering_include_shared_albums() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith('/users/me'):
            return httpx.Response(200, json={'id': 'me-user'})
        if request.url.path.endswith('/search/random'):
            return httpx.Response(
                200,
                json={
                    'assets': {
                        'items': [
                            asset(id='my-photo', ownerId='me-user'),
                            asset(id='shared-photo', ownerId='other-user', isShared=True),
                            asset(id='partner-photo', ownerId='partner-user', isShared=False),
                        ]
                    }
                },
            )
        return httpx.Response(404, json={'error': 'not found'})

    client = build_client(handler)
    items = await client.search_random_assets('family', include_shared_albums=True, include_partner_assets=False)
    await client.aclose()

    assert set(item['id'] for item in items) == {'my-photo', 'shared-photo'}


async def test_search_random_assets_owner_filtering_selected_album() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith('/users/me'):
            return httpx.Response(200, json={'id': 'me-user'})
        if request.url.path.endswith('/search/random'):
            return httpx.Response(
                200,
                json={
                    'assets': {
                        'items': [
                            asset(id='shared-album-photo', ownerId='other-user', isShared=True),
                        ]
                    }
                },
            )
        return httpx.Response(404, json={'error': 'not found'})

    client = build_client(handler)
    items = await client.search_random_assets(
        'family',
        album_ids=['album-shared'],
        include_shared_albums=False,
        include_partner_assets=False,
    )
    await client.aclose()

    assert [item['id'] for item in items] == ['shared-album-photo']


async def test_immich_client_async_context_manager() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={})

    transport = httpx.MockTransport(handler)
    async_client = httpx.AsyncClient(transport=transport)

    async with ImmichClient('https://example.test/api', {'family': 'token'}, client=async_client) as client:
        assert client._client is not None

    assert client._client is None


async def test_list_albums_lazy_loads_users_me() -> None:
    users_me_called = False

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal users_me_called
        if request.url.path.endswith('/users/me'):
            users_me_called = True
            return httpx.Response(200, json={'id': 'me-user'})
        if request.url.path.endswith('/albums'):
            return httpx.Response(
                200,
                json=[
                    {'id': 'album-1', 'albumName': 'Shared Album', 'ownerId': 'other-user'},
                ],
            )
        return httpx.Response(404, json={'error': 'not found'})

    client = build_client(handler)
    albums = await client.list_albums('family', include_shared_albums=True)
    await client.aclose()

    assert users_me_called is False
    assert len(albums) == 1


async def test_search_assets_lazy_loads_users_me_when_album_targeted_or_all_shared() -> None:
    users_me_called = False

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal users_me_called
        if request.url.path.endswith('/users/me'):
            users_me_called = True
            return httpx.Response(200, json={'id': 'me-user'})
        if request.url.path.endswith('/search/metadata'):
            return httpx.Response(200, json={'assets': {'items': [asset()]}})
        return httpx.Response(404, json={'error': 'not found'})

    client = build_client(handler)

    items1 = await client.search_assets('family', album_id='album-1')
    assert users_me_called is False
    assert len(items1) == 1

    items2 = await client.search_assets('family', include_shared_albums=True, include_partner_assets=True)
    assert users_me_called is False
    assert len(items2) == 1

    await client.aclose()


def test_extract_owner_id() -> None:
    assert ImmichClient._extract_owner_id({'ownerId': '  user-1  '}) == 'user-1'
    assert ImmichClient._extract_owner_id({'owner': {'id': 'user-2'}}) == 'user-2'
    assert ImmichClient._extract_owner_id({'ownerId': ''}) == ''
    assert ImmichClient._extract_owner_id({}) == ''


def test_build_search_payload() -> None:
    payload1 = ImmichClient._build_search_payload(250)
    assert payload1 == {'size': 250, 'withExif': True}

    payload2 = ImmichClient._build_search_payload(
        10,
        album_id='album-123',
        page=2,
        include_shared_albums=True,
        include_partner_assets=True,
    )
    assert payload2 == {
        'size': 10,
        'page': 2,
        'withExif': True,
        'albumIds': ['album-123'],
        'withPartners': True,
    }
    assert 'isShared' not in payload2


def test_search_query_build_payload() -> None:
    from datetime import date

    from src.immich.client import SearchQuery

    q = SearchQuery(
        album_id='album-1',
        include_shared_albums=True,
        include_partner_assets=True,
        min_date=date(2020, 1, 1),
        max_date=date(2024, 12, 31),
    )
    payload = q.build_payload(size=50, page=3)
    assert payload == {
        'size': 50,
        'page': 3,
        'withExif': True,
        'albumIds': ['album-1'],
        'withPartners': True,
        'createdAfter': '2020-01-01T00:00:00.000Z',
        'createdBefore': '2024-12-31T23:59:59.999Z',
    }
    assert 'isShared' not in payload  # album_id is set


def test_search_query_should_filter_by_owner() -> None:
    from src.immich.client import SearchQuery

    assert SearchQuery(album_id='album-1').should_filter_by_owner is False
    assert SearchQuery(include_shared_albums=True, include_partner_assets=True).should_filter_by_owner is False
    assert SearchQuery(include_shared_albums=True, include_partner_assets=False).should_filter_by_owner is True
    assert SearchQuery().should_filter_by_owner is True

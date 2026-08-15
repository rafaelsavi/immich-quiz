from __future__ import annotations

import json
from datetime import date

import httpx
import pytest

from src.immich.client import CityInfo, ImmichClient, ImmichClientError, PersonInfo, SearchQuery


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
    assert ImmichClient.is_eligible_asset(older, False, False, min_date=date(2021, 1, 1)) is False


def test_date_upper_bound_filters_newer_assets() -> None:
    newer = asset(exifInfo={'latitude': 10.0, 'longitude': 20.0, 'dateTimeOriginal': '2025-01-01T10:11:12Z'})
    assert ImmichClient.is_eligible_asset(newer, False, False, max_date=date(2024, 12, 31)) is False


def test_date_bounds_require_parseable_date() -> None:
    bad_date = asset(exifInfo={'latitude': 10.0, 'longitude': 20.0, 'dateTimeOriginal': 'nope'}, fileCreatedAt=None)
    assert ImmichClient.is_eligible_asset(bad_date, False, False, min_date=date(2021, 1, 1)) is False


def test_valid_asset_accepted() -> None:
    assert ImmichClient.is_eligible_asset(asset(), True, True) is True


def test_asset_within_date_bounds_is_accepted() -> None:
    assert (
        ImmichClient.is_eligible_asset(
            asset(),
            True,
            True,
            min_date=date(2024, 1, 1),
            max_date=date(2024, 12, 31),
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


async def test_list_albums_excludes_modern_shared_albums() -> None:
    """Modern Immich payloads use shared: bool and albumUsers instead of top-level ownerId.

    Shared albums owned by the user should be included, while albums shared with the user
    by someone else should be excluded when include_shared_albums=False.
    """

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith('/users/me'):
            return httpx.Response(200, json={'id': 'me-user'})
        if request.url.path.endswith('/albums'):
            return httpx.Response(
                200,
                json=[
                    {
                        'id': 'album-private',
                        'albumName': 'Private Trip',
                        'shared': False,
                        'albumUsers': [{'role': 'owner', 'userId': 'me-user'}],
                    },
                    {
                        'id': 'album-shared-with-me',
                        'albumName': 'Family Shared By Bob',
                        'shared': True,
                        'albumUsers': [
                            {'role': 'owner', 'userId': 'other-user'},
                            {'role': 'viewer', 'userId': 'me-user'},
                        ],
                    },
                    {
                        'id': 'album-shared-by-me',
                        'albumName': 'My Album Shared To Family',
                        'shared': True,
                        'albumUsers': [
                            {'role': 'owner', 'userId': 'me-user'},
                            {'role': 'editor', 'userId': 'other-user'},
                        ],
                    },
                ],
            )
        return httpx.Response(404, json={'error': 'not found'})

    client = build_client(handler)
    albums = await client.list_albums('family', include_shared_albums=False)
    await client.aclose()

    # Private albums and shared albums owned by me should be returned; albums shared by others are excluded
    assert albums == [
        {'id': 'album-shared-by-me', 'name': 'My Album Shared To Family'},
        {'id': 'album-private', 'name': 'Private Trip'},
    ]


async def test_list_albums_includes_modern_shared_albums_when_true() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith('/users/me'):
            return httpx.Response(200, json={'id': 'me-user'})
        if request.url.path.endswith('/albums'):
            return httpx.Response(
                200,
                json=[
                    {
                        'id': 'album-private',
                        'albumName': 'Private Trip',
                        'shared': False,
                        'albumUsers': [{'role': 'owner', 'userId': 'me-user'}],
                    },
                    {
                        'id': 'album-shared-with-me',
                        'albumName': 'Family Shared By Bob',
                        'shared': True,
                        'albumUsers': [
                            {'role': 'owner', 'userId': 'other-user'},
                            {'role': 'viewer', 'userId': 'me-user'},
                        ],
                    },
                    {
                        'id': 'album-shared-by-me',
                        'albumName': 'My Album Shared To Family',
                        'shared': True,
                        'albumUsers': [
                            {'role': 'owner', 'userId': 'me-user'},
                            {'role': 'editor', 'userId': 'other-user'},
                        ],
                    },
                ],
            )
        return httpx.Response(404, json={'error': 'not found'})

    client = build_client(handler)
    albums = await client.list_albums('family', include_shared_albums=True)
    await client.aclose()

    assert albums == [
        {'id': 'album-shared-with-me', 'name': 'Family Shared By Bob'},
        {'id': 'album-shared-by-me', 'name': 'My Album Shared To Family'},
        {'id': 'album-private', 'name': 'Private Trip'},
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


async def test_list_albums_shared_by_user_retained_when_shared_false_and_top_level_owner() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith('/users/me'):
            return httpx.Response(200, json={'id': 'me-user'})
        if request.url.path.endswith('/albums'):
            return httpx.Response(
                200,
                json=[
                    {'id': 'album-1', 'albumName': 'My Shared Album', 'ownerId': 'me-user', 'isShared': True},
                    {'id': 'album-2', 'albumName': 'Other Shared Album', 'ownerId': 'other-user', 'isShared': True},
                    {
                        'id': 'album-3',
                        'albumName': 'My Nested Owner Album',
                        'owner': {'id': 'me-user'},
                        'shared': True,
                    },
                    {
                        'id': 'album-4',
                        'albumName': 'Other Nested Owner Album',
                        'owner': {'id': 'other-user'},
                        'shared': True,
                    },
                ],
            )
        return httpx.Response(404, json={'error': 'not found'})

    client = build_client(handler)
    albums = await client.list_albums('family', include_shared_albums=False)
    await client.aclose()

    assert albums == [
        {'id': 'album-3', 'name': 'My Nested Owner Album'},
        {'id': 'album-1', 'name': 'My Shared Album'},
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


async def test_search_random_assets_owner_filtering_with_shared_field() -> None:
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
                            asset(id='shared-photo', ownerId='other-user', shared=True),
                            asset(id='partner-photo', ownerId='partner-user', shared=False),
                        ]
                    }
                },
            )
        return httpx.Response(404, json={'error': 'not found'})

    client = build_client(handler)
    items_none = await client.search_random_assets('family', include_shared_albums=False, include_partner_assets=False)
    items_partner = await client.search_random_assets(
        'family', include_shared_albums=False, include_partner_assets=True
    )
    items_shared = await client.search_random_assets('family', include_shared_albums=True, include_partner_assets=False)
    await client.aclose()

    assert [item['id'] for item in items_none] == ['my-photo']
    assert set(item['id'] for item in items_partner) == {'my-photo', 'partner-photo'}
    assert set(item['id'] for item in items_shared) == {'my-photo', 'shared-photo'}


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

    items1 = await client.search_assets('family', album_ids=['album-1'])
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
    from src.immich.client import SearchQuery

    payload1 = SearchQuery().build_payload(250)
    assert payload1 == {'size': 250, 'withExif': True}

    payload2 = SearchQuery(
        album_ids=('album-123',),
        include_shared_albums=True,
        include_partner_assets=True,
    ).build_payload(10, page=2)
    assert payload2 == {
        'size': 10,
        'page': 2,
        'withExif': True,
        'albumIds': ['album-123'],
        'withPartners': True,
        'isShared': True,
    }


def test_search_query_build_payload() -> None:
    from datetime import date

    from src.immich.client import SearchQuery

    q = SearchQuery(
        album_ids=('album-1',),
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
        'isShared': True,
        'takenAfter': '2020-01-01T00:00:00.000Z',
        'takenBefore': '2024-12-31T23:59:59.999Z',
    }


def test_search_query_should_filter_by_owner() -> None:
    from src.immich.client import SearchQuery

    assert SearchQuery(album_ids=('album-1',)).should_filter_by_owner is False
    assert SearchQuery(include_shared_albums=True, include_partner_assets=True).should_filter_by_owner is False
    assert SearchQuery(include_shared_albums=True, include_partner_assets=False).should_filter_by_owner is True
    assert SearchQuery().should_filter_by_owner is True


def test_extract_asset_items_list_format() -> None:
    raw = {'assets': [{'id': 'a1'}, {'id': 'a2'}]}
    items = ImmichClient._extract_asset_items(raw)
    assert [x['id'] for x in items] == ['a1', 'a2']


def test_exif_fallback_top_level() -> None:
    asset = {'id': 'a1', 'latitude': 48.8584, 'longitude': 2.2945, 'dateTimeOriginal': '2023-06-15T12:00:00Z'}
    exif = ImmichClient._exif(asset)
    assert exif['latitude'] == 48.8584
    assert exif['longitude'] == 2.2945
    assert exif['dateTimeOriginal'] == '2023-06-15T12:00:00Z'
    assert ImmichClient.is_eligible_asset(asset, location_mode=True, date_mode=True) is True


async def test_search_random_assets_album_get_fallback() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith('/search/random') or request.url.path.endswith('/search/metadata'):
            return httpx.Response(200, json={'assets': []})
        if '/albums/album-fallback' in request.url.path:
            return httpx.Response(
                200,
                json={
                    'id': 'album-fallback',
                    'assets': [
                        asset(id='photo-in-album', latitude=10.0, longitude=20.0),
                    ],
                },
            )
        return httpx.Response(404, json={'error': 'not found'})

    client = build_client(handler)
    items = await client.search_random_assets('family', album_ids=['album-fallback'])
    await client.aclose()

    assert [item['id'] for item in items] == ['photo-in-album']


async def test_search_random_assets_multiple_albums_or_query() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith('/search/random') or request.url.path.endswith('/search/metadata'):
            body = request.read().decode('utf-8')
            if 'album-1' in body:
                return httpx.Response(200, json={'assets': [{'id': 'photo-album-1'}]})
            if 'album-2' in body:
                return httpx.Response(200, json={'assets': [{'id': 'photo-album-2'}]})
        return httpx.Response(404, json={'error': 'not found'})

    client = build_client(handler)
    items = await client.search_random_assets('family', album_ids=['album-1', 'album-2'])
    await client.aclose()

    item_ids = set(item['id'] for item in items)
    assert item_ids == {'photo-album-1', 'photo-album-2'}


async def test_search_random_assets_with_date_bounds_uses_metadata_search() -> None:
    recorded_endpoints: list[str] = []
    recorded_payloads: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        recorded_endpoints.append(request.url.path)
        if request.url.path.endswith('/users/me'):
            return httpx.Response(200, json={'id': 'me-user'})
        if request.url.path.endswith('/search/metadata'):
            data = json.loads(request.content.decode('utf-8'))
            recorded_payloads.append(data)
            return httpx.Response(
                200,
                json={
                    'total': 100,
                    'assets': {
                        'items': [
                            asset(id='vintage-photo', ownerId='me-user', dateTimeOriginal='1999-05-20T10:00:00Z'),
                        ]
                    },
                },
            )
        return httpx.Response(404, json={'error': 'not found'})

    client = build_client(handler)
    items = await client.search_random_assets(
        'family',
        min_date=date(1990, 1, 1),
        max_date=date(2000, 12, 31),
    )
    await client.aclose()

    assert any(ep.endswith('/search/metadata') for ep in recorded_endpoints)
    assert not any(ep.endswith('/search/random') for ep in recorded_endpoints)
    assert len(recorded_payloads) > 0
    assert recorded_payloads[0].get('takenAfter') == '1990-01-01T00:00:00.000Z'
    assert recorded_payloads[0].get('takenBefore') == '2000-12-31T23:59:59.999Z'
    assert [item['id'] for item in items] == ['vintage-photo']


async def test_list_people_parses_and_filters() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith('/people'):
            return httpx.Response(
                200,
                json={
                    'people': [
                        {'id': 'p1', 'name': 'Charlie', 'isHidden': False},
                        {'id': 'p2', 'name': 'Alice', 'isHidden': False},
                        {'id': 'p3', 'name': 'Bob', 'isHidden': False},
                        {'id': 'p4', 'name': 'Secret Agent', 'isHidden': True},
                        {'id': 'p5', 'name': '', 'isHidden': False},
                        {'id': '', 'name': 'No ID', 'isHidden': False},
                    ]
                },
            )
        return httpx.Response(404, json={'error': 'not found'})

    client = build_client(handler)

    # All unhidden people, sorted alphabetically
    people = await client.list_people('family')
    assert people == [
        PersonInfo(id='p2', name='Alice'),
        PersonInfo(id='p3', name='Bob'),
        PersonInfo(id='p1', name='Charlie'),
    ]

    # Whitelist filtering
    wl_people = await client.list_people('family', whitelist=frozenset({'alice', 'charlie'}))
    assert wl_people == [
        PersonInfo(id='p2', name='Alice'),
        PersonInfo(id='p1', name='Charlie'),
    ]

    # Blacklist filtering
    bl_people = await client.list_people('family', blacklist=frozenset({'bob'}))
    assert bl_people == [
        PersonInfo(id='p2', name='Alice'),
        PersonInfo(id='p1', name='Charlie'),
    ]

    # Whitelist and blacklist combined
    combo_people = await client.list_people(
        'family',
        whitelist=frozenset({'alice', 'bob'}),
        blacklist=frozenset({'bob'}),
    )
    assert combo_people == [
        PersonInfo(id='p2', name='Alice'),
    ]

    await client.aclose()


async def test_list_people_handles_direct_list_response() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith('/people'):
            return httpx.Response(
                200,
                json=[
                    {'id': 'p1', 'name': 'Dave', 'isHidden': False},
                ],
            )
        return httpx.Response(404, json={'error': 'not found'})

    client = build_client(handler)
    people = await client.list_people('family')
    await client.aclose()

    assert people == [PersonInfo(id='p1', name='Dave')]


async def test_get_timeline_bounds() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if 'buckets' in request.url.path:
            return httpx.Response(
                200,
                json=[
                    {'timeBucket': '2021-03-01T00:00:00.000Z', 'count': 10},
                    {'timeBucket': '2019-06-01T00:00:00.000Z', 'count': 5},
                    {'timeBucket': '2023-11-01T00:00:00.000Z', 'count': 20},
                    {'timeBucket': 'invalid-date', 'count': 1},
                ],
            )
        return httpx.Response(404, json={'error': 'not found'})

    client = build_client(handler)
    bounds = await client.get_timeline_bounds('family')
    await client.aclose()

    assert bounds.min_date == date(2019, 6, 1)
    assert bounds.max_date == date(2023, 11, 1)


async def test_get_timeline_bounds_empty_or_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if 'buckets' in request.url.path:
            return httpx.Response(500, json={'error': 'server error'})
        return httpx.Response(404, json={'error': 'not found'})

    client = build_client(handler)
    bounds = await client.get_timeline_bounds('family')
    await client.aclose()

    assert bounds.min_date is None
    assert bounds.max_date is None


async def test_list_countries() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith('/search/explore'):
            return httpx.Response(
                200,
                json=[
                    {
                        'fieldName': 'country',
                        'items': [
                            {'value': 'Brazil'},
                            {'value': 'Germany'},
                            {'value': 'France'},
                            {'value': 'Italy'},
                        ],
                    },
                    {
                        'fieldName': 'city',
                        'items': [{'value': 'Paris'}],
                    },
                ],
            )
        return httpx.Response(404, json={'error': 'not found'})

    client = build_client(handler)

    # All countries, sorted
    countries = await client.list_countries('family')
    assert countries == ['Brazil', 'France', 'Germany', 'Italy']

    # Whitelist filtering
    wl_countries = await client.list_countries('family', whitelist=frozenset({'brazil', 'france'}))
    assert wl_countries == ['Brazil', 'France']

    # Blacklist filtering
    bl_countries = await client.list_countries('family', blacklist=frozenset({'germany'}))
    assert bl_countries == ['Brazil', 'France', 'Italy']

    await client.aclose()


async def test_list_countries_whitelist_fallback_on_empty_explore() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith('/search/explore'):
            return httpx.Response(200, json=[])
        return httpx.Response(404, json={'error': 'not found'})

    client = build_client(handler)
    countries = await client.list_countries('family', whitelist=frozenset({'brazil', 'japan'}))
    await client.aclose()

    assert countries == ['Brazil', 'Japan']


async def test_list_cities() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith('/search/explore'):
            return httpx.Response(
                200,
                json=[
                    {
                        'fieldName': 'city',
                        'items': [
                            {'value': 'Paris', 'country': 'France'},
                            {'value': 'Berlin', 'country': 'Germany'},
                        ],
                    },
                    {
                        'fieldName': 'state',
                        'items': [
                            {'value': 'Bavaria', 'country': 'Germany'},
                        ],
                    },
                ],
            )
        return httpx.Response(404, json={'error': 'not found'})

    client = build_client(handler)

    cities = await client.list_cities('family')
    assert cities == [
        CityInfo(name='Bavaria', country='Germany'),
        CityInfo(name='Berlin', country='Germany'),
        CityInfo(name='Paris', country='France'),
    ]

    # Whitelist
    wl_cities = await client.list_cities('family', whitelist=frozenset({'berlin'}))
    assert wl_cities == [CityInfo(name='Berlin', country='Germany')]

    # Blacklist
    bl_cities = await client.list_cities('family', blacklist=frozenset({'paris'}))
    assert bl_cities == [
        CityInfo(name='Bavaria', country='Germany'),
        CityInfo(name='Berlin', country='Germany'),
    ]

    await client.aclose()


async def test_list_cities_whitelist_fallback_on_empty_explore() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith('/search/explore'):
            return httpx.Response(200, json=[])
        return httpx.Response(404, json={'error': 'not found'})

    client = build_client(handler)
    cities = await client.list_cities('family', whitelist=frozenset({'tokyo', 'london'}))
    await client.aclose()

    assert cities == [
        CityInfo(name='London', country=None),
        CityInfo(name='Tokyo', country=None),
    ]


def test_search_query_geo_and_people_payload() -> None:
    # Single country and single city are passed directly to payload
    q_single = SearchQuery(
        countries=('France',),
        cities=('Paris',),
        person_ids=('p1', 'p2'),
    )
    p_single = q_single.build_payload(size=100)
    assert p_single['country'] == 'France'
    assert p_single['city'] == 'Paris'
    assert p_single['personIds'] == ['p1', 'p2']

    # Multiple countries and multiple cities are omitted from API payload (handled post-fetch)
    q_multi = SearchQuery(
        countries=('France', 'Germany'),
        cities=('Paris', 'Berlin'),
        person_ids=('p1',),
    )
    p_multi = q_multi.build_payload(size=100)
    assert 'country' not in p_multi
    assert 'city' not in p_multi
    assert p_multi['personIds'] == ['p1']


def test_is_eligible_asset_country_filtering() -> None:
    asset_fr = asset(
        exifInfo={'latitude': 48.85, 'longitude': 2.35, 'country': 'France', 'dateTimeOriginal': '2024-01-01T10:00:00Z'}
    )
    asset_de = asset(
        exifInfo={
            'latitude': 52.52,
            'longitude': 13.40,
            'country': 'Germany',
            'dateTimeOriginal': '2024-01-01T10:00:00Z',
        }
    )
    asset_none = asset(exifInfo={'latitude': 10.0, 'longitude': 20.0, 'dateTimeOriginal': '2024-01-01T10:00:00Z'})

    assert ImmichClient.is_eligible_asset(asset_fr, True, True, countries=('France', 'Italy')) is True
    assert ImmichClient.is_eligible_asset(asset_fr, True, True, countries=('france',)) is True
    assert ImmichClient.is_eligible_asset(asset_de, True, True, countries=('France', 'Italy')) is False
    assert ImmichClient.is_eligible_asset(asset_none, True, True, countries=('France',)) is False


def test_is_eligible_asset_city_filtering() -> None:
    asset_paris = asset(
        exifInfo={'latitude': 48.85, 'longitude': 2.35, 'city': 'Paris', 'dateTimeOriginal': '2024-01-01T10:00:00Z'}
    )
    asset_bavaria = asset(
        exifInfo={'latitude': 48.13, 'longitude': 11.58, 'state': 'Bavaria', 'dateTimeOriginal': '2024-01-01T10:00:00Z'}
    )
    asset_none = asset(exifInfo={'latitude': 10.0, 'longitude': 20.0, 'dateTimeOriginal': '2024-01-01T10:00:00Z'})

    assert ImmichClient.is_eligible_asset(asset_paris, True, True, cities=('Paris', 'London')) is True
    assert ImmichClient.is_eligible_asset(asset_paris, True, True, cities=('paris',)) is True
    assert ImmichClient.is_eligible_asset(asset_bavaria, True, True, cities=('bavaria',)) is True
    assert ImmichClient.is_eligible_asset(asset_none, True, True, cities=('Paris',)) is False


def test_is_eligible_asset_people_filtering_or_mode() -> None:
    asset_alice_bob = asset(people=[{'id': 'p-alice', 'name': 'Alice'}, {'id': 'p-bob', 'name': 'Bob'}])
    asset_charlie = asset(faces=[{'id': 'p-charlie', 'name': 'Charlie'}])
    asset_nobody = asset()

    # OR mode: Matches if ANY target person is present
    assert (
        ImmichClient.is_eligible_asset(
            asset_alice_bob, False, False, person_ids=('p-alice', 'p-charlie'), people_mode='OR'
        )
        is True
    )
    assert (
        ImmichClient.is_eligible_asset(
            asset_charlie, False, False, person_ids=('p-alice', 'p-charlie'), people_mode='OR'
        )
        is True
    )
    assert (
        ImmichClient.is_eligible_asset(asset_nobody, False, False, person_ids=('p-alice',), people_mode='OR') is False
    )
    assert ImmichClient.is_eligible_asset(asset_charlie, False, False, person_ids=('p-bob',), people_mode='OR') is False


def test_is_eligible_asset_people_filtering_and_mode() -> None:
    asset_alice_bob = asset(people=[{'id': 'p-alice', 'name': 'Alice'}, {'id': 'p-bob', 'name': 'Bob'}])
    asset_alice_only = asset(people=[{'id': 'p-alice', 'name': 'Alice'}])
    asset_bob_only = asset(people=[{'id': 'p-bob', 'name': 'Bob'}])

    # AND mode: Matches ONLY if ALL target people are present
    assert (
        ImmichClient.is_eligible_asset(
            asset_alice_bob, False, False, person_ids=('p-alice', 'p-bob'), people_mode='AND'
        )
        is True
    )
    assert (
        ImmichClient.is_eligible_asset(
            asset_alice_only, False, False, person_ids=('p-alice', 'p-bob'), people_mode='AND'
        )
        is False
    )
    assert (
        ImmichClient.is_eligible_asset(asset_bob_only, False, False, person_ids=('p-alice', 'p-bob'), people_mode='AND')
        is False
    )
    assert (
        ImmichClient.is_eligible_asset(asset_alice_bob, False, False, person_ids=('p-alice',), people_mode='AND')
        is True
    )

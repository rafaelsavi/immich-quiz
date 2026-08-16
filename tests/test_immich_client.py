from __future__ import annotations

from datetime import date

import httpx
import pytest

from src.immich.client import ImmichClient, ImmichClientError
from src.models import PeopleMode


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
    albums = await client.list_albums('family', include_shared=False)
    await client.aclose()

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
    albums = await client.list_albums('family', include_shared=True)
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
    albums = await client.list_albums('family', include_shared=True)
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
    albums = await client.list_albums('family', include_shared=False)
    await client.aclose()

    assert albums == [
        {'id': 'album-3', 'name': 'My Nested Owner Album'},
        {'id': 'album-1', 'name': 'My Shared Album'},
    ]


async def test_get_asset_count_from_search_statistics_total() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith('/search/statistics') and request.method == 'POST':
            return httpx.Response(200, json={'total': 42, 'images': 30, 'videos': 12})
        return httpx.Response(404, json={'error': 'not found'})

    client = build_client(handler)
    count = await client.get_asset_count('family')
    await client.aclose()
    assert count == 42


async def test_get_asset_count_fallback_images_and_videos() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith('/search/statistics') and request.method == 'POST':
            return httpx.Response(200, json={'images': 50, 'videos': 10})
        return httpx.Response(404, json={'error': 'not found'})

    client = build_client(handler)
    count = await client.get_asset_count('family')
    await client.aclose()
    assert count == 60


async def test_get_asset_count_error_returns_none() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith('/search/statistics'):
            return httpx.Response(500, json={'error': 'internal server error'})
        return httpx.Response(404, json={'error': 'not found'})

    client = build_client(handler)
    count = await client.get_asset_count('family')
    await client.aclose()
    assert count is None


def test_is_eligible_asset_config_whitelists_and_blacklists() -> None:
    asset_brazil = {
        'id': 'a-1',
        'type': 'IMAGE',
        'fileCreatedAt': '2023-01-01T12:00:00Z',
        'exifInfo': {'latitude': -22.9, 'longitude': -43.1, 'country': 'Brazil', 'city': 'Rio de Janeiro'},
        'people': [{'id': 'p-1', 'name': 'Alice'}],
    }
    asset_germany = {
        'id': 'a-2',
        'type': 'IMAGE',
        'fileCreatedAt': '2023-02-01T12:00:00Z',
        'exifInfo': {'latitude': 52.5, 'longitude': 13.4, 'country': 'Germany', 'city': 'Berlin'},
        'people': [{'id': 'p-2', 'name': 'Charlie'}],
    }
    asset_landscape = {
        'id': 'a-3',
        'type': 'IMAGE',
        'fileCreatedAt': '2023-03-01T12:00:00Z',
        'exifInfo': {'latitude': 35.6, 'longitude': 139.6, 'country': 'Japan', 'city': 'Tokyo'},
        'people': [],
    }

    assert ImmichClient.is_eligible_asset(asset_brazil, location_mode=True, date_mode=True) is True
    assert ImmichClient.is_eligible_asset(asset_germany, location_mode=True, date_mode=True) is True
    assert ImmichClient.is_eligible_asset(asset_landscape, location_mode=True, date_mode=True) is True

    # Country blacklist
    assert (
        ImmichClient.is_eligible_asset(
            asset_germany,
            location_mode=True,
            date_mode=True,
            country_blacklist=frozenset({'germany'}),
        )
        is False
    )

    # City blacklist
    assert (
        ImmichClient.is_eligible_asset(
            asset_germany,
            location_mode=True,
            date_mode=True,
            city_blacklist=frozenset({'berlin'}),
        )
        is False
    )

    # People blacklist by name
    assert (
        ImmichClient.is_eligible_asset(
            asset_germany,
            location_mode=True,
            date_mode=True,
            people_blacklist=frozenset({'charlie'}),
        )
        is False
    )

    # People blacklist by ID
    assert (
        ImmichClient.is_eligible_asset(
            asset_germany,
            location_mode=True,
            date_mode=True,
            people_blacklist=frozenset({'p-2'}),
        )
        is False
    )

    # Country whitelist (only Japan)
    assert (
        ImmichClient.is_eligible_asset(
            asset_brazil,
            location_mode=True,
            date_mode=True,
            country_whitelist=frozenset({'japan'}),
        )
        is False
    )
    assert (
        ImmichClient.is_eligible_asset(
            asset_landscape,
            location_mode=True,
            date_mode=True,
            country_whitelist=frozenset({'japan'}),
        )
        is True
    )

    # People whitelist (only Alice)
    assert (
        ImmichClient.is_eligible_asset(
            asset_brazil,
            location_mode=True,
            date_mode=True,
            people_whitelist=frozenset({'alice'}),
        )
        is True
    )
    assert (
        ImmichClient.is_eligible_asset(
            asset_germany,
            location_mode=True,
            date_mode=True,
            people_whitelist=frozenset({'alice'}),
        )
        is False
    )
    assert (
        ImmichClient.is_eligible_asset(
            asset_landscape,
            location_mode=True,
            date_mode=True,
            people_whitelist=frozenset({'alice'}),
        )
        is True
    )


def test_is_eligible_asset_people_mode_enum() -> None:
    asset_p1_p2 = {
        'id': 'a1',
        'type': 'IMAGE',
        'exifInfo': {'latitude': 10.0, 'longitude': 20.0, 'dateTimeOriginal': '2023-05-01T12:00:00Z'},
        'people': [{'id': 'p1', 'name': 'Alice'}, {'id': 'p2', 'name': 'Bob'}],
    }
    asset_p1_only = {
        'id': 'a2',
        'type': 'IMAGE',
        'exifInfo': {'latitude': 10.0, 'longitude': 20.0, 'dateTimeOriginal': '2023-05-01T12:00:00Z'},
        'people': [{'id': 'p1', 'name': 'Alice'}],
    }

    # ANY mode with p1, p2: matches both
    assert (
        ImmichClient.is_eligible_asset(
            asset_p1_p2,
            location_mode=True,
            date_mode=True,
            person_ids=('p1', 'p2'),
            people_mode=PeopleMode.ANY,
        )
        is True
    )
    assert (
        ImmichClient.is_eligible_asset(
            asset_p1_only,
            location_mode=True,
            date_mode=True,
            person_ids=('p1', 'p2'),
            people_mode=PeopleMode.ANY,
        )
        is True
    )

    # ALL mode with p1, p2: matches asset_p1_p2 only
    assert (
        ImmichClient.is_eligible_asset(
            asset_p1_p2,
            location_mode=True,
            date_mode=True,
            person_ids=('p1', 'p2'),
            people_mode=PeopleMode.ALL,
        )
        is True
    )
    assert (
        ImmichClient.is_eligible_asset(
            asset_p1_only,
            location_mode=True,
            date_mode=True,
            person_ids=('p1', 'p2'),
            people_mode=PeopleMode.ALL,
        )
        is False
    )


@pytest.mark.asyncio
async def test_list_tags() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == '/api/tags'
        return httpx.Response(
            200,
            json=[
                {'id': 't1', 'name': 'Trip'},
                {'id': 't2', 'name': 'Architecture'},
                {'id': 't3', 'name': ''},  # Empty name should be filtered
            ],
        )

    client = build_client(handler)
    tags = await client.list_tags('family')
    assert len(tags) == 2
    assert tags[0] == {'id': 't2', 'name': 'Architecture'}
    assert tags[1] == {'id': 't1', 'name': 'Trip'}


def test_extract_answer_includes_state() -> None:
    raw = {
        'id': 'a1',
        'type': 'IMAGE',
        'exifInfo': {
            'latitude': 34.0522,
            'longitude': -118.2437,
            'city': 'Los Angeles',
            'state': 'California',
            'country': 'United States',
            'dateTimeOriginal': '2023-06-01T12:00:00Z',
        },
    }
    ans = ImmichClient.extract_answer(raw)
    assert ans.latitude == 34.0522
    assert ans.longitude == -118.2437
    assert ans.city == 'Los Angeles'
    assert ans.state == 'California'
    assert ans.country == 'United States'

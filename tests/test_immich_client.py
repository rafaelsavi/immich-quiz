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
        {'id': 'album-1', 'name': 'Mine'},
        {'id': 'album-3', 'name': 'Also Mine'},
    ]

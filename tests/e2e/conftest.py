"""Shared fixtures and live server harness for Playwright E2E browser testing."""

from __future__ import annotations

import asyncio
import base64
import socket
import threading
import time
import urllib.request
from collections.abc import AsyncIterator, Iterator
from datetime import date
from typing import Any

import pytest
import uvicorn
from playwright.async_api import Page, async_playwright

from src.config import AppSettings
from src.main import create_app
from src.models import SyncStatus
from src.storage.metadata import MetadataStore
from tests.conftest import CityInfo, FakeImmichClient, PersonInfo, TimelineBounds

# 1x1 Valid PNG image bytes
TINY_PNG_BYTES = base64.b64decode(
    'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=='
)


class E2EFakeImmichClient(FakeImmichClient):
    """Immich client returning valid media image bytes for browser rendering."""

    async def get_asset_bytes(self, library_name: str, asset_id: str) -> tuple[bytes, str]:
        return TINY_PNG_BYTES, 'image/png'


def get_free_port() -> int:
    """Find a random available TCP port on localhost."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('127.0.0.1', 0))
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return int(s.getsockname()[1])


def create_e2e_assets() -> list[dict[str, Any]]:
    """Create rich test assets spanning multiple years, locations, and albums."""
    cities_data = [
        ('Florianopolis', 'Brazil', -27.5969, -48.5495),
        ('Paris', 'France', 48.8566, 2.3522),
        ('Tokyo', 'Japan', 35.6762, 139.6503),
        ('New York', 'United States', 40.7128, -74.0060),
        ('Sydney', 'Australia', -33.8688, 151.2093),
        ('Rome', 'Italy', 41.9028, 12.4964),
        ('London', 'United Kingdom', 51.5074, -0.1278),
        ('Berlin', 'Germany', 52.5200, 13.4050),
        ('Toronto', 'Canada', 43.6532, -79.3832),
        ('Madrid', 'Spain', 40.4168, -3.7038),
    ]

    assets: list[dict[str, Any]] = []
    idx = 1
    for year in (2019, 2020, 2021, 2022):
        for month in (1, 4, 7, 10):
            for city_name, country_name, lat, lon in cities_data[:2]:
                dt_str = f'{year}-{month:02d}-15T12:00:00Z'
                person_id = f'p{(idx % 3) + 1}'
                person_name = ['Alice', 'Bob', 'Charlie'][(idx % 3)]
                album_id = f'album-{(idx % 2) + 1}'
                album_name = 'Holidays' if album_id == 'album-1' else 'World Tour'
                assets.append(
                    {
                        'id': f'asset-{idx}',
                        'type': 'IMAGE',
                        'exifInfo': {
                            'latitude': lat + ((idx % 5) * 0.01),
                            'longitude': lon + ((idx % 5) * 0.01),
                            'city': city_name,
                            'country': country_name,
                            'dateTimeOriginal': dt_str,
                        },
                        'fileCreatedAt': dt_str,
                        'people': [{'id': person_id, 'name': person_name}],
                        'albums': [{'id': album_id, 'name': album_name}],
                    }
                )
                idx += 1

    return assets


def seed_e2e_metadata(store: MetadataStore, library_name: str, assets: list[dict[str, Any]]) -> None:
    """Seed metadata database with rich test assets, people, and albums."""
    people_data = [
        {'id': 'p1', 'name': 'Alice'},
        {'id': 'p2', 'name': 'Bob'},
        {'id': 'p3', 'name': 'Charlie'},
    ]
    store.upsert_people(library_name, people_data)

    albums_data = [
        {'id': 'album-1', 'name': 'Holidays', 'isShared': 0},
        {'id': 'album-2', 'name': 'World Tour', 'isShared': 0},
    ]
    store.upsert_albums(library_name, albums_data)

    asset_records: list[dict[str, Any]] = []
    asset_people: list[tuple[str, str]] = []
    asset_albums: list[tuple[str, str]] = []
    asset_tags: list[tuple[str, str]] = []

    for a in assets:
        aid = a['id']
        exif = a['exifInfo']
        asset_records.append(
            {
                'id': aid,
                'is_shared': 0,
                'is_partner': 0,
                'file_type': a.get('type', 'IMAGE'),
                'latitude': float(exif['latitude']),
                'longitude': float(exif['longitude']),
                'country': exif.get('country'),
                'city': exif.get('city'),
                'capture_datetime': exif.get('dateTimeOriginal'),
            }
        )
        for p in a.get('people', []):
            asset_people.append((aid, p['id']))
        for alb in a.get('albums', []):
            asset_albums.append((aid, alb['id']))

    store.upsert_assets_batch(library_name, asset_records, asset_people, asset_albums, asset_tags)
    store.set_sync_state(
        library_name,
        status=SyncStatus.idle,
        total_assets=len(asset_records),
        synced_assets=len(asset_records),
    )


@pytest.fixture(scope='package')
def e2e_server(tmp_path_factory: pytest.TempPathFactory) -> Iterator[str]:
    """Launch a live FastAPI test server on an ephemeral port for Playwright tests."""
    data_path = tmp_path_factory.mktemp('e2e_data')
    port = get_free_port()

    assets = create_e2e_assets()
    immich_client = E2EFakeImmichClient(
        assets=assets,
        people=[
            PersonInfo(id='p1', name='Alice'),
            PersonInfo(id='p2', name='Bob'),
            PersonInfo(id='p3', name='Charlie'),
        ],
        timeline_bounds=TimelineBounds(min_date=date(2019, 1, 1), max_date=date(2024, 12, 31)),
        countries=['Brazil', 'France', 'Japan', 'United States', 'Australia', 'Italy'],
        cities=[
            CityInfo(name='Florianopolis', country='Brazil'),
            CityInfo(name='Paris', country='France'),
            CityInfo(name='Tokyo', country='Japan'),
            CityInfo(name='New York', country='United States'),
            CityInfo(name='Sydney', country='Australia'),
            CityInfo(name='Rome', country='Italy'),
        ],
    )

    settings = AppSettings(
        immich_server_url='https://placeholder.example.com/api',
        immich_libraries={'family': 'token'},
        app_title='Immich Quiz E2E',
        app_tagline='E2E Automated Browser Tests',
        app_host='127.0.0.1',
        app_port=port,
        language='EN',
        data_path=data_path,
        auto_sync_on_startup=False,
    )

    app = create_app(settings=settings)
    app.state.immich_client = immich_client
    if hasattr(app.state, 'metadata_store'):
        seed_e2e_metadata(app.state.metadata_store, 'family', assets)

    config = uvicorn.Config(
        app=app,
        host='127.0.0.1',
        port=port,
        log_level='warning',
    )
    server = uvicorn.Server(config=config)

    def run_server() -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(server.serve())
        finally:
            loop.close()

    thread = threading.Thread(target=run_server, daemon=True)
    thread.start()

    base_url = f'http://127.0.0.1:{port}'

    # Wait for server to become healthy and responsive
    deadline = time.time() + 10.0
    started = False
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f'{base_url}/') as response:
                if response.status == 200:
                    started = True
                    break
        except Exception:
            time.sleep(0.05)

    if not started:
        raise RuntimeError(f'FastAPI E2E test server failed to start at {base_url}')

    yield base_url

    # Gracefully shut down server
    server.should_exit = True
    thread.join(timeout=3.0)


@pytest.fixture
async def page(e2e_server: str) -> AsyncIterator[Page]:
    """Provide a configured Playwright Page fixture with base URL and desktop viewport."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={'width': 1280, 'height': 800},
            base_url=e2e_server,
            locale='en-US',
        )
        page_obj = await context.new_page()

        # Track any uncaught client console errors
        errors: list[str] = []
        page_obj.on('pageerror', lambda err: errors.append(str(err)))

        yield page_obj

        await context.close()
        await browser.close()
        if errors:
            pytest.fail(f'Client page errors detected: {errors}')


async def start_date_only_match(page: Page, rounds: int = 5, round_length: str | None = None) -> None:
    """Configure and start a date-only pinpoint match."""
    await page.locator('#mode-pinpoint-btn').click()
    loc_card = page.locator('#card-goal-location')
    date_card = page.locator('#card-goal-date')
    if 'active' in (await loc_card.get_attribute('class') or ''):
        await loc_card.click()
    if 'active' not in (await date_card.get_attribute('class') or ''):
        await date_card.click()
    if round_length is not None:
        await page.locator('#round-length').select_option(round_length)
    await page.locator('#round-count').select_option(str(rounds))
    await page.locator('#start-match-btn').click()


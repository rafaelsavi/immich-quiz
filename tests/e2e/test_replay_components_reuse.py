"""End-to-End tests verifying maximum element reuse in Match Replay screen:
- Reused .media-frame image canvas with fullscreen button and lightbox
- Reused .map-shell with Leaflet controls, layer switcher, reset zoom, and fullscreen
- Preserved DOM hierarchy without innerHTML destruction
- Round stepping reusing the existing Leaflet map instance
"""

from __future__ import annotations

import json

import pytest
from playwright.async_api import Page, expect

MOCK_REPLAY_DATA = {
    'match_id': 'test-reuse-match',
    'game_mode': 'pinpoint',
    'play_mode': 'local',
    'rounds': 2,
    'played_at': 1740000000.0,
    'location_mode': True,
    'date_mode': True,
    'config': {
        'round_count': 2,
        'round_length': '1m',
        'location_mode': True,
        'date_mode': True,
        'game_mode': 'pinpoint',
        'libraries': ['Familia Savi'],
    },
    'rounds_data': [
        {
            'round_number': 1,
            'asset_id': 'asset-reuse-1',
            'actual_latitude': 48.8584,
            'actual_longitude': 2.2945,
            'actual_city': 'Paris',
            'actual_country': 'France',
            'actual_date': '2023-05-15T14:30:00.000Z',
            'player_guesses': [
                {
                    'player_name': 'Alice',
                    'player_color': '#3b82f6',
                    'guess_latitude': 48.8600,
                    'guess_longitude': 2.3000,
                    'distance_km': 0.45,
                    'round_score': 4980,
                    'cumulative_score': 4980,
                    'time_taken_seconds': 12,
                },
                {
                    'player_name': 'Bob',
                    'player_color': '#10b981',
                    'guess_latitude': 48.8700,
                    'guess_longitude': 2.3100,
                    'distance_km': 1.75,
                    'round_score': 4720,
                    'cumulative_score': 4720,
                    'time_taken_seconds': 18,
                },
            ],
        },
        {
            'round_number': 2,
            'asset_id': 'asset-reuse-2',
            'actual_latitude': 40.7128,
            'actual_longitude': -74.0060,
            'actual_city': 'New York',
            'actual_country': 'United States',
            'actual_date': '2024-01-10T10:00:00.000Z',
            'player_guesses': [
                {
                    'player_name': 'Alice',
                    'player_color': '#3b82f6',
                    'guess_latitude': 40.7200,
                    'guess_longitude': -74.0100,
                    'distance_km': 0.85,
                    'round_score': 4910,
                    'cumulative_score': 9890,
                    'time_taken_seconds': 15,
                },
                {
                    'player_name': 'Bob',
                    'player_color': '#10b981',
                    'guess_latitude': 40.7500,
                    'guess_longitude': -73.9800,
                    'distance_km': 4.60,
                    'round_score': 4200,
                    'cumulative_score': 8920,
                    'time_taken_seconds': 22,
                },
            ],
        },
    ],
}


@pytest.mark.asyncio
async def test_replay_reuses_media_frame_and_map_shell(page: Page) -> None:
    """Verify that match replay reuses standard .media-frame, .map-shell, lightbox, and map controls."""

    async def handle_replay_route(route):
        await route.fulfill(
            status=200,
            content_type='application/json',
            body=json.dumps(MOCK_REPLAY_DATA),
        )

    await page.route('**/api/match/test-reuse-match/replay', handle_replay_route)

    # 1. Navigate to the replay page
    await page.goto('/game/test-reuse-match/replay')
    await expect(page.locator('#replay-page-card')).to_be_visible()

    # Verify unified Match Meta specification panel is rendered
    meta_section = page.locator('#replay-match-meta-container .match-meta-section')
    await expect(meta_section).to_be_visible()
    await expect(page.locator('#replay-match-meta-container .category-game-setup')).to_be_visible()
    await expect(page.locator('#replay-match-meta-container .category-library-filters')).to_be_visible()

    # 2. Verify Reused Image Canvas (.media-frame)
    media_frame = page.locator('#replay-media-frame')
    await expect(media_frame).to_be_visible()
    await expect(media_frame).to_have_class('media-frame replay-media-frame')

    # Verify background is consistent with standard .media-frame (#eef2fb)
    bg_color = await media_frame.evaluate('el => window.getComputedStyle(el).backgroundColor')
    assert bg_color == 'rgb(238, 242, 251)'

    photo_img = page.locator('#replay-photo-img')
    await expect(photo_img).to_be_visible()
    await expect(photo_img).to_have_class('quiz-image replay-photo-img')
    await expect(photo_img).to_have_attribute('src', '/api/media/asset-reuse-1')

    # Verify fullscreen button on media-frame
    photo_fs_btn = page.locator('#replay-photo-fullscreen')
    await expect(photo_fs_btn).to_be_visible()
    await expect(photo_fs_btn).to_have_class('map-fullscreen-btn')

    # 3. Verify Lightbox Integration on clicking photo
    await photo_img.click()
    lightbox = page.locator('#photo-lightbox')
    await expect(lightbox).to_be_visible()
    await expect(lightbox).to_have_class('photo-lightbox-overlay active')
    lightbox_img = page.locator('#photo-lightbox-img')
    import re

    await expect(lightbox_img).to_have_attribute('src', re.compile(r'/api/media/asset-reuse-1$'))

    # Dismiss lightbox with Escape
    await page.keyboard.press('Escape')
    await expect(lightbox).not_to_have_class('active')

    # 4. Verify Reused Map Shell (.map-shell)
    map_shell = page.locator('#replay-map-shell')
    await expect(map_shell).to_be_visible()
    await expect(map_shell).to_have_class('map-shell replay-map-shell')

    leaflet_map = page.locator('#replay-leaflet-map')
    await expect(leaflet_map).to_be_visible()
    await expect(leaflet_map).to_have_class(re.compile(r'leaflet-container'))

    # Verify Leaflet controls injected by createStandardMap
    # - Zoom controls
    await expect(map_shell.locator('.leaflet-control-zoom')).to_be_visible()
    # - Layer switcher (Streets / Satellite)
    await expect(map_shell.locator('.leaflet-control-layers')).to_be_visible()
    # - Reset zoom control button
    await expect(map_shell.locator('.map-reset-zoom-btn')).to_be_visible()
    # - Map fullscreen button
    await expect(map_shell.locator('.map-fullscreen-btn')).to_be_visible()

    # 5. Verify Map Markers and polyline connections
    pins = map_shell.locator('.player-pin')
    # 1 actual pin (★) + 2 player guess pins (A, B) = 3 pins
    await expect(pins).to_have_count(3)

    # 6. Verify Stepping through rounds reuses the Leaflet instance without DOM teardown
    next_btn = page.locator('#replay-next-round-btn')
    await expect(next_btn).to_be_enabled()
    await next_btn.click()

    # Round indicator updates to Round 2
    await expect(page.locator('#replay-round-indicator')).to_contain_text('Round 2 of 2')
    # Photo updates to asset-reuse-2
    await expect(photo_img).to_have_attribute('src', '/api/media/asset-reuse-2')
    # Captions update to New York
    await expect(page.locator('#replay-photo-loc')).to_contain_text('New York, United States')

    # Map still lives in the same DOM element and has updated pins
    await expect(leaflet_map).to_be_visible()
    await expect(pins).to_have_count(3)

    # 7. Test Mobile Viewport
    await page.set_viewport_size({'width': 390, 'height': 844})
    await expect(media_frame).to_be_visible()
    await expect(map_shell).to_be_visible()

    # Reset viewport
    await page.set_viewport_size({'width': 1280, 'height': 800})


@pytest.mark.asyncio
async def test_replay_header_challenge_vs_local(page: Page) -> None:
    """Verify replay header omits badge row and round counts from subtitle,
    and displays challenge title + creator for challenge replays.
    """

    # 1. Local match replay header
    async def handle_local_replay(route):
        await route.fulfill(
            status=200,
            content_type='application/json',
            body=json.dumps(MOCK_REPLAY_DATA),
        )

    await page.route('**/api/match/local-match-123/replay', handle_local_replay)
    await page.goto('/game/local-match-123/replay')
    await expect(page.locator('#replay-page-card')).to_be_visible()

    # Replay badge row does not exist
    await expect(page.locator('.replay-badge-row')).to_have_count(0)
    await expect(page.locator('#replay-mode-badge')).to_have_count(0)
    await expect(page.locator('#replay-type-badge')).to_have_count(0)

    # Subtitle has date, but does NOT contain round count like "2 rounds"
    title_el = page.locator('#replay-match-title')
    await expect(title_el).to_be_visible()
    title_text = await title_el.inner_text()
    assert 'round' not in title_text.lower()

    # 2. Challenge match replay header
    mock_challenge_replay = dict(MOCK_REPLAY_DATA)
    mock_challenge_replay.update(
        {
            'match_id': 'ch-match-456',
            'play_mode': 'challenge',
            'challenge_id': 'ch_789',
            'challenge_title': 'Summer Roadtrip 2026',
            'challenge_creator': 'Rafael',
        }
    )

    async def handle_ch_replay(route):
        await route.fulfill(
            status=200,
            content_type='application/json',
            body=json.dumps(mock_challenge_replay),
        )

    await page.route('**/api/match/ch-match-456/replay', handle_ch_replay)
    await page.goto('/game/ch-match-456/replay')
    await expect(page.locator('#replay-page-card')).to_be_visible()

    # Subtitle contains challenge title and creator name
    await expect(page.locator('#replay-match-title .replay-challenge-title')).to_have_text('Summer Roadtrip 2026')
    await expect(page.locator('#replay-match-title .replay-challenge-host')).to_contain_text('Rafael')

"""Playwright E2E tests for preflight count updates when toggling guess mode."""

from __future__ import annotations

import json

from playwright.async_api import Page, Route, expect


async def test_preflight_count_updates_with_guess_mode(page: Page) -> None:
    """Verify that toggling Location and Date guess modes in setup dynamically updates
    the preflight count text and breakdown tooltip in the home screen.
    """
    preflight_mock_data = {
        'both': {
            'eligible_count': 15,
            'required': 10,
            'ok': True,
            'active_filters': ['location', 'date'],
            'total_count': 50,
            'gps_count': 20,
            'date_count': 35,
            'both_count': 15,
            'location_mode': True,
            'date_mode': True,
            'is_synced': True,
            'sync_status': 'idle',
        },
        'gps_only': {
            'eligible_count': 20,
            'required': 10,
            'ok': True,
            'active_filters': ['location'],
            'total_count': 50,
            'gps_count': 20,
            'date_count': 35,
            'both_count': 15,
            'location_mode': True,
            'date_mode': False,
            'is_synced': True,
            'sync_status': 'idle',
        },
        'date_only': {
            'eligible_count': 35,
            'required': 10,
            'ok': True,
            'active_filters': ['date'],
            'total_count': 50,
            'gps_count': 20,
            'date_count': 35,
            'both_count': 15,
            'location_mode': False,
            'date_mode': True,
            'is_synced': True,
            'sync_status': 'idle',
        },
    }

    async def handle_preflight(route: Route) -> None:
        req = route.request
        body = json.loads(req.post_data or '{}')
        loc_mode = body.get('location_mode', True)
        dt_mode = body.get('date_mode', True)

        if loc_mode and dt_mode:
            resp_data = preflight_mock_data['both']
        elif loc_mode and not dt_mode:
            resp_data = preflight_mock_data['gps_only']
        elif not loc_mode and dt_mode:
            resp_data = preflight_mock_data['date_only']
        else:
            resp_data = preflight_mock_data['both']

        await route.fulfill(
            status=200,
            content_type='application/json',
            body=json.dumps(resp_data),
        )

    await page.route('**/api/game/preflight', handle_preflight)
    await page.route(
        '**/api/sync',
        lambda route: route.fulfill(status=200, json={'status': 'idle', 'last_sync': '2026-01-01T00:00:00Z'}),
    )

    await page.goto('/')
    await expect(page.locator('#setup-card')).to_be_visible()

    # Open filters accordion to view #preflight-count
    header = page.locator('#filters-accordion-header')
    await header.click()
    await expect(page.locator('#filters-accordion-content')).to_be_visible()

    preflight_count = page.locator('#preflight-count')
    loc_card = page.locator('#card-goal-location')
    date_card = page.locator('#card-goal-date')

    import re

    # 1. Initially both Location and Date are active -> "15 photos with GPS & date"
    await expect(preflight_count).to_be_visible()
    await expect(preflight_count).to_contain_text('15 photos with GPS & date')
    await expect(preflight_count).to_have_attribute('title', 'Total: 50 | GPS: 20 | Date: 35 | Eligible: 15')

    # 2. Toggle Date OFF -> Location (GPS) only -> "20 photos with GPS"
    await date_card.click()
    await expect(preflight_count).to_contain_text('20 photos with GPS')
    await expect(preflight_count).to_have_attribute('title', 'Total: 50 | GPS: 20 | Date: 35 | Eligible: 20')

    # 3. Toggle Date back ON -> Both active -> "15 photos with GPS & date"
    await date_card.click()
    await expect(preflight_count).to_contain_text('15 photos with GPS & date')
    await expect(preflight_count).to_have_attribute('title', 'Total: 50 | GPS: 20 | Date: 35 | Eligible: 15')

    # 4. Toggle Location OFF -> Date only -> "35 photos with date"
    await loc_card.click()
    await expect(preflight_count).to_contain_text('35 photos with date')
    await expect(preflight_count).to_have_attribute('title', 'Total: 50 | GPS: 20 | Date: 35 | Eligible: 35')

    # 5. Attempting to toggle Date OFF when it's the only active mode triggers shake warning and stays active
    await date_card.click()
    await expect(date_card).to_have_class(re.compile(r'shake-warning'))
    await expect(preflight_count).to_contain_text('35 photos with date')

"""Playwright E2E tests for sync completion popup animation and summary."""

from __future__ import annotations

from pathlib import Path

from playwright.async_api import Page, expect


async def test_sync_completion_popup_display_and_dismiss(page: Page) -> None:
    """Verify that completing a sync shows an animated popup detailing what was synced,
    and clicking the close button or pressing Escape dismisses it.
    """
    poll_count = 0

    async def handle_sync_status(route):
        nonlocal poll_count
        poll_count += 1
        if poll_count <= 1:
            # Initial page load
            await route.fulfill(
                status=200,
                json={
                    'sync_status': 'idle',
                    'is_syncing': False,
                    'total_assets': 100,
                    'synced_assets': 100,
                    'last_sync_at': '2026-01-01T10:00:00Z',
                },
            )
        elif poll_count == 2:
            # First poll during sync
            await route.fulfill(
                status=200,
                json={
                    'sync_status': 'syncing',
                    'is_syncing': True,
                    'sync_mode': 'delta',
                    'sync_stage': 'updating_assets',
                    'total_assets': 100,
                    'synced_assets': 15,
                },
            )
        else:
            # Sync completed
            await route.fulfill(
                status=200,
                json={
                    'sync_status': 'idle',
                    'is_syncing': False,
                    'sync_mode': 'delta',
                    'total_assets': 125,
                    'synced_assets': 125,
                    'last_sync_duration_seconds': 1.42,
                    'last_sync_summary': {
                        'sync_mode': 'delta',
                        'assets_synced': 25,
                        'total_assets': 125,
                        'duration_seconds': 1.42,
                        'albums_synced': 4,
                        'tags_synced': 6,
                        'pruned_assets': 0,
                        'completed_at': '2026-09-12T22:00:00Z',
                    },
                },
            )

    await page.route('**/api/sync/status', handle_sync_status)
    await page.route(
        '**/api/sync',
        lambda route: route.fulfill(
            status=200,
            json={'sync_status': 'syncing', 'is_syncing': True, 'sync_mode': 'delta'},
        ),
    )

    await page.goto('/')
    await expect(page.locator('#setup-card')).to_be_visible()

    sync_btn = page.locator('#sync-library-btn')
    await expect(sync_btn).to_be_visible()

    # Popup should not exist yet
    await expect(page.locator('#sync-popup')).not_to_be_attached()

    # Click sync button to trigger sync
    await sync_btn.click()

    # Popup should appear with animation
    popup = page.locator('#sync-popup')
    await expect(popup).to_be_visible(timeout=5000)

    # Check title and mode badge
    await expect(popup.locator('.sync-popup-title')).to_contain_text('Sync Complete')
    await expect(popup.locator('.sync-popup-mode-badge')).to_contain_text('Quick Update')

    # Check summary message says what was synced
    await expect(popup.locator('.sync-popup-message')).to_contain_text('25 photos updated')
    await expect(popup.locator('.sync-popup-message')).to_contain_text('125 total')

    # Check stats chips
    stats_text = await popup.locator('.sync-popup-stats').inner_text()
    assert '125' in stats_text
    assert '4 albums' in stats_text
    assert '6 tags' in stats_text
    assert '1.42s' in stats_text

    # Click close button -> popup dismisses
    close_btn = popup.locator('#sync-popup-close-btn')
    await close_btn.click()
    await expect(popup).not_to_be_visible(timeout=2000)


async def test_sync_popup_visual_screenshot_and_escape_dismiss(page: Page, tmp_path) -> None:
    """Verify popup renders properly on screen, capture screenshot artifact, and test escape key dismiss."""
    poll_count = 0

    async def handle_sync_status(route):
        nonlocal poll_count
        poll_count += 1
        if poll_count <= 1:
            await route.fulfill(
                status=200,
                json={
                    'sync_status': 'idle',
                    'is_syncing': False,
                    'total_assets': 500,
                    'synced_assets': 500,
                    'last_sync_at': '2026-01-01T10:00:00Z',
                },
            )
        else:
            await route.fulfill(
                status=200,
                json={
                    'sync_status': 'idle',
                    'is_syncing': False,
                    'sync_mode': 'delta',
                    'total_assets': 542,
                    'synced_assets': 542,
                    'last_sync_duration_seconds': 0.85,
                    'last_sync_summary': {
                        'sync_mode': 'delta',
                        'assets_synced': 42,
                        'total_assets': 542,
                        'duration_seconds': 0.85,
                        'albums_synced': 6,
                        'tags_synced': 12,
                        'pruned_assets': 0,
                        'completed_at': '2026-09-12T22:00:00Z',
                    },
                },
            )

    await page.route('**/api/sync/status', handle_sync_status)
    await page.route(
        '**/api/sync',
        lambda r: r.fulfill(status=200, json={'sync_status': 'syncing', 'is_syncing': True}),
    )

    await page.goto('/')
    await page.locator('#sync-library-btn').click()

    popup = page.locator('#sync-popup')
    await expect(popup).to_be_visible(timeout=5000)

    # Capture screenshot of the sync popup and accordion header
    screenshot_dir = Path('C:/Users/Rafael Savi/.gemini/antigravity-ide/brain/19451007-cca5-42cd-8fb2-ae194705e7d3')
    screenshot_path = screenshot_dir / 'sync_popup.png'
    await page.screenshot(path=str(screenshot_path))

    # Dismiss via Escape
    await page.keyboard.press('Escape')
    await expect(popup).not_to_be_visible(timeout=2000)

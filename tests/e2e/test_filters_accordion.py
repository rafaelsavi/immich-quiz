"""Playwright E2E tests for filters accordion header clickability."""

from __future__ import annotations

from playwright.async_api import Page, expect


async def test_filters_accordion_header_full_clickability(page: Page) -> None:
    """Verify that clicking anywhere on the filters-accordion-header opens and closes the accordion,
    and clicking sync button does not toggle the accordion state.
    """
    await page.route(
        '**/api/sync',
        lambda route: route.fulfill(status=200, json={'status': 'idle', 'last_sync': '2026-01-01T00:00:00Z'}),
    )
    await page.goto('/')
    await expect(page.locator('#setup-card')).to_be_visible()

    content = page.locator('#filters-accordion-content')
    header = page.locator('#filters-accordion-header')
    sync_btn = page.locator('#sync-library-btn')
    arrow = page.locator('#accordion-arrow-icon')
    toggle_btn = page.locator('#filters-toggle-btn')

    # 1. Initially collapsed
    await expect(content).not_to_be_visible()

    # 2. Click header while collapsed -> expands
    await header.click()
    await expect(content).to_be_visible()

    # 3. Click header while expanded -> collapses
    await header.click()
    await expect(content).not_to_be_visible()

    # 4. Click arrow icon while collapsed -> expands
    await arrow.click()
    await expect(content).to_be_visible()

    # 5. Click toggle button -> collapses
    await toggle_btn.click()
    await expect(content).not_to_be_visible()

    # 6. Click sync button while collapsed -> remains collapsed
    await sync_btn.click()
    await expect(content).not_to_be_visible()

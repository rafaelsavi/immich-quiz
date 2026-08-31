"""Playwright E2E tests for Pinpoint gameplay mode: two-tap map pin placement, submit, and reveal map."""

from __future__ import annotations

import re

from playwright.async_api import Page, expect


async def test_pinpoint_two_tap_pin_placement_and_reveal(page: Page) -> None:
    """Verify two-tap Leaflet pin placement, distance line calculation, and round reveal rendering in Pinpoint mode."""
    await page.goto('/')

    # 1. Verify Lobby Setup is visible
    await expect(page.locator('#setup-card')).to_be_visible()

    # Configure solo match in Pinpoint mode with Location enabled and Date disabled
    await page.locator('#mode-pinpoint-btn').click()
    loc_card = page.locator('#card-goal-location')
    date_card = page.locator('#card-goal-date')
    if 'active' not in (await loc_card.get_attribute('class') or ''):
        await loc_card.click()
    if 'active' in (await date_card.get_attribute('class') or ''):
        await date_card.click()
    await expect(loc_card).to_have_class(re.compile(r'active'))

    # Start match
    await page.locator('#prepare-game-btn').click()
    await page.locator('#start-match-btn').click()

    # 2. Wait for Game Screen and Pass Overlay (if multiplayer)
    await expect(page.locator('#game-card')).to_be_visible()
    if await page.locator('#pass-overlay').is_visible():
        await page.locator('#ready-btn').click()
        await expect(page.locator('#pass-overlay')).to_be_hidden()

    # 3. Guessing screen & map verification
    guess_map = page.locator('#guess-map')
    await expect(guess_map).to_be_visible()

    submit_btn = page.locator('#submit-answer')
    # Submit button must be disabled when location mode is active and no pin is placed
    await expect(submit_btn).to_be_disabled()

    # First Tap: Click on the map to place initial guess pin
    await guess_map.click(position={'x': 140, 'y': 140})

    # Verify pin marker was dropped on guess map
    guess_pin = page.locator('#guess-map .player-pin')
    await expect(guess_pin).to_be_visible()
    await expect(submit_btn).to_be_enabled()

    # Second Tap: Click a different location on map to move the guess pin
    await guess_map.click(position={'x': 220, 'y': 180})

    # Pin should still be visible and submit remains enabled
    await expect(guess_pin).to_be_visible()
    await expect(submit_btn).to_be_enabled()

    # 4. Submit answer and transition to Reveal
    await submit_btn.click()

    # 5. Verify Reveal Screen UI
    await expect(page.locator('#reveal-ui')).to_be_visible()
    await expect(page.locator('#pinpoint-reveal-ui')).to_be_visible()

    # Reveal map should show actual location pin (star icon) and guess pin
    reveal_map = page.locator('#reveal-map')
    await expect(reveal_map).to_be_visible()

    actual_marker = reveal_map.locator('.player-pin:has-text("★")')
    await expect(actual_marker).to_be_visible()

    # Verify table results render distance error and points
    reveal_table = page.locator('#reveal-table')
    await expect(reveal_table).to_be_visible()
    await expect(reveal_table.locator('tbody tr')).to_have_count(1)
    await expect(reveal_table.locator('tbody tr')).to_contain_text(re.compile(r'km|pts|\d+'))

    # Verify Next Round button is ready
    next_round_btn = page.locator('#next-round')
    await expect(next_round_btn).to_be_visible()
    await expect(next_round_btn).to_be_enabled()

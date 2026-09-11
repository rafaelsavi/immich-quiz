"""Playwright E2E tests for Album Shuffle gameplay: photo card reordering and multi-pin map assignment."""

from __future__ import annotations

import re

from playwright.async_api import Page, expect


async def test_album_shuffle_card_reordering_and_multi_pin_placement(page: Page) -> None:
    """Verify Album Shuffle interactive photo reordering, map pin selection, and reveal scoring."""
    await page.goto('/')

    # Select Album Shuffle mode
    await page.locator('#mode-album-shuffle-btn').click()
    await expect(page.locator('#mode-album-shuffle-btn')).to_have_class(re.compile(r'active'))

    # Start match
    await page.locator('#prepare-game-btn').click()
    await page.locator('#start-match-btn').click()

    # Pass overlay (if multiplayer)
    if await page.locator('#pass-overlay').is_visible():
        await page.locator('#ready-btn').click()
        await expect(page.locator('#pass-overlay')).to_be_hidden()

    # Verify Album Shuffle Board & Cards
    shuffle_ui = page.locator('#album-shuffle-ui')
    await expect(shuffle_ui).to_be_visible()

    cards = page.locator('#shuffle-cards-list .shuffle-card-row')
    await expect(cards).to_have_count(3)

    # 1. Card Reordering Test
    first_card = cards.nth(0)
    second_card = cards.nth(1)

    first_card_img_src = await first_card.locator('img').get_attribute('src')
    second_card_img_src = await second_card.locator('img').get_attribute('src')

    # Click down arrow on first card
    down_btn = first_card.locator('button.shuffle-rank-btn:has-text("▼")')
    await expect(down_btn).to_be_enabled()
    await down_btn.click()

    # Verify that cards have swapped places in the DOM
    reordered_cards = page.locator('#shuffle-cards-list .shuffle-card-row')
    await expect(reordered_cards.nth(0).locator('img')).to_have_attribute('src', second_card_img_src or '')
    await expect(reordered_cards.nth(1).locator('img')).to_have_attribute('src', first_card_img_src or '')

    # 2. Multi-Pin Placement Test (Direct Card Chips & Map Pin Heads)
    submit_btn = page.locator('#submit-answer')
    await expect(submit_btn).to_be_disabled()

    # Find the map pin markers on the shuffle map
    map_pins = page.locator('#shuffle-map-shell .shuffle-pin-icon, #shuffle-map-shell .leaflet-marker-icon')
    await expect(map_pins).to_have_count(3)

    # Assign Pin A to Card 0 via direct card chip (Idea 1)
    chip_a_card0 = reordered_cards.nth(0).locator('.shuffle-pin-chip[data-pin="A"]')
    await expect(chip_a_card0).to_be_visible()
    await chip_a_card0.click()
    await expect(reordered_cards.nth(0).locator('.shuffle-assigned-pin-badge.assigned')).to_be_visible()
    await expect(reordered_cards.nth(0).locator('.shuffle-pin-chip.active')).to_have_text('A')

    # Verify photo thumbnail on assigned map marker (Idea 3)
    await expect(map_pins.nth(0).locator('.shuffle-pin-photo-img')).to_be_visible()
    await expect(map_pins.nth(0).locator('.shuffle-pin-letter-badge')).to_have_text('A')

    # Assign Pin B to Card 1 via direct card chip
    chip_b_card1 = reordered_cards.nth(1).locator('.shuffle-pin-chip[data-pin="B"]')
    await chip_b_card1.click()
    await expect(reordered_cards.nth(1).locator('.shuffle-assigned-pin-badge.assigned')).to_be_visible()
    await expect(reordered_cards.nth(1).locator('.shuffle-pin-chip.active')).to_have_text('B')
    await expect(map_pins.nth(1).locator('.shuffle-pin-photo-img')).to_be_visible()

    # Assign Pin C to Card 2 via direct card chip
    chip_c_card2 = reordered_cards.nth(2).locator('.shuffle-pin-chip[data-pin="C"]')
    await chip_c_card2.click()
    await expect(reordered_cards.nth(2).locator('.shuffle-assigned-pin-badge.assigned')).to_be_visible()
    await expect(reordered_cards.nth(2).locator('.shuffle-pin-chip.active')).to_have_text('C')
    await expect(map_pins.nth(2).locator('.shuffle-pin-photo-img')).to_be_visible()

    # All pins assigned: Submit button must become enabled
    await expect(submit_btn).to_be_enabled()

    # 3. Submit and Verify Reveal
    await submit_btn.click()

    await expect(page.locator('#reveal-ui')).to_be_visible()
    await expect(page.locator('#album-shuffle-reveal-ui')).to_be_visible()

    # Verify reveal score table rendered
    reveal_table = page.locator('#shuffle-reveal-table')
    await expect(reveal_table).to_be_visible()
    await expect(reveal_table.locator('tbody tr')).to_have_count(1)

    # Verify photo breakdown cards rendered and positioned side-by-side on wide viewport
    breakdown_cards = page.locator('#shuffle-breakdown-grid .shuffle-photo-card')
    await expect(breakdown_cards).to_have_count(3)
    card0_offset_left = await breakdown_cards.nth(0).evaluate('el => el.offsetLeft')
    card1_offset_left = await breakdown_cards.nth(1).evaluate('el => el.offsetLeft')
    card0_offset_top = await breakdown_cards.nth(0).evaluate('el => el.offsetTop')
    card1_offset_top = await breakdown_cards.nth(1).evaluate('el => el.offsetTop')
    assert card0_offset_left < card1_offset_left, 'Cards should be laid out horizontally side-by-side'
    assert card0_offset_top == card1_offset_top, 'Cards should be on the same row on desktop viewports'

    # Verify round meta in reveal shows round number and reveal badge, but no player chip in local match
    await expect(page.locator('#round-meta .round-meta-number')).to_be_visible()
    await expect(page.locator('#round-meta .round-meta-reveal-tag')).to_be_visible()
    await expect(page.locator('#round-meta .round-meta-player')).to_have_count(0)

    # Verify next round button is present
    next_btn = page.locator('#next-round')
    await expect(next_btn).to_be_visible()

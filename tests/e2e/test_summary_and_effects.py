"""Playwright E2E tests for score rollup animations and post-game summary awards rendering."""

from __future__ import annotations

import re

from playwright.async_api import Page, expect

from tests.e2e.conftest import start_date_only_match


async def test_score_rollup_animation_and_post_game_summary(page: Page) -> None:
    """Verify score rollup spans animate on reveal, and post-game summary awards
    and memory cards render on match completion.
    """
    await page.goto('/')
    await start_date_only_match(page, rounds=5)
    await expect(page.locator('#game-card')).to_be_visible()

    # Play through 5 rounds quickly
    for _round_idx in range(1, 6):
        # 1. Pass overlay (if multiplayer)
        if await page.locator('#pass-overlay').is_visible():
            await page.locator('#ready-btn').click()
            await expect(page.locator('#pass-overlay')).to_be_hidden()

        # 2. Submit date guess
        await expect(page.locator('#guessing-ui')).to_be_visible()
        await page.locator('#date-guess-year').select_option('2021')
        await page.locator('#date-guess-month').select_option('6')
        await page.locator('#submit-answer').click()

        # 3. Reveal screen
        await expect(page.locator('#reveal-ui')).to_be_visible()

        # Verify score rollup elements are present in table cells
        score_rollups = page.locator('#reveal-table .score-rollup')
        await expect(score_rollups.first).to_be_visible()

        # Advance to next round or finish game
        next_btn = page.locator('#next-round')
        await expect(next_btn).to_be_visible()
        await next_btn.click()

    # Verify transition to Match Summary screen
    await expect(page).to_have_url(re.compile(r'/game/[^/]+/summary$'))
    summary_card = page.locator('#summary-card')
    await expect(summary_card).to_be_visible()

    # Verify winner / podium section
    await expect(page.locator('#summary-winner')).to_be_visible()

    # Verify Summary Results Table
    summary_table = page.locator('#summary-table')
    await expect(summary_table).to_be_visible()
    await expect(summary_table.locator('tbody tr')).to_have_count(1)

    # Verify Polaroid Memory Cards Gallery
    polaroids = page.locator('#polaroid-gallery')
    await expect(polaroids).to_be_visible()
    await expect(polaroids.locator('.polaroid-card')).to_have_count(5)

    # Verify Start New Match & Share Summary Buttons
    await expect(page.locator('#new-match')).to_be_visible()
    await expect(page.locator('#share-summary-btn')).to_be_visible()


async def test_multiplayer_podium_and_winner_resolution(page: Page) -> None:
    """Verify multiplayer match summary displays the 1st place podium avatar and ranks both players in results table."""
    await page.goto('/')

    # Date mode only, 5 rounds
    await page.locator('#mode-pinpoint-btn').click()
    loc_card = page.locator('#card-goal-location')
    date_card = page.locator('#card-goal-date')
    if 'active' in (await loc_card.get_attribute('class') or ''):
        await loc_card.click()
    if 'active' not in (await date_card.get_attribute('class') or ''):
        await date_card.click()
    await page.locator('#round-count').select_option('5')

    # Open modal, add second player Bob, start match
    await page.locator('#prepare-game-btn').click()
    player_input = page.locator('#player-text-input')
    await expect(player_input).to_be_visible()
    await player_input.fill('Bob')
    await page.keyboard.press('Enter')
    await page.locator('#start-match-btn').click()

    pass_overlay = page.locator('#pass-overlay')

    for _ in range(5):
        # --- Player 1 (Alice): Turn ---
        await expect(pass_overlay).to_be_visible()
        await page.locator('#ready-btn').click()
        await expect(pass_overlay).to_be_hidden()

        await expect(page.locator('#guessing-ui')).to_be_visible()
        await page.locator('#date-guess-year').select_option('2021')
        await page.locator('#date-guess-month').select_option('6')
        await page.locator('#submit-answer').click()

        # --- Player 2 (Bob): Turn ---
        await expect(pass_overlay).to_be_visible()
        await page.locator('#ready-btn').click()
        await expect(pass_overlay).to_be_hidden()

        await expect(page.locator('#guessing-ui')).to_be_visible()
        await page.locator('#date-guess-year').select_option('2019')
        await page.locator('#date-guess-month').select_option('1')
        await page.locator('#submit-answer').click()

        # --- Round Reveal ---
        await expect(page.locator('#reveal-ui')).to_be_visible()
        await page.locator('#next-round').click()

    # --- Match Summary ---
    await expect(page).to_have_url(re.compile(r'/game/[^/]+/summary$'))
    summary_card = page.locator('#summary-card')
    await expect(summary_card).to_be_visible()

    # Winner section / podium avatar
    winner_section = page.locator('#summary-winner')
    await expect(winner_section).to_be_visible()
    # Winner text should mention Alice (Player 1 who scored higher)
    await expect(winner_section).to_contain_text(re.compile(r'Player 1|Alice', re.IGNORECASE))

    # Results Table contains both players
    summary_table = page.locator('#summary-table')
    await expect(summary_table).to_be_visible()
    rows = summary_table.locator('tbody tr')
    await expect(rows).to_have_count(2)

    # First row is rank 1
    await expect(rows.nth(0)).to_contain_text('1')

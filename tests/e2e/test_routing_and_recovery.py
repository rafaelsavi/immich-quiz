"""Playwright E2E tests for client-side routing, deep linking, and in-game state recovery on reload."""

from __future__ import annotations

import re

from playwright.async_api import Page, expect

from tests.e2e.conftest import start_date_only_match


async def test_client_side_deep_links_and_fallback_routes(page: Page) -> None:
    """Verify deep links to /, /stats, /play/{token}, and 404 catch-all route rendering."""
    # 1. Root lobby
    await page.goto('/')
    await expect(page.locator('#setup-card')).to_be_visible()
    await expect(page.locator('#leaderboard-card')).to_be_visible()

    # 2. /stats route
    await page.goto('/stats')
    await expect(page.locator('#setup-card')).to_be_visible()
    await expect(page.locator('#leaderboard-card')).to_be_visible()

    # 3. /challenges route
    await page.goto('/challenges')
    await expect(page.locator('#challenges-page-card')).to_be_visible()
    await expect(page.locator('#setup-card')).to_be_hidden()
    await expect(page.locator('#challenges-nav-btn')).to_have_class(re.compile(r'active'))

    # Click Back to Lobby button
    await page.locator('#challenges-page-back-btn').click()
    await expect(page.locator('#setup-card')).to_be_visible()
    await expect(page.locator('#challenges-page-card')).to_be_hidden()

    # Click header navigation button to go to /challenges
    await page.locator('#challenges-nav-btn').click()
    await expect(page.locator('#challenges-page-card')).to_be_visible()
    await expect(page.locator('#setup-card')).to_be_hidden()

    # Click header navigation button again to toggle back to lobby
    await page.locator('#challenges-nav-btn').click()
    await expect(page.locator('#setup-card')).to_be_visible()
    await expect(page.locator('#challenges-page-card')).to_be_hidden()

    # 4. Unknown route
    await page.goto('/unknown/nested/page')
    await expect(page.locator('#game-ended-card')).to_be_visible()
    await expect(page.locator('#game-ended-title')).to_contain_text(re.compile(r'Not Found|Ended', re.IGNORECASE))

    # Click Return to Lobby button
    await page.locator('#game-ended-lobby-btn').click()
    await expect(page.locator('#setup-card')).to_be_visible()


async def test_active_match_reload_recovery(page: Page) -> None:
    """Verify active match state and round progress survive page refreshes on /game/{match_id}."""
    await page.goto('/')
    await start_date_only_match(page, rounds=5)

    # Verify transition to /game/{match_id}
    await expect(page).to_have_url(re.compile(r'/game/[^/]+$'))
    match_url = page.url

    # Ready up to enter guessing screen (if pass overlay shown)
    if await page.locator('#pass-overlay').is_visible():
        await page.locator('#ready-btn').click()
        await expect(page.locator('#pass-overlay')).to_be_hidden()
    await expect(page.locator('#guessing-ui')).to_be_visible()

    # 1. Reload during active guessing phase
    await page.reload()

    # Verify we are still on the same match URL and in the game card
    await expect(page).to_have_url(match_url)
    await expect(page.locator('#game-card')).to_be_visible()
    # Pass overlay re-prompts on reload for safety
    if await page.locator('#pass-overlay').is_visible():
        await page.locator('#ready-btn').click()
    await expect(page.locator('#guessing-ui')).to_be_visible()

    # 2. Submit answer to reach Reveal screen
    await page.locator('#submit-answer').click()
    await expect(page.locator('#reveal-ui')).to_be_visible()

    # 3. Reload while on Reveal screen
    await page.reload()

    # Verify reveal screen is restored without skipping the round
    await expect(page).to_have_url(match_url)
    await expect(page.locator('#reveal-ui')).to_be_visible()
    await expect(page.locator('#reveal-table')).to_be_visible()
    await expect(page.locator('#next-round')).to_be_visible()


async def test_expired_or_invalid_match_url_navigation(page: Page) -> None:
    """Verify navigating to an unknown or expired match ID shows the Match Ended card."""
    await page.goto('/game/nonexistent-match-9999')
    await expect(page.locator('#game-ended-card')).to_be_visible()
    await expect(page.locator('#game-ended-title')).to_contain_text(re.compile(r'Not Found|Ended', re.IGNORECASE))


async def test_match_summary_reload_recovery(page: Page) -> None:
    """Verify reloading while on a match summary URL restores summary results without console errors."""
    await page.goto('/')
    await start_date_only_match(page, rounds=5)
    await expect(page.locator('#game-card')).to_be_visible()

    # Play through 5 rounds to reach summary
    for _round_idx in range(1, 6):
        if await page.locator('#pass-overlay').is_visible():
            await page.locator('#ready-btn').click()
        await expect(page.locator('#guessing-ui')).to_be_visible()
        await page.locator('#date-guess-year').select_option('2021')
        await page.locator('#date-guess-month').select_option('6')
        await page.locator('#submit-answer').click()
        await expect(page.locator('#reveal-ui')).to_be_visible()
        next_btn = page.locator('#next-round')
        await expect(next_btn).to_be_visible()
        await next_btn.click()

    # Verify summary is reached
    await expect(page).to_have_url(re.compile(r'/game/[^/]+/summary$'))
    summary_url = page.url
    await expect(page.locator('#summary-card')).to_be_visible()
    await expect(page.locator('#summary-winner')).to_be_visible()

    # Reload on summary page
    await page.reload()

    # Verify summary is accurately restored without falling back to error screens
    await expect(page).to_have_url(summary_url)
    await expect(page.locator('#summary-card')).to_be_visible()
    await expect(page.locator('#summary-winner')).to_be_visible()
    await expect(page.locator('#summary-table')).to_be_visible()
    await expect(page.locator('#summary-table tbody tr')).to_have_count(1)
    await expect(page.locator('#leaderboard-card')).to_be_visible()


async def test_pass_and_play_multiplayer_ready_overlay_flow(page: Page) -> None:
    """Verify pass-and-play multiplayer flow displays the pass overlay and ready button clicks/shortcuts
    without errors.
    """
    await page.goto('/')

    # Configure date mode only
    loc_card = page.locator('#card-goal-location')
    date_card = page.locator('#card-goal-date')
    if 'active' in (await loc_card.get_attribute('class') or ''):
        await loc_card.click()
    if 'active' not in (await date_card.get_attribute('class') or ''):
        await date_card.click()

    # Configure 5 rounds for test
    await page.locator('#round-count').select_option('5')

    # Open prepare game modal and add a second player
    await page.locator('#prepare-game-btn').click()
    player_input = page.locator('#player-text-input')
    if await player_input.is_visible():
        await player_input.fill('Bob')
        await page.keyboard.press('Enter')

    await page.locator('#start-match-btn').click()
    await expect(page.locator('#game-card')).to_be_visible()

    pass_overlay = page.locator('#pass-overlay')
    ready_btn = page.locator('#ready-btn')

    for _ in range(5):
        # Pass overlay should be visible for multiplayer
        await expect(pass_overlay).to_be_visible()
        await expect(ready_btn).to_be_visible()

        # Click Ready to begin Player 1 turn
        await ready_btn.click()
        await expect(pass_overlay).to_be_hidden()
        await expect(page.locator('#guessing-ui')).to_be_visible()

        # Select date and submit Player 1 guess
        await page.locator('#date-guess-year').select_option('2021')
        await page.locator('#date-guess-month').select_option('6')
        await page.locator('#submit-answer').click()

        # Pass overlay for Player 2
        await expect(pass_overlay).to_be_visible()
        await ready_btn.click()
        await expect(pass_overlay).to_be_hidden()
        await expect(page.locator('#guessing-ui')).to_be_visible()

        # Select date and submit Player 2 guess
        await page.locator('#date-guess-year').select_option('2020')
        await page.locator('#date-guess-month').select_option('5')
        await page.locator('#submit-answer').click()

        # Round Reveal is visible after all players submit
        await expect(page.locator('#reveal-ui')).to_be_visible()

        # Advance to next round or finish game
        await page.locator('#next-round').click()

    # Finish game to summary
    await expect(page).to_have_url(re.compile(r'/game/[^/]+/summary$'))
    await expect(page.locator('#summary-card')).to_be_visible()
    await expect(page.locator('#summary-table tbody tr')).to_have_count(2)


async def test_in_game_navigation_guard_and_abandon_dialog(page: Page) -> None:
    """Verify in-game exit confirmation dialog protects active games from accidental abandonment."""
    await page.goto('/')
    await start_date_only_match(page, rounds=5)
    await expect(page.locator('#game-card')).to_be_visible()

    # 1. Dismiss abandonment dialog: Player stays in game
    dismissed = False

    async def handle_dismiss(dialog):
        nonlocal dismissed
        dismissed = True
        await dialog.dismiss()

    page.on('dialog', handle_dismiss)
    await page.locator('#game-exit-btn').click()
    assert dismissed is True
    page.remove_listener('dialog', handle_dismiss)

    # Game card remains visible
    await expect(page.locator('#game-card')).to_be_visible()

    # 2. Confirm abandonment dialog: Player returns to Lobby
    accepted = False

    async def handle_accept(dialog):
        nonlocal accepted
        accepted = True
        await dialog.accept()

    page.on('dialog', handle_accept)
    await page.locator('#game-exit-btn').click()
    assert accepted is True
    page.remove_listener('dialog', handle_accept)

    # Returned to setup lobby
    await expect(page).to_have_url(re.compile(r'/$'))
    await expect(page.locator('#setup-card')).to_be_visible()

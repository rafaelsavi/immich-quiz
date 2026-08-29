"""Playwright E2E tests for timeline range slider filtering and single year/month date guessing."""

from __future__ import annotations

import re

from playwright.async_api import Page, expect

from tests.e2e.conftest import start_date_only_match


async def test_dual_handle_timeline_range_slider_filtering(page: Page) -> None:
    """Verify dual-handle range slider updates visual range readout and responds to filter reset."""
    await page.goto('/')
    await expect(page.locator('#setup-card')).to_be_visible()

    # Expand Filters Accordion
    await page.locator('#filters-toggle-btn').click()
    await expect(page.locator('#filters-accordion-content')).to_be_visible()

    # Verify initial Date Range readout
    readout = page.locator('#date-slider-readout')
    await expect(readout).to_contain_text(re.compile(r'All (Time|Dates)', re.IGNORECASE))

    # Move minimum slider thumb forward
    min_thumb = page.locator('#date-slider-min')
    max_thumb = page.locator('#date-slider-max')

    max_idx = int(await max_thumb.get_attribute('max') or '10')
    target_min = min(3, max_idx)

    # Set min thumb value and fire input event
    eval_script = f'(el) => {{ el.value = "{target_min}"; el.dispatchEvent(new Event("input", {{ bubbles: true }})); }}'
    await min_thumb.evaluate(eval_script)

    # Readout should now show a formatted date range instead of "All Time"
    await expect(readout).not_to_contain_text(re.compile(r'All (Time|Dates)', re.IGNORECASE))
    await expect(readout).to_contain_text('—')

    # Click Reset Filters
    await page.locator('#reset-filters-btn').click()
    await expect(readout).to_contain_text(re.compile(r'All (Time|Dates)', re.IGNORECASE))


async def test_pinpoint_single_year_and_month_date_selection(page: Page) -> None:
    """Verify single-year and single-month dropdown date selection and scoring in Pinpoint mode."""
    await page.goto('/')

    # Configure match with Date mode enabled and Location mode disabled
    await page.locator('#mode-pinpoint-btn').click()

    # Ensure Date mode card is active and Location mode card is inactive
    loc_card = page.locator('#card-goal-location')
    date_card = page.locator('#card-goal-date')

    if 'active' in (await loc_card.get_attribute('class') or ''):
        await loc_card.click()
    if 'active' not in (await date_card.get_attribute('class') or ''):
        await date_card.click()

    # Start match
    await page.locator('#start-match-btn').click()

    # Pass overlay (if multiplayer/present)
    if await page.locator('#pass-overlay').is_visible():
        await page.locator('#ready-btn').click()
        await expect(page.locator('#pass-overlay')).to_be_hidden()

    # Verify Date Guess controls are visible
    date_wrap = page.locator('#date-guess-wrap')
    await expect(date_wrap).to_be_visible()

    year_select = page.locator('#date-guess-year')
    month_select = page.locator('#date-guess-month')

    await expect(year_select).to_be_visible()
    await expect(month_select).to_be_visible()

    # Select Year 2021 and Month 06 (June)
    await year_select.select_option('2021')
    await month_select.select_option('6')

    # Submit date guess
    await page.locator('#submit-answer').click()

    # Verify Reveal screen displays date score, guessed date, and error
    await expect(page.locator('#reveal-ui')).to_be_visible()
    await expect(page.locator('#reveal-actual')).to_contain_text(re.compile(r'Date|Actual', re.IGNORECASE))

    reveal_table = page.locator('#reveal-table')
    await expect(reveal_table).to_be_visible()
    # Table should show the guessed year/month
    await expect(reveal_table).to_contain_text('2021')


async def test_countdown_timer_tick_and_timeout_zero_crossing(page: Page) -> None:
    """Verify that timer expiration disables input, displays time's up notice, and submits a 0-point timeout round."""
    await page.goto('/')
    await start_date_only_match(page, rounds=5, round_length='30s')
    await expect(page.locator('#game-card')).to_be_visible()

    # Pass overlay (if present)
    if await page.locator('#pass-overlay').is_visible():
        await page.locator('#ready-btn').click()

    await expect(page.locator('#guessing-ui')).to_be_visible()
    await expect(page.locator('#quiz-image')).to_be_visible()
    await expect(page.locator('#timer-remaining')).to_contain_text(re.compile(r'\d+'))

    # Simulate timer expiration by setting timerEndTimeMs to the past
    await page.evaluate('() => { if (window.__state) window.__state.timerEndTimeMs = Date.now() - 500; }')

    # Wait for timeout notice to trigger
    timeout_notice = page.locator('#timeout-notice')
    await expect(timeout_notice).to_be_visible()
    await expect(timeout_notice).to_contain_text(re.compile(r"Time's up|Tempo esgotado", re.IGNORECASE))

    # Submit button transforms into Continue button and becomes enabled
    submit_btn = page.locator('#submit-answer')
    await expect(submit_btn).to_be_enabled()
    await expect(submit_btn).to_contain_text(re.compile(r'Continue|Continuar', re.IGNORECASE))

    # Click Continue to advance to Reveal
    await submit_btn.click()

    # Verify reveal screen shows 0 points / timeout
    await expect(page.locator('#reveal-ui')).to_be_visible()
    reveal_table = page.locator('#reveal-table')
    await expect(reveal_table).to_be_visible()
    await expect(reveal_table).to_contain_text('0')

    # Next Round button is ready
    await expect(page.locator('#next-round')).to_be_visible()

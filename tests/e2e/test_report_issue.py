"""Playwright E2E tests for reporting photo map or date inconsistencies."""

from __future__ import annotations

import re

from playwright.async_api import Page, expect


async def test_report_issue_modal_flow(page: Page) -> None:
    """Verify opening the Report Issue modal on round reveal, form validation, and submitting a report."""
    await page.goto('/')

    # 1. Start a game in Pinpoint mode
    await expect(page.locator('#setup-card')).to_be_visible()
    await page.locator('#mode-pinpoint-btn').click()

    loc_card = page.locator('#card-goal-location')
    date_card = page.locator('#card-goal-date')
    await expect(loc_card).to_be_visible()
    if 'active' not in (await loc_card.get_attribute('class') or ''):
        await loc_card.click()
    if 'active' in (await date_card.get_attribute('class') or ''):
        await date_card.click()
    await expect(loc_card).to_have_class(re.compile(r'active'))

    await page.locator('#start-match-btn').click()

    # 2. Handle pass overlay if shown
    await expect(page.locator('#game-card')).to_be_visible()
    if await page.locator('#pass-overlay').is_visible():
        await page.locator('#ready-btn').click()
        await expect(page.locator('#pass-overlay')).to_be_hidden()

    # 3. Place a guess and submit
    guess_map = page.locator('#guess-map')
    await expect(guess_map).to_be_visible()
    await guess_map.click(position={'x': 150, 'y': 150})

    submit_btn = page.locator('#submit-answer')
    await expect(submit_btn).to_be_enabled()
    await submit_btn.click()

    # 4. Arrive at Reveal Screen
    await expect(page.locator('#reveal-ui')).to_be_visible()
    report_btn = page.locator('#reveal-report-btn')
    await expect(report_btn).to_be_visible()

    # 5. Open Report Modal
    await report_btn.click()
    modal = page.locator('#report-issue-modal')
    await expect(modal).to_be_visible()

    # Verify Immich Web direct link
    immich_link = page.locator('#report-immich-link')
    await expect(immich_link).to_be_visible()
    link_href = await immich_link.get_attribute('href')
    assert link_href and '/photos/' in link_href

    # Verify submit button starts disabled
    submit_report_btn = page.locator('#report-submit-btn')
    await expect(submit_report_btn).to_be_disabled()

    # 6. Check coordinates checkbox -> submit becomes enabled
    coords_checkbox = page.locator('#report-flag-coordinates')
    await coords_checkbox.check()
    await expect(submit_report_btn).to_be_enabled()

    # Enter notes
    other_input = page.locator('#report-flag-other')
    await other_input.fill('Photo location is off by 10km')

    # 7. Submit report
    await submit_report_btn.click()

    # Modal should close
    await expect(modal).to_be_hidden()

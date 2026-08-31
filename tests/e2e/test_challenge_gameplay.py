"""Playwright E2E tests for Challenge mode: join, guess, submit answer, personal reveal, and intermission."""

from __future__ import annotations

import httpx
from playwright.async_api import Page, expect


async def test_challenge_answer_submission_and_personal_reveal(page: Page, e2e_server: str) -> None:
    """Verify challenge mode plays smoothly and submitting answers does not throw 422 errors."""
    # 1. Create challenge via API
    async with httpx.AsyncClient(base_url=e2e_server) as client:
        res = await client.post(
            '/api/challenge/create',
            json={
                'title': 'Weekend Adventure Challenge',
                'creator_name': 'Host',
                'game_mode': 'pinpoint',
                'location_mode': True,
                'date_mode': False,
                'round_count': 3,
                'round_length': 'unlimited',
            },
        )
        assert res.status_code == 200
        data = res.json()
        token = data['capability_token']

    # Monitor for any uncaught dialog alerts or 422 responses
    error_alerts: list[str] = []
    page.on('dialog', lambda dialog: error_alerts.append(dialog.message))

    failed_responses: list[str] = []

    def on_response(response: httpx.Response) -> None:
        if response.status >= 400 and '/api/' in response.url:
            failed_responses.append(f'{response.url} -> {response.status}')

    page.on('response', on_response)

    # 2. Open challenge link
    await page.goto(f'/play/{token}')
    await expect(page.locator('#challenge-card')).to_be_visible()
    await expect(page.locator('#challenge-join-form')).to_be_visible()

    # 3. Enter name and start
    await page.locator('#player-name-input').fill('Explorer')
    await page.locator('#challenge-start-btn').click()

    # 4. Verify Question 1 is displayed
    await expect(page.locator('#game-card')).to_be_visible()
    await expect(page.locator('#guessing-ui')).to_be_visible()

    # Place a pin on guess map
    guess_map = page.locator('#guess-map')
    await expect(guess_map).to_be_visible()
    await guess_map.click(position={'x': 120, 'y': 120})

    submit_btn = page.locator('#submit-answer')
    await expect(submit_btn).to_be_enabled()

    # Submit answer via button click
    await submit_btn.click()

    # 5. Verify personal reveal screen is shown without 422 error
    await expect(page.locator('#reveal-ui')).to_be_visible()
    assert not error_alerts, f'Unexpected alert popups: {error_alerts}'
    assert not any('422' in r for r in failed_responses), f'422 errors occurred: {failed_responses}'

    # Verify true pin is shown on reveal map
    reveal_map = page.locator('#reveal-map')
    await expect(reveal_map).to_be_visible()
    await expect(reveal_map.locator('.player-pin:has-text("★")')).to_be_visible()

    # 6. Click Next Round to transition to Social Intermission
    next_round_btn = page.locator('#next-round')
    await expect(next_round_btn).to_be_visible()
    await next_round_btn.click()

    await expect(page.locator('.challenge-intermission')).to_be_visible()
    await expect(page.locator('#intermission-next-btn')).to_be_visible()

    # 7. Advance to Round 2
    await page.locator('#intermission-next-btn').click()
    await expect(page.locator('#game-card')).to_be_visible()
    await expect(page.locator('#guessing-ui')).to_be_visible()

    # Place pin for round 2
    await guess_map.click(position={'x': 150, 'y': 150})
    await expect(submit_btn).to_be_enabled()

    # Submit round 2 answer via Enter keyboard shortcut
    await page.keyboard.press('Enter')

    # 8. Verify personal reveal for round 2
    await expect(page.locator('#reveal-ui')).to_be_visible()
    await expect(next_round_btn).to_be_visible()
    await expect(next_round_btn).to_contain_text('Next Round')
    await next_round_btn.click()

    # Intermission 2
    await expect(page.locator('.challenge-intermission')).to_be_visible()
    await page.locator('#intermission-next-btn').click()

    # 9. Round 3 (final round)
    await expect(page.locator('#game-card')).to_be_visible()
    await expect(page.locator('#guessing-ui')).to_be_visible()

    await guess_map.click(position={'x': 180, 'y': 180})
    await expect(submit_btn).to_be_enabled()
    await submit_btn.click()

    # Personal reveal for round 3
    await expect(page.locator('#reveal-ui')).to_be_visible()
    await expect(next_round_btn).to_be_visible()
    await expect(next_round_btn).to_contain_text('See Final Results')

    # Click See Results
    await next_round_btn.click()

    # Verify Invite Friends screen
    await expect(page.locator('.challenge-invite')).to_be_visible()
    await expect(page.locator('#challenge-see-results-btn')).to_be_visible()

    # Click See Results to open Grand Reveal
    await page.locator('#challenge-see-results-btn').click()
    await expect(page.locator('.challenge-grand-reveal')).to_be_visible()
    await expect(page.locator('#grand-reveal-podium')).to_be_visible()

    assert not error_alerts, f'Unexpected alert popups: {error_alerts}'
    assert not any('422' in r for r in failed_responses), f'422 errors occurred: {failed_responses}'


async def test_homepage_header_challenges_badge_on_load(page: Page, e2e_server: str) -> None:
    """Verify header challenges badge displays active challenge count immediately upon homepage load."""
    async with httpx.AsyncClient(base_url=e2e_server) as client:
        res = await client.post(
            '/api/challenge/create',
            json={
                'title': 'Homepage Badge Verification Challenge',
                'creator_name': 'BadgeTester',
                'game_mode': 'pinpoint',
                'location_mode': True,
                'date_mode': False,
                'round_count': 3,
                'round_length': 'unlimited',
            },
        )
        assert res.status_code == 200

    # Navigate to homepage
    await page.goto('/')
    await expect(page.locator('#setup-card')).to_be_visible()

    # The header challenges badge should become visible with active count without clicking the button
    badge = page.locator('#header-challenges-badge')
    await expect(badge).to_be_visible()
    badge_text = await badge.text_content()
    assert badge_text is not None and int(badge_text) >= 1

    # Clicking the challenges button should transition to the hub page where the challenge is rendered
    challenges_btn = page.locator('#challenges-nav-btn')
    await challenges_btn.click()
    await expect(page.locator('#challenges-page-card')).to_be_visible()
    await expect(page.locator('.detailed-challenge-card')).to_have_count(int(badge_text))


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
    await expect(guess_map.locator('.player-pin:has-text("E")')).to_be_visible()

    submit_btn = page.locator('#submit-answer')
    await expect(submit_btn).to_be_enabled()

    # Submit answer via button click
    await submit_btn.click()

    # 5. Verify personal reveal screen is shown without 422 error
    await expect(page.locator('#reveal-ui')).to_be_visible()
    await expect(page.locator('#leaderboard-card')).to_be_hidden()
    assert not error_alerts, f'Unexpected alert popups: {error_alerts}'
    assert not any('422' in r for r in failed_responses), f'422 errors occurred: {failed_responses}'

    # Verify true pin is shown on reveal map
    reveal_map = page.locator('#reveal-map')
    await expect(reveal_map).to_be_visible()
    await expect(reveal_map.locator('.player-pin:has-text("★")')).to_be_visible()

    # 6. Click Next Round to advance directly to Round 2 (unified round review)
    next_round_btn = page.locator('#next-round')
    await expect(next_round_btn).to_be_visible()
    await expect(next_round_btn).to_contain_text('Next Round')
    await next_round_btn.click()

    # 7. Advance to Round 2
    await expect(page.locator('#game-card')).to_be_visible()
    await expect(page.locator('#guessing-ui')).to_be_visible()

    # Place pin for round 2
    await guess_map.click(position={'x': 150, 'y': 150})
    await expect(submit_btn).to_be_enabled()

    # Submit round 2 answer via Enter keyboard shortcut
    await page.keyboard.press('Enter')

    # 8. Verify round review for round 2 and advance to Round 3
    await expect(page.locator('#reveal-ui')).to_be_visible()
    await expect(next_round_btn).to_be_visible()
    await expect(next_round_btn).to_contain_text('Next Round')
    await next_round_btn.click()

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
    await expect(page.locator('#finisher-count-text')).to_contain_text('You + 0 friends')

    # Click See Results to open Grand Reveal
    await page.locator('#challenge-see-results-btn').click()
    await expect(page.locator('.challenge-grand-reveal')).to_be_visible()
    await expect(page.locator('#grand-reveal-provisional')).to_be_visible()
    await expect(page.locator('#grand-reveal-table')).to_be_visible()
    await expect(page.locator('.challenge-rounds-pill')).to_be_visible()

    assert not error_alerts, f'Unexpected alert popups: {error_alerts}'
    assert not any('422' in r for r in failed_responses), f'422 errors occurred: {failed_responses}'

    # 10. Player 2 joins and finishes, verifying challenge-invite screen is shown to subsequent finishers
    page2 = await page.context.new_page()
    page2.on('dialog', lambda dialog: error_alerts.append(dialog.message))
    page2.on('response', on_response)

    await page2.goto(f'/play/{token}')
    await expect(page2.locator('#challenge-card')).to_be_visible()
    await page2.locator('#player-name-input').fill('Explorer2')
    await page2.locator('#challenge-start-btn').click()

    # Play 3 rounds for Player 2
    for r in range(3):
        await expect(page2.locator('#game-card')).to_be_visible()
        await expect(page2.locator('#guessing-ui')).to_be_visible()
        p2_guess_map = page2.locator('#guess-map')
        await expect(p2_guess_map).to_be_visible()
        await p2_guess_map.click(position={'x': 100 + r * 20, 'y': 100 + r * 20})
        p2_submit_btn = page2.locator('#submit-answer')
        await expect(p2_submit_btn).to_be_enabled()
        await p2_submit_btn.click()
        await expect(page2.locator('#reveal-ui')).to_be_visible()
        p2_next_btn = page2.locator('#next-round')
        await expect(p2_next_btn).to_be_visible()
        await p2_next_btn.click()

    # Verify Player 2 is presented with the challenge-invite screen (not auto-bypassed)
    await expect(page2.locator('.challenge-invite')).to_be_visible()
    await expect(page2.locator('#challenge-see-results-btn')).to_be_visible()
    await expect(page2.locator('#finisher-count-text')).to_contain_text('You + 1 friend has finished')

    # Player 2 clicks See Results to open settled Grand Reveal
    await page2.locator('#challenge-see-results-btn').click()
    await expect(page2.locator('.challenge-grand-reveal')).to_be_visible()
    await expect(page2.locator('#grand-reveal-podium')).to_be_visible()
    await expect(page2.locator('#grand-reveal-table')).to_be_visible()

    # Verify Player 1's open Grand Reveal page dynamically unlocked the podium via background polling!
    await expect(page.locator('#grand-reveal-podium')).to_be_visible()
    await expect(page.locator('#grand-reveal-live-status')).to_contain_text('2/2 finished')

    await page2.close()


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


async def test_challenge_exit_game_button(page: Page, e2e_server: str) -> None:
    """Test exit game button behavior when challenge is active and when stopped."""
    async with httpx.AsyncClient(base_url=e2e_server) as client:
        res = await client.post(
            '/api/challenge/create',
            json={
                'title': 'Exit Button Challenge',
                'creator_name': 'HostExit',
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
        ch_id = data['challenge_id']

    # Open challenge and start
    await page.goto(f'/play/{token}')
    await page.locator('#player-name-input').fill('ExitTester')
    await page.locator('#challenge-start-btn').click()
    await expect(page.locator('#game-card')).to_be_visible()
    await expect(page.locator('#guessing-ui')).to_be_visible()

    # Now deactivate the challenge (stopped)
    async with httpx.AsyncClient(base_url=e2e_server) as client:
        deact_res = await client.post(f'/api/challenge/{ch_id}/deactivate')
        assert deact_res.status_code == 200

    # Click Exit button on question screen
    dialog_messages = []

    async def handle_dialog(d):
        dialog_messages.append(d.message)
        await d.accept()

    page.on('dialog', handle_dialog)
    await page.locator('#game-exit-btn').click()

    await expect(page.locator('#setup-card')).to_be_visible()
    await expect(page.locator('#game-card')).to_be_hidden()
    await expect(page.locator('#challenge-card')).to_be_hidden()
    assert page.url.rstrip('/').endswith(e2e_server.rstrip('/'))


async def test_challenge_individual_icon_colors_e2e(page: Page, e2e_server: str) -> None:
    """Verify each new person starting a challenge receives an individual icon color."""
    async with httpx.AsyncClient(base_url=e2e_server) as client:
        res = await client.post(
            '/api/challenge/create',
            json={
                'title': 'Color Verification Challenge',
                'creator_name': 'Host',
                'game_mode': 'pinpoint',
                'location_mode': True,
                'date_mode': False,
                'round_count': 3,
                'round_length': 'unlimited',
            },
        )
        assert res.status_code == 200
        token = res.json()['capability_token']

    # 1. Open challenge page as Player 1 (Alice)
    await page.goto(f'/play/{token}')
    await expect(page.locator('#challenge-card')).to_be_visible()
    avatar_preview = page.locator('#challenge-avatar-preview')
    await expect(avatar_preview).to_be_visible()
    await expect(avatar_preview).to_have_text('?')

    # Type name and verify avatar initial updates dynamically
    await page.locator('#player-name-input').fill('Alice')
    await expect(avatar_preview).to_have_text('A')

    # Get avatar background color for Player 1
    p1_bg_color = await avatar_preview.evaluate('el => getComputedStyle(el).backgroundColor')

    await page.locator('#challenge-start-btn').click()
    await expect(page.locator('#game-card')).to_be_visible()

    # Verify Player 1 header badge has matching color
    p1_header_badge = page.locator('.round-meta-pill.round-meta-player .legend-badge')
    await expect(p1_header_badge).to_be_visible()
    await expect(p1_header_badge).to_have_text('A')
    p1_header_color = await p1_header_badge.evaluate('el => getComputedStyle(el).backgroundColor')
    assert p1_header_color == p1_bg_color

    # 2. In a separate browser page/tab, join as Player 2 (Bob)
    page2 = await page.context.new_page()
    await page2.goto(f'/play/{token}')
    await expect(page2.locator('#challenge-card')).to_be_visible()

    avatar_preview2 = page2.locator('#challenge-avatar-preview')
    await expect(avatar_preview2).to_be_visible()
    await page2.locator('#player-name-input').fill('Bob')
    await expect(avatar_preview2).to_have_text('B')

    p2_bg_color = await avatar_preview2.evaluate('el => getComputedStyle(el).backgroundColor')
    # Player 2 must have an individual, distinct color from Player 1
    assert p2_bg_color != p1_bg_color

    await page2.locator('#challenge-start-btn').click()
    await expect(page2.locator('#game-card')).to_be_visible()

    p2_header_badge = page2.locator('.round-meta-pill.round-meta-player .legend-badge')
    await expect(p2_header_badge).to_be_visible()
    await expect(p2_header_badge).to_have_text('B')
    p2_header_color = await p2_header_badge.evaluate('el => getComputedStyle(el).backgroundColor')
    assert p2_header_color == p2_bg_color
    assert p2_header_color != p1_header_color
    await page2.close()


async def test_challenges_hub_standings_drawer_col_rank(page: Page, e2e_server: str) -> None:
    """Verify that expanding standings drawer in challenges hub displays proper rank in col-rank, not 'unknown'."""
    async with httpx.AsyncClient(base_url=e2e_server) as client:
        res = await client.post(
            '/api/challenge/create',
            json={
                'title': 'Rank Verification Challenge',
                'creator_name': 'HostRank',
                'game_mode': 'pinpoint',
                'location_mode': True,
                'date_mode': False,
                'round_count': 3,
                'round_length': 'unlimited',
            },
        )
        assert res.status_code == 200
        token = res.json()['capability_token']

    # Join and submit round 1 as Player 1
    await page.goto(f'/play/{token}')
    await expect(page.locator('#challenge-card')).to_be_visible()
    await page.locator('#player-name-input').fill('RankTester')
    await page.locator('#challenge-start-btn').click()
    await expect(page.locator('#game-card')).to_be_visible()

    # Place a pin and submit
    guess_map = page.locator('#guess-map')
    await expect(guess_map).to_be_visible()
    await guess_map.click(position={'x': 100, 'y': 100})
    await page.locator('#submit-answer').click()
    await expect(page.locator('#reveal-ui')).to_be_visible()

    # Navigate to Challenges Hub page
    await page.goto('/')
    await expect(page.locator('#setup-card')).to_be_visible()
    await page.locator('#challenges-nav-btn').click()
    await expect(page.locator('#challenges-page-card')).to_be_visible()

    # Open standings drawer
    standings_btn = page.locator('.btn-standings-toggle').first
    await expect(standings_btn).to_be_visible()
    await standings_btn.click()

    # Verify standings table is rendered
    table_wrap = page.locator('.standings-table-wrap')
    await expect(table_wrap).to_be_visible()

    # Verify col-rank text
    rank_cells = page.locator('.standings-table td.col-rank')
    await expect(rank_cells.first).to_be_visible()
    rank_text = await rank_cells.first.text_content()
    assert rank_text is not None
    assert 'unknown' not in rank_text.lower()
    assert '1' in rank_text


async def test_challenge_multi_tab_session_isolation_and_standings_on_reload(page: Page, e2e_server: str) -> None:
    """Verify that multiple tabs in the same browser maintain isolated player identities on reload.

    When Player 1 and Player 2 finish, and Player 3 starts the challenge in a 3rd tab,
    reloading the results page in Tab 1 and Tab 2 must NOT overwrite Player 1 or Player 2
    with Player 3's in-progress state or pill.
    """
    # 1. Create a 3-round challenge
    async with httpx.AsyncClient(base_url=e2e_server) as client:
        res = await client.post(
            '/api/challenge/create',
            json={
                'title': 'Multi-Tab Isolation Challenge',
                'creator_name': 'Host',
                'game_mode': 'pinpoint',
                'location_mode': True,
                'date_mode': False,
                'round_count': 3,
                'round_length': 'unlimited',
            },
        )
        assert res.status_code == 200
        token = res.json()['capability_token']

    # 2. Tab 1: Player 1 (Alice) plays and finishes all 3 rounds
    await page.goto(f'/play/{token}')
    await expect(page.locator('#challenge-card')).to_be_visible()
    await page.locator('#player-name-input').fill('Alice')
    await page.locator('#challenge-start-btn').click()

    for _ in range(3):
        await expect(page.locator('#game-card')).to_be_visible()
        guess_map = page.locator('#guess-map')
        await expect(guess_map).to_be_visible()
        await guess_map.click(position={'x': 110, 'y': 110})
        await page.locator('#submit-answer').click()
        await expect(page.locator('#reveal-ui')).to_be_visible()
        await page.locator('#next-round').click()

    await expect(page.locator('.challenge-invite')).to_be_visible()
    await page.locator('#challenge-see-results-btn').click()
    await expect(page.locator('.challenge-grand-reveal')).to_be_visible()

    # Verify Tab 1 shows Alice as (You) with finished 3/3 pill
    alice_row_tab1 = page.locator('tr[data-player-name="Alice"]')
    await expect(alice_row_tab1).to_be_visible()
    await expect(alice_row_tab1.locator('.challenge-you-tag')).to_have_text('(You)')
    await expect(alice_row_tab1.locator('.challenge-rounds-pill.finished')).to_contain_text('3/3')

    # 3. Tab 2: Player 2 (Bob) plays and finishes all 3 rounds
    page2 = await page.context.new_page()
    await page2.goto(f'/play/{token}')
    await expect(page2.locator('#challenge-card')).to_be_visible()
    await page2.locator('#player-name-input').fill('Bob')
    await page2.locator('#challenge-start-btn').click()

    for _ in range(3):
        await expect(page2.locator('#game-card')).to_be_visible()
        p2_map = page2.locator('#guess-map')
        await expect(p2_map).to_be_visible()
        await p2_map.click(position={'x': 130, 'y': 130})
        await page2.locator('#submit-answer').click()
        await expect(page2.locator('#reveal-ui')).to_be_visible()
        await page2.locator('#next-round').click()

    await expect(page2.locator('.challenge-invite')).to_be_visible()
    await page2.locator('#challenge-see-results-btn').click()
    await expect(page2.locator('.challenge-grand-reveal')).to_be_visible()

    # Verify Tab 2 shows Bob as (You) with finished 3/3 pill
    bob_row_tab2 = page2.locator('tr[data-player-name="Bob"]')
    await expect(bob_row_tab2).to_be_visible()
    await expect(bob_row_tab2.locator('.challenge-you-tag')).to_have_text('(You)')
    await expect(bob_row_tab2.locator('.challenge-rounds-pill.finished')).to_contain_text('3/3')

    # 4. Tab 3: Player 3 (Charlie) starts challenge (round 0 in-progress)
    page3 = await page.context.new_page()
    await page3.goto(f'/play/{token}')
    await expect(page3.locator('#challenge-card')).to_be_visible()
    await page3.locator('#player-name-input').fill('Charlie')
    await page3.locator('#challenge-start-btn').click()
    await expect(page3.locator('#game-card')).to_be_visible()

    # 5. Reload Tab 1 (Alice)
    await page.reload()
    await expect(page.locator('.challenge-grand-reveal')).to_be_visible()
    await expect(page.locator('tr[data-player-name="Alice"] .challenge-you-tag')).to_have_text('(You)')
    await expect(page.locator('tr[data-player-name="Alice"] .challenge-rounds-pill.finished')).to_contain_text('3/3')
    await expect(page.locator('tr[data-player-name="Bob"] .challenge-rounds-pill.finished')).to_contain_text('3/3')
    charlie_pill_tab1 = page.locator('tr[data-player-name="Charlie"] .challenge-rounds-pill.in-progress')
    await expect(charlie_pill_tab1).to_contain_text('0/3')

    # 6. Reload Tab 2 (Bob)
    await page2.reload()
    await expect(page2.locator('.challenge-grand-reveal')).to_be_visible()
    await expect(page2.locator('tr[data-player-name="Bob"] .challenge-you-tag')).to_have_text('(You)')
    await expect(page2.locator('tr[data-player-name="Alice"] .challenge-rounds-pill.finished')).to_contain_text('3/3')
    await expect(page2.locator('tr[data-player-name="Bob"] .challenge-rounds-pill.finished')).to_contain_text('3/3')
    charlie_pill_tab2 = page2.locator('tr[data-player-name="Charlie"] .challenge-rounds-pill.in-progress')
    await expect(charlie_pill_tab2).to_contain_text('0/3')

    await page2.close()
    await page3.close()

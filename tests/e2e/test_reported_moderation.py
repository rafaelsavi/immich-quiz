"""Playwright E2E tests for the Reported Asset Moderation Dashboard & Resolution Workflow."""

from __future__ import annotations

from playwright.async_api import Page, expect


async def test_reported_asset_moderation_workflow(page: Page) -> None:
    """Verify that /reported displays flagged assets, permits inspection, deep links, and resolving issues."""
    # 0. Clean up existing flagged items for deterministic isolation
    existing_res = await page.request.get('/api/assets/flagged')
    if existing_res.ok:
        for item in await existing_res.json():
            await page.request.delete(f'/api/assets/flagged/{item["asset_id"]}')

    # 1. Seed flagged assets via API request
    res1 = await page.request.post(
        '/api/assets/flag',
        data={
            'asset_id': 'asset-mod-1',
            'flag_coordinates': True,
            'flag_date': False,
            'other': 'GPS location is in the ocean',
            'reported_by': 'Alice',
        },
    )
    assert res1.ok

    res2 = await page.request.post(
        '/api/assets/flag',
        data={
            'asset_id': 'asset-mod-2',
            'flag_coordinates': False,
            'flag_date': True,
            'other': 'Wrong timestamp from camera clock reset',
            'reported_by': 'Bob',
        },
    )
    assert res2.ok

    # 2. Navigate directly to /reported
    await page.goto('/reported')
    await page.wait_for_selector('#reported-page-card')

    reported_card = page.locator('#reported-page-card')
    await expect(reported_card).to_be_visible()

    # Ensure lobby and other cards are hidden
    await expect(page.locator('#setup-card')).to_be_hidden()
    await expect(page.locator('#leaderboard-card')).to_be_hidden()

    # Verify header badge and title
    await expect(reported_card.locator('.badge-reported')).to_have_text('Moderation')
    await expect(reported_card.locator('h2')).to_have_text('Reported Photos')

    # Total counter badge
    total_badge = page.locator('#reported-page-total-badge')
    await expect(total_badge).to_contain_text('2 / 2')

    # 3. Verify items listed in master column
    item_cards = page.locator('.reported-item-card')
    await expect(item_cards).to_have_count(2)

    # Verify first item content and badges (sorted newest first)
    first_item = item_cards.first
    await expect(first_item.locator('.reported-item-id')).to_have_text('asset-mod-2')
    await expect(first_item.locator('.issue-badge-date')).to_be_visible()

    # 4. Verify inspection panel on the right
    inspection_panel = page.locator('#reported-inspection-panel')
    await expect(inspection_panel).to_be_visible()
    await expect(inspection_panel.locator('.inspection-asset-id-val')).to_have_text('asset-mod-2')
    await expect(inspection_panel.locator('.inspection-issues-box')).to_contain_text('Wrong Date / EXIF Timestamp')
    await expect(inspection_panel.locator('.inspection-notes-text')).to_contain_text(
        'Wrong timestamp from camera clock reset'
    )

    # Verify Immich Web link
    immich_link = inspection_panel.locator('.btn-open-immich')
    await expect(immich_link).to_be_visible()
    href = await immich_link.get_attribute('href')
    assert '/photos/asset-mod-2' in (href or '')

    # 5. Click on the second item in list
    second_item = item_cards.nth(1)
    await second_item.click()
    await expect(second_item).to_have_class('reported-item-card active')
    await expect(inspection_panel.locator('.inspection-asset-id-val')).to_have_text('asset-mod-1')
    await expect(inspection_panel.locator('.inspection-issues-box')).to_contain_text('Inaccurate GPS / Map Location')
    await expect(inspection_panel.locator('.inspection-notes-text')).to_contain_text('GPS location is in the ocean')

    # 6. Test search filter
    search_input = page.locator('#reported-search-input')
    await search_input.fill('Alice')
    await expect(page.locator('.reported-item-card')).to_have_count(1)
    await search_input.fill('')
    await expect(page.locator('.reported-item-card')).to_have_count(2)

    # 7. Test issue type filter pills
    await page.locator("#reported-issue-tabs button[data-issue='location']").click()
    await expect(page.locator('.reported-item-card')).to_have_count(1)
    await expect(page.locator('.reported-item-card .reported-item-id')).to_have_text('asset-mod-1')

    await page.locator("#reported-issue-tabs button[data-issue='all']").click()
    await expect(page.locator('.reported-item-card')).to_have_count(2)

    # 8. Resolve asset-mod-1
    page.on('dialog', lambda dialog: dialog.accept())
    resolve_btn = inspection_panel.locator('#btn-resolve-current-report')
    await resolve_btn.click()

    # Asset should be removed from view
    await expect(page.locator('.reported-item-card')).to_have_count(1)
    check1 = await page.request.get('/api/assets/flagged')
    flagged_list = await check1.json()
    assert all(item['asset_id'] != 'asset-mod-1' for item in flagged_list)

    # 9. Resolve remaining asset-mod-2 to test empty state
    await resolve_btn.click()
    await expect(page.locator('.reported-item-card')).to_have_count(0)
    await expect(page.locator('#reported-items-list .reported-empty-state')).to_be_visible()
    await expect(page.locator('#reported-items-list .reported-empty-state h3')).to_have_text('No Reported Photos')
    await expect(inspection_panel).to_be_hidden()

    # 10. Exit to Lobby via Header Home button
    await page.locator('#home-nav-btn').click()
    await expect(page.locator('#setup-card')).to_be_visible()
    await expect(page.locator('#reported-page-card')).to_be_hidden()

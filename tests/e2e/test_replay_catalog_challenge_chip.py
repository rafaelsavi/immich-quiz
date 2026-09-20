"""End-to-End test verifying challenge chip and badge formatting in Match Replay screen and catalog."""

from __future__ import annotations

import json

import pytest
from playwright.async_api import Page, expect

MOCK_MATCHES_DATA = [
    {
        'match_id': 'match-challenge-1',
        'game_mode': 'pinpoint',
        'play_mode': 'challenge',
        'played_at': 1740000000.0,
        'players': ['Rafael'],
        'winners': ['Rafael'],
        'rounds': 5,
        'top_accuracy_pct': 4.8,
    },
    {
        'match_id': 'match-challenge-2',
        'game_mode': 'pinpoint',
        'play_mode': 'challenge',
        'played_at': 1739990000.0,
        'players': ['Rafael'],
        'winners': ['Rafael'],
        'rounds': 10,
        'top_accuracy_pct': None,
    },
    {
        'match_id': 'match-local-3',
        'game_mode': 'unshuffle',
        'play_mode': 'local',
        'played_at': 1739980000.0,
        'players': ['Ivana', 'Rafael'],
        'winners': ['Ivana'],
        'rounds': 5,
        'top_accuracy_pct': 56.8,
    },
]


@pytest.mark.asyncio
async def test_replay_catalog_and_challenge_chip_design(page: Page) -> None:
    """Verify that challenge chips follow the app's standard design:
    - 6px border radius (not pill 999px)
    - Title case (not uppercase)
    - No drop shadows
    - Proper class badge-type-challenge
    """

    async def handle_matches_route(route):
        await route.fulfill(
            status=200,
            content_type='application/json',
            body=json.dumps(MOCK_MATCHES_DATA),
        )

    await page.route('**/api/matches*', handle_matches_route)

    # Navigate to /replays
    await page.goto('/replays')
    await expect(page.locator('#replays-page-card')).to_be_visible()

    # Wait for catalog items to render
    items = page.locator('.replay-catalog-item')
    await expect(items).to_have_count(3)

    # First item has Pinpoint + Challenge chips
    first_item = items.nth(0)
    mode_badge = first_item.locator('.badge-mode')
    type_badge = first_item.locator('.badge-type-challenge')

    await expect(mode_badge).to_contain_text('Pinpoint')
    await expect(type_badge).to_contain_text('Challenge')

    # Evaluate CSS styles of type_badge
    styles = await type_badge.evaluate("""el => {
        const cs = window.getComputedStyle(el);
        return {
            borderRadius: cs.borderRadius,
            textTransform: cs.textTransform,
            boxShadow: cs.boxShadow,
            letterSpacing: cs.letterSpacing,
            color: cs.color,
        };
    }""")

    assert styles['borderRadius'] == '6px', f'Expected 6px border-radius, got {styles["borderRadius"]}'
    assert styles['textTransform'] == 'none', f'Expected none text-transform, got {styles["textTransform"]}'
    assert styles['boxShadow'] == 'none', f'Expected none box-shadow, got {styles["boxShadow"]}'

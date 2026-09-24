#!/usr/bin/env python3
"""Automated script to generate high-resolution, privacy-safe, anonymized screenshots
for Immich Quiz documentation and README.
"""

from __future__ import annotations

import asyncio
import socket
import sys
import threading
import time
import urllib.request
from datetime import date
from pathlib import Path
from typing import Any

import uvicorn
from playwright.async_api import Page, async_playwright, expect

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from src.config import AppSettings  # noqa: E402
from src.main import create_app  # noqa: E402
from tests.conftest import CityInfo, FakeImmichClient, PersonInfo, TimelineBounds  # noqa: E402
from tests.e2e.conftest import create_e2e_assets, seed_e2e_metadata  # noqa: E402

DOCS_ASSETS = REPO_ROOT / 'docs' / 'assets'
DOCS_ASSETS.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Beautiful Vector SVG Artwork for Anonymized Travel Scenes
# ---------------------------------------------------------------------------

SCENE_PARIS_SVG = """
<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="900" viewBox="0 0 1200 900">
  <defs>
    <linearGradient id="parisSky" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#121829"/>
      <stop offset="35%" stop-color="#2c1a4d"/>
      <stop offset="65%" stop-color="#8c2e5b"/>
      <stop offset="85%" stop-color="#d45b47"/>
      <stop offset="100%" stop-color="#f7a75e"/>
    </linearGradient>
    <radialGradient id="sunGlow" cx="0.5" cy="0.5" r="0.5">
      <stop offset="0%" stop-color="#fff5db" stop-opacity="1"/>
      <stop offset="40%" stop-color="#fca34d" stop-opacity="0.8"/>
      <stop offset="100%" stop-color="#e24a4a" stop-opacity="0"/>
    </radialGradient>
    <linearGradient id="river" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#4a1936"/>
      <stop offset="100%" stop-color="#150a1f"/>
    </linearGradient>
  </defs>

  <!-- Sky & Setting Sun -->
  <rect width="1200" height="700" fill="url(#parisSky)"/>
  <circle cx="720" cy="500" r="140" fill="url(#sunGlow)"/>

  <!-- Seine River -->
  <rect y="700" width="1200" height="200" fill="url(#river)"/>
  <ellipse cx="600" cy="730" rx="350" ry="15" fill="#f7a75e" opacity="0.35"/>
  <ellipse cx="620" cy="760" rx="220" ry="10" fill="#f7a75e" opacity="0.25"/>

  <!-- Distant Skyline & Trees -->
  <path d="M0,700 Q150,680 300,695 T600,685 T900,690 T1200,685 L1200,705 L0,705 Z" fill="#180e22" opacity="0.9"/>

  <!-- Parisian Haussmann Rooftops Silhouette -->
  <path d="M0,700 L60,650 L120,650 L140,630 L180,630 L200,650 L260,640 L280,610 L340,610 L370,660 L440,645
           L480,630 L520,630 L550,670 L600,665 L660,650 L720,650 L780,620 L840,620 L870,660 L920,640
           L980,640 L1020,615 L1080,615 L1120,645 L1200,640 L1200,700 Z" fill="#0d0714"/>

  <!-- Eiffel Tower Silhouette -->
  <g fill="#08040d" transform="translate(680, 220)">
    <polygon points="50,0 48,90 52,90"/>
    <rect x="46" y="90" width="8" height="25" rx="2"/>
    <rect x="44" y="115" width="12" height="15"/>
    <circle cx="50" cy="85" r="4" fill="#ffd166"/>
    <rect x="36" y="130" width="28" height="8" rx="2"/>
    <polygon points="44,138 34,250 66,250 56,138"/>
    <rect x="24" y="250" width="52" height="14" rx="3"/>
    <polygon points="32,264 6,430 24,430 46,264"/>
    <polygon points="68,264 94,430 76,430 54,264"/>
    <path d="M18,430 Q50,330 82,430 L74,430 Q50,345 26,430 Z" fill="#08040d"/>
  </g>

  <!-- Foreground Bridge & Streetlamp -->
  <rect y="740" width="450" height="160" fill="#08040d" rx="10"/>
  <circle cx="380" cy="720" r="14" fill="#ffeaa7" opacity="0.95"/>
  <rect x="377" y="730" width="6" height="50" fill="#08040d"/>

  <!-- Photo Watermark -->
  <text x="1150" y="860" font-family="-apple-system, BlinkMacSystemFont, sans-serif"
        font-size="28" font-weight="600" fill="#ffffff" opacity="0.4" text-anchor="end">Paris · France</text>
</svg>
"""

SCENE_TOKYO_SVG = """
<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="900" viewBox="0 0 1200 900">
  <defs>
    <linearGradient id="fujiSky" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#1e1338"/>
      <stop offset="45%" stop-color="#4a256d"/>
      <stop offset="75%" stop-color="#a44279"/>
      <stop offset="100%" stop-color="#fca07a"/>
    </linearGradient>
    <linearGradient id="fujiSnow" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#ffffff"/>
      <stop offset="80%" stop-color="#f0d5e2"/>
      <stop offset="100%" stop-color="#b689a0"/>
    </linearGradient>
    <linearGradient id="fujiRock" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#2d1a3b"/>
      <stop offset="100%" stop-color="#11091a"/>
    </linearGradient>
  </defs>

  <rect width="1200" height="900" fill="url(#fujiSky)"/>
  <circle cx="600" cy="420" r="160" fill="#ff4757" opacity="0.9"/>
  <polygon points="120,780 600,240 1080,780" fill="url(#fujiRock)"/>
  <path d="M480,400 L600,240 L720,400 Q680,440 650,410 Q620,450 600,415
           Q580,450 550,410 Q520,440 480,400 Z" fill="url(#fujiSnow)"/>
  <rect y="740" width="1200" height="160" fill="#140b22"/>
  <polygon points="260,740 600,880 940,740" fill="#2d1a3b" opacity="0.3"/>

  <!-- Pagoda & Branch -->
  <g fill="#0b0612">
    <polygon points="180,520 80,560 280,560"/>
    <polygon points="180,570 70,610 290,610"/>
    <polygon points="180,620 50,670 310,670"/>
    <rect x="110" y="670" width="140" height="80"/>
    <line x1="180" y1="480" x2="180" y2="520" stroke="#0b0612" stroke-width="6"/>
  </g>
  <path d="M800,0 Q950,150 1200,100 M920,80 Q1050,220 1200,200" stroke="#0b0612" stroke-width="8" fill="none"/>
  <circle cx="950" cy="110" r="12" fill="#ff7675"/>
  <circle cx="980" cy="90" r="14" fill="#ff7675"/>
  <circle cx="1040" cy="160" r="15" fill="#ff7675"/>
  <circle cx="1080" cy="140" r="12" fill="#ff7675"/>

  <!-- Photo Watermark -->
  <text x="1150" y="860" font-family="-apple-system, BlinkMacSystemFont, sans-serif"
        font-size="28" font-weight="600" fill="#ffffff" opacity="0.4" text-anchor="end">Tokyo · Japan</text>
</svg>
"""


def get_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('127.0.0.1', 0))
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return int(s.getsockname()[1])


class ScenicImmichClient(FakeImmichClient):
    """Fake Immich Client returning high-res synthesized scenic travel photos."""

    def __init__(self, scenes: list[bytes], **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.scenes = scenes

    async def get_asset_bytes(self, library_name: str, asset_id: str) -> tuple[bytes, str]:
        # Cycle through scenic photos based on asset hash
        idx = hash(asset_id) % len(self.scenes)
        return self.scenes[idx], 'image/png'


async def render_svg_to_png(page: Page, svg_content: str) -> bytes:
    html = (
        '<!DOCTYPE html><html>'
        f"<body style='margin:0;padding:0;background:#000;overflow:hidden;'>{svg_content}</body>"
        '</html>'
    )
    await page.set_content(html)
    return await page.locator('svg').screenshot(type='png')


async def main() -> None:
    print('[*] Launching headless browser to synthesize scenic travel photos...')
    port = get_free_port()
    base_url = f'http://127.0.0.1:{port}'

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        render_page = await browser.new_page(viewport={'width': 1200, 'height': 900})

        paris_png = await render_svg_to_png(render_page, SCENE_PARIS_SVG)
        tokyo_png = await render_svg_to_png(render_page, SCENE_TOKYO_SVG)
        await render_page.close()

        # Setup full rich test assets
        assets = create_e2e_assets()
        immich_client = ScenicImmichClient(
            scenes=[paris_png, tokyo_png],
            assets=assets,
            people=[
                PersonInfo(id='p1', name='Alice'),
                PersonInfo(id='p2', name='Bob'),
                PersonInfo(id='p3', name='Charlie'),
            ],
            timeline_bounds=TimelineBounds(min_date=date(2019, 1, 1), max_date=date(2024, 12, 31)),
            countries=['Brazil', 'France', 'Japan', 'United States', 'Australia', 'Italy'],
            cities=[
                CityInfo(name='Florianopolis', country='Brazil'),
                CityInfo(name='Paris', country='France'),
                CityInfo(name='Tokyo', country='Japan'),
                CityInfo(name='New York', country='United States'),
            ],
        )

        tmp_data = REPO_ROOT / 'scratch' / 'screenshots_data'
        tmp_data.mkdir(parents=True, exist_ok=True)

        settings = AppSettings(
            immich_server_url='https://photos.example.com/api',
            immich_libraries={'Family': 'token123'},
            app_title='Immich Quiz',
            app_tagline='Photo trivia powered by your Immich library',
            app_host='127.0.0.1',
            app_port=port,
            language='EN',
            data_path=tmp_data,
            auto_sync_on_startup=False,
        )

        app = create_app(settings=settings)
        app.state.immich_client = immich_client
        if hasattr(app.state, 'metadata_store'):
            seed_e2e_metadata(app.state.metadata_store, 'Family', assets)

        config = uvicorn.Config(app=app, host='127.0.0.1', port=port, log_level='warning')
        server = uvicorn.Server(config=config)

        def run_server() -> None:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(server.serve())
            finally:
                loop.close()

        server_thread = threading.Thread(target=run_server, daemon=True)
        server_thread.start()

        deadline = time.time() + 10.0
        while time.time() < deadline:
            try:
                with urllib.request.urlopen(f'{base_url}/') as r:
                    if r.status == 200:
                        break
            except Exception:
                time.sleep(0.05)

        print(f'[+] Server running at {base_url}')

        context = await browser.new_context(
            viewport={'width': 1280, 'height': 960},
            device_scale_factor=2,  # Retina high DPI
        )
        page = await context.new_page()

        # Set dark theme & english
        await page.goto(base_url)
        await page.evaluate(
            "() => { localStorage.setItem('immich_quiz_theme', 'dark'); "
            "localStorage.setItem('immich_quiz_language', 'en-US'); }"
        )
        await page.reload()
        await page.wait_for_selector('#setup-card')
        await asyncio.sleep(0.8)

        # -------------------------------------------------------------------
        # Screenshot 1: Home Lobby (Dark Mode Setup with Bento layout)
        # -------------------------------------------------------------------
        print('[*] Capturing Screenshot 1: Lobby Setup Screen (docs/assets/home.webp)...')
        accordion_toggle = page.locator('#filter-accordion-toggle')
        if await accordion_toggle.is_visible():
            await accordion_toggle.click()
            await asyncio.sleep(0.4)

        await page.screenshot(path=str(DOCS_ASSETS / 'home.webp'))
        print(f'    Saved: {DOCS_ASSETS / "home.webp"}')

        # -------------------------------------------------------------------
        # Screenshot 2: Interactive Gameplay (Pinpoint Location & Date)
        # -------------------------------------------------------------------
        print('[*] Launching game for Screenshot 2: Gameplay Screen (docs/assets/gameplay_pinpoint.webp)...')
        # Ensure 5 rounds
        await page.locator('#round-count button[data-value="5"]').click()

        prepare_btn = page.locator('#prepare-game-btn')
        await prepare_btn.click()

        # Add second player in local modal for realistic multiplayer podium & comparisons
        player_input = page.locator('#player-text-input')
        if await player_input.is_visible():
            await player_input.fill('Taylor')
            await page.keyboard.press('Enter')
            await asyncio.sleep(0.3)

        # Start match in local modal
        start_btn = page.locator('#start-match-btn')
        await start_btn.click()

        pass_overlay = page.locator('#pass-overlay')
        ready_btn = page.locator('#ready-btn')
        submit_btn = page.locator('#submit-answer')
        next_btn = page.locator('#next-round')

        async def pass_and_ready():
            await expect(pass_overlay).to_be_visible()
            await ready_btn.click()
            await expect(pass_overlay).to_be_hidden()
            await expect(page.locator('#quiz-image')).to_be_visible()

        month_select = page.locator('#date-guess-month')
        year_select = page.locator('#date-guess-year')
        guess_map = page.locator('#guess-map')

        async def make_guess(x: int, y: int, year: str, month: str):
            for _ in range(6):
                await guess_map.click(position={'x': x, 'y': y})
                await asyncio.sleep(0.3)
                if await submit_btn.is_enabled():
                    break
                await page.evaluate(
                    f'() => {{ if (window.__state && window.__state.guessMap) '
                    f"window.__state.guessMap.fire('click', {{ latlng: L.latLng({x / 4}, {y / 4}) }}); }}"
                )
                await asyncio.sleep(0.2)
                if await submit_btn.is_enabled():
                    break

            if await month_select.is_visible():
                await month_select.select_option(value=month)
            if await year_select.is_visible():
                await year_select.select_option(value=year)
            await asyncio.sleep(0.2)

        # --- Round 1: Player 1 (Turn) ---
        await pass_and_ready()
        await make_guess(160, 140, '2021', '6')

        await page.evaluate('() => window.scrollTo(0, 0)')
        await asyncio.sleep(0.5)
        await page.screenshot(path=str(DOCS_ASSETS / 'gameplay_pinpoint.webp'))
        print(f'    Saved: {DOCS_ASSETS / "gameplay_pinpoint.webp"}')

        # Player 1 submits
        await submit_btn.click()

        # --- Round 1: Player 2 (Taylor) ---
        await pass_and_ready()
        await make_guess(210, 170, '2020', '8')

        # -------------------------------------------------------------------
        # Screenshot 3: Round Reveal (Distance, Points, Golden Star)
        # -------------------------------------------------------------------
        print('[*] Submitting guess for Screenshot 3: Round Reveal Screen (docs/assets/round_reveal.webp)...')
        await submit_btn.click()

        # Reveal screen
        await page.wait_for_selector('#reveal-ui', state='visible')
        await asyncio.sleep(1.8)  # Wait for score rollup animations to finish

        await page.screenshot(path=str(DOCS_ASSETS / 'round_reveal.webp'))
        print(f'    Saved: {DOCS_ASSETS / "round_reveal.webp"}')

        # -------------------------------------------------------------------
        # Screenshot 4: Winner Podium & Summary Review Deck
        # -------------------------------------------------------------------
        print('[*] Fast-forwarding rounds for Screenshot 4: Winner Podium (docs/assets/summary_podium.webp)...')
        await next_btn.click()

        # Play remaining 4 rounds (rounds 2 through 5)
        for _round_num in range(2, 6):
            # Player 1 turn
            await pass_and_ready()
            await make_guess(180, 150, '2021', '4')
            await submit_btn.click()

            # Player 2 turn
            await pass_and_ready()
            await make_guess(150, 160, '2020', '9')
            await submit_btn.click()

            # Reveal -> Advance
            await page.wait_for_selector('#reveal-ui', state='visible')
            await asyncio.sleep(0.4)
            await next_btn.click()

        # Final screen: Summary card
        await page.wait_for_selector('#summary-card', state='visible')
        await page.wait_for_selector('#summary-winner', state='visible')
        await asyncio.sleep(2.0)  # Wait for 3D podium and confetti animations

        await page.screenshot(path=str(DOCS_ASSETS / 'summary_podium.webp'))
        print(f'    Saved: {DOCS_ASSETS / "summary_podium.webp"}')

        await browser.close()
        print('\n[+] All 4 documentation screenshots generated successfully with zero personal photos!')


if __name__ == '__main__':
    asyncio.run(main())

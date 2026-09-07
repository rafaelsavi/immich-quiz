"""Playwright E2E tests for dynamic language switching across all screens without page reload."""

from __future__ import annotations

import re

from playwright.async_api import Page, expect


async def _ensure_language(page: Page, target_lang: str) -> None:
    """Ensure page is set to target_lang ('en-US' or 'pt-BR') without page reload."""
    current_lang = await page.evaluate("() => localStorage.getItem('immich_quiz_language') || 'en-US'")
    if current_lang != target_lang:
        await page.locator('#lang-toggle-btn').click()
        # Brief tick for DOM dispatch
        await page.wait_for_timeout(100)


async def test_lobby_setup_dynamic_language_switch(page: Page) -> None:
    """Verify that toggling language dynamically updates all lobby/setup elements without reload or losing icons."""
    await page.goto('/')
    await page.wait_for_selector('#setup-card')
    await _ensure_language(page, 'en-US')

    # 1. Verify English initial states
    setup_heading = page.locator('#setup-card h2').first
    await expect(setup_heading).to_have_text('Game Setup')

    prepare_btn = page.locator('#prepare-game-btn')
    await expect(prepare_btn).to_be_visible()
    # Ensure gamepad emoji is present
    await expect(prepare_btn.locator('.btn-icon')).to_have_text('🎮')
    await expect(prepare_btn.locator("span[data-i18n='setup.prepare_game_label']")).to_have_text('Prepare Game')

    sync_btn_label = page.locator('#sync-btn-label')
    await expect(sync_btn_label).to_have_text(re.compile(r'Sync( library)?'))

    # Open filters accordion to inspect multi-select search input placeholders
    await page.locator('#filters-toggle-btn').click()
    await expect(page.locator('#filters-accordion-content')).to_be_visible()

    library_search = page.locator('#library-multi-select .multi-select-search')
    await expect(library_search).to_have_attribute('placeholder', 'Search libraries...')

    country_search = page.locator('#country-multi-select .multi-select-search')
    await expect(country_search).to_have_attribute('placeholder', 'Search countries...')

    # Audio button title
    audio_btn = page.locator('#audio-toggle-btn')
    await expect(audio_btn).to_have_attribute('title', 'Toggle Sound Effects')

    # Leaderboard scope pill & empty cell
    scope_pill = page.locator('#leaderboard-scope-pill')
    await expect(scope_pill).to_contain_text('Full Library')

    empty_cell = page.locator('#leaderboard-table .leaderboard-empty-cell')
    await expect(empty_cell).to_contain_text('No games recorded for this configuration yet.')

    # 2. Toggle to Portuguese
    await page.locator('#lang-toggle-btn').click()

    # Verify Portuguese updates dynamically WITHOUT reloading the page
    await expect(setup_heading).to_have_text('Configuração do Jogo')
    # Verify gamepad emoji was NOT wiped out by translation!
    await expect(prepare_btn.locator('.btn-icon')).to_have_text('🎮')
    await expect(prepare_btn.locator("span[data-i18n='setup.prepare_game_label']")).to_have_text('Preparar Jogo')

    await expect(sync_btn_label).to_have_text(re.compile(r'Sincronizar( biblioteca)?'))
    await expect(library_search).to_have_attribute('placeholder', 'Pesquisar bibliotecas...')
    await expect(country_search).to_have_attribute('placeholder', 'Pesquisar países...')
    await expect(audio_btn).to_have_attribute('title', 'Efeitos de Som: Ativados')
    await expect(scope_pill).to_contain_text('Toda a Biblioteca')
    await expect(empty_cell).to_contain_text('Nenhum jogo registrado para esta configuração ainda.')

    # 3. Toggle back to English
    await page.locator('#lang-toggle-btn').click()

    await expect(setup_heading).to_have_text('Game Setup')
    await expect(prepare_btn.locator('.btn-icon')).to_have_text('🎮')
    await expect(prepare_btn.locator("span[data-i18n='setup.prepare_game_label']")).to_have_text('Prepare Game')
    await expect(sync_btn_label).to_have_text(re.compile(r'Sync( library)?'))
    await expect(library_search).to_have_attribute('placeholder', 'Search libraries...')
    await expect(audio_btn).to_have_attribute('title', 'Sound Effects: Enabled')
    await expect(scope_pill).to_contain_text('Full Library')


async def test_modal_dynamic_language_switch(page: Page) -> None:
    """Verify modal contents and close buttons translate dynamically when language changes."""
    await page.goto('/')
    await _ensure_language(page, 'en-US')

    # Open Prepare Game modal
    await page.locator('#prepare-game-btn').click()
    modal = page.locator('#prepare-game-modal')
    await expect(modal).to_be_visible()

    # English state
    await expect(modal.locator('#prepare-modal-title')).to_have_text('Prepare Game')
    await expect(modal.locator('#tab-local-game')).to_contain_text('Local Game')
    await expect(modal.locator('#tab-challenge-game')).to_contain_text('Challenge Link')
    start_btn = modal.locator('#start-match-btn')
    await expect(start_btn.locator('.btn-icon')).to_have_text('🚀')
    await expect(start_btn).to_contain_text('Start Game')
    close_btn = modal.locator('#prepare-modal-close-btn')
    await expect(close_btn).to_have_attribute('title', 'Close')

    # Toggle to Portuguese while modal is open (via DOM dispatch to avoid backdrop interception)
    await page.evaluate("() => document.getElementById('lang-toggle-btn').click()")

    await expect(modal.locator('#prepare-modal-title')).to_have_text('Preparar Jogo')
    await expect(modal.locator('#tab-local-game')).to_contain_text('Jogo Local')
    await expect(modal.locator('#tab-challenge-game')).to_contain_text('Link do Desafio')
    # Rocket icon must NOT be wiped!
    await expect(start_btn.locator('.btn-icon')).to_have_text('🚀')
    await expect(start_btn).to_contain_text('Iniciar Jogo')
    await expect(close_btn).to_have_attribute('title', 'Fechar')

    # Close modal
    await close_btn.click()
    await expect(modal).to_be_hidden()


async def test_pinpoint_gameplay_and_reveal_dynamic_language_switch(page: Page) -> None:
    """Verify active Pinpoint gameplay round meta, timer, and reveal table translate dynamically."""
    await page.goto('/')
    await _ensure_language(page, 'en-US')

    # Start match
    await page.locator('#prepare-game-btn').click()
    await page.locator('#start-match-btn').click()

    if await page.locator('#pass-overlay').is_visible():
        await page.locator('#ready-btn').click()
        await expect(page.locator('#pass-overlay')).to_be_hidden()

    await expect(page.locator('#game-card')).to_be_visible()
    await expect(page.locator('#guessing-ui')).to_be_visible()

    # 1. Gameplay screen in English
    round_meta = page.locator('#round-meta')
    await expect(round_meta).to_contain_text(re.compile(r'Round 1 of'))

    submit_btn = page.locator('#submit-answer')
    await expect(submit_btn).to_have_text('Submit Guess')

    timer_label = page.locator('#timer-label')
    await expect(timer_label).to_contain_text(re.compile(r'Time left|Unlimited', re.IGNORECASE))

    # Toggle language to PT during active guessing
    await page.locator('#lang-toggle-btn').click()

    # Verify dynamic updates during guessing
    await expect(round_meta).to_contain_text(re.compile(r'Rodada 1 de'))
    await expect(submit_btn).to_have_text('Confirmar Palpite')
    await expect(timer_label).to_contain_text(re.compile(r'Tempo restante|Sem limite', re.IGNORECASE))

    # Toggle back to EN
    await page.locator('#lang-toggle-btn').click()
    await expect(round_meta).to_contain_text(re.compile(r'Round 1 of'))
    await expect(submit_btn).to_have_text('Submit Guess')

    # Place a guess on the map to enable submit
    guess_map = page.locator('#guess-map')
    await expect(guess_map).to_be_visible()
    await guess_map.click(position={'x': 100, 'y': 100})
    await expect(submit_btn).to_be_enabled()
    await submit_btn.click()

    # 2. Reveal screen
    reveal_ui = page.locator('#reveal-ui')
    await expect(reveal_ui).to_be_visible()

    next_round_btn = page.locator('#next-round')
    await expect(next_round_btn).to_contain_text(re.compile(r'Next Round|See Results'))

    reveal_table = page.locator('#reveal-table')
    await expect(reveal_table).to_contain_text('Score')

    # Toggle language on reveal screen
    await page.locator('#lang-toggle-btn').click()

    await expect(next_round_btn).to_contain_text(re.compile(r'Próxima Rodada|Ver Resultados'))
    await expect(reveal_table).to_contain_text('Pontuação')

    # Toggle back to English
    await page.locator('#lang-toggle-btn').click()
    await expect(next_round_btn).to_contain_text(re.compile(r'Next Round|See Results'))
    await expect(reveal_table).to_contain_text('Score')


async def test_album_shuffle_gameplay_dynamic_language_switch(page: Page) -> None:
    """Verify Album Shuffle timeline headers and reordering button tooltips translate dynamically."""
    await page.goto('/')
    await _ensure_language(page, 'en-US')

    # Select Album Shuffle mode
    await page.locator('#mode-album-shuffle-btn').click()
    await expect(page.locator('#mode-album-shuffle-btn')).to_have_class(re.compile(r'active'))

    # Start match
    await page.locator('#prepare-game-btn').click()
    await page.locator('#start-match-btn').click()

    if await page.locator('#pass-overlay').is_visible():
        await page.locator('#ready-btn').click()
        await expect(page.locator('#pass-overlay')).to_be_hidden()

    shuffle_ui = page.locator('#album-shuffle-ui')
    await expect(shuffle_ui).to_be_visible()

    cards = page.locator('#shuffle-cards-list .shuffle-card-row')
    await expect(cards).to_have_count(3)

    # 1. Verify English timeline headers and rank button titles
    oldest_header = page.locator('#shuffle-cards-list .shuffle-timeline-header.oldest')
    if await oldest_header.is_visible():
        await expect(oldest_header).to_contain_text('First')

    newest_header = page.locator('#shuffle-cards-list .shuffle-timeline-header.newest')
    if await newest_header.is_visible():
        await expect(newest_header).to_contain_text('Last')

    down_btn = cards.first.locator("button.shuffle-rank-btn:has-text('▼')")
    await expect(down_btn).to_have_attribute('title', 'Move Down (Later)')

    up_btn = cards.last.locator("button.shuffle-rank-btn:has-text('▲')")
    await expect(up_btn).to_have_attribute('title', 'Move Up (Earlier)')

    # 2. Toggle language to PT during active Album Shuffle guessing
    await page.locator('#lang-toggle-btn').click()

    if await oldest_header.is_visible():
        await expect(oldest_header).to_contain_text('Primeira')
    if await newest_header.is_visible():
        await expect(newest_header).to_contain_text('Última')

    # Verify buttons dynamically updated their titles
    await expect(down_btn).to_have_attribute('title', 'Mover para Baixo (Mais Recente)')
    await expect(up_btn).to_have_attribute('title', 'Mover para Cima (Mais Antiga)')

    # 3. Toggle back to English
    await page.locator('#lang-toggle-btn').click()
    if await oldest_header.is_visible():
        await expect(oldest_header).to_contain_text('First')
    if await newest_header.is_visible():
        await expect(newest_header).to_contain_text('Last')
    await expect(down_btn).to_have_attribute('title', 'Move Down (Later)')
    await expect(up_btn).to_have_attribute('title', 'Move Up (Earlier)')

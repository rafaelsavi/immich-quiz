"""Playwright E2E tests for dynamic language switching across all screens without page reload."""

from __future__ import annotations

import re

from playwright.async_api import Page, expect


async def _toggle_language(page: Page) -> None:
    """Toggle language between English and Portuguese without page reload."""
    await page.evaluate("() => document.getElementById('lang-toggle-btn')?.click()")
    # Brief tick for DOM dispatch
    await page.wait_for_timeout(150)


async def _ensure_language(page: Page, target_lang: str) -> None:
    """Ensure page is set to target_lang ('en-US' or 'pt-BR') without page reload."""
    current_lang = await page.evaluate("() => localStorage.getItem('immich_quiz_language') || 'en-US'")
    if current_lang != target_lang:
        await _toggle_language(page)


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
    await _toggle_language(page)

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
    await _toggle_language(page)

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
    await expect(modal.locator('#tab-challenge-game')).to_contain_text('Challenge')
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
    await _toggle_language(page)

    # Verify dynamic updates during guessing
    await expect(round_meta).to_contain_text(re.compile(r'Rodada 1 de'))
    await expect(submit_btn).to_have_text('Confirmar Palpite')
    await expect(timer_label).to_contain_text(re.compile(r'Tempo restante|Sem limite', re.IGNORECASE))

    # Toggle back to EN
    await _toggle_language(page)
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
    await _toggle_language(page)

    await expect(next_round_btn).to_contain_text(re.compile(r'Próxima Rodada|Ver Resultados'))
    await expect(reveal_table).to_contain_text('Pontuação')

    # Toggle back to English
    await _toggle_language(page)
    await expect(next_round_btn).to_contain_text(re.compile(r'Next Round|See Results'))
    await expect(reveal_table).to_contain_text('Score')


async def test_unshuffle_gameplay_dynamic_language_switch(page: Page) -> None:
    """Verify Unshuffle timeline headers and reordering button tooltips translate dynamically."""
    await page.goto('/')
    await _ensure_language(page, 'en-US')

    # Select Unshuffle mode
    await page.locator('#mode-unshuffle-btn').click()
    await expect(page.locator('#mode-unshuffle-btn')).to_have_class(re.compile(r'active'))

    # Start match
    await page.locator('#prepare-game-btn').click()
    await page.locator('#start-match-btn').click()

    if await page.locator('#pass-overlay').is_visible():
        await page.locator('#ready-btn').click()
        await expect(page.locator('#pass-overlay')).to_be_hidden()

    shuffle_ui = page.locator('#unshuffle-ui')
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

    # 2. Toggle language to PT during active Unshuffle guessing
    await _toggle_language(page)

    if await oldest_header.is_visible():
        await expect(oldest_header).to_contain_text('Primeira')
    if await newest_header.is_visible():
        await expect(newest_header).to_contain_text('Última')

    # Verify buttons dynamically updated their titles
    await expect(down_btn).to_have_attribute('title', 'Mover para Baixo (Mais Recente)')
    await expect(up_btn).to_have_attribute('title', 'Mover para Cima (Mais Antiga)')

    # 3. Toggle back to English
    await _toggle_language(page)
    if await oldest_header.is_visible():
        await expect(oldest_header).to_contain_text('First')
    if await newest_header.is_visible():
        await expect(newest_header).to_contain_text('Last')
    await expect(down_btn).to_have_attribute('title', 'Move Down (Later)')
    await expect(up_btn).to_have_attribute('title', 'Move Up (Earlier)')


async def test_stats_hub_and_replay_dynamic_language_switch(page: Page) -> None:
    """Verify that all new v3.1.0 pages (/players directory, replays, leaderboard,
    player profile, and round replay) support realtime translation.
    """
    await page.goto('/players')
    await page.wait_for_selector('#stats-page-card')
    await _ensure_language(page, 'en-US')

    # 1. /players Page in English
    await expect(page.locator('#stats-page-heading')).to_have_text('Player Directory & Statistics')
    await expect(page.locator('#stats-players-search')).to_have_attribute('placeholder', 'Search players by name...')

    # Replays page in English
    await page.goto('/replays')
    await page.wait_for_selector('#replays-page-card')
    await expect(page.locator('#replays-page-heading')).to_have_text('Match Replays')
    await expect(page.locator('#stats-replays-player-search')).to_have_attribute('placeholder', 'Filter by player...')
    await expect(page.locator('#stats-replays-mode-filter option[value="all"]')).to_have_text('All Modes')
    await expect(page.locator('#stats-replays-mode-filter option[value="pinpoint"]')).to_have_text('🎯 Pinpoint')
    await expect(page.locator('#stats-replays-mode-filter option[value="unshuffle"]')).to_have_text('🔀 Unshuffle')
    await expect(page.locator('#stats-replays-type-filter option[value="all"]')).to_have_text('All Types')
    await expect(page.locator('#stats-replays-type-filter option[value="local"]')).to_have_text('👥 Local Match')
    await expect(page.locator('#stats-replays-type-filter option[value="challenge"]')).to_have_text('⚔️ Challenge')

    # 2. Toggle to Portuguese in realtime
    await _toggle_language(page)
    await expect(page.locator('#replays-page-heading')).to_have_text('Replays de Partidas')
    await expect(page.locator('#replays-page-desc')).to_have_text(
        'Reviva partidas passadas com mapas interativos rodada a rodada e fotos.'
    )
    await expect(page.locator('#stats-replays-player-search')).to_have_attribute(
        'placeholder', 'Filtrar por jogador...'
    )
    await expect(page.locator('#stats-replays-mode-filter option[value="all"]')).to_have_text('Todos os Modos')
    await expect(page.locator('#stats-replays-mode-filter option[value="pinpoint"]')).to_have_text('🎯 Pinpoint')
    await expect(page.locator('#stats-replays-mode-filter option[value="unshuffle"]')).to_have_text('🔀 Embaralhado')
    await expect(page.locator('#stats-replays-type-filter option[value="all"]')).to_have_text('Todos os Tipos')
    await expect(page.locator('#stats-replays-type-filter option[value="local"]')).to_have_text('👥 Partida Local')
    await expect(page.locator('#stats-replays-type-filter option[value="challenge"]')).to_have_text('⚔️ Desafio')

    # Players page in Portuguese
    await page.goto('/players')
    await page.wait_for_selector('#stats-page-card')
    await expect(page.locator('#stats-page-heading')).to_have_text('Diretório de Jogadores & Estatísticas')
    await expect(page.locator('#stats-players-search')).to_have_attribute('placeholder', 'Buscar jogadores por nome...')

    # 3. Test Match Replay page with mocked data
    async def handle_replay_route(route):
        await route.fulfill(
            status=200,
            content_type='application/json',
            json={
                'match_id': 'mock-match-1',
                'game_mode': 'pinpoint',
                'play_mode': 'local',
                'played_at': '2026-09-12T10:00:00Z',
                'rounds': 1,
                'players': ['Alice', 'Bob'],
                'winners': ['Alice'],
                'top_score': 250,
                'top_accuracy_pct': 92.5,
                'rounds_data': [
                    {
                        'round_number': 1,
                        'asset_id': 'asset-1',
                        'actual_latitude': 48.856,
                        'actual_longitude': 2.352,
                        'actual_date': '2023-06-15',
                        'actual_city': 'Paris',
                        'actual_country': 'France',
                        'player_guesses': [
                            {
                                'player_name': 'Alice',
                                'player_color': '#ff5722',
                                'guess_latitude': 48.857,
                                'guess_longitude': 2.353,
                                'distance_km': 0.1,
                                'round_score': 150,
                                'cumulative_score': 150,
                                'time_taken_seconds': 4.2,
                            },
                        ],
                    }
                ],
            },
        )

    await page.route('**/api/match/mock-match-1/replay', handle_replay_route)

    # Navigate to /game/mock-match-1/replay
    await page.goto('/game/mock-match-1/replay')
    await expect(page.locator('#replay-page-card')).to_be_visible()

    # Still in Portuguese from previous toggle
    await expect(page.locator('#replay-round-indicator')).to_contain_text(re.compile(r'Rodada 1 de 1', re.IGNORECASE))
    await expect(page.locator('#replay-scoreboard-round-tag')).to_contain_text(re.compile(r'Após R1', re.IGNORECASE))
    await expect(page.locator('#replay-back-btn')).to_contain_text('Sair do Replay')
    await expect(page.locator("span[data-i18n='replay.player_guess_heading']")).to_have_text('Palpites dos Jogadores')

    # Realtime toggle replay to English
    await _toggle_language(page)
    await expect(page.locator('#replay-round-indicator')).to_contain_text(re.compile(r'Round 1 of 1', re.IGNORECASE))
    await expect(page.locator('#replay-scoreboard-round-tag')).to_contain_text(re.compile(r'After R1', re.IGNORECASE))
    await expect(page.locator('#replay-back-btn')).to_contain_text('Exit Replay')
    await expect(page.locator("span[data-i18n='replay.player_guess_heading']")).to_have_text('Player Guesses')

    # 4. Test Player Profile with mocked data
    async def handle_profile_route(route):
        await route.fulfill(
            status=200,
            content_type='application/json',
            json={
                'player': {
                    'player_name': 'Alice',
                    'avatar_color': '#ff5722',
                    'first_played_at': '2026-01-01T12:00:00Z',
                    'matches_played': 10,
                    'matches_won': 7,
                    'win_rate_pct': 70.0,
                    'career_points': 24500,
                    'avg_accuracy_pct': 85.0,
                    'peak_match_accuracy_pct': 98.0,
                    'podiums_count': 9,
                },
                'analytics': {
                    'best_distance_km': 0.1,
                    'perfect_location_rounds_count': 3,
                    'avg_location_accuracy_pct': 88.0,
                    'avg_date_accuracy_pct': 82.0,
                    'exact_year_month_pct': 75.0,
                    'exact_year_pct': 90.0,
                    'perfect_date_rounds_count': 5,
                    'avg_response_time_seconds': 5.4,
                    'fastest_response_time_seconds': 2.1,
                    'total_active_time_seconds': 3600,
                    'preferred_cadence': 'Casual',
                    'location_tiers': [
                        {'tier_key': 'top', 'label': 'Top', 'count': 6, 'percentage': 60.0},
                    ],
                    'date_tiers': [
                        {'tier_key': 'top', 'label': 'Top', 'count': 5, 'percentage': 50.0},
                    ],
                    'mode_mastery': [
                        {'game_mode': 'pinpoint', 'matches_played': 6, 'wins': 4, 'avg_accuracy_pct': 88.0},
                    ],
                },
                'recent_matches': [
                    {
                        'match_id': 'mock-match-1',
                        'game_mode': 'pinpoint',
                        'played_at': '2026-09-12T10:00:00Z',
                        'rank': 1,
                        'total_score': 4800,
                        'accuracy_pct': 96.0,
                        'is_winner': True,
                    }
                ],
            },
        )

    await page.route('**/api/players/Alice/profile', handle_profile_route)

    # Navigate to /players/Alice
    await page.goto('/players/Alice')
    await expect(page.locator('#stats-page-card')).to_be_visible()
    await expect(page.locator('#stats-profile-view')).to_be_visible()

    # In English
    await expect(page.locator('#stats-page-heading')).to_have_text('Player Profile')
    await expect(page.locator('#profile-back-to-hub-btn')).to_contain_text('Back to Players')
    await expect(page.locator('.player-profile-view h3').first).to_contain_text('Location Accuracy')

    # Realtime toggle profile to Portuguese
    await _toggle_language(page)
    await expect(page.locator('#stats-page-heading')).to_have_text('Perfil do Jogador')
    await expect(page.locator('#profile-back-to-hub-btn')).to_contain_text('Voltar para Jogadores')
    await expect(page.locator('.player-profile-view h3').first).to_contain_text('Precisão de Localização')

    # Realtime toggle back to English
    await _toggle_language(page)
    await expect(page.locator('#stats-page-heading')).to_have_text('Player Profile')
    await expect(page.locator('#profile-back-to-hub-btn')).to_contain_text('Back to Players')
    await expect(page.locator('.player-profile-view h3').first).to_contain_text('Location Accuracy')


async def test_settings_menu_dropdown_interaction(page: Page) -> None:
    """Verify that settings gear dropdown opens on hover/click, switches language/audio,
    and dismisses on outside click.
    """
    await page.goto('/')
    await page.wait_for_selector('#setup-card')
    await _ensure_language(page, 'en-US')

    settings_toggle = page.locator('#settings-toggle-btn')
    settings_menu = page.locator('#settings-menu')
    lang_btn = page.locator('#lang-toggle-btn')
    audio_btn = page.locator('#audio-toggle-btn')

    await expect(settings_toggle).to_be_visible()
    await expect(settings_menu).not_to_be_visible()

    # 1. Desktop Hover Interaction: hover over gear reveals menu
    await settings_toggle.hover()
    await expect(settings_menu).to_be_visible()
    await expect(lang_btn).to_be_visible()
    await expect(audio_btn).to_be_visible()

    # Moving mouse away hides menu
    await page.mouse.move(0, 0)
    await expect(settings_menu).not_to_be_visible()

    # 2. Click Interaction: toggle open
    await settings_toggle.click()
    await expect(settings_menu).to_be_visible()
    await expect(settings_toggle).to_have_attribute('aria-expanded', 'true')

    # 3. Toggle language from inside the open menu
    await lang_btn.click()
    setup_heading = page.locator('#setup-card h2').first
    await expect(setup_heading).to_have_text('Configuração do Jogo')

    # 4. Test outside click dismiss
    await settings_toggle.click()
    await expect(settings_menu).to_be_visible()
    await page.locator('#setup-card').click()
    await expect(settings_menu).not_to_be_visible()
    await expect(settings_toggle).to_have_attribute('aria-expanded', 'false')

    # Restore language to English
    await _ensure_language(page, 'en-US')

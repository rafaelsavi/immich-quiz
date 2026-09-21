"""Playwright E2E tests for Clear/Dark/Auto theme switching via settings gear menu."""

from __future__ import annotations

from playwright.async_api import Page, expect


async def _open_settings_menu(page: Page) -> None:
    """Ensure the settings menu dropdown is open."""
    settings_dropdown = page.locator('#settings-dropdown')
    if not await settings_dropdown.evaluate("el => el.classList.contains('open')"):
        await page.locator('#settings-toggle-btn').click()
    await expect(page.locator('#settings-menu')).to_be_visible()


async def test_theme_switch_default_and_cycle(page: Page) -> None:
    """Verify default auto theme, gear menu theme toggle presence, and cycling between auto, light, and dark."""
    # Ensure fresh state
    await page.goto('/')
    await page.evaluate("() => localStorage.removeItem('immich_quiz_theme')")
    await page.reload()
    await page.wait_for_selector('#setup-card')

    # 1. Verify default theme state
    theme_setting = await page.evaluate("() => document.documentElement.getAttribute('data-theme-setting')")
    assert theme_setting == 'auto'

    await _open_settings_menu(page)
    theme_btn = page.locator('#theme-toggle-btn')
    await expect(theme_btn).to_be_visible()
    await expect(theme_btn).to_have_attribute('title', 'Theme: Auto')
    await expect(theme_btn).to_have_attribute('aria-label', 'Switch Theme')

    # 2. Cycle Auto -> Light (Clear)
    await theme_btn.click()
    await expect(page.locator('html')).to_have_attribute('data-theme-setting', 'light')
    await expect(page.locator('html')).to_have_attribute('data-theme', 'light')
    await expect(theme_btn).to_have_attribute('title', 'Theme: Clear')
    stored = await page.evaluate("() => localStorage.getItem('immich_quiz_theme')")
    assert stored == 'light'

    # 3. Cycle Light -> Dark
    await theme_btn.click()
    await expect(page.locator('html')).to_have_attribute('data-theme-setting', 'dark')
    await expect(page.locator('html')).to_have_attribute('data-theme', 'dark')
    await expect(theme_btn).to_have_attribute('title', 'Theme: Dark')
    stored = await page.evaluate("() => localStorage.getItem('immich_quiz_theme')")
    assert stored == 'dark'

    # 4. Cycle Dark -> Auto
    await theme_btn.click()
    await expect(page.locator('html')).to_have_attribute('data-theme-setting', 'auto')
    await expect(theme_btn).to_have_attribute('title', 'Theme: Auto')
    stored = await page.evaluate("() => localStorage.getItem('immich_quiz_theme')")
    assert stored == 'auto'


async def test_theme_persistence_on_reload(page: Page) -> None:
    """Verify that user-selected theme persists across page reload without flash."""
    await page.goto('/')
    await page.wait_for_selector('#setup-card')

    await _open_settings_menu(page)
    theme_btn = page.locator('#theme-toggle-btn')

    # Switch to Dark (Auto -> Light -> Dark)
    await theme_btn.click()  # -> light
    await theme_btn.click()  # -> dark
    await expect(page.locator('html')).to_have_attribute('data-theme', 'dark')

    # Reload page
    await page.reload()
    await page.wait_for_selector('#setup-card')

    # Verify theme is dark immediately on reload
    await expect(page.locator('html')).to_have_attribute('data-theme', 'dark')
    await expect(page.locator('html')).to_have_attribute('data-theme-setting', 'dark')

    # Restore to Auto
    await _open_settings_menu(page)
    await theme_btn.click()  # -> auto
    await expect(page.locator('html')).to_have_attribute('data-theme-setting', 'auto')


async def test_theme_button_language_translation(page: Page) -> None:
    """Verify that theme button tooltip translates dynamically when language is switched."""
    await page.goto('/')
    await page.wait_for_selector('#setup-card')

    # Ensure English
    await page.evaluate("() => localStorage.setItem('immich_quiz_language', 'en-US')")
    await page.evaluate("() => localStorage.setItem('immich_quiz_theme', 'auto')")
    await page.reload()

    await _open_settings_menu(page)
    theme_btn = page.locator('#theme-toggle-btn')
    await expect(theme_btn).to_have_attribute('title', 'Theme: Auto')
    await expect(theme_btn).to_have_attribute('aria-label', 'Switch Theme')

    # Switch language to Portuguese
    lang_btn = page.locator('#lang-toggle-btn')
    await lang_btn.click()

    # Verify Portuguese translation
    await expect(theme_btn).to_have_attribute('title', 'Tema: Automático')
    await expect(theme_btn).to_have_attribute('aria-label', 'Alternar Tema')

    # Cycle to Claro (Light)
    await theme_btn.click()
    await expect(theme_btn).to_have_attribute('title', 'Tema: Claro')

    # Cycle to Escuro (Dark)
    await theme_btn.click()
    await expect(theme_btn).to_have_attribute('title', 'Tema: Escuro')

    # Restore to English and Auto
    await lang_btn.click()
    await expect(theme_btn).to_have_attribute('title', 'Theme: Dark')
    await theme_btn.click()  # -> auto
    await expect(theme_btn).to_have_attribute('title', 'Theme: Auto')

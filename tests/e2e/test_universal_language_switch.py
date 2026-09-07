"""Universal DOM Language Scanner E2E tests.

Validates dynamic language conversion across all components and screens without
relying on hardcoded element IDs. Automatically discovers rendered DOM elements
displaying translatable text, switches language via #lang-toggle-btn, and verifies
that zero components fail to convert.
"""

from __future__ import annotations

from typing import Any

import pytest
from playwright.async_api import Page, expect

JS_DISCOVER_TRANSLATABLE_ELEMENTS = """
() => {
  const enDict = window.TRANSLATIONS?.["en-US"] || {};
  const ptDict = window.TRANSLATIONS?.["pt-BR"] || {};

  // Build map of English text strings to their Portuguese equivalents
  const enToPt = new Map();
  for (const [k, enVal] of Object.entries(enDict)) {
    const ptVal = ptDict[k];
    if (!enVal || !ptVal) continue;
    if (typeof enVal !== "string" || typeof ptVal !== "string") continue;
    const cleanEn = enVal.trim();
    const cleanPt = ptVal.trim();
    if (cleanEn.length < 3) continue;
    if (cleanEn.toLowerCase() === cleanPt.toLowerCase()) continue;
    if (cleanEn.includes("{") || cleanPt.includes("{")) continue;
    if (!enToPt.has(cleanEn)) {
      enToPt.set(cleanEn, { key: k, ptVal: cleanPt });
    }
  }

  function getSelector(el) {
    if (el.id) return `#${CSS.escape(el.id)}`;
    const path = [];
    let cur = el;
    while (cur && cur !== document.body && path.length < 6) {
      let part = cur.tagName.toLowerCase();
      if (cur.id) {
        path.unshift(`#${CSS.escape(cur.id)}`);
        break;
      }
      if (cur.className && typeof cur.className === "string") {
        const cls = cur.className
          .trim()
          .split(/\\s+/)
          .filter((c) => !["active", "hover", "focus", "selected", "visible"].some((kw) => c.includes(kw)))
          .slice(0, 2);
        if (cls.length > 0) part += "." + cls.join(".");
      }
      path.unshift(part);
      cur = cur.parentElement;
    }
    return path.join(" > ");
  }

  function isVisible(el) {
    if (!el) return false;
    const style = window.getComputedStyle(el);
    if (style.display === "none" || style.visibility === "hidden" || style.opacity === "0") return false;
    return (el.offsetWidth > 0 || el.offsetHeight > 0 || el.getClientRects().length > 0);
  }

  const items = [];
  const seenSelectors = new Set();
  const allElements = document.querySelectorAll("body *");

  allElements.forEach((el) => {
    if (!isVisible(el)) return;
    if (["SCRIPT", "STYLE", "NOSCRIPT", "SVG", "PATH"].includes(el.tagName)) return;

    const selector = getSelector(el);
    if (!selector) return;

    // 1. Direct text node inspection
    let directText = "";
    for (const node of el.childNodes) {
      if (node.nodeType === Node.TEXT_NODE) {
        directText += node.nodeValue;
      }
    }
    directText = directText.trim();
    if (directText && enToPt.has(directText)) {
      const info = enToPt.get(directText);
      const uniqueKey = `${selector}::text`;
      if (!seenSelectors.has(uniqueKey)) {
        seenSelectors.add(uniqueKey);
        items.push({
          selector,
          type: "text",
          en: directText,
          pt: info.ptVal,
          key: info.key,
        });
      }
    }

    // 2. data-i18n attribute inspection
    const i18nKey = el.getAttribute("data-i18n");
    if (i18nKey && enDict[i18nKey] && ptDict[i18nKey] && enDict[i18nKey] !== ptDict[i18nKey]) {
      const uniqueKey = `${selector}::data-i18n`;
      if (!seenSelectors.has(uniqueKey)) {
        seenSelectors.add(uniqueKey);
        items.push({
          selector,
          type: "data-i18n",
          en: enDict[i18nKey],
          pt: ptDict[i18nKey],
          key: i18nKey,
        });
      }
    }

    // 3. title attribute
    const title = el.getAttribute("title")?.trim();
    if (title && enToPt.has(title)) {
      const info = enToPt.get(title);
      const uniqueKey = `${selector}::title`;
      if (!seenSelectors.has(uniqueKey)) {
        seenSelectors.add(uniqueKey);
        items.push({
          selector,
          type: "title",
          en: title,
          pt: info.ptVal,
          key: info.key,
        });
      }
    }

    // 4. placeholder attribute
    const placeholder = el.getAttribute("placeholder")?.trim();
    if (placeholder && enToPt.has(placeholder)) {
      const info = enToPt.get(placeholder);
      const uniqueKey = `${selector}::placeholder`;
      if (!seenSelectors.has(uniqueKey)) {
        seenSelectors.add(uniqueKey);
        items.push({
          selector,
          type: "placeholder",
          en: placeholder,
          pt: info.ptVal,
          key: info.key,
        });
      }
    }

    // 5. aria-label attribute
    const ariaLabel = el.getAttribute("aria-label")?.trim();
    if (ariaLabel && enToPt.has(ariaLabel)) {
      const info = enToPt.get(ariaLabel);
      const uniqueKey = `${selector}::aria-label`;
      if (!seenSelectors.has(uniqueKey)) {
        seenSelectors.add(uniqueKey);
        items.push({
          selector,
          type: "aria-label",
          en: ariaLabel,
          pt: info.ptVal,
          key: info.key,
        });
      }
    }
  });

  return items;
}
"""

JS_VERIFY_TRANSLATIONS = """
(items) => {
  const failures = [];
  items.forEach((item) => {
    let el = null;
    try {
      el = document.querySelector(item.selector);
    } catch (_) {}
    if (!el) return;

    let currentValue = "";
    if (item.type === "text" || item.type === "data-i18n") {
      currentValue = el.textContent.trim();
    } else if (item.type === "title") {
      currentValue = el.getAttribute("title")?.trim() || "";
    } else if (item.type === "placeholder") {
      currentValue = el.getAttribute("placeholder")?.trim() || "";
    } else if (item.type === "aria-label") {
      currentValue = el.getAttribute("aria-label")?.trim() || "";
    }

    // If the text has not updated and still equals the English version:
    if (currentValue === item.en && item.en.toLowerCase() !== item.pt.toLowerCase()) {
      failures.push({
        selector: item.selector,
        key: item.key,
        type: item.type,
        expected: item.pt,
        actual: currentValue,
      });
    }
  });
  return failures;
}
"""


async def _ensure_language(page: Page, target_lang: str) -> None:
    current_lang = await page.evaluate("() => localStorage.getItem('immich_quiz_language') || 'en-US'")
    if current_lang != target_lang:
        await page.evaluate("() => document.getElementById('lang-toggle-btn')?.click()")
        await page.wait_for_timeout(150)


async def assert_universal_dynamic_language_switch(
    page: Page, context_name: str, min_expected_elements: int = 5
) -> list[dict[str, Any]]:
    """Scan all visible components on the current page, toggle language, and verify every component converts."""
    await _ensure_language(page, 'en-US')

    # 1. Discover all visible translatable elements in English
    discovered: list[dict[str, Any]] = await page.evaluate(JS_DISCOVER_TRANSLATABLE_ELEMENTS)
    assert len(discovered) >= min_expected_elements, (
        f'[{context_name}] Expected at least {min_expected_elements} translatable elements, '
        f'but only found {len(discovered)}'
    )

    # 2. Toggle to Portuguese via direct click
    await page.evaluate("() => document.getElementById('lang-toggle-btn')?.click()")
    await page.wait_for_timeout(200)

    # 3. Verify zero elements failed to translate
    failures: list[dict[str, Any]] = await page.evaluate(JS_VERIFY_TRANSLATIONS, discovered)
    if failures:
        msg_lines = [f'[{context_name}] {len(failures)} component(s) failed dynamic translation to Portuguese:']
        for f in failures:
            msg_lines.append(
                f"  - Element '{f['selector']}' ({f['type']}) key='{f['key']}': "
                f"expected='{f['expected']}', still displayed English='{f['actual']}'"
            )
        pytest.fail('\n'.join(msg_lines))

    # 4. Toggle back to English
    await page.evaluate("() => document.getElementById('lang-toggle-btn')?.click()")
    await page.wait_for_timeout(200)

    return discovered


async def test_universal_scanner_lobby_and_filters(page: Page) -> None:
    """Universal scanner dynamically verifies all lobby setup components and expanded filter controls."""
    await page.goto('/')
    await page.wait_for_selector('#setup-card')

    # Open filters accordion to expose all multi-selects and range slider
    await page.locator('#filters-toggle-btn').click()
    await expect(page.locator('#filters-accordion-content')).to_be_visible()

    # Scan and verify all lobby elements
    discovered = await assert_universal_dynamic_language_switch(
        page, 'Lobby Setup with Filters Accordion', min_expected_elements=10
    )
    assert any('prepare' in item['key'] for item in discovered)
    assert any('filter' in item['key'] or 'libraries' in item['key'] for item in discovered)


async def test_universal_scanner_prepare_modal(page: Page) -> None:
    """Universal scanner dynamically verifies all elements inside the Prepare Game modal."""
    await page.goto('/')
    await _ensure_language(page, 'en-US')

    # Open Prepare Game modal
    await page.locator('#prepare-game-btn').click()
    await expect(page.locator('#prepare-game-modal')).to_be_visible()

    # Scan and verify modal contents
    await assert_universal_dynamic_language_switch(page, 'Prepare Game Modal', min_expected_elements=4)

    # Close modal
    await page.locator('#prepare-modal-close-btn').click()
    await expect(page.locator('#prepare-game-modal')).to_be_hidden()


async def test_universal_scanner_pinpoint_gameplay_and_reveal(page: Page) -> None:
    """Universal scanner dynamically verifies Pinpoint guessing screen and reveal results."""
    await page.goto('/')
    await _ensure_language(page, 'en-US')

    # Start Pinpoint match
    await page.locator('#prepare-game-btn').click()
    await page.locator('#start-match-btn').click()

    if await page.locator('#pass-overlay').is_visible():
        await page.locator('#ready-btn').click()
        await expect(page.locator('#pass-overlay')).to_be_hidden()

    await expect(page.locator('#game-card')).to_be_visible()
    await expect(page.locator('#guessing-ui')).to_be_visible()

    # 1. Scan Guessing UI
    await assert_universal_dynamic_language_switch(page, 'Pinpoint Guessing UI', min_expected_elements=5)

    # Place a guess on map and submit
    guess_map = page.locator('#guess-map')
    await expect(guess_map).to_be_visible()
    await guess_map.click(position={'x': 100, 'y': 100})
    await page.locator('#submit-answer').click()

    # 2. Scan Reveal UI
    await expect(page.locator('#reveal-ui')).to_be_visible()
    await assert_universal_dynamic_language_switch(page, 'Pinpoint Reveal UI', min_expected_elements=5)


async def test_universal_scanner_album_shuffle_gameplay_and_reveal(page: Page) -> None:
    """Universal scanner dynamically verifies Album Shuffle guessing UI, cards, and reveal table."""
    await page.goto('/')
    await _ensure_language(page, 'en-US')

    # Switch to Album Shuffle
    await page.locator('#mode-album-shuffle-btn').click()
    await page.locator('#prepare-game-btn').click()
    await page.locator('#start-match-btn').click()

    if await page.locator('#pass-overlay').is_visible():
        await page.locator('#ready-btn').click()
        await expect(page.locator('#pass-overlay')).to_be_hidden()

    await expect(page.locator('#album-shuffle-ui')).to_be_visible()

    # 1. Scan Album Shuffle Guessing UI
    await assert_universal_dynamic_language_switch(page, 'Album Shuffle Guessing UI', min_expected_elements=5)

    # Assign map pins to photo cards to enable submit button
    cards = page.locator('#shuffle-cards-list .shuffle-card-row')
    map_pins = page.locator('#shuffle-map-shell .shuffle-pin-icon, #shuffle-map-shell .leaflet-marker-icon')
    card_count = await cards.count()
    for i in range(card_count):
        await cards.nth(i).click()
        await map_pins.nth(i).click()

    await expect(page.locator('#submit-answer')).to_be_enabled()
    await page.locator('#submit-answer').click()
    await expect(page.locator('#reveal-ui')).to_be_visible()

    # 2. Scan Album Shuffle Reveal UI
    await assert_universal_dynamic_language_switch(page, 'Album Shuffle Reveal UI', min_expected_elements=5)


async def test_universal_scanner_challenges_hub(page: Page) -> None:
    """Universal scanner dynamically verifies all components on the Challenges Hub page."""
    await page.goto('/challenges')
    await page.wait_for_selector('#challenges-page-card')

    # Scan and verify Challenges Hub
    await assert_universal_dynamic_language_switch(page, 'Challenges Hub', min_expected_elements=5)

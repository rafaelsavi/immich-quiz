/**
 * Theme Management Module (Clear / Dark)
 * Controls user-selected color scheme, gear menu toggle button,
 * and zero-flash persistence.
 */

import { t } from "./i18n.js";
import { el } from "./state.js";

const THEME_STORAGE_KEY = "immich_quiz_theme";
const VALID_THEMES = ["light", "dark"];

export const THEME_ICONS = {
  light: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="theme-svg" aria-hidden="true"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M6.34 17.66l-1.41 1.41M19.07 4.93l-1.41 1.41"/></svg>`,
  dark: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="theme-svg" aria-hidden="true"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>`,
};

let _initialized = false;

/**
 * Returns the currently stored user theme preference ('light' or 'dark').
 */
export function getThemeSetting() {
  try {
    const saved = localStorage.getItem(THEME_STORAGE_KEY);
    if (saved === "dark") {
      return "dark";
    }
  } catch (_) {}
  return "light";
}

/**
 * Returns the active visual theme ('light' or 'dark').
 */
export function getEffectiveTheme(setting = getThemeSetting()) {
  return setting === "dark" ? "dark" : "light";
}

/**
 * Updates UI elements (icon, title, aria-label) representing active theme setting.
 */
export function updateThemeUi() {
  const setting = getThemeSetting();
  const btn = (el && el.themeToggleBtn) || document.getElementById("theme-toggle-btn");
  const icon = (el && el.themeIcon) || document.getElementById("theme-icon");

  if (icon) {
    icon.innerHTML = THEME_ICONS[setting] || THEME_ICONS.light;
  }
  if (btn) {
    const localizedTitle = t(`theme.${setting}`);
    const toggleLabel = t("theme.toggle_title");
    btn.setAttribute("title", localizedTitle);
    btn.setAttribute("aria-label", toggleLabel);
    btn.dataset.themeSetting = setting;
  }
}

/**
 * Applies a theme setting ('light' or 'dark'), persisting it and updating DOM attributes.
 */
export function applyTheme(setting) {
  const normalized = setting === "dark" ? "dark" : "light";
  try {
    localStorage.setItem(THEME_STORAGE_KEY, normalized);
  } catch (_) {}

  if (typeof document !== "undefined") {
    document.documentElement.setAttribute("data-theme", normalized);
    document.documentElement.setAttribute("data-theme-setting", normalized);

    const themeColorMeta = document.querySelector('meta[name="theme-color"]');
    if (themeColorMeta) {
      themeColorMeta.setAttribute("content", normalized === "dark" ? "#0b0f19" : "#f4efe4");
    }
  }

  updateThemeUi();
}

/**
 * Toggles theme between light and dark.
 */
export function toggleTheme() {
  const current = getThemeSetting();
  const next = current === "dark" ? "light" : "dark";
  applyTheme(next);
}

/**
 * Initializes theme setting and button bindings.
 */
export function initTheme() {
  if (_initialized) {
    updateThemeUi();
    return;
  }
  _initialized = true;

  // Apply initial theme
  applyTheme(getThemeSetting());

  const btn = (el && el.themeToggleBtn) || document.getElementById("theme-toggle-btn");
  if (btn) {
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      toggleTheme();
    });
  }
}


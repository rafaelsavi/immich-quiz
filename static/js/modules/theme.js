/**
 * Theme Management Module (Clear / Dark / Auto)
 * Controls user-selected and OS-detected color schemes, gear menu toggle button,
 * and zero-flash persistence.
 */

import { t } from "./i18n.js";
import { el } from "./state.js";

const THEME_STORAGE_KEY = "immich_quiz_theme";
const VALID_THEMES = ["auto", "light", "dark"];

export const THEME_ICONS = {
  auto: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="theme-svg" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="M12 3a9 9 0 0 1 0 18z" fill="currentColor"/></svg>`,
  light: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="theme-svg" aria-hidden="true"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M6.34 17.66l-1.41 1.41M19.07 4.93l-1.41 1.41"/></svg>`,
  dark: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="theme-svg" aria-hidden="true"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>`,
};

let _initialized = false;

/**
 * Returns the currently stored user theme preference ('auto', 'light', or 'dark').
 */
export function getThemeSetting() {
  try {
    const saved = localStorage.getItem(THEME_STORAGE_KEY);
    if (saved && VALID_THEMES.includes(saved)) {
      return saved;
    }
  } catch (_) {}
  return "auto";
}

/**
 * Returns the active visual theme ('light' or 'dark'), resolving 'auto' against system preference.
 */
export function getEffectiveTheme(setting = getThemeSetting()) {
  if (setting === "light" || setting === "dark") {
    return setting;
  }
  if (typeof window !== "undefined" && window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches) {
    return "dark";
  }
  return "light";
}

/**
 * Updates UI elements (icon, title, aria-label) representing active theme setting.
 */
export function updateThemeUi() {
  const setting = getThemeSetting();
  const btn = (el && el.themeToggleBtn) || document.getElementById("theme-toggle-btn");
  const icon = (el && el.themeIcon) || document.getElementById("theme-icon");

  if (icon) {
    icon.innerHTML = THEME_ICONS[setting] || THEME_ICONS.auto;
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
 * Applies a theme setting ('auto', 'light', or 'dark'), persisting it and updating DOM attributes.
 */
export function applyTheme(setting) {
  const normalized = VALID_THEMES.includes(setting) ? setting : "auto";
  try {
    localStorage.setItem(THEME_STORAGE_KEY, normalized);
  } catch (_) {}

  const effective = getEffectiveTheme(normalized);
  if (typeof document !== "undefined") {
    document.documentElement.setAttribute("data-theme", effective);
    document.documentElement.setAttribute("data-theme-setting", normalized);

    const themeColorMeta = document.querySelector('meta[name="theme-color"]');
    if (themeColorMeta) {
      themeColorMeta.setAttribute("content", effective === "dark" ? "#0b0f19" : "#f4efe4");
    }
  }

  updateThemeUi();
}

/**
 * Cycles theme sequentially: auto -> light -> dark -> auto.
 */
export function toggleTheme() {
  const current = getThemeSetting();
  let next = "auto";
  if (current === "auto") {
    next = "light";
  } else if (current === "light") {
    next = "dark";
  } else {
    next = "auto";
  }
  applyTheme(next);
}

/**
 * Initializes theme listeners, media query synchronization, and button bindings.
 */
export function initTheme() {
  if (_initialized) {
    updateThemeUi();
    return;
  }
  _initialized = true;

  // Apply initial theme
  applyTheme(getThemeSetting());

  // Listen to OS color scheme changes if preference is set to auto
  if (typeof window !== "undefined" && window.matchMedia) {
    try {
      const mediaQuery = window.matchMedia("(prefers-color-scheme: dark)");
      const handler = () => {
        if (getThemeSetting() === "auto") {
          applyTheme("auto");
        }
      };
      if (typeof mediaQuery.addEventListener === "function") {
        mediaQuery.addEventListener("change", handler);
      } else if (typeof mediaQuery.addListener === "function") {
        mediaQuery.addListener(handler);
      }
    } catch (_) {}
  }

  const btn = (el && el.themeToggleBtn) || document.getElementById("theme-toggle-btn");
  if (btn) {
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      toggleTheme();
    });
  }
}

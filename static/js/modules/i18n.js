import { state, el } from "./state.js";
import enTranslations from "./locales/en_US.js";
import ptTranslations from "./locales/pt_BR.js";

export const TRANSLATIONS = {
  "en-US": enTranslations,
  "pt-BR": ptTranslations,
};

/**
 * Normalize arbitrary language code string into supported BCP-47 tag ('en-US' or 'pt-BR').
 */
export function normalizeLanguage(lang) {
  if (!lang) return null;
  const s = String(lang).trim().toLowerCase().replace("_", "-");
  if (s.startsWith("pt")) return "pt-BR";
  if (s.startsWith("en")) return "en-US";
  return null;
}

/**
 * Return current active BCP-47 locale tag ('en-US' or 'pt-BR').
 */
export function getLocale() {
  return (state && normalizeLanguage(state.language)) || "en-US";
}

/**
 * Locale-aware date formatter using active language.
 */
export function formatDate(dateInput, options) {
  if (!dateInput) return "";
  const d = dateInput instanceof Date ? dateInput : new Date(dateInput);
  if (isNaN(d.getTime())) return "";
  return d.toLocaleDateString(getLocale(), options);
}

/**
 * Locale-aware date & time formatter using active language.
 */
export function formatDateTime(dateInput, options) {
  if (!dateInput) return "";
  const d = dateInput instanceof Date ? dateInput : new Date(dateInput);
  if (isNaN(d.getTime())) return "";
  return d.toLocaleString(getLocale(), options);
}

/**
 * Locale-aware relative time formatter (e.g. '5 minutes ago', 'yesterday', 'just now').
 */
export function formatRelativeTime(dateInput, options = {}) {
  if (!dateInput) return "";
  const d = dateInput instanceof Date ? dateInput : new Date(dateInput);
  if (isNaN(d.getTime())) return "";

  const diffSec = Math.round((d.getTime() - Date.now()) / 1000);
  if (typeof Intl !== "undefined" && Intl.RelativeTimeFormat) {
    try {
      const rtf = new Intl.RelativeTimeFormat(getLocale(), {
        numeric: "auto",
        style: "long",
        ...options,
      });
      const abs = Math.abs(diffSec);
      if (abs < 45) {
        const justNow = t("time.just_now");
        return justNow !== "time.just_now" ? justNow : rtf.format(0, "second");
      }
      if (abs < 3600) return rtf.format(Math.round(diffSec / 60), "minute");
      if (abs < 86400) return rtf.format(Math.round(diffSec / 3600), "hour");
      if (abs < 2592000) return rtf.format(Math.round(diffSec / 86400), "day");
      if (abs < 31536000) return rtf.format(Math.round(diffSec / 2592000), "month");
      return rtf.format(Math.round(diffSec / 31536000), "year");
    } catch (_) { }
  }
  return formatDate(d);
}

/**
 * Locale-aware number formatter using active language.
 */
export function formatNumber(numInput, options) {
  if (numInput === undefined || numInput === null) return "0";
  if (typeof numInput === "string") {
    const trimmed = numInput.trim();
    if (/^-?\d+(\.\d+)?$/.test(trimmed)) {
      const n = Number(trimmed);
      return isNaN(n) ? "0" : n.toLocaleString(getLocale(), options);
    }
    return numInput;
  }
  const n = Number(numInput);
  if (isNaN(n)) return "0";
  return n.toLocaleString(getLocale(), options);
}

/**
 * Select plural category using standard Unicode CLDR rules (Intl.PluralRules).
 */
export function plural(count, forms = {}) {
  let n = 0;
  let displayStr = "";

  if (typeof count === "number") {
    n = isNaN(count) ? 0 : count;
    displayStr = formatNumber(n);
  } else if (typeof count === "string") {
    const trimmed = count.trim();
    if (/^-?\d+(\.\d+)?$/.test(trimmed)) {
      n = Number(trimmed);
      displayStr = formatNumber(n);
    } else {
      displayStr = trimmed;
      const digitsOnly = trimmed.replace(/[^\d-]/g, "");
      n = digitsOnly ? Number(digitsOnly) : 0;
    }
  } else {
    n = Number(count) || 0;
    displayStr = formatNumber(n);
  }

  let rule = "other";
  if (typeof Intl !== "undefined" && Intl.PluralRules) {
    try {
      rule = new Intl.PluralRules(getLocale()).select(n);
    } catch (_) {
      rule = n === 1 ? "one" : "other";
    }
  } else {
    rule = n === 1 ? "one" : "other";
  }

  const template = forms[rule] || forms.other || forms.one || "";
  if (typeof template === "function") {
    return template(displayStr);
  }
  return String(template)
    .replace(/\{count\}/g, displayStr)
    .replace(/\{0\}/g, displayStr);
}

/**
 * Translate a key using the current language stored in state.
 * Supports string templates with {0}, {1}, {count} as well as plural forms { one, other }.
 */
export function t(key, ...args) {
  const lang = getLocale();
  const dict = TRANSLATIONS[lang] || TRANSLATIONS["en-US"] || {};
  const entry = key in dict ? dict[key] : (TRANSLATIONS["en-US"] ? TRANSLATIONS["en-US"][key] : undefined);
  if (entry === undefined) {
    return key;
  }
  if (typeof entry === "function") {
    return entry(...args);
  }
  if (typeof entry === "object" && entry !== null && ("one" in entry || "other" in entry)) {
    return plural(args[0], entry);
  }
  if (typeof entry === "string" && args.length > 0) {
    let res = entry;
    args.forEach((arg, idx) => {
      const formattedArg = typeof arg === "number" ? formatNumber(arg) : String(arg);
      res = res.replace(new RegExp(`\\{${idx}\\}`, "g"), formattedArg);
      if (idx === 0) {
        res = res.replace(/\{count\}/g, formattedArg);
      }
    });
    return res;
  }
  return entry !== undefined ? entry : key;
}

export function translateError(msg) {
  if (!msg) return "";
  const raw = typeof msg === "string" ? msg : msg.message || String(msg);
  const str = raw.trim();

  const key = `error.${str}`;
  const translated = t(key);
  if (translated !== key) {
    return translated;
  }

  if (str.startsWith("Unknown album_id for library")) {
    return t("error.unknown_album");
  }

  return str;
}

export function showAlert(msg) {
  if (!msg) return;
  alert(translateError(msg));
}

export function getInitialLanguagePreference() {
  try {
    const stored = localStorage.getItem("immich_quiz_language");
    const normalized = normalizeLanguage(stored);
    if (normalized) return normalized;
  } catch (_) { }

  if (typeof navigator !== "undefined") {
    const browserLang = navigator.language || (navigator.languages && navigator.languages[0]);
    const normalized = normalizeLanguage(browserLang);
    if (normalized) return normalized;
  }

  return "en-US";
}

export const FLAGS = {
  "en-US": `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 60 60" class="flag-svg" aria-hidden="true"><rect width="60" height="60" fill="#012169"/><path d="M0,0 L60,60 M60,0 L0,60" stroke="#FFFFFF" stroke-width="10"/><path d="M0,0 L60,60 M60,0 L0,60" stroke="#C8102E" stroke-width="6"/><path d="M30,0 V60 M0,30 H60" stroke="#FFFFFF" stroke-width="16"/><path d="M30,0 V60 M0,30 H60" stroke="#C8102E" stroke-width="10"/></svg>`,
  "pt-BR": `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 60 60" class="flag-svg" aria-hidden="true"><rect width="60" height="60" fill="#009B3A"/><polygon points="30,10 52,30 30,50 8,30" fill="#FEDF00"/><circle cx="30" cy="30" r="12" fill="#002776"/><path d="M18,31 C23,26.5 37,26.5 42,31 C37,28 23,28 18,31 Z" fill="#FFFFFF"/></svg>`,
};

export function updateLanguageUi() {
  const lang = getLocale();
  const iconEl = (el && el.langIcon) || document.getElementById("lang-icon");
  const btnEl = (el && el.langToggleBtn) || document.getElementById("lang-toggle-btn");
  if (iconEl) {
    iconEl.innerHTML = FLAGS[lang] || FLAGS["en-US"];
  }
  if (btnEl) {
    btnEl.setAttribute("title", t("lang.title"));
    btnEl.setAttribute("aria-label", t("lang.toggle_title"));
  }
}

export function toggleLanguage(onLanguageChanged) {
  if (!state) return;
  const current = getLocale();
  state.language = current === "pt-BR" ? "en-US" : "pt-BR";
  try {
    localStorage.setItem("immich_quiz_language", state.language);
  } catch (_) { }
  updateLanguageUi();
  applyLanguage();
  if (typeof onLanguageChanged === "function") {
    onLanguageChanged();
  }
}

/**
 * Locale-aware list formatter using active language and conjunction.
 * e.g. ['France', 'Germany', 'Spain'] -> "France, Germany, and Spain" (en-US) or "França, Alemanha e Espanha" (pt-BR)
 */
export function formatList(items, options = {}) {
  if (!items || !items.length) return "";
  if (typeof Intl !== "undefined" && Intl.ListFormat) {
    try {
      const formatter = new Intl.ListFormat(getLocale(), {
        style: "long",
        type: "conjunction",
        ...options,
      });
      return formatter.format(items);
    } catch (_) { }
  }
  const sep = getLocale() === "pt-BR" ? " e " : " & ";
  if (items.length <= 2) return items.join(sep);
  return `${items.slice(0, -1).join(", ")}${sep}${items[items.length - 1]}`;
}

/**
 * Locale-aware collator for alphabetical sorting respecting accents.
 */
export function getCollator(options = {}) {
  if (typeof Intl !== "undefined" && Intl.Collator) {
    try {
      return new Intl.Collator(getLocale(), {
        sensitivity: "base",
        numeric: true,
        ...options,
      });
    } catch (_) { }
  }
  return {
    compare: (a, b) => String(a).localeCompare(String(b)),
  };
}

/**
 * Apply translations to all [data-i18n], [data-i18n-title], and [data-i18n-placeholder] elements in the DOM.
 * Elements with a sort arrow child keep the arrow intact.
 * Dynamic function-valued keys (expecting parameters) are skipped to avoid overwriting runtime state.
 */
export function applyLanguage() {
  const currentLocale = getLocale();
  if (typeof document !== "undefined" && document.documentElement) {
    document.documentElement.lang = currentLocale;
    document.documentElement.dir = "ltr";
  }

  document.querySelectorAll("[data-i18n]").forEach((element) => {
    const key = element.getAttribute("data-i18n");
    const dict = TRANSLATIONS[currentLocale] || TRANSLATIONS["en-US"] || {};
    const rawEntry = key in dict ? dict[key] : (TRANSLATIONS["en-US"] ? TRANSLATIONS["en-US"][key] : undefined);

    // Skip dynamic entries whose translation value is a function or plural needing arguments
    if (typeof rawEntry === "function" || (typeof rawEntry === "object" && rawEntry !== null)) {
      return;
    }

    const translation = rawEntry !== undefined ? rawEntry : key;
    if (typeof translation !== "string") {
      return;
    }

    const arrow = element.querySelector(".sort-arrow");
    if (arrow) {
      const arrowClone = arrow.cloneNode(true);
      element.textContent = translation;
      element.appendChild(arrowClone);
    } else if (element.tagName === "INPUT" || element.tagName === "TEXTAREA") {
      element.setAttribute("placeholder", translation);
    } else if (translation.includes("<") && translation.includes(">")) {
      element.innerHTML = translation;
    } else {
      element.textContent = translation;
    }
  });

  document.querySelectorAll("[data-i18n-title]").forEach((element) => {
    const key = element.getAttribute("data-i18n-title");
    element.setAttribute("title", t(key));
  });

  document.querySelectorAll("[data-i18n-aria-label]").forEach((element) => {
    const key = element.getAttribute("data-i18n-aria-label");
    element.setAttribute("aria-label", t(key));
  });

  document.querySelectorAll("[data-i18n-alt]").forEach((element) => {
    const key = element.getAttribute("data-i18n-alt");
    element.setAttribute("alt", t(key));
  });

  document.querySelectorAll("[data-i18n-placeholder]").forEach((element) => {
    const key = element.getAttribute("data-i18n-placeholder");
    element.setAttribute("placeholder", t(key));
  });
}

/**
 * Unified Match Metadata Component for Immich Quiz.
 *
 * Renders a standardized 2-category specification panel:
 *  1. Game Setup (Mode, Targets/Guessing, Rounds, Time Limit)
 *  2. Library Filters (Libraries, Places, Albums, People, Dates, Shared / Full Library)
 *
 * Used across the Match Results Summary (#summary-meta), Challenge Cards in
 * Challenges Hub, and Challenge Entry screens.
 */

import { t } from "../i18n.js";

/**
 * Escapes HTML characters for safe attribute and text insertion.
 * @param {string} str
 * @returns {string}
 */
function escapeHtml(str) {
  if (!str) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

/**
 * Build structured specification item objects for both categories.
 * @param {Object} data - Match summary, challenge object, or game config.
 * @returns {{ gameItems: Array<Object>, libItems: Array<Object> }}
 */
export function getMatchMetaCategories(data) {
  if (!data) {
    return { gameItems: [], libItems: [] };
  }

  const isShuffle = data.game_mode === "album_shuffle";
  const modeEmoji = isShuffle ? "🔀" : "📍";
  const modeLabel = isShuffle ? t("mode.album_shuffle") : t("mode.pinpoint");
  const modeDesc = isShuffle ? t("mode.album_shuffle_desc") : t("mode.pinpoint_desc");

  // 1. Targets / Guessing Mode
  let targetsLabel = "";
  if (isShuffle) {
    targetsLabel = t("meta.targets_shuffle") !== "meta.targets_shuffle" ? t("meta.targets_shuffle") : "Pins & Timeline";
  } else if (data.location_mode && data.date_mode) {
    targetsLabel = t("meta.targets_loc_date") !== "meta.targets_loc_date" ? t("meta.targets_loc_date") : "Location & Date";
  } else if (data.location_mode) {
    targetsLabel = t("meta.targets_loc_only") !== "meta.targets_loc_only" ? t("meta.targets_loc_only") : "Location only";
  } else if (data.date_mode) {
    targetsLabel = t("meta.targets_date_only") !== "meta.targets_date_only" ? t("meta.targets_date_only") : "Date only";
  } else {
    targetsLabel = "—";
  }

  // 2. Rounds Count
  const rounds = data.rounds || data.round_count || data.rounds_played || data.total_rounds || 10;
  const roundsUnit = t("challenges_page.rounds_label") !== "challenges_page.rounds_label" ? t("challenges_page.rounds_label") : "Rounds";
  const roundsVal = `${rounds} ${roundsUnit}`;

  // 3. Round Time Limit
  const rawRoundLen = data.round_length || "1m";
  let timerVal = rawRoundLen;
  if (rawRoundLen === "unlimited" || rawRoundLen === "none") {
    timerVal = t("meta.time_unlimited") !== "meta.time_unlimited" ? t("meta.time_unlimited") : "Unlimited";
  } else {
    timerVal = rawRoundLen;
  }

  const gameItems = [
    {
      type: "mode",
      icon: modeEmoji,
      label: t("meta.mode_label") !== "meta.mode_label" ? t("meta.mode_label") : "Mode",
      val: modeLabel,
      title: modeDesc,
    },
    {
      type: "targets",
      icon: "🎯",
      label: t("meta.targets_label") !== "meta.targets_label" ? t("meta.targets_label") : "Targets",
      val: targetsLabel,
      title: `${t("setup.game_settings_label") || "What to Guess"}: ${targetsLabel}`,
    },
    {
      type: "rounds",
      icon: "🔢",
      label: t("meta.rounds_label") !== "meta.rounds_label" ? t("meta.rounds_label") : "Rounds",
      val: roundsVal,
      title: `${rounds} ${t("setup.rounds_label") || "Rounds"}`,
    },
    {
      type: "timer",
      icon: "⏱️",
      label: t("meta.time_limit_label") !== "meta.time_limit_label" ? t("meta.time_limit_label") : "Time Limit",
      val: timerVal,
      title: `${t("setup.round_length_label") || "Round Length"}: ${timerVal}`,
    },
  ];

  // 4. Library Setup / Pool Filters
  const filterConfig = data.config || data;
  const libItems = [];

  // Libraries
  const libraries = data.libraries || filterConfig.libraries;
  if (libraries && libraries.length > 0) {
    const libVal = libraries.join(", ");
    const libLabel = libraries.length > 1
      ? (t("meta.libraries_label") !== "meta.libraries_label" ? t("meta.libraries_label") : "Libraries")
      : (t("meta.library_label") !== "meta.library_label" ? t("meta.library_label") : "Library");
    libItems.push({
      type: "library",
      icon: "📚",
      label: libLabel,
      val: libVal,
      title: `${libLabel}: ${libVal}`,
    });
  }

  // Places (Countries / Cities)
  const countries = filterConfig.countries || [];
  const cities = filterConfig.cities || [];
  if (countries.length > 0 || cities.length > 0) {
    const placesList = [...countries, ...cities];
    const placesVal = placesList.length <= 2 ? placesList.join(", ") : `${placesList[0]} +${placesList.length - 1}`;
    libItems.push({
      type: "places",
      icon: "🌍",
      label: t("meta.places_label") !== "meta.places_label" ? t("meta.places_label") : "Places",
      val: placesVal,
      title: `${t("meta.places_label") || "Places"}: ${placesList.join(", ")}`,
    });
  }

  // Albums
  const albumNames = filterConfig.album_names || filterConfig.albums || [];
  if (albumNames.length > 0) {
    const albumVal = albumNames.length <= 2 ? albumNames.join(", ") : `${albumNames[0]} +${albumNames.length - 1}`;
    libItems.push({
      type: "albums",
      icon: "📁",
      label: t("meta.albums_label") !== "meta.albums_label" ? t("meta.albums_label") : "Albums",
      val: albumVal,
      title: `${t("meta.albums_label") || "Albums"}: ${albumNames.join(", ")}`,
    });
  }

  // People
  const personNames = filterConfig.person_names || filterConfig.people || [];
  if (personNames.length > 0) {
    const pVal = personNames.length <= 2 ? personNames.join(", ") : `${personNames[0]} +${personNames.length - 1}`;
    libItems.push({
      type: "people",
      icon: "👤",
      label: t("meta.people_label") !== "meta.people_label" ? t("meta.people_label") : "People",
      val: pVal,
      title: `${t("meta.people_label") || "People"}: ${personNames.join(", ")}`,
    });
  }

  // Dates
  if (filterConfig.min_date || filterConfig.max_date) {
    const dateVal = `${filterConfig.min_date || "—"} → ${filterConfig.max_date || "—"}`;
    libItems.push({
      type: "dates",
      icon: "🗓️",
      label: t("meta.dates_label") !== "meta.dates_label" ? t("meta.dates_label") : "Dates",
      val: dateVal,
      title: `${t("meta.dates_label") || "Dates"}: ${dateVal}`,
    });
  }

  // Shared
  if (filterConfig.include_shared) {
    libItems.push({
      type: "shared",
      icon: "🔗",
      label: t("meta.shared_label") !== "meta.shared_label" ? t("meta.shared_label") : "Shared",
      val: t("meta.shared_included") !== "meta.shared_included" ? t("meta.shared_included") : "Included",
      title: t("challenges_page.scope_shared") || "Shared albums included",
    });
  }

  // Full Library fallback when no filters are set
  if (libItems.length === 0) {
    libItems.push({
      type: "all",
      icon: "🌐",
      label: t("challenges_page.scope_heading") !== "challenges_page.scope_heading" ? t("challenges_page.scope_heading") : "Scope",
      val: t("meta.scope_all") !== "meta.scope_all" ? t("meta.scope_all") : "Full Library",
      title: t("challenges_page.scope_all") || "All Photos (Full Library)",
    });
  }

  return { gameItems, libItems };
}

/**
 * Generate HTML markup for the 2-category match specifications.
 * @param {Object} data - Match summary or challenge data.
 * @returns {string}
 */
export function buildMatchMetaHtml(data) {
  const { gameItems, libItems } = getMatchMetaCategories(data);
  if (gameItems.length === 0 && libItems.length === 0) return "";

  const renderItem = (item) => `
    <div class="match-meta-item meta-${item.type}" title="${escapeHtml(item.title || item.val)}">
      <span class="match-meta-item-icon" aria-hidden="true">${item.icon}</span>
      <div class="match-meta-item-body">
        <span class="match-meta-item-label">${escapeHtml(item.label)}</span>
        <span class="match-meta-item-val">${escapeHtml(item.val)}</span>
      </div>
    </div>
  `;

  return `
    <div class="match-meta-section">
      <!-- Category 1: Game Setup -->
      <div class="match-meta-category category-game-setup">
        <div class="match-meta-cat-header">
          <span class="match-meta-cat-icon" aria-hidden="true">⚙️</span>
          <span class="match-meta-cat-title">${t("meta.game_setup_heading") !== "meta.game_setup_heading" ? t("meta.game_setup_heading") : "Game Setup"}</span>
        </div>
        <div class="match-meta-items">
          ${gameItems.map(renderItem).join("")}
        </div>
      </div>

      <!-- Category 2: Library Setup / Pool Filters -->
      <div class="match-meta-category category-library-filters">
        <div class="match-meta-cat-header">
          <span class="match-meta-cat-icon" aria-hidden="true">🎛️</span>
          <span class="match-meta-cat-title">${t("meta.library_setup_heading") !== "meta.library_setup_heading" ? t("meta.library_setup_heading") : "Library Filters"}</span>
        </div>
        <div class="match-meta-items">
          ${libItems.map(renderItem).join("")}
        </div>
      </div>
    </div>
  `;
}

/**
 * Render the match meta specifications directly into a DOM container.
 * @param {HTMLElement} container
 * @param {Object} data
 */
export function renderMatchMeta(container, data) {
  if (!container) return;
  container.innerHTML = buildMatchMetaHtml(data);
}

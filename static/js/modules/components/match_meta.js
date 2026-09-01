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

import { t, tOr } from "../i18n.js";

/**
 * Escapes HTML characters for safe attribute and text insertion.
 * @param {string} str
 * @returns {string}
 */
export function escapeHtml(str) {
  if (!str) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

/**
 * Render an array of match meta item objects to HTML.
 * @param {Array<Object>} items
 * @returns {string}
 */
export function renderMatchMetaItemsHtml(items) {
  if (!items || items.length === 0) return "";
  return items
    .map(
      (item) => `
    <div class="match-meta-item meta-${escapeHtml(item.type)}" title="${escapeHtml(item.title || item.val)}">
      <span class="match-meta-item-icon" aria-hidden="true">${item.icon}</span>
      <div class="match-meta-item-body">
        <span class="match-meta-item-label">${escapeHtml(item.label)}</span>
        <span class="match-meta-item-val">${escapeHtml(item.val)}</span>
      </div>
    </div>
  `
    )
    .join("");
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

  const filterConfig = data.config || data;

  const isShuffle = (data.game_mode || filterConfig.game_mode) === "album_shuffle";
  const modeEmoji = isShuffle ? "🔀" : "📍";
  const modeLabel = isShuffle ? t("mode.album_shuffle") : t("mode.pinpoint");
  const modeDesc = isShuffle ? t("mode.album_shuffle_desc") : t("mode.pinpoint_desc");

  // 1. Targets / Guessing Mode
  const locMode = data.location_mode !== undefined ? data.location_mode : filterConfig.location_mode;
  const dateMode = data.date_mode !== undefined ? data.date_mode : filterConfig.date_mode;
  let targetsLabel = "";
  if (isShuffle) {
    targetsLabel = tOr("meta.targets_shuffle", "Pins & Timeline");
  } else if (locMode && dateMode) {
    targetsLabel = tOr("meta.targets_loc_date", "Location & Date");
  } else if (locMode) {
    targetsLabel = tOr("meta.targets_loc_only", "Location only");
  } else if (dateMode) {
    targetsLabel = tOr("meta.targets_date_only", "Date only");
  } else {
    targetsLabel = "—";
  }

  // 2. Rounds Count
  const rounds = data.rounds || data.round_count || data.rounds_played || data.total_rounds || filterConfig.round_count || 10;
  const roundsUnit = tOr("challenges_page.rounds_label", "Rounds");
  const roundsVal = `${rounds} ${roundsUnit}`;

  // 3. Round Time Limit
  const rawRoundLen = data.round_length || filterConfig.round_length || "1m";
  let timerVal = rawRoundLen;
  if (rawRoundLen === "unlimited" || rawRoundLen === "none") {
    timerVal = tOr("meta.time_unlimited", "Unlimited");
  } else {
    const timerKey = `setup.round_${rawRoundLen}`;
    timerVal = tOr(timerKey, rawRoundLen);
  }

  const gameItems = [
    {
      type: "mode",
      icon: modeEmoji,
      label: tOr("meta.mode_label", "Mode"),
      val: modeLabel,
      title: modeDesc,
    },
    {
      type: "targets",
      icon: "🎯",
      label: tOr("meta.targets_label", "Targets"),
      val: targetsLabel,
      title: `${t("setup.game_settings_label") || "What to Guess"}: ${targetsLabel}`,
    },
    {
      type: "rounds",
      icon: "🔢",
      label: tOr("meta.rounds_label", "Rounds"),
      val: roundsVal,
      title: `${rounds} ${t("setup.rounds_label") || "Rounds"}`,
    },
    {
      type: "timer",
      icon: "⏱️",
      label: tOr("meta.time_limit_label", "Time Limit"),
      val: timerVal,
      title: `${t("setup.round_length_label") || "Round Length"}: ${timerVal}`,
    },
  ];

  // 4. Library Setup / Pool Filters
  const libItems = [];

  // Libraries
  const libraries = data.libraries || filterConfig.libraries;
  if (libraries && libraries.length > 0) {
    const libVal = libraries.join(", ");
    const libLabel = libraries.length > 1
      ? tOr("meta.libraries_label", "Libraries")
      : tOr("meta.library_label", "Library");
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
    const placesLabel = tOr("meta.places_label", "Places");
    libItems.push({
      type: "places",
      icon: "🌍",
      label: placesLabel,
      val: placesVal,
      title: `${placesLabel}: ${placesList.join(", ")}`,
    });
  }

  // Albums
  const albumNames = filterConfig.album_names || filterConfig.albums || [];
  if (albumNames.length > 0) {
    const albumVal = albumNames.length <= 2 ? albumNames.join(", ") : `${albumNames[0]} +${albumNames.length - 1}`;
    const albumsLabel = tOr("meta.albums_label", "Albums");
    libItems.push({
      type: "albums",
      icon: "📁",
      label: albumsLabel,
      val: albumVal,
      title: `${albumsLabel}: ${albumNames.join(", ")}`,
    });
  }

  // People
  const personNames = filterConfig.person_names || filterConfig.people || [];
  if (personNames.length > 0) {
    const pVal = personNames.length <= 2 ? personNames.join(", ") : `${personNames[0]} +${personNames.length - 1}`;
    const peopleLabel = tOr("meta.people_label", "People");
    libItems.push({
      type: "people",
      icon: "👤",
      label: peopleLabel,
      val: pVal,
      title: `${peopleLabel}: ${personNames.join(", ")}`,
    });
  }

  // Dates
  if (filterConfig.min_date || filterConfig.max_date) {
    const dateVal = `${filterConfig.min_date || "—"} → ${filterConfig.max_date || "—"}`;
    const datesLabel = tOr("meta.dates_label", "Dates");
    libItems.push({
      type: "dates",
      icon: "🗓️",
      label: datesLabel,
      val: dateVal,
      title: `${datesLabel}: ${dateVal}`,
    });
  }

  // Shared
  if (filterConfig.include_shared) {
    libItems.push({
      type: "shared",
      icon: "🔗",
      label: tOr("meta.shared_label", "Shared"),
      val: tOr("meta.shared_included", "Included"),
      title: t("challenges_page.scope_shared") || "Shared albums included",
    });
  }

  // Full Library fallback when no filters are set
  if (libItems.length === 0) {
    libItems.push({
      type: "all",
      icon: "🌐",
      label: tOr("challenges_page.scope_heading", "Scope"),
      val: tOr("meta.scope_all", "Full Library"),
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

  const gameSetupTitle = tOr("meta.game_setup_heading", "Game Setup");
  const libFiltersTitle = tOr("meta.library_setup_heading", "Library Filters");

  return `
    <div class="match-meta-section">
      <!-- Category 1: Game Setup -->
      <div class="match-meta-category category-game-setup" title="${escapeHtml(gameSetupTitle)}">
        <div class="match-meta-cat-header" aria-hidden="true">
          <span class="match-meta-cat-icon">⚙️</span>
        </div>
        <div class="match-meta-items">
          ${renderMatchMetaItemsHtml(gameItems)}
        </div>
      </div>

      <!-- Category 2: Library Setup / Pool Filters -->
      <div class="match-meta-category category-library-filters" title="${escapeHtml(libFiltersTitle)}">
        <div class="match-meta-cat-header" aria-hidden="true">
          <span class="match-meta-cat-icon">🎛️</span>
        </div>
        <div class="match-meta-items">
          ${renderMatchMetaItemsHtml(libItems)}
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

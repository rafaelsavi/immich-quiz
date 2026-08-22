import { state, el } from "./state.js";
import { t } from "./i18n.js";
import { api } from "./api.js";
import { MultiSelect } from "./components/multi_select.js";
import { DateRangeSlider } from "./components/range_slider.js";
import { PlayerInput } from "./components/player_input.js";
import { loadLeaderboard, loadLeaderboardDebounced } from "./leaderboard.js";
import { checkSyncStatus, triggerLibrarySync, renderSyncStatus } from "./sync.js";

/** @type {MultiSelect|null} */
export let libraryMultiSelect = null;
/** @type {MultiSelect|null} */
export let albumMultiSelect = null;
/** @type {MultiSelect|null} */
export let countryMultiSelect = null;
/** @type {MultiSelect|null} */
export let cityMultiSelect = null;
/** @type {MultiSelect|null} */
export let peopleMultiSelect = null;
/** @type {DateRangeSlider|null} */
export let dateRangeSlider = null;
/** @type {PlayerInput|null} */
export let playerInput = null;

const PLAYERS_STORAGE_KEY = "immich_quiz_saved_players";
const STORAGE_KEY_PREFIX = "immich_quiz_filters_";

let cachedRawCities = [];
let _preflightDebounceTimer = null;
let _lastPreflightData = null;

let _getActiveModeFn = null;

export function setGetActiveModeFn(fn) {
  _getActiveModeFn = fn;
}

function getActiveMode() {
  return _getActiveModeFn ? _getActiveModeFn() : null;
}

export function getLastPreflightData() {
  return _lastPreflightData;
}

export function initPlayerInput() {
  const root = document.getElementById("player-input-root");
  if (!root) return;

  let savedPlayers = null;
  try {
    const raw = localStorage.getItem(PLAYERS_STORAGE_KEY);
    if (raw) {
      const parsed = JSON.parse(raw);
      if (Array.isArray(parsed) && parsed.length > 0) {
        savedPlayers = parsed;
      }
    }
  } catch (e) {
    console.warn("Failed to load saved players from localStorage:", e);
  }

  playerInput = new PlayerInput({
    container: root,
    hiddenInput: el.players,
    countBadge: document.getElementById("player-count-badge"),
    initialPlayers: savedPlayers || [],
    onChange: (players) => {
      try {
        localStorage.setItem(PLAYERS_STORAGE_KEY, JSON.stringify(players));
      } catch (e) {
        console.warn("Failed to save players to localStorage:", e);
      }
      triggerPreflightDebounced();
    },
  });
}

export function initFilterComponents() {
  libraryMultiSelect = new MultiSelect({
    container: document.getElementById("library-multi-select"),
    placeholderKey: "setup.all_libraries",
    searchPlaceholderKey: "setup.library_search_placeholder",
    noResultsKey: "setup.no_libraries_found",
    summaryFormatter: (count) => t("setup.libraries_selected", count),
    onChange: () => {
      onLibrariesChanged();
    },
  });

  albumMultiSelect = new MultiSelect({
    container: document.getElementById("album-multi-select"),
    placeholderKey: "setup.all_photos",
    searchPlaceholderKey: "setup.album_search_placeholder",
    noResultsKey: "setup.no_albums_found",
    summaryFormatter: (count) => t("setup.albums_selected", count),
    onChange: () => {
      saveCurrentFilters();
      updateFiltersSummaryBadge();
      triggerPreflightDebounced();
      loadLeaderboardDebounced();
    },
  });

  countryMultiSelect = new MultiSelect({
    container: document.getElementById("country-multi-select"),
    placeholderKey: "setup.all_countries",
    searchPlaceholderKey: "setup.country_search_placeholder",
    noResultsKey: "setup.no_countries_found",
    summaryFormatter: (count) => t("setup.countries_selected", count),
    onChange: () => {
      const selectedCountries = countryMultiSelect.getSelectedIds();
      updateDependentCities(selectedCountries);
      saveCurrentFilters();
      updateFiltersSummaryBadge();
      triggerPreflightDebounced();
      loadLeaderboardDebounced();
    },
  });

  cityMultiSelect = new MultiSelect({
    container: document.getElementById("city-multi-select"),
    placeholderKey: "setup.all_cities",
    searchPlaceholderKey: "setup.city_search_placeholder",
    noResultsKey: "setup.no_cities_found",
    summaryFormatter: (count) => t("setup.cities_selected", count),
    onChange: () => {
      saveCurrentFilters();
      updateFiltersSummaryBadge();
      triggerPreflightDebounced();
      loadLeaderboardDebounced();
    },
  });

  peopleMultiSelect = new MultiSelect({
    container: document.getElementById("people-multi-select"),
    placeholderKey: "setup.all_people",
    searchPlaceholderKey: "setup.people_search_placeholder",
    noResultsKey: "setup.no_people_found",
    summaryFormatter: (count) => t("setup.people_selected", count),
    onChange: () => {
      updatePeopleModeToggleVisibility();
      saveCurrentFilters();
      updateFiltersSummaryBadge();
      triggerPreflightDebounced();
      loadLeaderboardDebounced();
    },
  });

  dateRangeSlider = new DateRangeSlider({
    minThumb: document.getElementById("date-slider-min"),
    maxThumb: document.getElementById("date-slider-max"),
    fillEl: document.getElementById("date-slider-fill"),
    readoutEl: document.getElementById("date-slider-readout"),
    boundMinEl: document.getElementById("date-slider-bound-min"),
    boundMaxEl: document.getElementById("date-slider-bound-max"),
    onChange: () => {
      saveCurrentFilters();
      updateFiltersSummaryBadge();
      triggerPreflightDebounced();
      loadLeaderboardDebounced();
    },
  });

  if (state.filters) {
    state.filters.libraryMultiSelect = libraryMultiSelect;
    state.filters.albumMultiSelect = albumMultiSelect;
    state.filters.countryMultiSelect = countryMultiSelect;
    state.filters.cityMultiSelect = cityMultiSelect;
    state.filters.peopleMultiSelect = peopleMultiSelect;
    state.filters.dateRangeSlider = dateRangeSlider;
  }

  // People Mode Segmented Toggle (ANY / ALL)
  const peopleModeToggleEl = document.getElementById("people-mode-toggle");
  if (peopleModeToggleEl) {
    peopleModeToggleEl.querySelectorAll(".people-mode-btn").forEach((btn) => {
      btn.addEventListener("click", () => {
        peopleModeToggleEl.querySelectorAll(".people-mode-btn").forEach((b) => b.classList.remove("active"));
        btn.classList.add("active");
        saveCurrentFilters();
        triggerPreflightDebounced();
        loadLeaderboardDebounced();
      });
    });
  }

  // Photo Sources Checkboxes
  if (el.includeSharedCheckbox) {
    el.includeSharedCheckbox.addEventListener("change", () => {
      if (el.labelIncludeShared) {
        el.labelIncludeShared.classList.toggle("active", el.includeSharedCheckbox.checked);
      }
      saveCurrentFilters();
      updateFiltersSummaryBadge();
      triggerPreflightDebounced();
      loadLeaderboardDebounced();
    });
  }

  // Accordion Toggle
  const toggleBtn = document.getElementById("filters-toggle-btn");
  const contentEl = document.getElementById("filters-accordion-content");
  const accordionEl = document.getElementById("filters-accordion");
  const headerEl = document.getElementById("filters-accordion-header");
  if (toggleBtn && contentEl) {
    toggleBtn.addEventListener("click", () => {
      const isExpanded = toggleBtn.getAttribute("aria-expanded") === "true";
      toggleBtn.setAttribute("aria-expanded", String(!isExpanded));
      contentEl.classList.toggle("hidden", isExpanded);
      if (accordionEl) accordionEl.classList.toggle("expanded", !isExpanded);
      if (headerEl) headerEl.setAttribute("data-expanded", String(!isExpanded));
    });
  }

  // Reset Filters Button
  const resetBtn = document.getElementById("reset-filters-btn");
  if (resetBtn) {
    resetBtn.addEventListener("click", () => {
      if (libraryMultiSelect) libraryMultiSelect.clear();
      if (albumMultiSelect) albumMultiSelect.clear();
      if (countryMultiSelect) countryMultiSelect.clear();
      updateDependentCities([]);
      if (cityMultiSelect) cityMultiSelect.clear();
      if (peopleMultiSelect) peopleMultiSelect.clear();
      if (dateRangeSlider) dateRangeSlider.reset();
      resetPeopleMode();
      updatePeopleModeToggleVisibility();

      if (el.includeSharedCheckbox) {
        el.includeSharedCheckbox.checked = false;
        if (el.labelIncludeShared) el.labelIncludeShared.classList.remove("active");
      }

      clearSavedFilters();
      onLibrariesChanged();
    });
  }

  // Manual Sync Button
  if (el.syncLibraryBtn) {
    el.syncLibraryBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      triggerLibrarySync(onLibrariesChanged);
    });
  }
}

export function updateDependentCities(selectedCountryNames) {
  if (!cityMultiSelect) return;
  if (!selectedCountryNames || selectedCountryNames.length === 0) {
    cityMultiSelect.setItems(cachedRawCities.map((c) => ({ id: c.name, name: c.name, subtitle: c.country })));
  } else {
    const lowerCountries = selectedCountryNames.map((c) => (c || "").toLowerCase());
    const filtered = cachedRawCities.filter(
      (c) => !c.country || lowerCountries.includes(c.country.toLowerCase())
    );
    cityMultiSelect.setItems(filtered.map((c) => ({ id: c.name, name: c.name, subtitle: c.country })));
  }
}

export function saveCurrentFilters() {
  const { minDate, maxDate } = dateRangeSlider ? dateRangeSlider.getSelectedRange() : { minDate: null, maxDate: null };
  const filterState = {
    libraries: libraryMultiSelect ? libraryMultiSelect.getSelectedIds() : [],
    album_ids: albumMultiSelect ? albumMultiSelect.getSelectedIds() : [],
    countries: countryMultiSelect ? countryMultiSelect.getSelectedIds() : [],
    cities: cityMultiSelect ? cityMultiSelect.getSelectedIds() : [],
    person_ids: peopleMultiSelect ? peopleMultiSelect.getSelectedIds() : [],
    people_mode: getSelectedPeopleMode(),
    min_month: minDate ? minDate.slice(0, 7) : null,
    max_month: maxDate ? maxDate.slice(0, 7) : null,
    include_shared: el.includeSharedCheckbox ? el.includeSharedCheckbox.checked : false,
  };
  try {
    localStorage.setItem(STORAGE_KEY_PREFIX + "global", JSON.stringify(filterState));
  } catch (e) {
    console.warn("Failed to persist filters to localStorage", e);
  }
}

export function restoreFilters() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY_PREFIX + "global");
    if (!raw) {
      if (el.includeSharedCheckbox) {
        el.includeSharedCheckbox.checked = false;
        if (el.labelIncludeShared) el.labelIncludeShared.classList.remove("active");
      }
      return;
    }
    const saved = JSON.parse(raw);
    if (saved.libraries && libraryMultiSelect) libraryMultiSelect.setSelectedIds(saved.libraries);
    if (saved.album_ids && albumMultiSelect) albumMultiSelect.setSelectedIds(saved.album_ids);
    if (saved.countries && countryMultiSelect) {
      countryMultiSelect.setSelectedIds(saved.countries);
      updateDependentCities(saved.countries);
    }
    if (saved.cities && cityMultiSelect) cityMultiSelect.setSelectedIds(saved.cities);
    if (saved.person_ids && peopleMultiSelect) peopleMultiSelect.setSelectedIds(saved.person_ids);
    if (saved.people_mode) setPeopleMode(saved.people_mode);
    if (dateRangeSlider && saved.min_month && saved.max_month) {
      dateRangeSlider.setSelectedRange(saved.min_month, saved.max_month);
    }

    const sharedChecked = Boolean(saved.include_shared);
    if (el.includeSharedCheckbox) {
      el.includeSharedCheckbox.checked = sharedChecked;
      if (el.labelIncludeShared) el.labelIncludeShared.classList.toggle("active", sharedChecked);
    }
  } catch (e) {
    console.warn("Failed to restore filters from localStorage", e);
  }
}

export function clearSavedFilters() {
  try {
    localStorage.removeItem(STORAGE_KEY_PREFIX + "global");
  } catch (e) {
    console.warn("Failed to clear filters from localStorage", e);
  }
}

export function getSelectedPeopleMode() {
  const activeBtn = document.querySelector("#people-mode-toggle .people-mode-btn.active");
  return activeBtn ? activeBtn.getAttribute("data-people-mode") || "ANY" : "ANY";
}

export function setPeopleMode(mode) {
  const toggleEl = document.getElementById("people-mode-toggle");
  if (toggleEl) {
    toggleEl.querySelectorAll(".people-mode-btn").forEach((b) => {
      b.classList.toggle("active", b.getAttribute("data-people-mode") === mode);
    });
  }
}

export function resetPeopleMode() {
  setPeopleMode("ANY");
}

export function updatePeopleModeToggleVisibility() {
  const toggleEl = document.getElementById("people-mode-toggle");
  if (!toggleEl) return;
  const selectedCount = peopleMultiSelect ? peopleMultiSelect.getSelectedIds().length : 0;
  toggleEl.classList.toggle("hidden", selectedCount < 2);
}

export function updateFiltersSummaryBadge() {
  const badge = el.filtersSummaryBadge;
  if (!badge) return;

  let count = 0;
  if (libraryMultiSelect && libraryMultiSelect.getSelectedIds().length > 0) count++;
  if (albumMultiSelect && albumMultiSelect.getSelectedIds().length > 0) count++;
  if (countryMultiSelect && countryMultiSelect.getSelectedIds().length > 0) count++;
  if (cityMultiSelect && cityMultiSelect.getSelectedIds().length > 0) count++;
  if (peopleMultiSelect && peopleMultiSelect.getSelectedIds().length > 0) count++;
  if (dateRangeSlider) {
    const { minDate, maxDate } = dateRangeSlider.getSelectedRange();
    if (minDate || maxDate) count++;
  }
  if (el.includeSharedCheckbox && el.includeSharedCheckbox.checked) count++;

  if (count === 0) {
    badge.textContent = t("setup.filters_summary_default");
  } else {
    badge.textContent = t("setup.filters_active_count", count);
  }
}

export function isCustomFilteredActive() {
  if (libraryMultiSelect && libraryMultiSelect.getSelectedIds().length > 0) return true;
  if (albumMultiSelect && albumMultiSelect.getSelectedIds().length > 0) return true;
  if (countryMultiSelect && countryMultiSelect.getSelectedIds().length > 0) return true;
  if (cityMultiSelect && cityMultiSelect.getSelectedIds().length > 0) return true;
  if (peopleMultiSelect && peopleMultiSelect.getSelectedIds().length > 0) return true;
  if (dateRangeSlider) {
    const { minDate, maxDate } = dateRangeSlider.getSelectedRange();
    if (minDate || maxDate) return true;
  }
  if (el.includeSharedCheckbox && el.includeSharedCheckbox.checked) return true;
  return false;
}

export function getActiveFilterSummary() {
  const activeCount =
    (libraryMultiSelect && libraryMultiSelect.getSelectedIds().length > 0 ? 1 : 0) +
    (albumMultiSelect && albumMultiSelect.getSelectedIds().length > 0 ? 1 : 0) +
    (countryMultiSelect && countryMultiSelect.getSelectedIds().length > 0 ? 1 : 0) +
    (cityMultiSelect && cityMultiSelect.getSelectedIds().length > 0 ? 1 : 0) +
    (peopleMultiSelect && peopleMultiSelect.getSelectedIds().length > 0 ? 1 : 0) +
    (dateRangeSlider && (dateRangeSlider.getSelectedRange().minDate || dateRangeSlider.getSelectedRange().maxDate) ? 1 : 0) +
    (el.includeSharedCheckbox && el.includeSharedCheckbox.checked ? 1 : 0);

  const maxItems = activeCount > 1 ? 1 : 2;
  const parts = [];
  if (libraryMultiSelect) {
    const libs = libraryMultiSelect.getSelectedItems();
    if (libs.length > 0 && libs.length <= maxItems) parts.push(libs.map((l) => l.name).join(", "));
    else if (libs.length > maxItems) parts.push(t("filters.libraries_count", libs.length));
  }
  if (albumMultiSelect) {
    const albums = albumMultiSelect.getSelectedItems();
    if (albums.length > 0 && albums.length <= maxItems) parts.push(albums.map((a) => a.name).join(", "));
    else if (albums.length > maxItems) parts.push(`${albums.length} albums`);
  }
  if (countryMultiSelect) {
    const countries = countryMultiSelect.getSelectedItems();
    if (countries.length > 0 && countries.length <= maxItems) parts.push(countries.map((c) => c.name).join(", "));
    else if (countries.length > maxItems) parts.push(`${countries.length} countries`);
  }
  if (cityMultiSelect) {
    const cities = cityMultiSelect.getSelectedItems();
    if (cities.length > 0 && cities.length <= maxItems) parts.push(cities.map((c) => c.name).join(", "));
    else if (cities.length > maxItems) parts.push(`${cities.length} cities`);
  }
  if (peopleMultiSelect) {
    const people = peopleMultiSelect.getSelectedItems();
    if (people.length > 0 && people.length <= maxItems) parts.push(people.map((p) => p.name).join(", "));
    else if (people.length > maxItems) parts.push(`${people.length} people`);
  }
  if (dateRangeSlider) {
    const { minDate, maxDate } = dateRangeSlider.getSelectedRange();
    if (minDate && maxDate) {
      const y1 = minDate.substring(0, 4);
      const y2 = maxDate.substring(0, 4);
      parts.push(y1 === y2 ? y1 : `${y1}–${y2}`);
    } else if (minDate) {
      parts.push(`from ${minDate.substring(0, 4)}`);
    } else if (maxDate) {
      parts.push(`until ${maxDate.substring(0, 4)}`);
    }
  }
  if (el.includeSharedCheckbox && el.includeSharedCheckbox.checked) {
    parts.push("Shared");
  }
  return parts.length > 0 ? parts.join(" • ") : t("leaderboard.scope_all");
}

export function showPreflightWarning(message) {
  let warningEl = document.getElementById("preflight-warning");
  const submitBtn = el.setupSubmitBtn || document.querySelector("#setup-form button[type=submit]");
  if (!warningEl) {
    warningEl = document.createElement("div");
    warningEl.id = "preflight-warning";
    warningEl.className = "preflight-warning";
    if (submitBtn) {
      submitBtn.insertAdjacentElement("beforebegin", warningEl);
    } else {
      document.getElementById("setup-form")?.appendChild(warningEl);
    }
  }
  warningEl.textContent = message;
  warningEl.classList.remove("hidden");
  if (submitBtn) {
    submitBtn.disabled = true;
  }
}

export function hidePreflightWarning() {
  const warningEl = document.getElementById("preflight-warning");
  if (warningEl) warningEl.classList.add("hidden");
  const submitBtn = el.setupSubmitBtn || document.querySelector("#setup-form button[type=submit]");
  if (submitBtn) {
    submitBtn.disabled = false;
  }
}

export function updatePreflightCount(preflight) {
  const countEl = document.getElementById("preflight-count");
  if (!countEl) return;

  let count, locMode, dtMode, totalCount, gpsCount, dateCount;
  if (typeof preflight === "number") {
    count = preflight;
    const mode = getActiveMode();
    const modePayload = mode ? mode.getModePayload() : {};
    locMode = modePayload.location_mode ?? true;
    dtMode = modePayload.date_mode ?? true;
  } else if (preflight && typeof preflight === "object") {
    count = preflight.eligible_count;
    locMode = preflight.location_mode ?? true;
    dtMode = preflight.date_mode ?? true;
    totalCount = preflight.total_count;
    gpsCount = preflight.gps_count;
    dateCount = preflight.date_count;
  }

  if (count === undefined || count === null || count === 0) {
    countEl.classList.add("hidden");
    countEl.removeAttribute("title");
    return;
  }

  const display = Number(count).toLocaleString();
  let key = "setup.preflight_count_all";
  if (locMode && dtMode) {
    key = "setup.preflight_count_both";
  } else if (locMode && !dtMode) {
    key = "setup.preflight_count_gps";
  } else if (!locMode && dtMode) {
    key = "setup.preflight_count_date";
  }

  countEl.textContent = t(key, display);

  if (totalCount !== undefined && totalCount !== null) {
    const dispTotal = Number(totalCount).toLocaleString();
    const dispGps = Number(gpsCount ?? 0).toLocaleString();
    const dispDate = Number(dateCount ?? 0).toLocaleString();
    const dispBoth = Number(count).toLocaleString();
    countEl.title = t("setup.preflight_count_breakdown_tooltip", dispTotal, dispGps, dispDate, dispBoth);
  } else {
    countEl.removeAttribute("title");
  }

  countEl.classList.remove("hidden");
  countEl.classList.toggle("preflight-count--ok", count > 0);
}

export function hidePreflightCount() {
  _lastPreflightData = null;
  const countEl = document.getElementById("preflight-count");
  if (countEl) {
    countEl.classList.add("hidden");
    countEl.removeAttribute("title");
  }
}

export function triggerPreflightDebounced() {
  if (_preflightDebounceTimer) {
    clearTimeout(_preflightDebounceTimer);
  }
  _preflightDebounceTimer = setTimeout(() => {
    _preflightDebounceTimer = null;
    executePreflight().catch((err) => {
      console.warn("Preflight check failed:", err);
    });
  }, 500);
}

export async function executePreflight() {
  const { minDate, maxDate } = dateRangeSlider ? dateRangeSlider.getSelectedRange() : { minDate: null, maxDate: null };
  const activeMode = getActiveMode();
  const modePayload = activeMode ? activeMode.getModePayload() : {};

  const selectedLibs = libraryMultiSelect ? libraryMultiSelect.getSelectedIds() : [];

  let locationMode = modePayload.location_mode ?? true;
  let dateMode = modePayload.date_mode ?? true;
  if (!locationMode && !dateMode) {
    locationMode = true;
    dateMode = true;
  }

  const payload = {
    players: playerInput
      ? playerInput.getPlayers()
      : el.players
        ? el.players.value.split(",").map((n) => n.trim()).filter(Boolean)
        : [],
    round_count: el.roundCount ? parseInt(el.roundCount.value, 10) : 10,
    location_mode: locationMode,
    date_mode: dateMode,
    game_mode: activeMode ? activeMode.name : "pinpoint",
    libraries: selectedLibs,
    album_ids: albumMultiSelect ? albumMultiSelect.getSelectedIds() : [],
    person_ids: peopleMultiSelect ? peopleMultiSelect.getSelectedIds() : [],
    people_mode: getSelectedPeopleMode(),
    countries: countryMultiSelect ? countryMultiSelect.getSelectedIds() : [],
    cities: cityMultiSelect ? cityMultiSelect.getSelectedIds() : [],
    min_date: minDate,
    max_date: maxDate,
    include_shared: el.includeSharedCheckbox ? el.includeSharedCheckbox.checked : false,
  };

  try {
    const preflight = await api("/api/game/preflight", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    _lastPreflightData = {
      ...preflight,
      location_mode: payload.location_mode,
      date_mode: payload.date_mode,
    };

    updatePreflightCount(_lastPreflightData);

    if (preflight && preflight.facet_counts) {
      if (countryMultiSelect) countryMultiSelect.updateCounts(preflight.facet_counts.countries);
      if (cityMultiSelect) cityMultiSelect.updateCounts(preflight.facet_counts.cities);
      if (peopleMultiSelect) peopleMultiSelect.updateCounts(preflight.facet_counts.people);
      if (albumMultiSelect) albumMultiSelect.updateCounts(preflight.facet_counts.albums);
    }

    if (!preflight.ok) {
      if (preflight.is_synced === false || preflight.sync_status === "never_synced") {
        showPreflightWarning(t("setup.library_not_synced_warning"));
      } else {
        showPreflightWarning(
          t("setup.not_enough_media", preflight.eligible_count, preflight.required)
        );
      }
    } else {
      hidePreflightWarning();
    }
  } catch (err) {
    hidePreflightCount();
    console.warn("Live preflight error:", err);
  }
}

export async function onLibrariesChanged() {
  const selectedLibs = libraryMultiSelect ? libraryMultiSelect.getSelectedIds() : [];
  const queryParams = new URLSearchParams();
  selectedLibs.forEach((lib) => queryParams.append("libraries", lib));
  const queryString = queryParams.toString() ? `?${queryParams.toString()}` : "";

  try {
    const [albumsRes, filtersRes] = await Promise.all([
      api(`/api/albums${queryString}`),
      api(`/api/filters${queryString}`),
    ]);

    cachedRawCities = filtersRes.cities || [];

    if (albumMultiSelect) albumMultiSelect.setItems(albumsRes.albums || []);
    if (countryMultiSelect) countryMultiSelect.setItems((filtersRes.countries || []).map((c) => ({ id: c, name: c })));
    if (cityMultiSelect) cityMultiSelect.setItems(cachedRawCities.map((c) => ({ id: c.name, name: c.name, subtitle: c.country })));
    if (peopleMultiSelect) peopleMultiSelect.setItems(filtersRes.people || []);

    if (dateRangeSlider) {
      if (filtersRes.date_range && filtersRes.date_range.min_month && filtersRes.date_range.max_month) {
        dateRangeSlider.setBounds(filtersRes.date_range.min_month, filtersRes.date_range.max_month);
      } else {
        dateRangeSlider.setBounds(null, null);
      }
    }

    updatePeopleModeToggleVisibility();
    saveCurrentFilters();
    updateFiltersSummaryBadge();
    triggerPreflightDebounced();
    loadLeaderboardDebounced();
  } catch (err) {
    console.error("Failed to load library filters:", err);
  }
}

export async function initLibraries() {
  initFilterComponents();
  const data = await api("/api/libraries");
  if (libraryMultiSelect) {
    libraryMultiSelect.setItems((data.libraries || []).map((name) => ({ id: name, name })));
  }
  restoreFilters();
  await onLibrariesChanged();
  checkSyncStatus(onLibrariesChanged);
}

export function stepSelectOption(selectEl, direction) {
  if (!selectEl || selectEl.disabled || selectEl.options.length === 0) {
    return;
  }

  const current = selectEl.selectedIndex;
  const next = Math.max(0, Math.min(selectEl.options.length - 1, current + direction));
  if (next === current) {
    return;
  }

  selectEl.selectedIndex = next;
  selectEl.dispatchEvent(new Event("change", { bubbles: true }));
}

export function bindSelectWheelScroll(selectEl, invertScroll = false) {
  if (!selectEl || selectEl.dataset.wheelBound) {
    return;
  }
  selectEl.dataset.wheelBound = "true";

  selectEl.addEventListener(
    "wheel",
    (event) => {
      event.preventDefault();
      let direction = event.deltaY > 0 ? 1 : -1;
      if (invertScroll) direction = -direction;
      stepSelectOption(selectEl, direction);
    },
    { passive: false }
  );
}

export function initWheelScrolls() {
  bindSelectWheelScroll(el.roundCount, false);
  bindSelectWheelScroll(el.roundLength, false);
}

export function refreshFilterComponentsLanguage() {
  if (playerInput) playerInput.updateLanguage();
  if (libraryMultiSelect) libraryMultiSelect.updateTriggerUi();
  if (albumMultiSelect) albumMultiSelect.updateTriggerUi();
  if (countryMultiSelect) countryMultiSelect.updateTriggerUi();
  if (cityMultiSelect) cityMultiSelect.updateTriggerUi();
  if (peopleMultiSelect) peopleMultiSelect.updateTriggerUi();
  if (dateRangeSlider) dateRangeSlider.updateVisuals();
  updateFiltersSummaryBadge();
  if (_lastPreflightData) {
    updatePreflightCount(_lastPreflightData);
    if (!_lastPreflightData.ok) {
      showPreflightWarning(
        t("setup.not_enough_media", _lastPreflightData.eligible_count, _lastPreflightData.required)
      );
    }
  }
}

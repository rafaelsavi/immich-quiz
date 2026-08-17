import { state, el } from "./state.js";
import { getSelectedPeopleMode } from "./setup_filters.js";

export async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });

  if (!response.ok) {
    const text = await response.text();
    let message = text;
    try {
      const data = JSON.parse(text);
      if (data && data.detail) {
        if (typeof data.detail === "string") {
          message = data.detail;
        } else if (Array.isArray(data.detail)) {
          message = data.detail
            .map((item) => {
              if (typeof item === "string") return item;
              if (item && item.msg) {
                return item.msg.replace(/^Value error,\s*/i, "");
              }
              return JSON.stringify(item);
            })
            .join("\n");
        } else {
          message = JSON.stringify(data.detail);
        }
      } else if (data && data.message) {
        message = data.message;
      }
    } catch (_) {
      // Keep plain text response if not JSON
    }
    throw new Error(message || `Request failed with ${response.status}`);
  }

  const contentType = response.headers.get("content-type") || "";
  if (!contentType.includes("application/json")) {
    return response;
  }
  return response.json();
}

/**
 * Build query params from the current setup form selections and fetch
 * leaderboard entries filtered to that exact game configuration.
 */
export function setupFilterParams() {
  const albumSelect = state.filters && state.filters.albumMultiSelect;
  const selectedAlbums = albumSelect ? albumSelect.getSelectedItems() : [];
  const albumText = selectedAlbums.length > 0
    ? selectedAlbums.map((i) => i.name).sort((a, b) => a.localeCompare(b)).join(", ")
    : "-";
  const albumIds = albumSelect ? albumSelect.getSelectedIds().sort() : [];

  const locEl = el.goalLocation;
  const dateEl = el.goalDate;
  const locCard = document.getElementById("card-goal-location");
  const dateCard = document.getElementById("card-goal-date");
  const locationMode = locEl ? Boolean(locEl.checked) : (locCard ? locCard.classList.contains("active") : true);
  const dateMode = dateEl ? Boolean(dateEl.checked) : (dateCard ? dateCard.classList.contains("active") : true);
  const gameMode = (state && state.gameMode) || "pinpoint";

  const params = new URLSearchParams({
    round_length: el.roundLength ? el.roundLength.value : "1m",
    location_mode: String(locationMode),
    date_mode: String(dateMode),
    game_mode: gameMode,
    library: el.library ? el.library.value : "",
    albums: albumText,
  });

  if (albumIds.length > 0) {
    params.set("album_ids", albumIds.join(","));
  }

  const slider = state.filters && state.filters.dateRangeSlider;
  if (slider) {
    const { minDate, maxDate } = slider.getSelectedRange();
    if (minDate) params.set("min_date", minDate);
    if (maxDate) params.set("max_date", maxDate);
  }

  const countrySelect = state.filters && state.filters.countryMultiSelect;
  if (countrySelect) {
    const countries = countrySelect.getSelectedIds().sort((a, b) => a.localeCompare(b));
    if (countries.length > 0) params.set("countries", countries.join(","));
  }

  const citySelect = state.filters && state.filters.cityMultiSelect;
  if (citySelect) {
    const cities = citySelect.getSelectedIds().sort((a, b) => a.localeCompare(b));
    if (cities.length > 0) params.set("cities", cities.join(","));
  }

  const peopleSelect = state.filters && state.filters.peopleMultiSelect;
  if (peopleSelect) {
    const personIds = peopleSelect.getSelectedIds().sort();
    if (personIds.length > 0) {
      params.set("person_ids", personIds.join(","));
      const peopleMode = typeof getSelectedPeopleMode === "function" ? getSelectedPeopleMode() : "ANY";
      params.set("people_mode", peopleMode);
    }
  }

  if (el.includeSharedCheckbox && el.includeSharedCheckbox.checked) {
    params.set("include_shared", "true");
  }

  return params;
}

import { state, el } from "./state.js";

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
  const selectedOptions = el.album ? Array.from(el.album.selectedOptions).filter((opt) => opt.value !== "") : [];
  const albumText = selectedOptions.length > 0 ? selectedOptions.map((opt) => opt.textContent).join(", ") : "-";
  const locEl = el.goalLocation;
  const dateEl = el.goalDate;
  const locCard = document.getElementById("card-goal-location");
  const dateCard = document.getElementById("card-goal-date");
  const locationMode = locEl ? Boolean(locEl.checked) : (locCard ? locCard.classList.contains("active") : true);
  const dateMode = dateEl ? Boolean(dateEl.checked) : (dateCard ? dateCard.classList.contains("active") : true);
  const gameMode = (state && state.gameMode) || "pinpoint";
  const params = new URLSearchParams({
    rounds: el.roundCount ? el.roundCount.value : "10",
    round_length: el.roundLength ? el.roundLength.value : "1m",
    location_mode: String(locationMode),
    date_mode: String(dateMode),
    game_mode: gameMode,
    library: el.library ? el.library.value : "",
    album: albumText,
  });
  return params;
}

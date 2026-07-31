import { el } from "./state.js";

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
  const albumId = el.album.value || null;
  const albumText = albumId ? el.album.options[el.album.selectedIndex].text : "-";
  const params = new URLSearchParams({
    rounds: el.roundCount.value,
    round_length: el.roundLength.value,
    location_mode: String(el.goalLocation.checked),
    date_mode: String(el.goalDate.checked),
    library: el.library.value,
    album: albumText,
  });
  return params;
}

import { state } from "./state.js";
import { t } from "./i18n.js";

export const PLAYER_COLORS = [
  "#f25f5c",
  "#0f7c7f",
  "#7048e8",
  "#f7b267",
  "#2f80ed",
  "#e0338d",
  "#3aa655",
  "#8d5524",
];

export const ACTUAL_COLOR = "#1f2a44";

export function normalizedName(playerName) {
  return String(playerName || "?").replace(/[^\p{L}\p{N}]/gu, "");
}

export function playerColor(playerName) {
  const index = state.players.indexOf(playerName);
  return PLAYER_COLORS[(index < 0 ? 0 : index) % PLAYER_COLORS.length];
}

export function playerInitial(playerName) {
  const letters = normalizedName(playerName);
  const first = (letters[0] || "?").toUpperCase();

  // Players sharing a first letter get a second character so map pins stay unambiguous.
  const clashes = state.players.filter((name) => (normalizedName(name)[0] || "?").toUpperCase() === first);
  if (clashes.length > 1 && letters.length > 1) {
    return first + letters[1].toLowerCase();
  }
  return first;
}

export function formatMonth(year, month) {
  if (!year || !month) {
    return t("fmt.no_guess");
  }
  return `${String(month).padStart(2, "0")}/${year}`;
}

export function formatPlace(reveal) {
  // Immich reverse-geocodes assets already, so reuse its labels.
  const parts = [reveal.actual_country, reveal.actual_city].filter(Boolean);
  if (parts.length > 0) {
    return parts.join(", ");
  }
  if (reveal.actual_latitude === null || reveal.actual_longitude === null) {
    return t("fmt.unknown_place");
  }
  return `${reveal.actual_latitude.toFixed(4)}, ${reveal.actual_longitude.toFixed(4)}`;
}

export function formatDistance(km) {
  if (km === null || km === undefined) {
    return "-";
  }
  if (km < 1) {
    return `${Math.round(km * 1000)} m`;
  }
  if (km < 10) {
    return `${km.toFixed(1)} km`;
  }
  return `${Math.round(km).toLocaleString()} km`;
}

export function formatMonthError(result) {
  if (result.date_diff_days === null || result.date_diff_days === undefined) {
    return "-";
  }

  const years = result.date_diff_years_part ?? 0;
  const months = result.date_diff_months_part ?? 0;
  const days = result.date_diff_days_part ?? result.date_diff_days ?? 0;

  if (years === 0 && months === 0) {
    const dayWord = days === 1 ? t("fmt.day") : t("fmt.days");
    return `${days} ${dayWord}`;
  }

  if (years === 0) {
    const dayWord = days === 1 ? t("fmt.day") : t("fmt.days");
    return `${months} ${t("fmt.mon")} ${days} ${dayWord}`;
  }

  const yearWord = years === 1 ? t("fmt.year") : t("fmt.years");
  return `${years} ${yearWord} ${months} ${t("fmt.mon")}`;
}

export function buildCell(content, isHeader = false) {
  const cell = document.createElement(isHeader ? "th" : "td");
  if (content instanceof Node) {
    cell.appendChild(content);
  } else {
    cell.textContent = content;
  }
  return cell;
}

export function playerBadge(playerName) {
  const badge = document.createElement("span");
  badge.className = "legend-badge";
  badge.style.background = playerColor(playerName);
  badge.textContent = playerInitial(playerName);
  return badge;
}

export function playerNameCell(playerName, timedOut = false) {
  const wrap = document.createElement("span");
  wrap.className = "player-cell";
  wrap.append(playerBadge(playerName), document.createTextNode(playerName));
  if (timedOut) {
    const tag = document.createElement("span");
    tag.className = "timed-out-tag";
    tag.textContent = t("fmt.timed_out_tag");
    wrap.appendChild(tag);
  }
  return wrap;
}

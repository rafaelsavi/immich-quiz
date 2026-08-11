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
    if (days === 0) {
      return `${months} ${t("fmt.mon")}`;
    }
    const dayWord = days === 1 ? t("fmt.day") : t("fmt.days");
    return `${months} ${t("fmt.mon")} ${days} ${dayWord}`;
  }

  const yearWord = years === 1 ? t("fmt.year") : t("fmt.years");
  if (months === 0) {
    return `${years} ${yearWord}`;
  }
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

export function renderRoundMeta(container, options = {}) {
  if (!container) return;
  const {
    roundNum,
    totalRounds,
    playerNum,
    totalPlayers = 1,
    playerName,
    isReveal = false,
    showHelp = false,
    onHelpClick = null,
  } = options;

  container.replaceChildren();

  const pillsWrap = document.createElement("div");
  pillsWrap.className = "round-meta-pills";

  // 1. Round Number Pill
  if (roundNum && totalRounds) {
    const roundPill = document.createElement("span");
    roundPill.className = "round-meta-pill round-meta-number";

    const flagSvgWrap = document.createElement("span");
    flagSvgWrap.className = "meta-pill-icon-wrap";
    flagSvgWrap.innerHTML = `<svg class="meta-pill-icon" viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M4 15s1-1 4-1 5 2 8 2 4-1 4-1V3s-1 1-4 1-5-2-8-2-4 1-4 1z"></path><line x1="4" y1="22" x2="4" y2="15"></line></svg>`;

    const roundText = document.createElement("span");
    roundText.className = "round-meta-text";
    roundText.textContent = t("game.round_label", roundNum, totalRounds);

    roundPill.append(flagSvgWrap.firstElementChild, roundText);
    pillsWrap.appendChild(roundPill);
  }

  if (isReveal) {
    // 2. Reveal Tag Pill
    const revealPill = document.createElement("span");
    revealPill.className = "round-meta-pill round-meta-reveal-tag";

    const starSvgWrap = document.createElement("span");
    starSvgWrap.className = "meta-pill-icon-wrap";
    starSvgWrap.innerHTML = `<svg class="meta-pill-icon" viewBox="0 0 24 24" width="13" height="13" fill="currentColor"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"></polygon></svg>`;

    const revealText = document.createElement("span");
    revealText.textContent = t("reveal.badge");

    revealPill.append(starSvgWrap.firstElementChild, revealText);
    pillsWrap.appendChild(revealPill);
  } else if (playerName) {
    // 2. Player Info Pill
    const playerPill = document.createElement("span");
    playerPill.className = "round-meta-pill round-meta-player";

    const badge = playerBadge(playerName);
    playerPill.appendChild(badge);

    const playerSpan = document.createElement("span");
    const labelText = totalPlayers > 1 ? t("game.player_label", playerNum, "") : "";
    if (labelText) {
      playerSpan.appendChild(document.createTextNode(labelText + " "));
    }
    const strong = document.createElement("strong");
    strong.textContent = playerName;
    playerSpan.appendChild(strong);

    playerPill.appendChild(playerSpan);
    pillsWrap.appendChild(playerPill);
  }

  container.appendChild(pillsWrap);

  if (showHelp) {
    const helpBtn = document.createElement("button");
    helpBtn.type = "button";
    helpBtn.className = "shuffle-help-btn";
    helpBtn.textContent = t("game.help_btn");
    if (onHelpClick) {
      helpBtn.addEventListener("click", onHelpClick);
    }
    container.appendChild(helpBtn);
  }
}


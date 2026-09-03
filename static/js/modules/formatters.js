import { state } from "./state.js";
import { t, formatNumber } from "./i18n.js";

export const PLAYER_COLORS = [
  "#f25f5c",
  "#0f7c7f",
  "#7048e8",
  "#f7b267",
  "#2f80ed",
  "#e0338d",
  "#3aa655",
  "#8d5524",
  "#17a2b8",
  "#fd7e14",
  "#6f42c1",
  "#20c997",
  "#d63384",
  "#4d96ff",
  "#ff6b6b",
  "#198754",
];

export const ACTUAL_COLOR = "#1f2a44";

const _assignedPlayerColors = new Map();

/**
 * Register a specific individual color for a player name (e.g. from challenge session/leaderboard).
 * @param {string} playerName
 * @param {string} color
 */
export function registerPlayerColor(playerName, color) {
  if (!playerName || !color) return;
  _assignedPlayerColors.set(playerName, color);
}

/**
 * Clear all explicitly registered player colors.
 */
export function clearPlayerColors() {
  _assignedPlayerColors.clear();
}

export function normalizedName(playerName) {
  return String(playerName || "?").replace(/[^\p{L}\p{N}]/gu, "");
}

export function playerColor(playerName) {
  if (typeof playerName === "number") {
    return PLAYER_COLORS[Math.abs(playerName) % PLAYER_COLORS.length];
  }
  if (!playerName) {
    return PLAYER_COLORS[0];
  }

  // 1. Explicitly registered color (e.g. from challenge session or leaderboard)
  if (_assignedPlayerColors.has(playerName)) {
    return _assignedPlayerColors.get(playerName);
  }

  // 2. Index in state.players (for local games and synced challenge rosters)
  const index = state.players ? state.players.indexOf(playerName) : -1;
  if (index >= 0) {
    return PLAYER_COLORS[index % PLAYER_COLORS.length];
  }

  // 3. Deterministic hash fallback for unregistered names so distinct players don't all get color 0
  let hash = 0;
  const str = String(playerName);
  for (let i = 0; i < str.length; i++) {
    hash = (hash * 31 + str.charCodeAt(i)) & 0xffffffff;
  }
  const assigned = PLAYER_COLORS[Math.abs(hash) % PLAYER_COLORS.length];
  _assignedPlayerColors.set(playerName, assigned);
  return assigned;
}

export function playerInitial(playerName) {
  if (typeof playerName === "number") {
    return `#${playerName + 1}`;
  }
  const letters = normalizedName(playerName);
  const first = (letters[0] || "?").toUpperCase();

  // Players sharing a first letter get a second character so map pins stay unambiguous.
  const pool = state.players && state.players.length > 0
    ? state.players
    : Array.from(_assignedPlayerColors.keys());

  const clashes = pool.filter((name) => (normalizedName(name)[0] || "?").toUpperCase() === first);
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
  if (!reveal) {
    return t("fmt.unknown_place");
  }
  // Immich reverse-geocodes assets already, so reuse its labels.
  const parts = [reveal.actual_city, reveal.actual_country].filter(Boolean);
  if (parts.length > 0) {
    return parts.join(", ");
  }
  if (
    reveal.actual_latitude === null ||
    reveal.actual_latitude === undefined ||
    reveal.actual_longitude === null ||
    reveal.actual_longitude === undefined
  ) {
    return t("fmt.unknown_place");
  }
  return `${Number(reveal.actual_latitude).toFixed(4)}, ${Number(reveal.actual_longitude).toFixed(4)}`;
}

/**
 * Create a standardized DOM element for a rank medal or number badge.
 * @param {number|string} rank
 * @param {object} [options]
 * @param {boolean} [options.dot=false]
 * @param {boolean} [options.showNumber=false]
 * @returns {HTMLSpanElement}
 */
export function createRankBadge(rank, options = {}) {
  const r = parseInt(rank, 10);
  const span = document.createElement("span");
  if (isNaN(r) || r <= 0) {
    span.className = "rank-num rank-empty";
    span.textContent = "—";
    return span;
  }
  const showNumber = options.showNumber ?? false;
  if (r === 1) {
    span.className = "rank-medal";
    span.textContent = showNumber ? "🥇 1" : "🥇";
    span.setAttribute("title", t("leaderboard.rank_1st"));
  } else if (r === 2) {
    span.className = "rank-medal";
    span.textContent = showNumber ? "🥈 2" : "🥈";
    span.setAttribute("title", t("leaderboard.rank_2nd"));
  } else if (r === 3) {
    span.className = "rank-medal";
    span.textContent = showNumber ? "🥉 3" : "🥉";
    span.setAttribute("title", t("leaderboard.rank_3rd"));
  } else {
    span.className = "rank-num";
    span.textContent = options.dot ? `${r}.` : `${r}`;
  }
  return span;
}

/**
 * Render a standardized rank badge HTML string for leaderboard and standings tables.
 * @param {number|string} rank
 * @param {object} [options]
 * @param {boolean} [options.dot=false]
 * @param {boolean} [options.showNumber=false]
 * @returns {string} HTML string
 */
export function formatRankBadge(rank, options = {}) {
  const r = parseInt(rank, 10);
  if (isNaN(r) || r <= 0) {
    return `<span class="rank-num rank-empty">—</span>`;
  }
  const showNumber = options.showNumber ?? false;
  if (r === 1) {
    const text = showNumber ? "🥇 1" : "🥇";
    return `<span class="rank-medal" title="${t("leaderboard.rank_1st")}">${text}</span>`;
  }
  if (r === 2) {
    const text = showNumber ? "🥈 2" : "🥈";
    return `<span class="rank-medal" title="${t("leaderboard.rank_2nd")}">${text}</span>`;
  }
  if (r === 3) {
    const text = showNumber ? "🥉 3" : "🥉";
    return `<span class="rank-medal" title="${t("leaderboard.rank_3rd")}">${text}</span>`;
  }
  const suffix = options.dot ? "." : "";
  return `<span class="rank-num">${r}${suffix}</span>`;
}

/**
 * Format a competitive rank or place badge.
 * Returns a medal badge for top 3 (🥇 1, 🥈 2, 🥉 3) or the rank number (e.g. "4").
 * @param {number|string} rank
 * @param {object} [options]
 * @param {boolean} [options.medals=true] Whether to prefix top 3 ranks with medal emojis.
 * @param {boolean} [options.asBadge=false] Whether to wrap in HTML badge span.
 * @returns {string}
 */
export function formatRank(rank, options = {}) {
  const r = parseInt(rank, 10);
  if (isNaN(r) || r <= 0) {
    return "—";
  }
  if (options.asBadge) {
    return formatRankBadge(r, options);
  }
  const useMedals = options.medals !== false;
  if (useMedals) {
    if (r === 1) return "🥇 1";
    if (r === 2) return "🥈 2";
    if (r === 3) return "🥉 3";
  }
  return String(r);
}

/**
 * Format a challenge rounds completion badge.
 * Standardized across Grand Reveal (#grand-reveal-table) and Challenges Hub (.standings-table).
 * @param {number} completedRounds
 * @param {number} totalRounds
 * @param {boolean} [isFinished=false]
 * @returns {string} HTML string
 */
export function formatRoundsBadge(completedRounds, totalRounds, isFinished = false) {
  const isFin = Boolean(isFinished || (totalRounds && completedRounds >= totalRounds));
  const progressStr = totalRounds ? `${completedRounds}/${totalRounds}` : `${completedRounds}`;
  if (isFin) {
    return `<span class="challenge-rounds-pill finished" title="${t("challenge.finished_badge")}">🏁 ${progressStr}</span>`;
  }
  return `<span class="challenge-rounds-pill in-progress" title="${t("challenge.in_progress_badge")}">⏳ ${progressStr}</span>`;
}

/**
 * Render a standardized player cell HTML string for leaderboard and standings tables.
 * @param {string} playerName
 * @param {object} [options]
 * @param {boolean} [options.isWinner=false]
 * @param {boolean} [options.isCurrent=false]
 * @param {string} [options.awardsHtml=""]
 * @returns {string} HTML string
 */
export function formatPlayerCellHtml(playerName, options = {}) {
  const col = playerColor(playerName);
  const init = playerInitial(playerName);
  const crown = options.isWinner ? ` <span class="winner-crown" title="Winner">👑</span>` : "";
  const you = options.isCurrent ? ` <span class="challenge-you-tag">(You)</span>` : "";
  const awards = options.awardsHtml ? `<div class="player-awards-list">${options.awardsHtml}</div>` : "";

  return `
    <span class="player-cell">
      <span class="legend-badge" style="background:${col};">${init}</span>
      <span class="player-name-text">${playerName}</span>
      ${crown}${you}
    </span>
    ${awards}
  `;
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
  return `${formatNumber(Math.round(km))} km`;
}

export function formatMonthError(result) {
  if (result.date_diff_days === null || result.date_diff_days === undefined) {
    return "-";
  }

  let years = result.date_diff_years_part;
  let months = result.date_diff_months_part;
  let days = result.date_diff_days_part;

  if ((years === undefined || months === undefined) && result.guessed_year && result.guessed_month) {
    const actYear = result.actual_year ?? state.lastReveal?.actual_year;
    const actMonth = result.actual_month ?? state.lastReveal?.actual_month;
    if (actYear && actMonth) {
      const diffTotalMonths = Math.abs((result.guessed_year - actYear) * 12 + (result.guessed_month - actMonth));
      years = Math.floor(diffTotalMonths / 12);
      months = diffTotalMonths % 12;
      days = 0;
    }
  }

  if ((years === undefined || months === undefined) && result.date_diff_days !== null && result.date_diff_days !== undefined) {
    if (result.date_diff_days >= 30) {
      const totalMonthsApprox = Math.round(result.date_diff_days / 30.4375);
      years = Math.floor(totalMonthsApprox / 12);
      months = totalMonthsApprox % 12;
      days = 0;
    }
  }

  years = years ?? 0;
  months = months ?? 0;
  days = days ?? result.date_diff_days ?? 0;

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
  const nameSpan = document.createElement("span");
  nameSpan.className = "player-name-text";
  nameSpan.textContent = playerName;
  wrap.append(playerBadge(playerName), nameSpan);
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

/**
 * Format relative duration string from milliseconds.
 * @param {number} diffMs
 * @param {boolean} [isPast=false]
 * @returns {string}
 */
export function formatRelativeTime(diffMs, isPast = false) {
  const absSec = Math.floor(Math.abs(diffMs) / 1000);
  const minutes = Math.floor(absSec / 60);
  const hours = Math.floor(minutes / 60);
  const days = Math.floor(hours / 24);

  if (days > 0) {
    const dStr = `${days}d ${hours % 24}h`;
    return isPast ? t("challenges_page.expired_relative_ago", dStr) : t("challenges_page.expires_relative_in", dStr);
  }
  if (hours > 0) {
    const hStr = `${hours}h ${minutes % 60}m`;
    return isPast ? t("challenges_page.expired_relative_ago", hStr) : t("challenges_page.expires_relative_in", hStr);
  }
  if (minutes > 0) {
    const mStr = `${minutes}m`;
    return isPast ? t("challenges_page.expired_relative_ago", mStr) : t("challenges_page.expires_relative_in", mStr);
  }
  const sStr = `${absSec}s`;
  return isPast ? t("challenges_page.expired_relative_ago", sStr) : t("challenges_page.expires_relative_in", sStr);
}



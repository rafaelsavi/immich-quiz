import { state, el } from "./state.js";
import { api, setupFilterParams } from "./api.js";
import { buildCell } from "./formatters.js";
import { t, formatDateTime } from "./i18n.js";
import { getActiveFilterSummary } from "./setup_filters.js";

export function formatAccuracy(pct) {
  if (typeof pct !== "number" || isNaN(pct)) return "0%";
  const rounded = Math.round(pct * 10) / 10;
  return Number.isInteger(rounded) ? `${rounded}%` : `${rounded.toFixed(1)}%`;
}

export function updateLeaderboardScope() {
  if (!el.leaderboardScopePill) return;

  const lengthVal = el.roundLength ? el.roundLength.value : "1m";
  const lengthKey = `setup.round_${lengthVal}`;
  const lengthText = t(lengthKey) !== lengthKey ? t(lengthKey) : lengthVal;

  const gameMode = (state && state.gameMode) || "pinpoint";
  const modeText = gameMode === "album_shuffle" ? t("mode.album_shuffle") : t("mode.pinpoint");

  const filterScope = typeof getActiveFilterSummary === "function" ? getActiveFilterSummary() : t("leaderboard.scope_all");

  el.leaderboardScopePill.textContent = `${modeText} • ${lengthText} • ${filterScope}`;
}

let _leaderboardAbortCtrl = null;
let _leaderboardDebounceTimer = null;

export async function loadLeaderboard() {
  updateLeaderboardScope();
  if (_leaderboardAbortCtrl) {
    _leaderboardAbortCtrl.abort();
  }
  _leaderboardAbortCtrl = new AbortController();
  const signal = _leaderboardAbortCtrl.signal;

  try {
    const params = setupFilterParams();
    const raw = await api(`/api/leaderboard?${params}`, { signal });
    state.leaderboardRows = raw.map((row) => {
      const computedAcc =
        typeof row.accuracy_pct === "number"
          ? row.accuracy_pct
          : row.max_possible_score > 0
            ? (row.total_score / row.max_possible_score) * 100
            : 0;
      return {
        ...row,
        accuracy_pct: computedAcc,
      };
    });
    renderLeaderboard();
  } catch (err) {
    if (err.name === "AbortError" || (err.message && err.message.includes("abort"))) {
      // Ignored intentional request abort
      return;
    }
    throw err;
  }
}

export function loadLeaderboardDebounced(delay = 250) {
  updateLeaderboardScope();
  if (_leaderboardDebounceTimer) {
    clearTimeout(_leaderboardDebounceTimer);
  }
  _leaderboardDebounceTimer = setTimeout(() => {
    loadLeaderboard().catch((err) => {
      if (err.name !== "AbortError") {
        console.warn("Leaderboard refresh failed:", err);
      }
    });
  }, delay);
}

export function renderLeaderboard() {
  updateLeaderboardScope();
  const { key, asc } = state.leaderboardSort;
  const rows = [...state.leaderboardRows].sort((a, b) => {
    const av = a[key];
    const bv = b[key];

    if (typeof av === "number" && typeof bv === "number") {
      return asc ? av - bv : bv - av;
    }
    return asc ? String(av).localeCompare(String(bv)) : String(bv).localeCompare(String(av));
  });

  el.leaderboardBody.replaceChildren();

  if (rows.length === 0) {
    const tr = document.createElement("tr");
    tr.className = "leaderboard-empty-row";
    const td = document.createElement("td");
    td.colSpan = 3;
    td.className = "leaderboard-empty-cell";
    td.textContent = t("leaderboard.empty");
    tr.appendChild(td);
    el.leaderboardBody.appendChild(tr);
    renderSortIndicators();
    return;
  }

  rows.forEach((row, index) => {
    const tr = document.createElement("tr");
    const isPerfect = row.accuracy_pct >= 99.99;
    if (isPerfect) {
      tr.classList.add("is-perfect-row");
    }

    const cell1 = buildCell(formatDateTime(row.played_at));

    // Player cell with rank medal and optional perfect badge
    const playerWrap = document.createElement("span");
    playerWrap.className = "player-cell";

    const rankSpan = document.createElement("span");
    const isRankingDescending = (key === "accuracy_pct" || key === "total_score") && !asc;
    const effectiveRank = isRankingDescending ? index + 1 : row.rank;

    if (effectiveRank === 1) {
      rankSpan.className = "rank-medal";
      rankSpan.textContent = "🥇";
      rankSpan.setAttribute("title", t("leaderboard.rank_1st"));
    } else if (effectiveRank === 2) {
      rankSpan.className = "rank-medal";
      rankSpan.textContent = "🥈";
      rankSpan.setAttribute("title", t("leaderboard.rank_2nd"));
    } else if (effectiveRank === 3) {
      rankSpan.className = "rank-medal";
      rankSpan.textContent = "🥉";
      rankSpan.setAttribute("title", t("leaderboard.rank_3rd"));
    } else {
      rankSpan.className = "rank-num";
      rankSpan.textContent = `${effectiveRank || index + 1}.`;
    }

    const nameSpan = document.createElement("span");
    nameSpan.className = "player-name-text";
    nameSpan.textContent = row.player_name;

    playerWrap.append(rankSpan, nameSpan);

    if (isPerfect) {
      const perfectBadge = document.createElement("span");
      perfectBadge.className = "perfect-badge";
      perfectBadge.innerHTML = `<span>★</span><span class="perfect-badge-text">${t("leaderboard.perfect_badge")}</span>`;
      playerWrap.appendChild(perfectBadge);
    }

    const cell2 = buildCell(playerWrap);

    // Accuracy cell with color-coded tier badge
    const accBadge = document.createElement("span");
    accBadge.className = "accuracy-badge";
    if (isPerfect) {
      accBadge.classList.add("accuracy-tier-perfect");
    } else if (row.accuracy_pct >= 90) {
      accBadge.classList.add("accuracy-tier-high");
    } else if (row.accuracy_pct >= 75) {
      accBadge.classList.add("accuracy-tier-medium");
    } else {
      accBadge.classList.add("accuracy-tier-low");
    }
    accBadge.textContent = formatAccuracy(row.accuracy_pct);

    const cell3 = buildCell(accBadge);
    cell3.className = "col-accuracy";

    tr.append(cell1, cell2, cell3);
    el.leaderboardBody.appendChild(tr);
  });

  renderSortIndicators();
}

export function renderSortIndicators() {
  const { key, asc } = state.leaderboardSort;
  el.leaderboardHead.querySelectorAll("th[data-sort]").forEach((th) => {
    const arrow = th.querySelector(".sort-arrow");
    const isActive = th.getAttribute("data-sort") === key;
    if (arrow) {
      arrow.textContent = isActive ? (asc ? "\u25B2" : "\u25BC") : "";
    }
    th.setAttribute("aria-sort", isActive ? (asc ? "ascending" : "descending") : "none");
  });
}

export function handleSortClick(event) {
  const th = event.target.closest("th[data-sort]");
  if (!th) {
    return;
  }

  const key = th.getAttribute("data-sort");
  if (state.leaderboardSort.key === key) {
    state.leaderboardSort.asc = !state.leaderboardSort.asc;
  } else {
    state.leaderboardSort.key = key;
    state.leaderboardSort.asc = true;
  }
  renderLeaderboard();
}

import { state, el } from "./state.js";
import { api, setupFilterParams } from "./api.js";
import { buildCell } from "./formatters.js";
import { t } from "./i18n.js";

export function formatAccuracy(pct) {
  if (typeof pct !== "number" || isNaN(pct)) return "0%";
  const rounded = Math.round(pct * 10) / 10;
  return Number.isInteger(rounded) ? `${rounded}%` : `${rounded.toFixed(1)}%`;
}

export function updateLeaderboardScope() {
  if (!el.leaderboardScopePill) return;

  const rounds = el.roundCount ? el.roundCount.value : "10";
  const lengthVal = el.roundLength ? el.roundLength.value : "1m";
  const lengthKey = `setup.round_${lengthVal}`;
  const lengthText = t(lengthKey) !== lengthKey ? t(lengthKey) : lengthVal;

  const gameMode = (state && state.gameMode) || "pinpoint";
  const modeText = gameMode === "album_shuffle" ? t("mode.album_shuffle") : t("mode.pinpoint");

  const albumSelect = state.filters && state.filters.albumMultiSelect;
  const selectedAlbums = albumSelect ? albumSelect.getSelectedItems() : [];
  let albumScope = t("leaderboard.scope_all");
  if (selectedAlbums.length === 1) {
    albumScope = selectedAlbums[0].name;
  } else if (selectedAlbums.length > 1) {
    albumScope = `${selectedAlbums.length} albums`;
  }

  el.leaderboardScopePill.textContent = `${modeText} • ${rounds}R • ${lengthText} • ${albumScope}`;
}

export async function loadLeaderboard() {
  updateLeaderboardScope();
  const params = setupFilterParams();
  const raw = await api(`/api/leaderboard?${params}`);
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

    const cell1 = buildCell(new Date(row.played_at).toLocaleString(state.language));

    // Player cell with rank medal and optional perfect badge
    const playerWrap = document.createElement("span");
    playerWrap.className = "player-cell";

    const rankSpan = document.createElement("span");
    const isRankingDescending = (key === "accuracy_pct" || key === "total_score") && !asc;
    const effectiveRank = isRankingDescending ? index + 1 : row.rank;

    if (effectiveRank === 1) {
      rankSpan.className = "rank-medal";
      rankSpan.textContent = "🥇";
      rankSpan.setAttribute("title", "1st Place");
    } else if (effectiveRank === 2) {
      rankSpan.className = "rank-medal";
      rankSpan.textContent = "🥈";
      rankSpan.setAttribute("title", "2nd Place");
    } else if (effectiveRank === 3) {
      rankSpan.className = "rank-medal";
      rankSpan.textContent = "🥉";
      rankSpan.setAttribute("title", "3rd Place");
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

    const cell3 = buildCell(formatAccuracy(row.accuracy_pct));
    cell3.className = "col-accuracy hide-on-mobile";

    const cell4 = buildCell(`${row.total_score}/${row.max_possible_score}`);
    if (isPerfect) {
      cell4.classList.add("is-perfect-cell");
    }

    tr.append(cell1, cell2, cell3, cell4);
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

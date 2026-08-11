import { state, el } from "./state.js";
import { api, setupFilterParams } from "./api.js";
import { buildCell } from "./formatters.js";

export async function loadLeaderboard() {
  const params = setupFilterParams();
  const raw = await api(`/api/leaderboard?${params}`);
  // Compute accuracy_pct client-side so it can be sorted and displayed.
  state.leaderboardRows = raw.map((row) => ({
    ...row,
    accuracy_pct:
      row.max_possible_score > 0
        ? Math.round((row.total_score / row.max_possible_score) * 100)
        : 0,
  }));
  renderLeaderboard();
}

export function renderLeaderboard() {
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
  rows.forEach((row) => {
    const tr = document.createElement("tr");
    const cell1 = buildCell(new Date(row.played_at).toLocaleString(state.language));
    const cell2 = buildCell(row.player_name);
    const cell3 = buildCell(`${row.accuracy_pct}%`);
    cell3.className = "col-accuracy hide-on-mobile";
    const cell4 = buildCell(`${row.total_score}/${row.max_possible_score}`);
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

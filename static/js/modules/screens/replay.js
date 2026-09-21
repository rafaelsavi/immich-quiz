/**
 * Interactive Match Replay Screen & Catalog Controller
 * Replays directory (/replays) and delegation to Unified Match Review Screen (/game/:id/replay).
 */

import { el } from "../state.js";
import { t, formatDateTime } from "../i18n.js";
import { showCard } from "./common.js";
import { navigate } from "../router.js";
import { escapeHtml, playerColor, playerInitial } from "../formatters.js";
import { showMatchSummaryByMatchId, refreshSummaryLanguage } from "./summary.js";

let _listenersBound = false;

export function initReplay() {
  if (_listenersBound) return;
  _listenersBound = true;

  initReplayCatalog();

  const backBtn = document.getElementById("replay-back-btn");
  if (backBtn) {
    backBtn.addEventListener("click", () => {
      navigate("/replays");
    });
  }

  const exitBottomBtn = document.getElementById("replay-exit-bottom-btn");
  if (exitBottomBtn) {
    exitBottomBtn.addEventListener("click", () => {
      navigate("/replays");
    });
  }

  const errBackBtn = document.getElementById("replay-error-back-btn");
  if (errBackBtn) {
    errBackBtn.addEventListener("click", () => {
      navigate("/replays");
    });
  }

  const shareBtn = document.getElementById("replay-share-btn");
  if (shareBtn) {
    shareBtn.addEventListener("click", async () => {
      const url = window.location.href;
      if (navigator.share) {
        try {
          await navigator.share({
            title: "Immich Quiz Match Replay",
            url,
          });
          return;
        } catch (_) {}
      }
      try {
        await navigator.clipboard.writeText(url);
      } catch (_) {}
    });
  }
}

export { renderReplayTitleHeader } from "./summary.js";

export async function showMatchReplay(matchId) {
  await showMatchSummaryByMatchId(matchId, { mode: "replay" });
}

let _cachedMatches = [];
let _searchDebounceTimer = null;

export function initReplayCatalog() {
  const matchPlayerSearch = document.getElementById("stats-replays-player-search");
  const matchPlayerSearchClear = document.getElementById("stats-replays-search-clear");
  if (matchPlayerSearch) {
    matchPlayerSearch.addEventListener("input", () => {
      if (matchPlayerSearchClear) {
        matchPlayerSearchClear.classList.toggle("hidden", !matchPlayerSearch.value);
      }
      clearTimeout(_searchDebounceTimer);
      _searchDebounceTimer = setTimeout(() => {
        loadMatchesHistory();
      }, 200);
    });
  }

  if (matchPlayerSearchClear) {
    matchPlayerSearchClear.addEventListener("click", () => {
      if (matchPlayerSearch) {
        matchPlayerSearch.value = "";
        matchPlayerSearchClear.classList.add("hidden");
        matchPlayerSearch.focus();
        loadMatchesHistory();
      }
    });
  }

  const matchModeFilter = document.getElementById("stats-replays-mode-filter");
  if (matchModeFilter) {
    matchModeFilter.addEventListener("change", () => {
      loadMatchesHistory();
    });
  }

  const matchTypeFilter = document.getElementById("stats-replays-type-filter");
  if (matchTypeFilter) {
    matchTypeFilter.addEventListener("change", () => {
      loadMatchesHistory();
    });
  }

  const refreshBtn = document.getElementById("replays-page-refresh-btn");
  if (refreshBtn) {
    refreshBtn.addEventListener("click", () => {
      loadMatchesHistory();
    });
  }
}

export function showReplaysCatalog() {
  showCard(el.replaysPageCard);

  const heading = document.getElementById("replays-page-heading");
  const desc = document.getElementById("replays-page-desc");

  if (heading) {
    heading.setAttribute("data-i18n", "replay.catalog_title");
    heading.textContent = t("replay.catalog_title");
  }
  if (desc) {
    desc.setAttribute("data-i18n", "replay.catalog_subtitle");
    desc.textContent = t("replay.catalog_subtitle");
  }

  loadMatchesHistory();
}

async function loadMatchesHistory() {
  const container = document.getElementById("stats-replays-list");
  if (!container) return;

  const playerInput = document.getElementById("stats-replays-player-search");
  const modeSelect = document.getElementById("stats-replays-mode-filter");
  const typeSelect = document.getElementById("stats-replays-type-filter");

  const player = playerInput ? playerInput.value.trim() : "";
  const mode = modeSelect && modeSelect.value !== "all" ? modeSelect.value : "";
  const type = typeSelect && typeSelect.value !== "all" ? typeSelect.value : "";

  let url = `/api/matches?limit=40`;
  if (player) url += `&player=${encodeURIComponent(player)}`;
  if (mode) url += `&game_mode=${encodeURIComponent(mode)}`;
  if (type) url += `&play_mode=${encodeURIComponent(type)}`;

  container.innerHTML = `<div class="challenges-loading">${t("common.loading")}</div>`;

  try {
    const res = await fetch(url);
    if (!res.ok) throw new Error("Failed to fetch matches history");
    _cachedMatches = await res.json();
    renderMatchesHistory(_cachedMatches);
  } catch (err) {
    console.error("Error loading matches:", err);
    container.innerHTML = `<div class="empty-state">${t("replay.empty_matches")}</div>`;
  }
}

function renderMatchesHistory(matches) {
  const container = document.getElementById("stats-replays-list");
  if (!container) return;

  const playerInput = document.getElementById("stats-replays-player-search");
  const modeSelect = document.getElementById("stats-replays-mode-filter");
  const typeSelect = document.getElementById("stats-replays-type-filter");

  const player = playerInput ? playerInput.value.trim() : "";
  const mode = modeSelect && modeSelect.value !== "all" ? modeSelect.value : "";
  const type = typeSelect && typeSelect.value !== "all" ? typeSelect.value : "";
  const isFiltered = Boolean(player || mode || type);

  const replaysToolbar = document.querySelector("#replays-page-card .stats-toolbar");
  if (replaysToolbar) {
    replaysToolbar.style.display = (!matches || matches.length === 0) && !isFiltered ? "none" : "";
  }

  const totalBadge = document.getElementById("stats-replays-total-badge");
  if (totalBadge) {
    if (matches && matches.length > 0) {
      totalBadge.textContent = matches.length === 1
        ? t("replay.counter_single", matches.length)
        : t("replay.counter_plural", matches.length);
      totalBadge.classList.remove("hidden");
    } else {
      totalBadge.textContent = t("replay.counter_plural", 0);
      totalBadge.classList.toggle("hidden", !isFiltered);
    }
  }

  if (!matches || matches.length === 0) {
    if (isFiltered) {
      container.innerHTML = `
        <div class="stats-search-empty">
          <p>${t("replay.empty_matches")}</p>
          <button type="button" id="stats-clear-replays-filter-btn" class="btn-secondary btn-sm">
            <span>${t("stats.clear_search")}</span>
          </button>
        </div>
      `;
      document.getElementById("stats-clear-replays-filter-btn")?.addEventListener("click", () => {
        if (playerInput) playerInput.value = "";
        if (modeSelect) modeSelect.value = "all";
        if (typeSelect) typeSelect.value = "all";
        loadMatchesHistory();
      });
      return;
    }

    container.innerHTML = `
      <div class="stats-empty-guide">
        <div class="stats-empty-icon-wrap" aria-hidden="true">🎬</div>
        <h3 class="stats-empty-title">${t("replay.empty_title")}</h3>
        <p class="stats-empty-desc">${t("replay.empty_desc")}</p>
        <div class="stats-empty-actions">
          <button type="button" id="replay-empty-play-btn" class="btn-primary">
            <span>🎮</span>
            <span>${t("replay.play_match_cta")}</span>
          </button>
          <button type="button" id="replay-empty-challenge-btn" class="btn-secondary">
            <span>⚔️</span>
            <span>${t("stats.browse_challenges_cta")}</span>
          </button>
        </div>
        <div class="stats-empty-features">
          <div class="stats-empty-feature-item">
            <span class="stats-empty-feature-icon" aria-hidden="true">🎯</span>
            <span class="stats-empty-feature-title">${t("stats.feature_accuracy")}</span>
            <span class="stats-empty-feature-desc">${t("stats.feature_accuracy_desc")}</span>
          </div>
          <div class="stats-empty-feature-item">
            <span class="stats-empty-feature-icon" aria-hidden="true">🏆</span>
            <span class="stats-empty-feature-title">${t("stats.feature_podiums")}</span>
            <span class="stats-empty-feature-desc">${t("stats.feature_podiums_desc")}</span>
          </div>
          <div class="stats-empty-feature-item">
            <span class="stats-empty-feature-icon" aria-hidden="true">🎬</span>
            <span class="stats-empty-feature-title">${t("stats.feature_replays")}</span>
            <span class="stats-empty-feature-desc">${t("stats.feature_replays_desc")}</span>
          </div>
        </div>
      </div>
    `;

    document.getElementById("replay-empty-play-btn")?.addEventListener("click", () => {
      navigate("/");
    });
    document.getElementById("replay-empty-challenge-btn")?.addEventListener("click", () => {
      navigate("/challenges");
    });
    return;
  }

  container.innerHTML = matches
    .map((m) => {
      const modeIcon = m.game_mode === "unshuffle" ? "🔀" : "🎯";
      const modeLabel = m.game_mode === "unshuffle" ? t("mode.unshuffle") : t("mode.pinpoint");
      const isChallenge = m.play_mode === "challenge";
      const typeLabel = isChallenge
        ? t("replay.play_mode_challenge")
        : t("replay.play_mode_local");
      const typeIcon = isChallenge ? "⚔️" : "👥";
      const typeClass = isChallenge
        ? " badge-type-challenge"
        : " badge-type-local";
      const modeClass = m.game_mode === "unshuffle"
        ? " badge-mode-unshuffle"
        : " badge-mode-pinpoint";
      const playedStr = m.played_at ? formatDateTime(m.played_at) : "-";
      const winners = Array.isArray(m.winners)
        ? m.winners
        : (m.winner_name ? [m.winner_name] : []);

      const allPlayers = Array.isArray(m.players) ? m.players : [];
      // Put winners first so the winning player chip is prominently featured
      const sortedPlayers = [...allPlayers].sort((a, b) => {
        const aName = typeof a === "string" ? a : (a.player_name || "");
        const bName = typeof b === "string" ? b : (b.player_name || "");
        const aWin = winners.includes(aName) ? 1 : 0;
        const bWin = winners.includes(bName) ? 1 : 0;
        return bWin - aWin;
      });

      const maxVisible = 4;
      const visiblePlayers = sortedPlayers.slice(0, maxVisible);
      const remainingCount = sortedPlayers.length - visiblePlayers.length;
      const remainingNames = sortedPlayers
        .slice(maxVisible)
        .map((p) => (typeof p === "string" ? p : p.player_name || ""))
        .filter(Boolean)
        .join(", ");

      const playersListHtml = visiblePlayers
        .map((p) => {
          const playerName = typeof p === "string" ? p : (p.player_name || "");
          if (!playerName) return "";
          const color = (typeof p === "object" && (p.avatar_color || p.player_color))
            ? (p.avatar_color || p.player_color)
            : playerColor(playerName);
          const initial = playerInitial(playerName);
          const isWinner = winners.includes(playerName) || (typeof p === "object" && p.is_winner);
          const scoreInfo = (typeof p === "object" && p.total_score != null) ? ` (${p.total_score} pts)` : "";
          const winnerTooltip = isWinner ? ` 🏆 ${t("replay.winner")}` : "";
          const title = `${escapeHtml(playerName)}${scoreInfo}${winnerTooltip}`;

          return `
            <div class="replay-player-chip${isWinner ? " is-winner" : ""}" title="${title}">
              <span class="replay-player-avatar" style="background-color: ${color};">${initial}</span>
              <span class="replay-player-name">${escapeHtml(playerName)}</span>
              ${isWinner ? '<span class="replay-winner-crown" aria-hidden="true">👑</span>' : ""}
            </div>
          `;
        })
        .join("") +
        (remainingCount > 0
          ? `<span class="replay-more-players" title="${escapeHtml(remainingNames)}">+${remainingCount}</span>`
          : "");

      return `
        <div class="replay-catalog-item" data-match-id="${escapeHtml(m.match_id)}" role="button" tabindex="0" aria-label="${escapeHtml(modeLabel)} - ${escapeHtml(playedStr)}">
          <div class="replay-item-header">
            <div class="replay-item-badges">
              <span class="badge-tag badge-mode${modeClass}">${modeIcon} ${modeLabel}</span>
              <span class="badge-tag badge-type${typeClass}">${typeIcon} ${typeLabel}</span>
            </div>
            <div class="replay-item-time">${playedStr}</div>
          </div>

          <div class="replay-item-body">
            ${m.challenge_title ? `<div class="replay-item-challenge-title">${escapeHtml(m.challenge_title)}</div>` : ""}
            <div class="replay-item-players">
              ${playersListHtml}
            </div>
          </div>

          <div class="replay-item-footer">
            <span class="replay-action-link">🎬 ${t("replay.watch_replay")}</span>
            <span class="replay-action-arrow" aria-hidden="true">→</span>
          </div>
        </div>
      `;
    })
    .join("");

  container.querySelectorAll(".replay-catalog-item").forEach((item) => {
    const handleActivate = () => {
      const mid = item.getAttribute("data-match-id");
      if (mid) {
        navigate(`/game/${encodeURIComponent(mid)}/replay`);
      }
    };
    item.addEventListener("click", handleActivate);
    item.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        handleActivate();
      }
    });
  });
}

/**
 * Refresh replay screen in realtime when language toggle changes.
 */
export function refreshReplayPageLanguage() {
  const replaysCard = el.replaysPageCard || document.getElementById("replays-page-card");
  if (replaysCard && !replaysCard.classList.contains("hidden")) {
    const heading = document.getElementById("replays-page-heading");
    const desc = document.getElementById("replays-page-desc");
    if (heading) {
      heading.setAttribute("data-i18n", "replay.catalog_title");
      heading.textContent = t("replay.catalog_title");
    }
    if (desc) {
      desc.setAttribute("data-i18n", "replay.catalog_subtitle");
      desc.textContent = t("replay.catalog_subtitle");
    }
    renderMatchesHistory(_cachedMatches);
  }

  refreshSummaryLanguage();
}


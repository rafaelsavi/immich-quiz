/**
 * Dedicated Player Statistics, Directory & Profile Screen Controller
 * Handles player directory browsing, career accuracy analytics, and competitive profiles.
 */

import { state, el } from "../state.js";
import { api } from "../api.js";
import { t, tOr, formatDateTime } from "../i18n.js";
import { showCard } from "./common.js";
import { navigate } from "../router.js";
import { playerColor, playerInitial, escapeHtml, formatRankBadge } from "../formatters.js";

let _searchDebounceTimer = null;
let _cachedPlayers = [];
let _cachedProfileData = null;

export function initStats() {
  // Player search & sort
  const playerSearch = document.getElementById("stats-players-search");
  const playerSearchClear = document.getElementById("stats-players-search-clear");
  if (playerSearch) {
    playerSearch.addEventListener("input", () => {
      if (playerSearchClear) {
        playerSearchClear.classList.toggle("hidden", !playerSearch.value);
      }
      clearTimeout(_searchDebounceTimer);
      _searchDebounceTimer = setTimeout(() => {
        loadPlayerDirectory();
      }, 200);
    });
  }

  if (playerSearchClear) {
    playerSearchClear.addEventListener("click", () => {
      if (playerSearch) {
        playerSearch.value = "";
        playerSearchClear.classList.add("hidden");
        playerSearch.focus();
        loadPlayerDirectory();
      }
    });
  }

  const playerSort = document.getElementById("stats-players-sort");
  if (playerSort) {
    playerSort.addEventListener("change", () => {
      loadPlayerDirectory();
    });
  }

  const refreshBtn = document.getElementById("stats-page-refresh-btn");
  if (refreshBtn) {
    refreshBtn.addEventListener("click", () => {
      const profileView = document.getElementById("stats-profile-view");
      const isProfileActive = profileView && !profileView.classList.contains("hidden");
      if (isProfileActive && _cachedProfileData?.player?.player_name) {
        showPlayerProfile(_cachedProfileData.player.player_name);
      } else {
        loadPlayerDirectory();
      }
    });
  }
}

export function showPlayerDirectory() {
  _cachedProfileData = null;
  showCard(el.statsPageCard);

  const profileView = document.getElementById("stats-profile-view");
  const playersView = document.getElementById("stats-players-view");
  const heading = document.getElementById("stats-page-heading");
  const desc = document.getElementById("stats-page-desc");

  if (profileView) profileView.classList.add("hidden");
  if (playersView) playersView.classList.remove("hidden");

  if (heading) {
    heading.setAttribute("data-i18n", "stats.hub_title");
    heading.textContent = t("stats.hub_title");
  }
  if (desc) {
    desc.setAttribute("data-i18n", "stats.hub_subtitle");
    desc.textContent = t("stats.hub_subtitle");
  }

  loadPlayerDirectory();
}

// Backward-compatible alias for existing imports
export const showStatsHub = showPlayerDirectory;

async function loadPlayerDirectory() {
  const container = document.getElementById("stats-players-grid");
  if (!container) return;

  const searchInput = document.getElementById("stats-players-search");
  const sortSelect = document.getElementById("stats-players-sort");

  const search = searchInput ? searchInput.value.trim() : "";
  const sortBy = sortSelect ? sortSelect.value : "matches";

  container.innerHTML = `<div class="challenges-loading">${t("common.loading")}</div>`;

  try {
    const players = await api(`/api/players?search=${encodeURIComponent(search)}&sort_by=${encodeURIComponent(sortBy)}&limit=60`);
    _cachedPlayers = Array.isArray(players) ? players : [];
    renderPlayerDirectory(_cachedPlayers);
  } catch (err) {
    console.error("Error loading players:", err);
    container.innerHTML = `
      <div class="empty-state">
        <p>${escapeHtml(tOr("stats.error_loading_players", "Failed to load players directory."))}</p>
        <button type="button" id="stats-retry-btn" class="btn-secondary btn-sm" style="margin-top: 12px;">
          <span>${escapeHtml(tOr("stats.retry", "Try Again"))}</span>
        </button>
      </div>
    `;
    document.getElementById("stats-retry-btn")?.addEventListener("click", () => {
      loadPlayerDirectory();
    });
  }
}

function renderPlayerDirectory(players) {
  const container = document.getElementById("stats-players-grid");
  if (!container) return;

  const searchInput = document.getElementById("stats-players-search");
  const isFiltered = Boolean(searchInput && searchInput.value.trim());

  const playersToolbar = document.querySelector("#stats-players-view .stats-toolbar");
  if (playersToolbar) {
    playersToolbar.style.display = (!players || players.length === 0) && !isFiltered ? "none" : "";
  }

  const totalBadge = document.getElementById("stats-players-total-badge");
  if (totalBadge) {
    if (players && players.length > 0) {
      totalBadge.textContent = players.length === 1
        ? t("stats.player_count_single", players.length)
        : t("stats.player_count_plural", players.length);
      totalBadge.classList.remove("hidden");
    } else {
      totalBadge.textContent = t("stats.player_count_plural", 0);
      totalBadge.classList.toggle("hidden", !isFiltered);
    }
  }

  if (!players || players.length === 0) {
    if (isFiltered) {
      container.innerHTML = `
        <div class="stats-search-empty">
          <p>${t("stats.no_players_found")}</p>
          <button type="button" id="stats-clear-search-btn" class="btn-secondary btn-sm">
            <span>${t("stats.clear_search")}</span>
          </button>
        </div>
      `;
      document.getElementById("stats-clear-search-btn")?.addEventListener("click", () => {
        if (searchInput) {
          searchInput.value = "";
          document.getElementById("stats-players-search-clear")?.classList.add("hidden");
          loadPlayerDirectory();
        }
      });
      return;
    }

    container.innerHTML = `
      <div class="stats-empty-guide">
        <div class="stats-empty-icon-wrap" aria-hidden="true">👥</div>
        <h3 class="stats-empty-title">${t("stats.empty_players_title")}</h3>
        <p class="stats-empty-desc">${t("stats.empty_players_desc")}</p>
        <div class="stats-empty-actions">
          <button type="button" id="stats-empty-play-btn" class="btn-primary">
            <span>🎮</span>
            <span>${t("stats.start_game_cta")}</span>
          </button>
          <button type="button" id="stats-empty-challenge-btn" class="btn-secondary">
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

    document.getElementById("stats-empty-play-btn")?.addEventListener("click", () => {
      navigate("/");
    });
    document.getElementById("stats-empty-challenge-btn")?.addEventListener("click", () => {
      navigate("/challenges");
    });
    return;
  }

  container.innerHTML = players
    .map((p) => {
      const initial = (p.player_name || "?").charAt(0).toUpperCase();
      const color = p.avatar_color || playerColor(p.player_name);
      const pointsFormatted = p.career_points ? p.career_points.toLocaleString() : "0";
      const winRateFormatted = p.win_rate_pct !== undefined ? `${p.win_rate_pct}%` : "0%";
      const lastPlayedStr = p.last_played_at ? formatDateTime(p.last_played_at) : "-";

      return `
        <div class="player-card" data-player="${escapeHtml(p.player_name)}">
          <div class="player-card-head">
            <div class="player-card-avatar" style="background-color: ${color};">
              ${initial}
            </div>
            <div class="player-card-meta">
              <h3 class="player-card-name">${escapeHtml(p.player_name)}</h3>
              <div class="player-card-time">${lastPlayedStr}</div>
            </div>
          </div>

          <div class="player-card-stats-row">
            <div class="player-stat-col">
              <span class="player-stat-val">${p.matches_played ?? 0}</span>
              <span class="player-stat-lbl">${t("stats.matches_played")}</span>
            </div>
            <div class="player-stat-col">
              <span class="player-stat-val">${winRateFormatted}</span>
              <span class="player-stat-lbl">${t("stats.win_rate")}</span>
            </div>
            <div class="player-stat-col">
              <span class="player-stat-val">${pointsFormatted}</span>
              <span class="player-stat-lbl">${t("stats.score_col")}</span>
            </div>
          </div>

          <div class="player-card-footer">
            <span>${t("stats.view_profile")}</span>
            <span aria-hidden="true">→</span>
          </div>
        </div>
      `;
    })
    .join("");

  container.querySelectorAll(".player-card").forEach((card) => {
    card.addEventListener("click", () => {
      const name = card.getAttribute("data-player");
      if (name) {
        navigate(`/players/${encodeURIComponent(name)}`);
      }
    });
  });
}

export async function showPlayerProfile(playerName) {
  showCard(el.statsPageCard);

  const profileView = document.getElementById("stats-profile-view");
  const heading = document.getElementById("stats-page-heading");
  const desc = document.getElementById("stats-page-desc");

  document.getElementById("stats-players-view")?.classList.add("hidden");

  if (heading) {
    heading.setAttribute("data-i18n", "stats.profile_title");
    heading.textContent = t("stats.profile_title");
  }
  if (desc) {
    desc.removeAttribute("data-i18n");
    desc.textContent = playerName;
  }

  if (profileView) {
    profileView.classList.remove("hidden");
    profileView.innerHTML = `<div class="challenges-loading">${t("common.loading")}</div>`;
  }

  try {
    const profileData = await api(`/api/players/${encodeURIComponent(playerName)}/profile`);
    _cachedProfileData = profileData;
    renderPlayerProfile(profileData);
  } catch (err) {
    console.error("Error loading player profile:", err);
    if (profileView) {
      profileView.innerHTML = `
        <div class="empty-state" style="padding: 3rem 1rem; text-align: center;">
          <p style="color: var(--text-muted); font-size: 1.1rem;">${t("stats.player_not_found", playerName)}</p>
          <button type="button" class="btn-secondary btn-sm page-back-btn" style="margin-top: 1rem;" id="profile-back-btn">
            <span aria-hidden="true">←</span>
            <span>${t("stats.back_to_hub")}</span>
          </button>
        </div>
      `;
      document.getElementById("profile-back-btn")?.addEventListener("click", () => {
        navigate("/players");
      });
    }
  }
}

function createSvgGaugeHtml(pct) {
  const radius = 38;
  const circumference = 2 * Math.PI * radius;
  const clamped = Math.max(0, Math.min(100, pct));
  const offset = circumference - (clamped / 100) * circumference;

  let strokeColor = "#10b981"; // emerald
  if (clamped < 50) strokeColor = "#ef4444"; // red
  else if (clamped < 75) strokeColor = "#f59e0b"; // amber
  else if (clamped < 90) strokeColor = "#3b82f6"; // blue

  return `
    <div class="svg-gauge-wrap">
      <svg viewBox="0 0 100 100">
        <circle class="svg-gauge-bg" cx="50" cy="50" r="${radius}" fill="none" stroke-width="8" />
        <circle class="svg-gauge-fill" cx="50" cy="50" r="${radius}" fill="none" stroke="${strokeColor}" stroke-width="8"
          stroke-dasharray="${circumference}" stroke-dashoffset="${offset}" stroke-linecap="round" />
      </svg>
      <div class="svg-gauge-text">${clamped}%</div>
    </div>
  `;
}

function createTiersHtml(tiers) {
  if (!tiers || tiers.length === 0) return "";

  const fillClassMap = {
    top: "tier-fill-top",
    great: "tier-fill-great",
    moderate: "tier-fill-moderate",
    low: "tier-fill-low",
  };

  return `
    <div class="tiers-container">
      ${tiers
        .map((tier) => {
          const tierKey = tier.tier_key || tier.tier || "moderate";
          const fillClass = fillClassMap[tierKey] || "tier-fill-moderate";
          const countStr = tier.count === 1 ? t("stats.round_single", 1) : t("stats.rounds_plural", tier.count);
          let tierLabel = tOr(`stats.tier_${tierKey}`, tier.label || tierKey);
          if (tier.min_pct !== undefined && tier.max_pct !== undefined && !tierLabel.includes("%")) {
            tierLabel += ` (${tier.min_pct}–${tier.max_pct}%)`;
          }

          return `
            <div class="tier-bar-row">
              <div class="tier-bar-header">
                <span class="tier-name">${escapeHtml(tierLabel)}</span>
                <span class="tier-count">${countStr} (${tier.percentage}%)</span>
              </div>
              <div class="tier-bar-track">
                <div class="tier-bar-fill ${fillClass}" style="width: ${tier.percentage}%;"></div>
              </div>
            </div>
          `;
        })
        .join("")}
    </div>
  `;
}

function renderPlayerProfile(data) {
  const container = document.getElementById("stats-profile-view");
  if (!container) return;

  const player = data.player;
  const analytics = data.analytics;
  const recentMatches = data.recent_matches || [];

  const initial = (player.player_name || "?").charAt(0).toUpperCase();
  const color = player.avatar_color || playerColor(player.player_name);
  const careerPoints = player.career_points.toLocaleString();
  const winRate = `${player.win_rate_pct}%`;
  const peakAcc = `${player.peak_match_accuracy_pct}%`;
  const podiums = player.podiums_count;
  const activeHours = (analytics.total_active_time_seconds / 3600).toFixed(1);

  const locGauge = createSvgGaugeHtml(analytics.avg_location_accuracy_pct);
  const dateGauge = createSvgGaugeHtml(analytics.avg_date_accuracy_pct);

  const locTiersHtml = createTiersHtml(analytics.location_tiers);
  const dateTiersHtml = createTiersHtml(analytics.date_tiers);

  const bestDistStr = analytics.best_distance_km !== null ? `${analytics.best_distance_km} km` : "-";

  // Mode mastery
  const modeMap = {};
  (analytics.mode_mastery || []).forEach((m) => {
    modeMap[m.game_mode] = m;
  });
  const pinpointStats = modeMap["pinpoint"] || { matches_played: 0, avg_accuracy_pct: 0, wins: 0, win_rate_pct: 0 };
  const shuffleStats = modeMap["unshuffle"] || { matches_played: 0, avg_accuracy_pct: 0, wins: 0, win_rate_pct: 0 };

  const recentRowsHtml = recentMatches.length > 0
    ? recentMatches
        .map((m) => {
          const dateStr = formatDateTime(m.played_at);
          const modeIcon = m.game_mode === "unshuffle" ? "🔀" : "🎯";
          const modeLabel = m.game_mode === "unshuffle" ? t("mode.unshuffle") : t("mode.pinpoint");
          const rankBadge = formatRankBadge(m.rank, { dot: true });

          return `
            <tr>
              <td class="col-date">${dateStr}</td>
              <td class="col-mode"><span class="mode-icon" aria-hidden="true">${modeIcon}</span> <span class="mode-label">${modeLabel}</span></td>
              <td class="col-rank">${rankBadge}</td>
              <td class="col-score">${m.total_score.toLocaleString()}</td>
              <td class="col-acc"><strong>${m.accuracy_pct}%</strong></td>
              <td class="col-replay text-right">
                <a href="/game/${encodeURIComponent(m.match_id)}/replay" class="btn-secondary replay-action-btn" data-match-id="${escapeHtml(m.match_id)}" title="${t("replay.watch_replay")}" aria-label="${t("replay.watch_replay")}">
                  <span class="replay-icon" aria-hidden="true">🎬</span>
                </a>
              </td>
            </tr>
          `;
        })
        .join("")
    : `<tr><td colspan="6" style="text-align:center; color: var(--text-muted);">${t("stats.no_recent_matches")}</td></tr>`;

  container.innerHTML = `
    <div class="player-profile-view">
      <!-- Profile Header -->
      <div class="player-profile-header">
        <div class="profile-header-top">
          <button type="button" id="profile-back-to-hub-btn" class="btn-secondary btn-sm page-back-btn">
            <span aria-hidden="true">←</span>
            <span>${t("stats.back_to_hub")}</span>
          </button>
        </div>

        <div class="player-profile-hero">
          <div class="player-hero-avatar" style="background-color: ${color};">
            ${initial}
          </div>
          <div>
            <h2 class="player-hero-name">${escapeHtml(player.player_name)}</h2>
            <div class="player-hero-badges">
              <span class="player-hero-badge">📅 ${t("stats.active_since", player.first_played_at ? formatDateTime(player.first_played_at) : "-")}</span>
              <span class="player-hero-badge">⏱️ ${t("stats.last_played", player.last_played_at ? formatDateTime(player.last_played_at) : "-")}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- Key Metrics Row -->
      <div class="player-kpis-grid">
        <div class="player-kpi-card">
          <span class="player-kpi-label">${t("stats.career_points")}</span>
          <span class="player-kpi-value">${careerPoints}</span>
          <span class="player-kpi-sub">${t("stats.matches_played_count", player.matches_played ?? 0)}</span>
        </div>
        <div class="player-kpi-card">
          <span class="player-kpi-label">${t("stats.win_rate")}</span>
          <span class="player-kpi-value">${winRate}</span>
          <span class="player-kpi-sub">${t("stats.wins_count", player.matches_won ?? player.wins_count ?? 0)}</span>
        </div>
        <div class="player-kpi-card">
          <span class="player-kpi-label">${t("stats.podiums")}</span>
          <span class="player-kpi-value">🏆 ${podiums}</span>
          <span class="player-kpi-sub">${t("stats.podium_rate", ((podiums / Math.max(1, player.matches_played || 1)) * 100).toFixed(0))}</span>
        </div>
        <div class="player-kpi-card">
          <span class="player-kpi-label">${t("stats.peak_accuracy")}</span>
          <span class="player-kpi-value">${peakAcc}</span>
          <span class="player-kpi-sub">${t("stats.best_match")}</span>
        </div>
      </div>

      <!-- Accuracy Distribution (Location & Date side by side) -->
      <div class="accuracy-analytics-grid">
        <!-- Location Accuracy Card -->
        <div class="accuracy-dimension-card">
          <div class="dimension-card-head">
            <h3>📍 ${t("stats.location_accuracy")}</h3>
            ${locGauge}
          </div>
          <div class="accuracy-highlight-row">
            <div class="accuracy-highlight-box">
              <span class="accuracy-highlight-lbl">${t("stats.best_distance")}</span>
              <span class="accuracy-highlight-val">${bestDistStr}</span>
            </div>
            <div class="accuracy-highlight-box">
              <span class="accuracy-highlight-lbl">${t("stats.perfect_guesses")}</span>
              <span class="accuracy-highlight-val">${analytics.perfect_location_rounds_count ?? analytics.perfect_location_guesses ?? 0}</span>
            </div>
          </div>
          ${locTiersHtml}
        </div>

        <!-- Date Accuracy Card -->
        <div class="accuracy-dimension-card">
          <div class="dimension-card-head">
            <h3>📅 ${t("stats.date_accuracy")}</h3>
            ${dateGauge}
          </div>
          <div class="accuracy-highlight-row">
            <div class="accuracy-highlight-box">
              <span class="accuracy-highlight-lbl">${t("stats.exact_month_year")}</span>
              <span class="accuracy-highlight-val">${analytics.exact_year_month_pct !== undefined ? `${analytics.exact_year_month_pct}%` : (analytics.best_date_diff_days != null ? `${analytics.best_date_diff_days} ${t("stats.days_plural")}` : "-")}</span>
            </div>
            <div class="accuracy-highlight-box">
              <span class="accuracy-highlight-lbl">${t("stats.perfect_guesses")}</span>
              <span class="accuracy-highlight-val">${analytics.perfect_date_rounds_count ?? analytics.perfect_date_guesses ?? 0}</span>
            </div>
          </div>
          ${dateTiersHtml}
        </div>
      </div>

      <!-- Performance Insights & Mode Mastery Row -->
      <div class="accuracy-analytics-grid">
        <!-- Speed & Timing Insights -->
        <div class="meta-stat-card">
          <h3>⚡ ${t("stats.speed_and_timing")}</h3>
          <div class="speed-metrics-list">
            <div class="speed-metric-item">
              <span class="speed-metric-label">${t("stats.avg_response_time")}</span>
              <span class="speed-metric-value">${analytics.avg_response_time_seconds}s</span>
            </div>
            <div class="speed-metric-item">
              <span class="speed-metric-label">${t("stats.fastest_guess")}</span>
              <span class="speed-metric-value">${analytics.fastest_response_time_seconds}s</span>
            </div>
            <div class="speed-metric-item">
              <span class="speed-metric-label">${t("stats.total_time_played")}</span>
              <span class="speed-metric-value">${t("stats.hours_val", activeHours)}</span>
            </div>
            <div class="speed-metric-item">
              <span class="speed-metric-label">${t("stats.preferred_cadence")}</span>
              <span class="speed-metric-value">${escapeHtml(analytics.preferred_cadence || "")}</span>
            </div>
          </div>
        </div>

        <!-- Mode Mastery -->
        <div class="meta-stat-card">
          <h3>🎮 ${t("stats.mode_mastery")}</h3>
          <div class="mode-mastery-cards">
            <div class="mode-mastery-box">
              <span class="mode-mastery-title">🎯 ${t("mode.pinpoint")}</span>
              <span class="mode-mastery-acc">${pinpointStats.avg_accuracy_pct}%</span>
              <span class="mode-mastery-sub">${t("stats.matches_and_wins", pinpointStats.matches_played, pinpointStats.wins)}</span>
            </div>
            <div class="mode-mastery-box">
              <span class="mode-mastery-title">🔀 ${t("mode.unshuffle")}</span>
              <span class="mode-mastery-acc">${shuffleStats.avg_accuracy_pct}%</span>
              <span class="mode-mastery-sub">${t("stats.matches_and_wins", shuffleStats.matches_played, shuffleStats.wins)}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- Recent Matches Log -->
      <div class="recent-matches-card">
        <h3>📜 ${t("stats.recent_matches")}</h3>
        <div class="table-scroll">
          <table class="recent-matches-table">
            <thead>
              <tr>
                <th class="col-date">${t("stats.date_col")}</th>
                <th class="col-mode">${t("stats.mode_col")}</th>
                <th class="col-rank">${t("stats.rank_col")}</th>
                <th class="col-score">${t("stats.score_col")}</th>
                <th class="col-acc">${t("stats.accuracy_col")}</th>
                <th class="col-replay text-right" data-i18n="leaderboard.col_replay">${t("leaderboard.col_replay")}</th>
              </tr>
            </thead>
            <tbody>
              ${recentRowsHtml}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  `;

  document.getElementById("profile-back-to-hub-btn")?.addEventListener("click", () => {
    navigate("/players");
  });

  container.querySelectorAll(".replay-action-btn").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      e.preventDefault();
      const mid = btn.getAttribute("data-match-id");
      if (mid) {
        navigate(`/game/${encodeURIComponent(mid)}/replay`);
      }
    });
  });
}

/**
 * Refresh stats screen (directory cards or player profile)
 * when UI language changes in realtime.
 */
export function refreshStatsPageLanguage() {
  const card = el.statsPageCard || document.getElementById("stats-page-card");
  if (!card || card.classList.contains("hidden")) return;

  const profileView = document.getElementById("stats-profile-view");
  const isProfileActive = profileView && !profileView.classList.contains("hidden");

  if (isProfileActive) {
    const heading = document.getElementById("stats-page-heading");
    if (heading) {
      heading.setAttribute("data-i18n", "stats.profile_title");
      heading.textContent = t("stats.profile_title");
    }
    if (_cachedProfileData) {
      renderPlayerProfile(_cachedProfileData);
    }
  } else {
    const heading = document.getElementById("stats-page-heading");
    const desc = document.getElementById("stats-page-desc");
    if (heading) {
      heading.setAttribute("data-i18n", "stats.hub_title");
      heading.textContent = t("stats.hub_title");
    }
    if (desc) {
      desc.setAttribute("data-i18n", "stats.hub_subtitle");
      desc.textContent = t("stats.hub_subtitle");
    }

    renderPlayerDirectory(_cachedPlayers);
  }
}

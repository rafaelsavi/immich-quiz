/**
 * Dedicated Player Statistics, Directory & Profile Screen Controller
 * Handles player directory browsing, career accuracy analytics, and match history catalog.
 */

import { state, el } from "../state.js";
import { t, tOr, formatDateTime } from "../i18n.js";
import { showCard } from "./common.js";
import { navigate } from "../router.js";
import { playerColor, playerInitial, escapeHtml, formatRankBadge } from "../formatters.js";

let _currentTab = "players";
let _searchDebounceTimer = null;
let _cachedPlayers = [];
let _cachedMatches = [];
let _cachedProfileData = null;

export function initStats() {
  const tabsBar = document.getElementById("stats-tabs-bar");
  if (tabsBar) {
    tabsBar.querySelectorAll(".stats-tab-btn").forEach((btn) => {
      btn.addEventListener("click", () => {
        const tab = btn.getAttribute("data-tab");
        switchStatsTab(tab);
      });
    });
  }

  // Player search & sort
  const playerSearch = document.getElementById("stats-players-search");
  if (playerSearch) {
    playerSearch.addEventListener("input", () => {
      clearTimeout(_searchDebounceTimer);
      _searchDebounceTimer = setTimeout(() => {
        loadPlayerDirectory();
      }, 200);
    });
  }

  const playerSort = document.getElementById("stats-players-sort");
  if (playerSort) {
    playerSort.addEventListener("change", () => {
      loadPlayerDirectory();
    });
  }

  // Matches filters
  const matchPlayerSearch = document.getElementById("stats-replays-player-search");
  if (matchPlayerSearch) {
    matchPlayerSearch.addEventListener("input", () => {
      clearTimeout(_searchDebounceTimer);
      _searchDebounceTimer = setTimeout(() => {
        loadMatchesHistory();
      }, 200);
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

  const refreshBtn = document.getElementById("stats-page-refresh-btn");
  if (refreshBtn) {
    refreshBtn.addEventListener("click", () => {
      refreshActiveTab();
    });
  }
}

export function showStatsHub(tab = "players") {
  _cachedProfileData = null;
  showCard(el.statsPageCard);

  // Show hub header & tabs, hide profile view
  const profileView = document.getElementById("stats-profile-view");
  const tabsBar = document.getElementById("stats-tabs-bar");
  const heading = document.getElementById("stats-page-heading");
  const desc = document.getElementById("stats-page-desc");

  if (profileView) profileView.classList.add("hidden");
  if (tabsBar) tabsBar.classList.remove("hidden");
  if (heading) {
    heading.setAttribute("data-i18n", "stats.hub_title");
    heading.textContent = t("stats.hub_title");
  }
  if (desc) {
    desc.setAttribute("data-i18n", "stats.hub_subtitle");
    desc.textContent = t("stats.hub_subtitle");
  }

  switchStatsTab(tab);
}

export function switchStatsTab(tab) {
  _currentTab = tab;

  // Update tabs UI
  const tabsBar = document.getElementById("stats-tabs-bar");
  if (tabsBar) {
    tabsBar.querySelectorAll(".stats-tab-btn").forEach((btn) => {
      if (btn.getAttribute("data-tab") === tab) {
        btn.classList.add("active");
      } else {
        btn.classList.remove("active");
      }
    });
  }

  // Toggle tab views
  const playersView = document.getElementById("stats-players-view");
  const replaysView = document.getElementById("stats-replays-view");

  if (playersView) playersView.classList.toggle("hidden", tab !== "players");
  if (replaysView) replaysView.classList.toggle("hidden", tab !== "replays");

  if (tab === "players") {
    loadPlayerDirectory();
  } else if (tab === "replays") {
    loadMatchesHistory();
  }
}

function refreshActiveTab() {
  if (_currentTab === "players") {
    loadPlayerDirectory();
  } else if (_currentTab === "replays") {
    loadMatchesHistory();
  } else if (_currentTab === "leaderboard") {
    loadLeaderboardTab();
  }
}

async function loadPlayerDirectory() {
  const container = document.getElementById("stats-players-grid");
  if (!container) return;

  const searchInput = document.getElementById("stats-players-search");
  const sortSelect = document.getElementById("stats-players-sort");

  const search = searchInput ? searchInput.value.trim() : "";
  const sortBy = sortSelect ? sortSelect.value : "matches";

  container.innerHTML = `<div class="challenges-loading">${t("challenges_page.loading")}</div>`;

  try {
    const res = await fetch(`/api/players?search=${encodeURIComponent(search)}&sort_by=${encodeURIComponent(sortBy)}&limit=60`);
    if (!res.ok) throw new Error("Failed to fetch players directory");
    _cachedPlayers = await res.json();
    renderPlayerDirectory(_cachedPlayers);
  } catch (err) {
    console.error("Error loading players:", err);
    container.innerHTML = `<div class="empty-state">${t("stats.no_players_found")}</div>`;
  }
}

function renderPlayerDirectory(players) {
  const container = document.getElementById("stats-players-grid");
  if (!container) return;

  if (!players || players.length === 0) {
    container.innerHTML = `
      <div class="empty-state" style="grid-column: 1 / -1; padding: 3rem 1rem; text-align: center;">
        <p style="color: var(--text-muted); font-size: 1rem;">${t("stats.no_players_found")}</p>
      </div>
    `;
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
        navigate(`/stats/players/${encodeURIComponent(name)}`);
      }
    });
  });
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

  container.innerHTML = `<div class="challenges-loading">${t("challenges_page.loading")}</div>`;

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

  if (!matches || matches.length === 0) {
    container.innerHTML = `
      <div class="empty-state" style="padding: 3rem 1rem; text-align: center;">
        <p style="color: var(--text-muted); font-size: 1rem;">${t("replay.empty_matches")}</p>
      </div>
    `;
    return;
  }

  container.innerHTML = matches
    .map((m) => {
      const dateStr = formatDateTime(m.played_at);
      const modeLabel = m.game_mode === "album_shuffle" ? t("mode.album_shuffle") : t("mode.pinpoint");
      const modeIcon = m.game_mode === "album_shuffle" ? "🔀" : "🎯";
      const typeLabel = m.play_mode === "challenge" ? t("replay.play_mode_challenge") : t("replay.play_mode_local");
      const winnersList = (m.winners || []).join(", ");
      const winnerHtml = winnersList
        ? `<span class="replay-catalog-winner">🏆 ${escapeHtml(winnersList)} (${m.top_accuracy_pct}%)</span>`
        : "";

      const playerTags = (m.players || [])
        .slice(0, 4)
        .map((p) => `<span class="chip chip-sm" style="font-size: 0.76rem;">${escapeHtml(p)}</span>`)
        .join(" ");

      return `
        <div class="replay-catalog-item">
          <div class="replay-catalog-info">
            <div class="replay-catalog-head">
              <span class="badge-tag" style="background: rgba(15, 124, 127, 0.1); color: var(--accent);">${modeIcon} ${modeLabel}</span>
              <span class="badge-tag">${typeLabel}</span>
              <span class="replay-catalog-date">${dateStr}</span>
            </div>
            <div class="replay-catalog-meta">
              <span>${t("stats.rounds_count", m.rounds)}</span>
              ${winnerHtml ? `• ${winnerHtml}` : ""}
            </div>
            <div class="replay-catalog-players" style="display: flex; gap: 0.35rem; margin-top: 0.2rem; flex-wrap: wrap;">
              ${playerTags}
              ${(m.players || []).length > 4 ? `<span style="font-size: 0.74rem; color: var(--text-muted);">${t("stats.more_players", m.players.length - 4)}</span>` : ""}
            </div>
          </div>
          <a href="/game/${encodeURIComponent(m.match_id)}/replay" class="btn-primary replay-action-btn" data-match-id="${escapeHtml(m.match_id)}">
            <span>🎬</span>
            <span>${t("replay.watch_replay")}</span>
          </a>
        </div>
      `;
    })
    .join("");

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

export async function showPlayerProfile(playerName) {
  showCard(el.statsPageCard);

  const profileView = document.getElementById("stats-profile-view");
  const tabsBar = document.getElementById("stats-tabs-bar");
  const heading = document.getElementById("stats-page-heading");
  const desc = document.getElementById("stats-page-desc");

  if (tabsBar) tabsBar.classList.add("hidden");
  document.getElementById("stats-players-view")?.classList.add("hidden");
  document.getElementById("stats-replays-view")?.classList.add("hidden");

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
    profileView.innerHTML = `<div class="challenges-loading">${t("challenges_page.loading")}</div>`;
  }

  try {
    const res = await fetch(`/api/players/${encodeURIComponent(playerName)}/profile`);
    if (!res.ok) {
      throw new Error(`Player not found`);
    }
    const profileData = await res.json();
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
        navigate("/stats");
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
          const fillClass = fillClassMap[tier.tier_key] || "tier-fill-moderate";
          const tierLabel = tOr(`stats.tier_${tier.tier_key}`, tier.label);
          const countStr = tier.count === 1
            ? t("stats.round_one")
            : t("stats.rounds_other", tier.count);

          return `
            <div class="tier-row">
              <div class="tier-label-row">
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
  const shuffleStats = modeMap["album_shuffle"] || { matches_played: 0, avg_accuracy_pct: 0, wins: 0, win_rate_pct: 0 };

  const recentRowsHtml = recentMatches.length > 0
    ? recentMatches
        .map((m) => {
          const dateStr = formatDateTime(m.played_at);
          const modeIcon = m.game_mode === "album_shuffle" ? "🔀" : "🎯";
          const modeLabel = m.game_mode === "album_shuffle" ? t("mode.album_shuffle") : t("mode.pinpoint");
          const rankBadge = formatRankBadge(m.rank, { dot: true });

          return `
            <tr>
              <td>${dateStr}</td>
              <td>${modeIcon} ${modeLabel}</td>
              <td class="col-rank">${rankBadge}</td>
              <td>${m.total_score.toLocaleString()}</td>
              <td><strong>${m.accuracy_pct}%</strong></td>
              <td style="text-align: right;">
                <a href="/game/${encodeURIComponent(m.match_id)}/replay" class="btn-secondary replay-action-btn" data-match-id="${escapeHtml(m.match_id)}">
                  🎬 ${t("replay.watch_replay")}
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
              <span class="player-hero-badge">⏱️ ${escapeHtml(analytics.preferred_cadence || "")}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- KPI Overview Grid -->
      <div class="player-kpi-grid">
        <div class="player-kpi-card">
          <div class="player-kpi-icon">📈</div>
          <div class="player-kpi-value">${peakAcc}</div>
          <div class="player-kpi-label">${t("stats.peak_accuracy")}</div>
          <div class="player-kpi-sub">${t("stats.lifetime_best_match")}</div>
        </div>

        <div class="player-kpi-card">
          <div class="player-kpi-icon">🏆</div>
          <div class="player-kpi-value">${player.matches_played}</div>
          <div class="player-kpi-label">${t("stats.matches_played")}</div>
          <div class="player-kpi-sub">${t("stats.win_rate_sub", winRate, player.matches_won)}</div>
        </div>

        <div class="player-kpi-card">
          <div class="player-kpi-icon">⭐</div>
          <div class="player-kpi-value">${careerPoints}</div>
          <div class="player-kpi-label">${t("stats.career_points")}</div>
          <div class="player-kpi-sub">${t("stats.total_earned")}</div>
        </div>

        <div class="player-kpi-card">
          <div class="player-kpi-icon">🥇</div>
          <div class="player-kpi-value">${podiums}</div>
          <div class="player-kpi-label">${t("stats.podiums")}</div>
          <div class="player-kpi-sub">${t("stats.top_3_finishes")}</div>
        </div>
      </div>

      <!-- Symmetrical Accuracy Breakdown -->
      <div class="accuracy-analytics-grid">
        <!-- Location Accuracy Card -->
        <div class="accuracy-dimension-card">
          <h3>📍 ${t("stats.location_accuracy")}</h3>
          <div class="accuracy-gauge-row">
            ${locGauge}
            <div class="accuracy-highlights">
              <div class="accuracy-highlight-item">
                <span class="accuracy-highlight-val">${bestDistStr}</span>
                <span class="accuracy-highlight-lbl">${t("stats.best_distance")}</span>
              </div>
              <div class="accuracy-highlight-item">
                <span class="accuracy-highlight-val">${analytics.perfect_location_rounds_count}</span>
                <span class="accuracy-highlight-lbl">${t("stats.perfect_location_rounds")}</span>
              </div>
            </div>
          </div>
          <div>
            <div style="font-size: 0.82rem; font-weight: 700; margin-bottom: 0.5rem; color: var(--text-color);">
              ${t("stats.accuracy_tiers")}
            </div>
            ${locTiersHtml}
          </div>
        </div>

        <!-- Date Accuracy Card -->
        <div class="accuracy-dimension-card">
          <h3>📅 ${t("stats.date_accuracy")}</h3>
          <div class="accuracy-gauge-row">
            ${dateGauge}
            <div class="accuracy-highlights">
              <div class="accuracy-highlight-item">
                <span class="accuracy-highlight-val">${analytics.exact_year_month_pct}%</span>
                <span class="accuracy-highlight-lbl">${t("stats.exact_month_year")}</span>
              </div>
              <div class="accuracy-highlight-item">
                <span class="accuracy-highlight-val">${analytics.exact_year_pct}%</span>
                <span class="accuracy-highlight-lbl">${t("stats.exact_year")}</span>
              </div>
              <div class="accuracy-highlight-item">
                <span class="accuracy-highlight-val">${analytics.perfect_date_rounds_count}</span>
                <span class="accuracy-highlight-lbl">${t("stats.perfect_date_rounds")}</span>
              </div>
            </div>
          </div>
          <div>
            <div style="font-size: 0.82rem; font-weight: 700; margin-bottom: 0.5rem; color: var(--text-color);">
              ${t("stats.accuracy_tiers")}
            </div>
            ${dateTiersHtml}
          </div>
        </div>
      </div>

      <!-- Pacing & Game Mode Mastery -->
      <div class="meta-stats-grid">
        <!-- Speed & Pacing -->
        <div class="meta-stat-card">
          <h3>⏱️ ${t("stats.speed_cadence")}</h3>
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
              <span class="mode-mastery-title">🔀 ${t("mode.album_shuffle")}</span>
              <span class="mode-mastery-acc">${shuffleStats.avg_accuracy_pct}%</span>
              <span class="mode-mastery-sub">${t("stats.matches_and_wins", shuffleStats.matches_played, shuffleStats.wins)}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- Recent Matches Log -->
      <div class="recent-matches-card">
        <h3>📜 ${t("stats.recent_matches")}</h3>
        <div style="overflow-x: auto;">
          <table class="recent-matches-table">
            <thead>
              <tr>
                <th>${t("stats.date_col")}</th>
                <th>${t("stats.mode_col")}</th>
                <th class="col-rank">${t("stats.rank_col")}</th>
                <th>${t("stats.score_col")}</th>
                <th>${t("stats.accuracy_col")}</th>
                <th style="text-align: right;">${t("replay.watch_replay")}</th>
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
    navigate("/stats");
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
 * Refresh stats screen (directory cards, replays catalog, or player profile)
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

    if (_currentTab === "players" && _cachedPlayers && _cachedPlayers.length > 0) {
      renderPlayerDirectory(_cachedPlayers);
    } else if (_currentTab === "replays" && _cachedMatches && _cachedMatches.length > 0) {
      renderMatchesHistory(_cachedMatches);
    }
  }
}

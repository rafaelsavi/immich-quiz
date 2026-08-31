/**
 * Dedicated Challenges Hub Page Controller for Immich Quiz.
 *
 * Provides a comprehensive challenges management and discovery view:
 * - Real-time statistics overview (Active challenges, total players, most popular)
 * - Live keyword search, status tabs, game mode filters, and sorting
 * - Detailed challenge cards with host information, live expiration countdowns,
 *   photo scope badges (libraries, albums, people, date ranges, geography),
 *   quick 1-click sharing, instant play, and deactivation
 * - Inline expandable leaderboard & standings drawer with top podium preview
 */

import { api } from "./api.js";
import { state, el } from "./state.js";
import { t, formatDate } from "./i18n.js";
import { showCard } from "./screens/common.js";
import { navigate } from "./router.js";
import { showShareToast } from "./summary/share.js";
import { openAdminModal } from "./admin.js";
import { playerColor, playerInitial, formatPlace } from "./formatters.js";

let _challenges = [];
let _searchQuery = "";
let _statusFilter = "all";
let _modeFilter = "all";
let _sortBy = "newest";
let _expandedStandings = new Set();
let _cachedStandings = new Map(); // challenge_id -> leaderboard data
let _loadingStandings = new Set(); // challenge_ids currently fetching

// DOM references
let _pageCardEl = null;
let _hubListEl = null;
let _searchInputEl = null;
let _statusTabsEl = null;
let _modeFilterEl = null;
let _sortSelectEl = null;
let _refreshBtnEl = null;
let _createBtnEl = null;
let _backBtnEl = null;
let _totalBadgeEl = null;

let _statActiveEl = null;
let _statPlayersEl = null;
let _statTotalEl = null;
let _statPopularEl = null;

let _isInitialized = false;

/**
 * Format relative duration string from milliseconds.
 * @param {number} diffMs
 * @param {boolean} isPast
 * @returns {string}
 */
function formatRelativeTime(diffMs, isPast = false) {
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

/**
 * Initialize DOM element references and event listeners.
 */
export function initChallengesPage() {
  if (_isInitialized) return;

  _pageCardEl = document.getElementById("challenges-page-card");
  _hubListEl = document.getElementById("challenges-hub-list");
  _searchInputEl = document.getElementById("challenges-search-input");
  _statusTabsEl = document.getElementById("challenges-status-tabs");
  _modeFilterEl = document.getElementById("challenges-mode-filter");
  _sortSelectEl = document.getElementById("challenges-sort-select");
  _refreshBtnEl = document.getElementById("challenges-page-refresh-btn");
  _backBtnEl = document.getElementById("challenges-page-back-btn");
  _totalBadgeEl = document.getElementById("challenges-page-total-badge");

  _statActiveEl = document.getElementById("stat-active-challenges");
  _statPlayersEl = document.getElementById("stat-total-players");
  _statTotalEl = document.getElementById("stat-total-challenges");
  _statPopularEl = document.getElementById("stat-popular-challenge");

  // Search input
  if (_searchInputEl) {
    _searchInputEl.addEventListener("input", (e) => {
      _searchQuery = e.target.value.trim().toLowerCase();
      renderChallenges();
    });
  }

  // Status filter pills
  if (_statusTabsEl) {
    _statusTabsEl.querySelectorAll(".filter-pill").forEach((pill) => {
      pill.addEventListener("click", () => {
        _statusTabsEl.querySelectorAll(".filter-pill").forEach((p) => p.classList.remove("active"));
        pill.classList.add("active");
        _statusFilter = pill.getAttribute("data-status") || "all";
        renderChallenges();
      });
    });
  }

  // Mode filter
  if (_modeFilterEl) {
    _modeFilterEl.addEventListener("change", (e) => {
      _modeFilter = e.target.value;
      renderChallenges();
    });
  }

  // Sort select
  if (_sortSelectEl) {
    _sortSelectEl.addEventListener("change", (e) => {
      _sortBy = e.target.value;
      renderChallenges();
    });
  }

  // Refresh button
  if (_refreshBtnEl) {
    _refreshBtnEl.addEventListener("click", () => {
      loadChallengesList(true);
    });
  }

  // Back to lobby button
  if (_backBtnEl) {
    _backBtnEl.addEventListener("click", () => {
      navigate("/");
    });
  }

  _isInitialized = true;
}

/**
 * Open and display the Challenges Hub page.
 */
export async function openChallengesPage() {
  initChallengesPage();

  if (el.challengesPageCard) {
    showCard(el.challengesPageCard);
    if (el.leaderboardCard) {
      el.leaderboardCard.classList.add("hidden");
    }
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  // Update active state on header navigation button
  if (el.challengesNavBtn) {
    el.challengesNavBtn.classList.add("active");
  }

  await loadChallengesList();
}

/**
 * Update the active challenge badge counter in the header controls.
 * @param {number} [count]
 */
export function updateHeaderChallengeBadge(count) {
  if (typeof count !== "number") {
    const activeOnes = _challenges.filter((c) => isChallengeActive(c));
    count = activeOnes.length;
  }

  if (el.headerChallengesBadge) {
    el.headerChallengesBadge.textContent = String(count);
    el.headerChallengesBadge.classList.toggle("hidden", count === 0);
  }
}

/**
 * Helper to check if a challenge is currently active (not deactivated and not expired).
 * @param {any} ch
 * @returns {boolean}
 */
function isChallengeActive(ch) {
  if (!ch.is_active) return false;
  if (ch.expires_at) {
    return new Date(ch.expires_at).getTime() > Date.now();
  }
  return true;
}

/**
 * Load challenges from backend API and update hero stats and list.
 * @param {boolean} [showToast=false]
 */
export async function loadChallengesList(showToast = false) {
  if (!_hubListEl) return;

  if (_challenges.length === 0) {
    _hubListEl.innerHTML = `<div class="challenges-loading">${t("challenges_page.loading")}</div>`;
  }

  try {
    const res = await api("/api/challenge/list?limit=100&include_inactive=true");
    _challenges = res.challenges || [];

    updateHeroStats();
    updateHeaderChallengeBadge();
    renderChallenges();

    if (showToast) {
      showShareToast(t("challenges_page.refresh_btn") + " ✓");
    }
  } catch (err) {
    console.error("Failed to load challenges list:", err);
    _hubListEl.innerHTML = `
      <div class="challenges-error-box">
        <span class="error-icon">⚠️</span>
        <p>${err.message || "Failed to load challenges"}</p>
        <button type="button" class="btn-secondary btn-mini" id="retry-load-challenges-btn">
          ${t("challenges_page.refresh_btn")}
        </button>
      </div>
    `;
    const retryBtn = document.getElementById("retry-load-challenges-btn");
    if (retryBtn) {
      retryBtn.addEventListener("click", () => loadChallengesList());
    }
  }
}

/**
 * Update the hero stats metric cards based on fetched challenges.
 */
function updateHeroStats() {
  const totalCount = _challenges.length;
  const activeCount = _challenges.filter(isChallengeActive).length;
  const totalPlayers = _challenges.reduce((sum, c) => sum + (c.total_participants || 0), 0);

  if (_totalBadgeEl) {
    _totalBadgeEl.textContent = `${activeCount} ${t("challenges_page.filter_active").toLowerCase()}`;
    _totalBadgeEl.classList.toggle("hidden", totalCount === 0);
  }

  if (_statActiveEl) _statActiveEl.textContent = String(activeCount);
  if (_statPlayersEl) _statPlayersEl.textContent = String(totalPlayers);
  if (_statTotalEl) _statTotalEl.textContent = String(totalCount);

  if (_statPopularEl) {
    if (totalCount === 0) {
      _statPopularEl.textContent = "—";
    } else {
      const sortedByPlayers = [..._challenges].sort((a, b) => (b.total_participants || 0) - (a.total_participants || 0));
      const topChallenge = sortedByPlayers[0];
      if (topChallenge && topChallenge.total_participants > 0) {
        _statPopularEl.textContent = `${topChallenge.title || topChallenge.creator_name} (${topChallenge.total_participants})`;
        _statPopularEl.title = topChallenge.title || topChallenge.creator_name;
      } else {
        _statPopularEl.textContent = "—";
      }
    }
  }
}

/**
 * Filter, sort, and render challenge cards into the list container.
 */
export function renderChallenges() {
  if (!_hubListEl) return;

  let filtered = [..._challenges];

  // 1. Keyword search
  if (_searchQuery) {
    filtered = filtered.filter((ch) => {
      const title = (ch.title || "").toLowerCase();
      const creator = (ch.creator_name || "").toLowerCase();
      const summary = (ch.filter_summary || "").toLowerCase();
      const tooltip = (ch.filter_tooltip || "").toLowerCase();

      const config = ch.config || {};
      const albumNames = (config.album_names || []).join(" ").toLowerCase();
      const personNames = (config.person_names || []).join(" ").toLowerCase();
      const libraries = (ch.libraries || []).join(" ").toLowerCase();
      const countries = (config.countries || []).join(" ").toLowerCase();
      const cities = (config.cities || []).join(" ").toLowerCase();

      return (
        title.includes(_searchQuery) ||
        creator.includes(_searchQuery) ||
        summary.includes(_searchQuery) ||
        tooltip.includes(_searchQuery) ||
        albumNames.includes(_searchQuery) ||
        personNames.includes(_searchQuery) ||
        libraries.includes(_searchQuery) ||
        countries.includes(_searchQuery) ||
        cities.includes(_searchQuery)
      );
    });
  }

  // 2. Status filter
  if (_statusFilter === "active") {
    filtered = filtered.filter(isChallengeActive);
  } else if (_statusFilter === "expired") {
    filtered = filtered.filter((ch) => !isChallengeActive(ch));
  }

  // 3. Game mode filter
  if (_modeFilter !== "all") {
    filtered = filtered.filter((ch) => ch.game_mode === _modeFilter);
  }

  // 4. Sorting
  filtered.sort((a, b) => {
    switch (_sortBy) {
      case "players":
        return (b.total_participants || 0) - (a.total_participants || 0);
      case "expiring": {
        const aExp = a.expires_at ? new Date(a.expires_at).getTime() : Infinity;
        const bExp = b.expires_at ? new Date(b.expires_at).getTime() : Infinity;
        return aExp - bExp;
      }
      case "title": {
        const aTitle = (a.title || a.creator_name || "").toLowerCase();
        const bTitle = (b.title || b.creator_name || "").toLowerCase();
        return aTitle.localeCompare(bTitle);
      }
      case "newest":
      default: {
        const aCreated = a.created_at ? new Date(a.created_at).getTime() : 0;
        const bCreated = b.created_at ? new Date(b.created_at).getTime() : 0;
        return bCreated - aCreated;
      }
    }
  });

  // Handle empty states
  if (filtered.length === 0) {
    if (_challenges.length === 0) {
      _hubListEl.innerHTML = `
        <div class="challenges-empty-state">
          <div class="empty-state-icon">🌐</div>
          <h3>${t("challenges_page.empty_title")}</h3>
          <p>${t("challenges_page.empty_no_challenges")}</p>
          <button type="button" class="btn-primary" id="empty-state-create-btn">
            <span class="btn-icon">✨</span>
            ${t("challenges_page.create_btn")}
          </button>
        </div>
      `;
      const emptyBtn = document.getElementById("empty-state-create-btn");
      if (emptyBtn) {
        emptyBtn.addEventListener("click", () => openAdminModal("challenge"));
      }
    } else {
      _hubListEl.innerHTML = `
        <div class="challenges-empty-state">
          <div class="empty-state-icon">🔍</div>
          <h3>${t("challenges_page.empty_title")}</h3>
          <p>${t("challenges_page.empty_desc")}</p>
          <button type="button" class="btn-secondary" id="empty-state-clear-btn">
            ${t("challenges_page.clear_search")}
          </button>
        </div>
      `;
      const clearBtn = document.getElementById("empty-state-clear-btn");
      if (clearBtn) {
        clearBtn.addEventListener("click", () => {
          if (_searchInputEl) _searchInputEl.value = "";
          _searchQuery = "";
          _statusFilter = "all";
          _modeFilter = "all";
          if (_statusTabsEl) {
            _statusTabsEl.querySelectorAll(".filter-pill").forEach((p, idx) => {
              p.classList.toggle("active", idx === 0);
            });
          }
          if (_modeFilterEl) _modeFilterEl.value = "all";
          renderChallenges();
        });
      }
    }
    return;
  }

  // Render cards
  const now = Date.now();
  let html = "";

  filtered.forEach((ch) => {
    const isActive = isChallengeActive(ch);
    const modeEmoji = ch.game_mode === "album_shuffle" ? "🔀" : "📍";
    const modeLabel = ch.game_mode === "album_shuffle" ? t("mode.album_shuffle") : t("mode.pinpoint");
    const modeDesc = ch.game_mode === "album_shuffle" ? t("admin.shuffle_desc") : t("admin.pinpoint_desc");

    // Status pill and relative time
    let statusPillHtml = "";
    let timeStatusHtml = "";

    if (!ch.is_active) {
      statusPillHtml = `<span class="challenge-status-pill status-deactivated"><span class="status-dot"></span>${t("admin.status_deactivated")}</span>`;
      timeStatusHtml = `<span class="card-time-status text-muted">${t("admin.status_deactivated")}</span>`;
    } else if (ch.expires_at) {
      const expTime = new Date(ch.expires_at).getTime();
      const diffMs = expTime - now;
      if (diffMs > 0) {
        statusPillHtml = `<span class="challenge-status-pill status-active"><span class="status-dot pulse"></span>${t("admin.status_active")}</span>`;
        timeStatusHtml = `<span class="card-time-status status-active">⏳ ${formatRelativeTime(diffMs, false)}</span>`;
      } else {
        statusPillHtml = `<span class="challenge-status-pill status-expired"><span class="status-dot"></span>${t("admin.status_expired")}</span>`;
        timeStatusHtml = `<span class="card-time-status status-expired">⌛ ${formatRelativeTime(diffMs, true)}</span>`;
      }
    } else {
      statusPillHtml = `<span class="challenge-status-pill status-active"><span class="status-dot pulse"></span>${t("admin.status_active")}</span>`;
      timeStatusHtml = `<span class="card-time-status status-active">♾️ ${t("challenges_page.never_expires")}</span>`;
    }

    const hostInitial = playerInitial(ch.creator_name || "Host");
    const hostColor = playerColor(0);
    const participantCount = ch.total_participants || 0;
    const isStandingsExpanded = _expandedStandings.has(ch.challenge_id);

    // Build Scope Chips
    const config = ch.config || {};
    const scopeChips = [];

    // Libraries
    if (ch.libraries && ch.libraries.length > 0) {
      scopeChips.push(`<span class="scope-chip scope-library" title="${ch.libraries.join(", ")}">📚 ${ch.libraries.join(", ")}</span>`);
    }

    // Albums
    if (config.album_names && config.album_names.length > 0) {
      const albumCount = config.album_names.length;
      const albumText = albumCount <= 2 ? config.album_names.join(", ") : `${config.album_names[0]} +${albumCount - 1}`;
      scopeChips.push(`<span class="scope-chip scope-album" title="${config.album_names.join(", ")}">📁 ${albumText}</span>`);
    }

    // People
    if (config.person_names && config.person_names.length > 0) {
      const pCount = config.person_names.length;
      const pText = pCount <= 2 ? config.person_names.join(", ") : `${config.person_names[0]} +${pCount - 1}`;
      scopeChips.push(`<span class="scope-chip scope-people" title="${config.person_names.join(", ")}">👤 ${pText}</span>`);
    }

    // Date range
    if (config.min_date || config.max_date) {
      const dateText = `${config.min_date || "—"} → ${config.max_date || "—"}`;
      scopeChips.push(`<span class="scope-chip scope-date" title="${dateText}">🗓️ ${dateText}</span>`);
    }

    // Geographic
    if (config.countries && config.countries.length > 0) {
      scopeChips.push(`<span class="scope-chip scope-geo" title="${config.countries.join(", ")}">🌍 ${config.countries.join(", ")}</span>`);
    }
    if (config.cities && config.cities.length > 0) {
      scopeChips.push(`<span class="scope-chip scope-geo" title="${config.cities.join(", ")}">🏙️ ${config.cities.join(", ")}</span>`);
    }

    // Shared
    if (config.include_shared) {
      scopeChips.push(`<span class="scope-chip scope-shared" title="${t("challenges_page.scope_shared")}">🔗 Shared</span>`);
    }

    if (scopeChips.length === 0) {
      scopeChips.push(`<span class="scope-chip scope-all">🌐 ${t("challenges_page.scope_all")}</span>`);
    }

    // Standings toggle text
    const standingsBtnText = isStandingsExpanded
      ? t("challenges_page.hide_standings")
      : participantCount > 0
      ? t("challenges_page.view_standings", participantCount)
      : t("challenges_page.standings_btn");

    html += `
      <div class="detailed-challenge-card ${!isActive ? "card-inactive" : ""}" data-id="${ch.challenge_id}">
        <!-- Card Header -->
        <div class="detailed-card-header">
          <div class="card-title-block">
            <div class="card-status-row">
              ${statusPillHtml}
              <span class="card-mode-badge" title="${modeDesc}">${modeEmoji} ${modeLabel}</span>
              ${timeStatusHtml}
            </div>
            <h3 class="detailed-challenge-title">${ch.title || `${ch.creator_name}'s Challenge`}</h3>
            <div class="card-host-row">
              <span class="host-avatar" style="background-color: ${hostColor};">${hostInitial}</span>
              <span class="host-name">${t("challenges_page.host_label", ch.creator_name)}</span>
              <span class="host-dot">•</span>
              <span class="created-date">${t("admin.created_at_label")}: ${formatDate(ch.created_at)}</span>
            </div>
          </div>

          <div class="card-header-actions">
            <button type="button" class="btn-copy-challenge-link btn-action-icon" data-url="${ch.play_url}"
              title="${t("challenges_page.copy_btn")}">
              <span>📋</span>
            </button>
            ${
              isActive
                ? `<button type="button" class="btn-deactivate-challenge-hub btn-action-icon text-danger"
                    data-id="${ch.challenge_id}" data-title="${ch.title || "Challenge"}"
                    title="${t("challenges_page.deactivate_btn")}">
                    <span>🚫</span>
                  </button>`
                : ""
            }
          </div>
        </div>

        <!-- Card Specs & Rules Grid -->
        <div class="detailed-card-specs">
          <div class="spec-item">
            <span class="spec-icon">🎯</span>
            <span class="spec-text"><strong>${t("challenges_page.rounds_count", ch.rounds)}</strong></span>
          </div>
          <div class="spec-item">
            <span class="spec-icon">⏱️</span>
            <span class="spec-text">${ch.round_length || "1m"}</span>
          </div>
          <div class="spec-item">
            <span class="spec-icon">👥</span>
            <span class="spec-text"><strong>${t("challenge.participants", participantCount)}</strong></span>
          </div>
        </div>

        <!-- Scope & Filters Tag Cloud -->
        <div class="detailed-card-scope">
          <span class="scope-label">${t("challenges_page.scope_heading")}:</span>
          <div class="scope-chips-container">
            ${scopeChips.join("")}
          </div>
        </div>

        <!-- Card Footer & Actions -->
        <div class="detailed-card-footer">
          <div class="footer-left-actions">
            ${
              isActive
                ? `<a href="/play/${ch.capability_token}" class="btn-primary btn-play-challenge" data-token="${ch.capability_token}">
                    <span class="btn-icon">🎮</span>
                    ${t("challenges_page.play_btn")}
                  </a>`
                : `<button type="button" class="btn-secondary" disabled>
                    ${t("admin.status_expired")}
                  </button>`
            }
            <button type="button" class="btn-secondary btn-copy-challenge-link" data-url="${ch.play_url}">
              <span class="btn-icon">📋</span>
              ${t("challenges_page.copy_btn")}
            </button>
          </div>

          <button type="button" class="btn-standings-toggle ${isStandingsExpanded ? "active" : ""}"
            data-id="${ch.challenge_id}" data-token="${ch.capability_token}">
            <span class="standings-toggle-icon">${isStandingsExpanded ? "▲" : "▼"}</span>
            <span>${standingsBtnText}</span>
          </button>
        </div>

        <!-- Inline Standings & Leaderboard Drawer -->
        <div class="challenge-standings-drawer ${isStandingsExpanded ? "open" : "hidden"}" id="standings-drawer-${ch.challenge_id}">
          <div class="drawer-inner" id="drawer-content-${ch.challenge_id}">
            <!-- Rendered dynamically by toggleChallengeStandings -->
          </div>
        </div>
      </div>
    `;
  });

  _hubListEl.innerHTML = html;

  // Bind interactive elements
  _hubListEl.querySelectorAll(".btn-copy-challenge-link").forEach((btn) => {
    btn.addEventListener("click", async (e) => {
      e.stopPropagation();
      const url = btn.getAttribute("data-url");
      if (!url) return;
      try {
        await navigator.clipboard.writeText(url);
        showShareToast(t("challenge.link_copied"));
      } catch (_) {
        showShareToast(url);
      }
    });
  });

  _hubListEl.querySelectorAll(".btn-play-challenge").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      e.preventDefault();
      const token = btn.getAttribute("data-token");
      if (token) {
        navigate(`/play/${token}`);
      }
    });
  });

  _hubListEl.querySelectorAll(".btn-deactivate-challenge-hub").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      const id = btn.getAttribute("data-id");
      const title = btn.getAttribute("data-title");
      if (id) {
        confirmAndDeactivate(id, title);
      }
    });
  });

  _hubListEl.querySelectorAll(".btn-standings-toggle").forEach((btn) => {
    btn.addEventListener("click", () => {
      const id = btn.getAttribute("data-id");
      const token = btn.getAttribute("data-token");
      if (id && token) {
        toggleChallengeStandings(id, token);
      }
    });
  });

  // Re-render any currently expanded standings drawers
  _expandedStandings.forEach((chId) => {
    const ch = _challenges.find((c) => c.challenge_id === chId);
    if (ch) {
      renderStandingsDrawerContent(chId, ch.capability_token);
    }
  });
}

/**
 * Toggle challenge standings drawer and load standings data.
 * @param {string} challengeId
 * @param {string} capabilityToken
 */
export async function toggleChallengeStandings(challengeId, capabilityToken) {
  if (_expandedStandings.has(challengeId)) {
    _expandedStandings.delete(challengeId);
    const drawerEl = document.getElementById(`standings-drawer-${challengeId}`);
    if (drawerEl) {
      drawerEl.classList.add("hidden");
      drawerEl.classList.remove("open");
    }
    const btn = _hubListEl?.querySelector(`.btn-standings-toggle[data-id="${challengeId}"]`);
    if (btn) {
      btn.classList.remove("active");
      const ch = _challenges.find((c) => c.challenge_id === challengeId);
      const count = ch?.total_participants || 0;
      btn.innerHTML = `<span class="standings-toggle-icon">▼</span><span>${
        count > 0 ? t("challenges_page.view_standings", count) : t("challenges_page.standings_btn")
      }</span>`;
    }
    return;
  }

  _expandedStandings.add(challengeId);
  const drawerEl = document.getElementById(`standings-drawer-${challengeId}`);
  if (drawerEl) {
    drawerEl.classList.remove("hidden");
    drawerEl.classList.add("open");
  }
  const btn = _hubListEl?.querySelector(`.btn-standings-toggle[data-id="${challengeId}"]`);
  if (btn) {
    btn.classList.add("active");
    btn.innerHTML = `<span class="standings-toggle-icon">▲</span><span>${t("challenges_page.hide_standings")}</span>`;
  }

  await renderStandingsDrawerContent(challengeId, capabilityToken);
}

/**
 * Render standings table inside the expanded drawer.
 * @param {string} challengeId
 * @param {string} capabilityToken
 */
async function renderStandingsDrawerContent(challengeId, capabilityToken) {
  const contentEl = document.getElementById(`drawer-content-${challengeId}`);
  if (!contentEl) return;

  if (_loadingStandings.has(challengeId)) return;

  let data = _cachedStandings.get(challengeId);

  if (!data) {
    contentEl.innerHTML = `<div class="standings-loading-indicator">${t("challenges_page.leaderboard_loading")}</div>`;
    _loadingStandings.add(challengeId);

    try {
      data = await api(`/api/challenge/${encodeURIComponent(capabilityToken)}/leaderboard`);
      _cachedStandings.set(challengeId, data);
    } catch (err) {
      console.error(`Failed to fetch leaderboard for challenge ${challengeId}:`, err);
      contentEl.innerHTML = `<div class="standings-error-msg">${err.message || "Failed to load leaderboard"}</div>`;
      _loadingStandings.delete(challengeId);
      return;
    } finally {
      _loadingStandings.delete(challengeId);
    }
  }

  const entries = data.leaderboard || [];

  if (entries.length === 0) {
    contentEl.innerHTML = `
      <div class="standings-empty-state">
        <span class="empty-icon">👥</span>
        <p>${t("challenges_page.no_participants_yet")}</p>
      </div>
    `;
    return;
  }

  // Render Mini Podium for Top 3
  let podiumHtml = "";
  if (entries.length >= 2) {
    const top3 = entries.slice(0, 3);
    const podiumItems = top3
      .map((p, idx) => {
        const medal = idx === 0 ? "🥇" : idx === 1 ? "🥈" : "🥉";
        const placeCls = idx === 0 ? "podium-1st" : idx === 1 ? "podium-2nd" : "podium-3rd";
        const col = playerColor(idx);
        const init = playerInitial(p.player_name);
        return `
          <div class="mini-podium-item ${placeCls}">
            <div class="mini-podium-avatar" style="border-color: ${col};">${init}</div>
            <span class="mini-podium-medal">${medal}</span>
            <strong class="mini-podium-name">${p.player_name}</strong>
            <span class="mini-podium-acc">${p.accuracy_pct}%</span>
          </div>
        `;
      })
      .join("");
    podiumHtml = `<div class="mini-podium-bar">${podiumItems}</div>`;
  }

  // Render Standings Table
  let rowsHtml = "";
  entries.forEach((e, idx) => {
    const rankBadge = formatPlace(e.rank || idx + 1);
    const isWinner = e.is_winner;
    const completedBadge = e.is_finished
      ? `<span class="progress-badge badge-done">✓ ${e.completed_rounds}/${data.total_rounds}</span>`
      : `<span class="progress-badge badge-wip">⏳ ${e.completed_rounds}/${data.total_rounds}</span>`;

    const timeFormatted = e.total_time_seconds ? `${Math.round(e.total_time_seconds)}s` : "—";
    const awardsHtml = (e.awards || [])
      .map((aw) => `<span class="standing-award-badge" title="${aw}">${aw}</span>`)
      .join(" ");

    rowsHtml += `
      <tr class="${isWinner ? "winner-row" : ""}">
        <td class="col-rank">${rankBadge}</td>
        <td class="col-player">
          <strong>${e.player_name}</strong>
          ${awardsHtml ? `<div class="player-awards-list">${awardsHtml}</div>` : ""}
        </td>
        <td class="col-acc"><strong>${e.accuracy_pct}%</strong></td>
        <td class="col-score">${e.total_score} <span class="max-score">/ ${e.max_possible_score}</span></td>
        <td class="col-progress">${completedBadge}</td>
        <td class="col-time">${timeFormatted}</td>
      </tr>
    `;
  });

  contentEl.innerHTML = `
    ${podiumHtml}
    <div class="standings-table-wrap">
      <table class="standings-table">
        <thead>
          <tr>
            <th>${t("challenges_page.rank_col")}</th>
            <th>${t("challenges_page.player_col")}</th>
            <th>${t("challenges_page.accuracy_col")}</th>
            <th>${t("challenges_page.score_col")}</th>
            <th>${t("challenges_page.progress_col")}</th>
            <th>${t("challenges_page.time_col")}</th>
          </tr>
        </thead>
        <tbody>
          ${rowsHtml}
        </tbody>
      </table>
    </div>
  `;
}

/**
 * Confirm and deactivate challenge by ID.
 * @param {string} challengeId
 * @param {string} challengeTitle
 */
async function confirmAndDeactivate(challengeId, challengeTitle) {
  const confirmed = window.confirm(t("admin.deactivate_confirm", challengeTitle));
  if (!confirmed) return;

  try {
    await api(`/api/challenge/${challengeId}/deactivate`, { method: "POST" });
    showShareToast(t("admin.deactivate_success"));
    _cachedStandings.delete(challengeId);
    await loadChallengesList();
  } catch (err) {
    console.error("Failed to deactivate challenge:", err);
    showShareToast(err.message || "Failed to deactivate challenge");
  }
}

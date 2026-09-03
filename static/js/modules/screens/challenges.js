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

import { api } from "../api.js";
import { state, el } from "../state.js";
import { t, formatDate } from "../i18n.js";
import { showCard } from "./common.js";
import { navigate } from "../router.js";
import { showShareToast, copyToClipboard } from "../summary/share.js";
import { openAdminModal } from "../admin.js";
import { playerColor, playerInitial, registerPlayerColor, formatRank, formatRoundsBadge, formatPlayerCellHtml, formatRelativeTime } from "../formatters.js";
import { buildMatchMetaHtml } from "../components/match_meta.js";
import { renderQRCode } from "../components/qrcode.js";

let _challenges = [];
let _searchQuery = "";
let _statusFilter = "all";
let _modeFilter = "all";
let _sortBy = "newest";
let _expandedStandings = new Set();
let _expandedShareDrawers = new Set();
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
let _totalBadgeEl = null;

let _isInitialized = false;
let _hasLoaded = false;

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
  _totalBadgeEl = document.getElementById("challenges-page-total-badge");

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
  if (el.homeNavBtn) {
    el.homeNavBtn.classList.remove("active");
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
  initChallengesPage();
  if (!_hubListEl) return;

  if (_challenges.length === 0) {
    _hubListEl.innerHTML = `<div class="challenges-loading" data-i18n="challenges_page.loading">${t("challenges_page.loading")}</div>`;
  }

  try {
    const res = await api("/api/challenge/list?limit=100&include_inactive=true");
    _challenges = res.challenges || [];
    _cachedStandings.clear();
    _hasLoaded = true;

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
 * Update the challenges count badge based on fetched challenges.
 */
function updateHeroStats() {
  const totalCount = _challenges.length;
  const activeCount = _challenges.filter(isChallengeActive).length;

  if (_totalBadgeEl) {
    if (totalCount === 0) {
      _totalBadgeEl.textContent = `0 ${t("challenges_page.stats_total_short") || "total"}`;
      _totalBadgeEl.classList.add("hidden");
    } else {
      const activeLabel = t("challenges_page.filter_active").toLowerCase();
      const totalLabel = t("challenges_page.stats_total_short") || "total";
      _totalBadgeEl.textContent = `${activeCount} ${activeLabel} • ${totalCount} ${totalLabel}`;
      _totalBadgeEl.classList.remove("hidden");
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

    const participantCount = ch.total_participants || 0;
    const isStandingsExpanded = _expandedStandings.has(ch.challenge_id);
    const isShareExpanded = _expandedShareDrawers.has(ch.challenge_id);

    // Standings toggle text
    const standingsBtnText = isStandingsExpanded
      ? t("challenges_page.hide_standings")
      : t("challenges_page.view_standings", participantCount);

    html += `
      <div class="detailed-challenge-card ${!isActive ? "card-inactive" : ""}" data-id="${ch.challenge_id}">
        <!-- Card Header: Status Pill + Title (Left) and Quick Action Icons (Right) -->
        <div class="card-header-row">
          <div class="card-title-wrap">
            ${statusPillHtml}
            <h3 class="detailed-challenge-title">${ch.title || `${ch.creator_name}'s Challenge`}</h3>
          </div>

          <div class="card-header-actions">
            <button type="button" class="btn-share-challenge-hub ${isShareExpanded ? "active" : ""}"
              data-id="${ch.challenge_id}" data-url="${ch.play_url}"
              title="${t("challenges_page.share_btn_title")}"
              aria-label="${t("challenges_page.share_btn")}"
              aria-expanded="${isShareExpanded}"
              aria-controls="share-drawer-${ch.challenge_id}">
              <svg class="share-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                <circle cx="18" cy="5" r="3"></circle>
                <circle cx="6" cy="12" r="3"></circle>
                <circle cx="18" cy="19" r="3"></circle>
                <line x1="8.59" y1="13.51" x2="15.42" y2="17.49"></line>
                <line x1="15.41" y1="6.51" x2="8.59" y2="10.49"></line>
              </svg>
            </button>
            ${
              isActive
                ? `<button type="button" class="btn-deactivate-challenge-hub btn-action-icon text-danger"
                    data-id="${ch.challenge_id}" data-title="${ch.title || "Challenge"}"
                    title="${t("challenges_page.deactivate_btn")}"
                    aria-label="${t("challenges_page.deactivate_btn")}">
                    <span>🚫</span>
                  </button>`
                : ""
            }
          </div>
        </div>

        <!-- Expandable Share & QR Drawer -->
        <div class="challenge-hub-share-drawer ${isShareExpanded ? "open" : "hidden"}" id="share-drawer-${ch.challenge_id}">
          <div class="share-drawer-inner">
            <div class="share-drawer-grid">
              <div class="share-qr-card">
                <div class="share-qr-display" id="share-qr-${ch.challenge_id}"></div>
                <p class="share-qr-hint">${t("challenges_page.scan_qr_hint")}</p>
              </div>
              <div class="share-info-card">
                <h4 class="share-card-title">${t("challenges_page.share_drawer_title")}</h4>
                <p class="share-card-desc">${t("challenges_page.share_drawer_desc")}</p>
                <div class="share-url-box">
                  <input type="text" readonly value="${ch.play_url}" id="share-url-${ch.challenge_id}" class="share-url-input" spellcheck="false" autocomplete="off" />
                  <button type="button" class="btn-primary btn-copy-share-url" data-url="${ch.play_url}">
                    <span class="btn-icon">📋</span>
                    ${t("challenges_page.copy_btn")}
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Card Subtitle: Host, Created Date, and Time Status -->
        <div class="card-host-row">
          <span class="host-name">${t("challenges_page.host_label", ch.creator_name)}</span>
          <span class="host-dot">•</span>
          <span class="created-date">${t("admin.created_at_label")}: ${formatDate(ch.created_at)}</span>
          <span class="host-dot">•</span>
          ${timeStatusHtml}
        </div>

        <!-- Unified Match Meta: Game Setup & Library Filters -->
        ${buildMatchMetaHtml(ch)}

        <!-- Card Footer & Actions -->
        <div class="detailed-card-footer">
          <div class="footer-left-actions">
            ${
              isActive
                ? `<a href="/play/${ch.capability_token}" class="btn-primary btn-play-challenge" data-token="${ch.capability_token}">
                    <span class="btn-icon">🎮</span>
                    ${t("challenges_page.play_btn")}
                  </a>`
                : ""
            }
            <a href="/play/${ch.capability_token}/summary" class="btn-secondary btn-results-challenge" data-token="${ch.capability_token}">
              <span class="btn-icon">🏆</span>
              ${t("challenges_page.results_btn")}
            </a>
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
  _hubListEl.querySelectorAll(".btn-share-challenge-hub").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      const id = btn.getAttribute("data-id");
      const url = btn.getAttribute("data-url");
      if (id && url) {
        toggleChallengeShare(id, url);
      }
    });
  });

  _hubListEl.querySelectorAll(".btn-copy-share-url").forEach((btn) => {
    btn.addEventListener("click", async (e) => {
      e.stopPropagation();
      const url = btn.getAttribute("data-url");
      if (!url) return;
      await copyToClipboard(url, { successMessage: t("challenge.link_copied") });
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

  _hubListEl.querySelectorAll(".btn-results-challenge").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      e.preventDefault();
      const token = btn.getAttribute("data-token");
      if (token) {
        navigate(`/play/${token}/summary`);
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

  // Re-render any currently expanded share drawers
  _expandedShareDrawers.forEach((chId) => {
    const ch = _challenges.find((c) => c.challenge_id === chId);
    if (ch) {
      const qrEl = document.getElementById(`share-qr-${chId}`);
      if (qrEl) {
        renderQRCode(qrEl, ch.play_url, { size: 120 });
      }
    }
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
 * Toggle challenge share drawer and generate QR code.
 * @param {string} challengeId
 * @param {string} playUrl
 */
export function toggleChallengeShare(challengeId, playUrl) {
  const drawerEl = document.getElementById(`share-drawer-${challengeId}`);
  const btn = _hubListEl?.querySelector(`.btn-share-challenge-hub[data-id="${challengeId}"]`);

  if (_expandedShareDrawers.has(challengeId)) {
    _expandedShareDrawers.delete(challengeId);
    if (drawerEl) {
      drawerEl.classList.add("hidden");
      drawerEl.classList.remove("open");
    }
    if (btn) {
      btn.classList.remove("active");
      btn.setAttribute("aria-expanded", "false");
    }
    return;
  }

  _expandedShareDrawers.add(challengeId);
  if (drawerEl) {
    drawerEl.classList.remove("hidden");
    drawerEl.classList.add("open");
  }
  if (btn) {
    btn.classList.add("active");
    btn.setAttribute("aria-expanded", "true");
  }

  const qrEl = document.getElementById(`share-qr-${challengeId}`);
  if (qrEl) {
    renderQRCode(qrEl, playUrl, { size: 120 });
  }
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
        t("challenges_page.view_standings", count)
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
  entries.forEach((p) => {
    if (p.player_color) {
      registerPlayerColor(p.player_name, p.player_color);
    }
  });

  if (entries.length === 0) {
    contentEl.innerHTML = `
      <div class="standings-empty-state">
        <span class="empty-icon">👥</span>
        <p>${t("challenges_page.no_participants_yet")}</p>
      </div>
    `;
    return;
  }

  // Render Mini Podium for Top 3 (only players who finished)
  let podiumHtml = "";
  const finishedEntries = entries.filter((p) => p.is_finished);
  if (finishedEntries.length >= 2) {
    const top3 = finishedEntries.slice(0, 3);
    const podiumItems = top3
      .map((p, idx) => {
        const medal = idx === 0 ? "🥇" : idx === 1 ? "🥈" : "🥉";
        const placeCls = idx === 0 ? "podium-1st" : idx === 1 ? "podium-2nd" : "podium-3rd";
        const col = playerColor(p.player_name);
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

    podiumHtml = `
      <div class="mini-podium-container">
        <div class="mini-podium-bar">${podiumItems}</div>
      </div>
    `;
  }

  // Render Standings Table
  let rowsHtml = "";
  entries.forEach((e, idx) => {
    const rankBadge = formatRank(e.rank || idx + 1);
    const isWinner = e.is_winner;
    const completedBadge = formatRoundsBadge(e.completed_rounds, data.total_rounds, e.is_finished);

    const timeFormatted = e.total_time_seconds ? `${Math.round(e.total_time_seconds)}s` : "—";
    const awardsHtml = (e.awards || [])
      .map((aw) => `<span class="standing-award-badge" title="${aw}">${aw}</span>`)
      .join(" ");

    rowsHtml += `
      <tr class="${isWinner ? "winner-row" : ""}">
        <td class="col-rank">${rankBadge}</td>
        <td class="col-player">
          ${formatPlayerCellHtml(e.player_name, { isWinner, awardsHtml })}
        </td>
        <td class="col-acc"><strong>${e.accuracy_pct}%</strong></td>
        <td class="col-score">${e.total_score} <span class="max-score">/ ${e.max_possible_score}</span></td>
        <td class="col-progress text-center">${completedBadge}</td>
        <td class="col-time">${timeFormatted}</td>
      </tr>
    `;
  });

  contentEl.innerHTML = `
    ${podiumHtml}
    <div class="standings-table-wrap table-scroll">
      <table class="standings-table">
        <thead>
          <tr>
            <th class="col-rank">${t("challenges_page.rank_col")}</th>
            <th class="col-player">${t("challenges_page.player_col")}</th>
            <th class="col-acc">${t("challenges_page.accuracy_col")}</th>
            <th class="col-score">${t("challenges_page.score_col")}</th>
            <th class="col-progress text-center">${t("challenges_page.progress_col")}</th>
            <th class="col-time">${t("challenges_page.time_col")}</th>
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

/**
 * Refresh challenges hub list and hero stats when UI language changes.
 */
export function refreshChallengesPageLanguage() {
  if (!_isInitialized) return;

  if (_hasLoaded) {
    updateHeroStats();
    renderChallenges();
  } else {
    const loadingEl = _hubListEl?.querySelector(".challenges-loading");
    if (loadingEl) {
      loadingEl.textContent = t("challenges_page.loading");
    }
    const retryBtn = document.getElementById("retry-load-challenges-btn");
    if (retryBtn) {
      retryBtn.textContent = t("challenges_page.refresh_btn");
    }
  }
}


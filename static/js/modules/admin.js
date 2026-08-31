/**
 * Unified Prepare Game & Challenge Creator Module for Immich Quiz.
 * Handles opening the 2-tab "Prepare Game" modal (Local Match & Challenge Link),
 * local player name configuration, preflight checking, auto-title generation,
 * async multiplayer challenge creation, and clipboard link sharing.
 */

import { state, el } from "./state.js";
import { api } from "./api.js";
import { t, formatDate, formatDateTime } from "./i18n.js";
import { showShareToast } from "./summary/share.js";
import { startMatch } from "./screens/setup.js";
import {
  libraryMultiSelect,
  albumMultiSelect,
  countryMultiSelect,
  cityMultiSelect,
  peopleMultiSelect,
  dateRangeSlider,
  getSelectedPeopleMode,
  getActiveFilterSummary,
  playerInput,
} from "./setup_filters.js";
import { loadChallengesList } from "./challenges_page.js";
import { getActiveMode } from "./modes/index.js";
import { renderQRCode } from "./components/qrcode.js";

const CREATOR_NAME_STORAGE_KEY = "immich_challenge_creator_name";

let _modalEl = null;
let _tabLocalBtn = null;
let _tabChallengeBtn = null;
let _paneLocalEl = null;
let _paneChallengeEl = null;
let _modalLocalFooter = null;
let _modalChallengeFooter = null;

// Form elements
let _formViewEl = null;
let _titleInput = null;
let _creatorNameInput = null;
let _expirationSelect = null;
let _generateBtn = null;
let _startMatchBtn = null;
let _localCancelBtn = null;
let _challengeCancelBtn = null;
let _closeBtn = null;
let _openPrepareBtn = null;

// Share box elements
let _shareBoxEl = null;
let _createdTitleEl = null;
let _createdUrlInput = null;
let _createdTimeBadge = null;
let _createdExpBadge = null;
let _createdModeBadge = null;
let _copyLinkBtn = null;
let _qrBtn = null;
let _qrContainer = null;
let _qrCodeEl = null;
let _openLinkBtn = null;

/**
 * Generate smart automatic challenge title based on active configuration.
 */
export function generateAutoChallengeTitle() {
  const mode = state.gameMode || "pinpoint";
  const modeName = mode === "album_shuffle" ? t("mode.album_shuffle") : t("mode.pinpoint");
  const rounds = el.roundCount ? el.roundCount.value : "5";
  const summary = typeof getActiveFilterSummary === "function" ? getActiveFilterSummary() : "";
  const fullLibLabel =
    t("filters.full_library") !== "filters.full_library"
      ? t("filters.full_library")
      : t("leaderboard.scope_all");

  if (summary && summary !== fullLibLabel && summary !== t("setup.filters_summary_default")) {
    return `${summary} • ${modeName} (${rounds}R)`;
  }
  return `${modeName} • ${rounds} Rounds`;
}

/**
 * Initialize the Prepare Game Modal and bind events.
 */
export function initAdminModal() {
  _modalEl = document.getElementById("prepare-game-modal");
  if (!_modalEl) return;

  _tabLocalBtn = document.getElementById("tab-local-game");
  _tabChallengeBtn = document.getElementById("tab-challenge-game");
  _paneLocalEl = document.getElementById("pane-local-game");
  _paneChallengeEl = document.getElementById("pane-challenge-game");
  _modalLocalFooter = document.getElementById("modal-local-footer");
  _modalChallengeFooter = document.getElementById("modal-challenge-footer");

  _formViewEl = document.getElementById("challenge-form-view");
  _titleInput = document.getElementById("challenge-title-input");
  _creatorNameInput = document.getElementById("challenge-creator-name-input");
  _expirationSelect = document.getElementById("challenge-expiration");
  _generateBtn = document.getElementById("challenge-generate-btn");
  _startMatchBtn = document.getElementById("start-match-btn");
  _localCancelBtn = document.getElementById("local-cancel-btn");
  _challengeCancelBtn = document.getElementById("challenge-cancel-btn");
  _closeBtn = document.getElementById("prepare-modal-close-btn");
  _openPrepareBtn = document.getElementById("prepare-game-btn");

  _shareBoxEl = document.getElementById("challenge-share-box");
  _createdTitleEl = document.getElementById("challenge-created-title");
  _createdUrlInput = document.getElementById("challenge-created-url");
  _createdTimeBadge = document.getElementById("challenge-created-time-badge");
  _createdExpBadge = document.getElementById("challenge-created-exp-badge");
  _createdModeBadge = document.getElementById("challenge-created-mode-badge");
  _copyLinkBtn = document.getElementById("challenge-copy-link-btn");
  _qrBtn = document.getElementById("challenge-qr-btn");
  _qrContainer = document.getElementById("challenge-qr-container");
  _qrCodeEl = document.getElementById("challenge-qr-code");
  _openLinkBtn = document.getElementById("challenge-open-link-btn");

  // Tab switching
  if (_tabLocalBtn) _tabLocalBtn.addEventListener("click", () => switchTab("local"));
  if (_tabChallengeBtn) _tabChallengeBtn.addEventListener("click", () => switchTab("challenge"));

  // Open / Close modal
  if (_openPrepareBtn) {
    _openPrepareBtn.addEventListener("click", (e) => {
      e.preventDefault();
      openAdminModal("local");
    });
  }
  if (_closeBtn) _closeBtn.addEventListener("click", closeAdminModal);
  if (_localCancelBtn) _localCancelBtn.addEventListener("click", closeAdminModal);
  if (_challengeCancelBtn) _challengeCancelBtn.addEventListener("click", closeAdminModal);

  // Close on backdrop click
  _modalEl.addEventListener("click", (e) => {
    if (e.target === _modalEl) {
      closeAdminModal();
    }
  });

  // Close on Escape
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && _modalEl && !_modalEl.classList.contains("hidden")) {
      closeAdminModal();
    }
  });

  // Start match from local tab
  if (_startMatchBtn) {
    _startMatchBtn.addEventListener("click", (e) => {
      startMatch(e).catch((err) => showShareToast(err.message || err));
    });
  }

  // Generate challenge button
  if (_generateBtn) _generateBtn.addEventListener("click", handleGenerateChallenge);

  // Share box buttons
  if (_copyLinkBtn) _copyLinkBtn.addEventListener("click", copyCreatedUrl);
  const linkBox = document.getElementById("challenge-share-link-box");
  if (linkBox) {
    linkBox.addEventListener("click", (e) => {
      if (e.target !== _copyLinkBtn && !_copyLinkBtn?.contains(e.target)) {
        copyCreatedUrl();
      }
    });
  }
  if (_qrBtn) {
    _qrBtn.addEventListener("click", () => {
      if (!_qrContainer) return;
      const isHidden = _qrContainer.classList.toggle("hidden");
      _qrBtn.classList.toggle("active", !isHidden);
      _qrBtn.setAttribute("aria-expanded", String(!isHidden));
      _qrContainer.setAttribute("aria-hidden", String(isHidden));
    });
  }
  if (_openLinkBtn) {
    _openLinkBtn.addEventListener("click", () => {
      const url = _createdUrlInput?.value;
      if (url) {
        window.location.href = url;
      }
    });
  }
}

/**
 * Open Prepare Game Modal with initial tab ("local" or "challenge").
 */
export function openAdminModal(initialTab = "local") {
  if (!_modalEl) initAdminModal();
  if (!_modalEl) return;

  // Restore saved creator name or default from lobby
  let savedName = localStorage.getItem(CREATOR_NAME_STORAGE_KEY);
  if (!savedName) {
    const players = playerInput ? playerInput.getPlayers() : [];
    if (players.length > 0 && players[0] && players[0] !== "Player 1") {
      savedName = players[0];
    }
  }
  if (_creatorNameInput && savedName) {
    _creatorNameInput.value = savedName;
  }

  // Pre-fill challenge title with automatic value
  if (_titleInput) {
    _titleInput.value = generateAutoChallengeTitle();
  }

  resetCreateForm();
  switchTab(initialTab);

  _modalEl.classList.remove("hidden");
  _modalEl.setAttribute("aria-hidden", "false");
}

/**
 * Close Prepare Game Modal.
 */
export function closeAdminModal() {
  if (!_modalEl) return;
  _modalEl.classList.add("hidden");
  _modalEl.setAttribute("aria-hidden", "true");
}

/**
 * Switch modal tabs between "local" and "challenge".
 */
export function switchTab(tabName) {
  const isLocal = tabName === "local" || tabName === "create";
  const isChallenge = tabName === "challenge" || tabName === "manage";

  if (_tabLocalBtn) _tabLocalBtn.classList.toggle("active", isLocal);
  if (_tabChallengeBtn) _tabChallengeBtn.classList.toggle("active", isChallenge);

  if (_paneLocalEl) _paneLocalEl.classList.toggle("hidden", !isLocal);
  if (_paneChallengeEl) _paneChallengeEl.classList.toggle("hidden", !isChallenge);

  if (_modalLocalFooter) _modalLocalFooter.classList.toggle("hidden", !isLocal);
  if (_modalChallengeFooter) {
    const isShareShown = _shareBoxEl && !_shareBoxEl.classList.contains("hidden");
    _modalChallengeFooter.classList.toggle("hidden", !isChallenge || isShareShown);
  }

  if (isChallenge && _titleInput && !_titleInput.value.trim()) {
    _titleInput.value = generateAutoChallengeTitle();
  }
}

/**
 * Handle challenge creation request.
 */
async function handleGenerateChallenge(e) {
  if (e) e.preventDefault();

  const creatorName = _creatorNameInput?.value?.trim();
  if (!creatorName) {
    if (_creatorNameInput) _creatorNameInput.focus();
    showShareToast(t("admin.creator_name_required"));
    return;
  }

  // Save creator name for future sessions
  try {
    localStorage.setItem(CREATOR_NAME_STORAGE_KEY, creatorName);
  } catch (_) {}

  const title = _titleInput?.value?.trim() || generateAutoChallengeTitle();
  const roundCount = parseInt(el.roundCount?.value || "5", 10);
  const roundLength = el.roundLength?.value || "1m";
  const expValue = _expirationSelect?.value || "24h";

  let expiresInHours = 24;
  if (expValue === "1h") expiresInHours = 1;
  else if (expValue === "6h") expiresInHours = 6;
  else if (expValue === "24h") expiresInHours = 24;
  else if (expValue === "48h") expiresInHours = 48;
  else if (expValue === "7d") expiresInHours = 168;
  else if (expValue === "never") expiresInHours = null;

  const activeMode = getActiveMode();
  const gameMode = activeMode ? activeMode.name : state.gameMode || "pinpoint";
  const modePayload = activeMode ? activeMode.getModePayload() : {};

  const selectedLibs = libraryMultiSelect ? libraryMultiSelect.getSelectedIds() : [];
  const albumIds = albumMultiSelect ? albumMultiSelect.getSelectedIds() : [];
  const albumNames = albumMultiSelect ? albumMultiSelect.getSelectedItems().map((i) => i.name) : [];
  const { minDate, maxDate } = dateRangeSlider ? dateRangeSlider.getSelectedRange() : { minDate: null, maxDate: null };

  const payload = {
    creator_name: creatorName,
    title,
    game_mode: gameMode,
    round_count: roundCount,
    round_length: roundLength,
    location_mode: modePayload.location_mode ?? true,
    date_mode: modePayload.date_mode ?? true,
    expires_in_hours: expiresInHours,
    libraries: selectedLibs,
    albums: albumIds,
    album_names: albumNames,
    people: peopleMultiSelect ? peopleMultiSelect.getSelectedIds() : [],
    person_names: peopleMultiSelect ? peopleMultiSelect.getSelectedItems().map((p) => p.name) : [],
    people_mode: typeof getSelectedPeopleMode === "function" ? getSelectedPeopleMode() : "ANY",
    countries: countryMultiSelect ? countryMultiSelect.getSelectedIds() : [],
    cities: cityMultiSelect ? cityMultiSelect.getSelectedIds() : [],
    min_date: minDate,
    max_date: maxDate,
    include_shared: el.includeSharedCheckbox ? el.includeSharedCheckbox.checked : false,
  };

  if (_generateBtn) {
    _generateBtn.disabled = true;
  }

  try {
    const res = await api("/api/challenge/create", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    displayShareResult(res);
  } catch (err) {
    console.error("Failed to create challenge:", err);
    showShareToast(err.message || "Failed to create challenge");
    if (_generateBtn) {
      _generateBtn.disabled = false;
    }
  }
}

let _lastCreatedUrl = "";

/**
 * Display the created challenge link and details.
 */
function displayShareResult(challengeData) {
  _formViewEl = _formViewEl || document.getElementById("challenge-form-view");
  _shareBoxEl = _shareBoxEl || document.getElementById("challenge-share-box");
  _createdTitleEl = _createdTitleEl || document.getElementById("challenge-created-title");
  _createdUrlInput = _createdUrlInput || document.getElementById("challenge-created-url");
  _createdTimeBadge = _createdTimeBadge || document.getElementById("challenge-created-time-badge");
  _createdExpBadge = _createdExpBadge || document.getElementById("challenge-created-exp-badge");
  _createdModeBadge = _createdModeBadge || document.getElementById("challenge-created-mode-badge");
  _qrBtn = _qrBtn || document.getElementById("challenge-qr-btn");
  _qrContainer = _qrContainer || document.getElementById("challenge-qr-container");
  _qrCodeEl = _qrCodeEl || document.getElementById("challenge-qr-code");

  if (!_formViewEl || !_shareBoxEl) return;

  _formViewEl.classList.add("hidden");
  _shareBoxEl.classList.remove("hidden");
  if (_modalChallengeFooter) _modalChallengeFooter.classList.add("hidden");

  const token = challengeData?.capability_token || "";
  const playUrl =
    (token ? `${window.location.origin}/play/${token}` : "") ||
    challengeData?.play_url ||
    "";

  _lastCreatedUrl = playUrl;

  if (_createdTitleEl) {
    _createdTitleEl.textContent = challengeData?.title || "Challenge Created!";
  }
  if (_createdUrlInput) {
    _createdUrlInput.value = playUrl;
    _createdUrlInput.setAttribute("value", playUrl);
  }

  if (_qrCodeEl) {
    renderQRCode(_qrCodeEl, playUrl, { size: 180 });
  }
  if (_qrContainer) {
    _qrContainer.classList.add("hidden");
    _qrContainer.setAttribute("aria-hidden", "true");
  }
  if (_qrBtn) {
    _qrBtn.classList.remove("active");
    _qrBtn.setAttribute("aria-expanded", "false");
  }

  if (_createdTimeBadge) {
    const createdDate = challengeData?.created_at || new Date();
    const createdTimeStr = formatDateTime(createdDate, {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
    _createdTimeBadge.textContent = `📅 ${t("admin.created_at_label")}: ${createdTimeStr}`;
  }

  if (_createdExpBadge) {
    if (challengeData?.expires_at) {
      const expiresTimeStr = formatDateTime(challengeData.expires_at, {
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      });
      _createdExpBadge.textContent = `⏳ ${t("admin.expires_at_label")}: ${expiresTimeStr}`;
    } else {
      _createdExpBadge.textContent = `⏳ ${t("challenges_page.never_expires")}`;
    }
  }

  if (_createdModeBadge) {
    const modeEmoji = challengeData?.game_mode === "album_shuffle" ? "🔀" : "📍";
    const modeName = challengeData?.game_mode === "album_shuffle" ? t("mode.album_shuffle") : t("mode.pinpoint");
    const rounds = challengeData?.rounds || el.roundCount?.value || 5;
    _createdModeBadge.textContent = `${modeEmoji} ${rounds} ${t("challenge.rounds")} (${modeName})`;
  }

  // Refresh challenges list in hub if open
  try {
    loadChallengesList();
  } catch (_) {}
}

let _copyResetTimer = null;

/**
 * Reset form back to create view.
 */
function resetCreateForm() {
  if (_formViewEl) _formViewEl.classList.remove("hidden");
  if (_shareBoxEl) _shareBoxEl.classList.add("hidden");
  if (_qrContainer) {
    _qrContainer.classList.add("hidden");
    _qrContainer.setAttribute("aria-hidden", "true");
  }
  if (_qrBtn) {
    _qrBtn.classList.remove("active");
    _qrBtn.setAttribute("aria-expanded", "false");
  }
  if (_copyLinkBtn) {
    _copyLinkBtn.classList.remove("copied");
    _copyLinkBtn.innerHTML = `<span class="btn-icon">📋</span> <span class="copy-btn-text" data-i18n="challenge.copy_link">${t("challenge.copy_link")}</span>`;
  }
  if (_modalChallengeFooter && _tabChallengeBtn?.classList.contains("active")) {
    _modalChallengeFooter.classList.remove("hidden");
  }
  if (_titleInput) _titleInput.value = generateAutoChallengeTitle();
  if (_generateBtn) _generateBtn.disabled = false;
}

/**
 * Copy created capability URL to clipboard.
 */
async function copyCreatedUrl() {
  const input = _createdUrlInput || document.getElementById("challenge-created-url");
  const url = input?.value || _lastCreatedUrl;
  if (!url) return;

  if (input) {
    input.select();
  }

  try {
    await navigator.clipboard.writeText(url);
    showShareToast(t("challenge.link_copied"));
  } catch (_) {
    if (input) {
      input.select();
      document.execCommand("copy");
      showShareToast(t("challenge.link_copied"));
    }
  }

  if (_copyLinkBtn) {
    _copyLinkBtn.classList.add("copied");
    _copyLinkBtn.innerHTML = `<span>✅</span> <span class="copy-btn-text">${t("challenge.link_copied")}</span>`;
    if (_copyResetTimer) clearTimeout(_copyResetTimer);
    _copyResetTimer = setTimeout(() => {
      if (_copyLinkBtn) {
        _copyLinkBtn.classList.remove("copied");
        _copyLinkBtn.innerHTML = `<span class="btn-icon">📋</span> <span class="copy-btn-text" data-i18n="challenge.copy_link">${t("challenge.copy_link")}</span>`;
      }
    }, 2500);
  }
}

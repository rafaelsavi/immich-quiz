/**
 * Admin Challenge Creator & Management Module for Immich Quiz.
 * Handles challenge generation with game mode selection, customizable expiration,
 * preflight check validation, 1-click clipboard sharing, and challenge deactivation.
 */

import { state, el } from "./state.js";
import { api } from "./api.js";
import { t, formatDate } from "./i18n.js";
import { showShareToast } from "./summary/share.js";
import {
  libraryMultiSelect,
  albumMultiSelect,
  countryMultiSelect,
  cityMultiSelect,
  peopleMultiSelect,
  dateRangeSlider,
  getSelectedPeopleMode,
  playerInput,
} from "./setup_filters.js";

const CREATOR_NAME_STORAGE_KEY = "immich_challenge_creator_name";

let _modalEl = null;
let _tabCreateBtn = null;
let _tabManageBtn = null;
let _paneCreateEl = null;
let _paneManageEl = null;
let _paneFooterEl = null;
let _activeCountBadge = null;

// Form elements
let _formViewEl = null;
let _titleInput = null;
let _creatorNameInput = null;
let _selectedGameMode = "pinpoint";
let _modePinpointBtn = null;
let _modeShuffleBtn = null;
let _roundCountSelect = null;
let _roundLengthSelect = null;
let _expirationSelect = null;
let _filtersSummaryEl = null;
let _preflightStatusEl = null;
let _generateBtn = null;
let _cancelBtn = null;
let _closeBtn = null;
let _openModalBtn = null;

// Share box elements
let _shareBoxEl = null;
let _createdTitleEl = null;
let _createdUrlInput = null;
let _createdExpBadge = null;
let _createdModeBadge = null;
let _copyLinkBtn = null;
let _openLinkBtn = null;
let _createAnotherBtn = null;

// Management elements
let _challengesListEl = null;
let _refreshChallengesBtn = null;

let _preflightTimer = null;
let _preflightAbortCtrl = null;
let _isPreflightValid = true;

/**
 * Initialize the Admin Challenge Creator modal and bind events.
 */
export function initAdminModal() {
  _modalEl = document.getElementById("challenge-creator-modal");
  if (!_modalEl) return;

  _tabCreateBtn = document.getElementById("tab-create-challenge");
  _tabManageBtn = document.getElementById("tab-manage-challenges");
  _paneCreateEl = document.getElementById("pane-create-challenge");
  _paneManageEl = document.getElementById("pane-manage-challenges");
  _paneFooterEl = document.getElementById("pane-create-footer");
  _activeCountBadge = document.getElementById("active-challenges-badge");

  _formViewEl = document.getElementById("challenge-form-view");
  _titleInput = document.getElementById("challenge-title-input");
  _creatorNameInput = document.getElementById("challenge-creator-name-input");
  _modePinpointBtn = document.getElementById("challenge-mode-pinpoint-btn");
  _modeShuffleBtn = document.getElementById("challenge-mode-shuffle-btn");
  _roundCountSelect = document.getElementById("challenge-round-count");
  _roundLengthSelect = document.getElementById("challenge-round-length");
  _expirationSelect = document.getElementById("challenge-expiration");
  _filtersSummaryEl = document.getElementById("challenge-filters-summary-text");
  _preflightStatusEl = document.getElementById("challenge-preflight-status");
  _generateBtn = document.getElementById("challenge-generate-btn");
  _cancelBtn = document.getElementById("challenge-cancel-btn");
  _closeBtn = document.getElementById("challenge-modal-close-btn");
  _openModalBtn = document.getElementById("open-challenge-creator-btn");

  _shareBoxEl = document.getElementById("challenge-share-box");
  _createdTitleEl = document.getElementById("challenge-created-title");
  _createdUrlInput = document.getElementById("challenge-created-url");
  _createdExpBadge = document.getElementById("challenge-created-exp-badge");
  _createdModeBadge = document.getElementById("challenge-created-mode-badge");
  _copyLinkBtn = document.getElementById("challenge-copy-link-btn");
  _openLinkBtn = document.getElementById("challenge-open-link-btn");
  _createAnotherBtn = document.getElementById("challenge-create-another-btn");

  _challengesListEl = document.getElementById("active-challenges-list");
  _refreshChallengesBtn = document.getElementById("refresh-active-challenges-btn");

  // Tab switching
  if (_tabCreateBtn) _tabCreateBtn.addEventListener("click", () => switchTab("create"));
  if (_tabManageBtn) _tabManageBtn.addEventListener("click", () => switchTab("manage"));

  // Open / Close modal
  if (_openModalBtn) _openModalBtn.addEventListener("click", () => openAdminModal("create"));
  if (_closeBtn) _closeBtn.addEventListener("click", closeAdminModal);
  if (_cancelBtn) _cancelBtn.addEventListener("click", closeAdminModal);

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

  // Mode buttons
  if (_modePinpointBtn) {
    _modePinpointBtn.addEventListener("click", () => setChallengeGameMode("pinpoint"));
  }
  if (_modeShuffleBtn) {
    _modeShuffleBtn.addEventListener("click", () => setChallengeGameMode("album_shuffle"));
  }

  // Preflight change triggers
  if (_roundCountSelect) _roundCountSelect.addEventListener("change", triggerPreflightCheck);
  if (_roundLengthSelect) _roundLengthSelect.addEventListener("change", triggerPreflightCheck);
  if (_expirationSelect) _expirationSelect.addEventListener("change", triggerPreflightCheck);

  // Generate button
  if (_generateBtn) _generateBtn.addEventListener("click", handleGenerateChallenge);

  // Share box buttons
  if (_copyLinkBtn) _copyLinkBtn.addEventListener("click", copyCreatedUrl);
  if (_createAnotherBtn) _createAnotherBtn.addEventListener("click", resetCreateForm);
  if (_openLinkBtn) {
    _openLinkBtn.addEventListener("click", () => {
      const url = _createdUrlInput?.value;
      if (url) {
        window.location.href = url;
      }
    });
  }

  // Refresh active challenges
  if (_refreshChallengesBtn) {
    _refreshChallengesBtn.addEventListener("click", loadActiveChallenges);
  }
}

/**
 * Open Admin Challenge modal with initial tab.
 */
export function openAdminModal(initialTab = "create") {
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

  // Sync initial game mode from lobby if available
  const lobbyMode = state.gameMode || "pinpoint";
  setChallengeGameMode(lobbyMode, false);

  updateFilterSummaryReadout();
  resetCreateForm();
  switchTab(initialTab);

  _modalEl.classList.remove("hidden");
  _modalEl.setAttribute("aria-hidden", "false");

  triggerPreflightCheck();
}

/**
 * Close Admin Challenge modal.
 */
export function closeAdminModal() {
  if (!_modalEl) return;
  _modalEl.classList.add("hidden");
  _modalEl.setAttribute("aria-hidden", "true");
  if (_preflightAbortCtrl) {
    _preflightAbortCtrl.abort();
    _preflightAbortCtrl = null;
  }
}

/**
 * Switch modal tabs.
 */
export function switchTab(tabName) {
  if (!_tabCreateBtn || !_tabManageBtn) return;

  const isCreate = tabName === "create";
  _tabCreateBtn.classList.toggle("active", isCreate);
  _tabManageBtn.classList.toggle("active", !isCreate);

  if (_paneCreateEl) _paneCreateEl.classList.toggle("hidden", !isCreate);
  if (_paneManageEl) _paneManageEl.classList.toggle("hidden", isCreate);
  if (_paneFooterEl) {
    // Footer is only shown on Create tab when not showing share result
    const isShareShown = _shareBoxEl && !_shareBoxEl.classList.contains("hidden");
    _paneFooterEl.classList.toggle("hidden", !isCreate || isShareShown);
  }

  if (!isCreate) {
    loadActiveChallenges();
  }
}

/**
 * Set the selected challenge game mode.
 */
function setChallengeGameMode(mode, triggerCheck = true) {
  _selectedGameMode = mode;
  if (_modePinpointBtn) _modePinpointBtn.classList.toggle("active", mode === "pinpoint");
  if (_modeShuffleBtn) _modeShuffleBtn.classList.toggle("active", mode === "album_shuffle");

  if (triggerCheck) {
    triggerPreflightCheck();
  }
}

/**
 * Update the active filters summary readout from the lobby.
 */
function updateFilterSummaryReadout() {
  if (!_filtersSummaryEl) return;
  const lobbySummaryBadge = document.getElementById("filters-summary-badge");
  const text = lobbySummaryBadge ? lobbySummaryBadge.textContent : t("setup.filters_summary_default");
  _filtersSummaryEl.textContent = text || t("setup.filters_summary_default");
}

/**
 * Trigger live preflight check against current filters and selected mode.
 */
function triggerPreflightCheck() {
  if (_preflightTimer) clearTimeout(_preflightTimer);
  _preflightTimer = setTimeout(runPreflightCheck, 150);
}

async function runPreflightCheck() {
  if (!_preflightStatusEl) return;

  if (_preflightAbortCtrl) {
    _preflightAbortCtrl.abort();
  }
  _preflightAbortCtrl = new AbortController();
  const { signal } = _preflightAbortCtrl;

  const roundCount = parseInt(_roundCountSelect?.value || "5", 10);
  const batchSize = _selectedGameMode === "album_shuffle" ? 3 : 1;
  const required = roundCount * batchSize;

  _preflightStatusEl.className = "challenge-preflight-status loading";
  _preflightStatusEl.innerHTML = `<span class="preflight-spinner"></span><span class="preflight-text">${t("admin.checking_photos")}</span>`;

  const selectedLibs = libraryMultiSelect ? libraryMultiSelect.getSelectedIds() : [];
  const { minDate, maxDate } = dateRangeSlider ? dateRangeSlider.getSelectedRange() : { minDate: null, maxDate: null };

  const payload = {
    players: [_creatorNameInput?.value?.trim() || "Host"],
    round_count: roundCount,
    location_mode: true,
    date_mode: true,
    game_mode: _selectedGameMode,
    libraries: selectedLibs,
    albums: albumMultiSelect ? albumMultiSelect.getSelectedIds() : [],
    people: peopleMultiSelect ? peopleMultiSelect.getSelectedIds() : [],
    people_mode: typeof getSelectedPeopleMode === "function" ? getSelectedPeopleMode() : "ANY",
    countries: countryMultiSelect ? countryMultiSelect.getSelectedIds() : [],
    cities: cityMultiSelect ? cityMultiSelect.getSelectedIds() : [],
    min_date: minDate,
    max_date: maxDate,
    include_shared: el.includeSharedCheckbox ? el.includeSharedCheckbox.checked : false,
  };

  try {
    const res = await api("/api/game/preflight", {
      method: "POST",
      signal,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    const eligible = res.eligible_count ?? 0;
    const ok = eligible >= required;
    _isPreflightValid = ok;

    if (ok) {
      _preflightStatusEl.className = "challenge-preflight-status success";
      _preflightStatusEl.innerHTML = `<span>${t("admin.photos_ready", eligible, required)}</span>`;
    } else {
      _preflightStatusEl.className = "challenge-preflight-status warning";
      _preflightStatusEl.innerHTML = `<span>${t("admin.photos_insufficient", eligible, required)}</span>`;
    }

    if (_generateBtn) {
      _generateBtn.disabled = !ok;
    }
  } catch (err) {
    if (err.name === "AbortError" || (err.message && err.message.includes("abort"))) {
      return;
    }
    _preflightStatusEl.className = "challenge-preflight-status warning";
    _preflightStatusEl.innerHTML = `<span>${err.message || "Preflight check failed"}</span>`;
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

  const title = _titleInput?.value?.trim() || null;
  const roundCount = parseInt(_roundCountSelect?.value || "5", 10);
  const roundLength = _roundLengthSelect?.value || "1m";
  const expValue = _expirationSelect?.value || "24h";

  let expiresInHours = 24;
  if (expValue === "1h") expiresInHours = 1;
  else if (expValue === "6h") expiresInHours = 6;
  else if (expValue === "24h") expiresInHours = 24;
  else if (expValue === "48h") expiresInHours = 48;
  else if (expValue === "7d") expiresInHours = 168;
  else if (expValue === "never") expiresInHours = null;

  const selectedLibs = libraryMultiSelect ? libraryMultiSelect.getSelectedIds() : [];
  const albumIds = albumMultiSelect ? albumMultiSelect.getSelectedIds() : [];
  const albumNames = albumMultiSelect ? albumMultiSelect.getSelectedItems().map((i) => i.name) : [];
  const { minDate, maxDate } = dateRangeSlider ? dateRangeSlider.getSelectedRange() : { minDate: null, maxDate: null };

  const payload = {
    creator_name: creatorName,
    title,
    game_mode: _selectedGameMode,
    round_count: roundCount,
    round_length: roundLength,
    location_mode: true,
    date_mode: true,
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

/**
 * Display the created challenge link and details.
 */
function displayShareResult(challengeData) {
  if (!_formViewEl || !_shareBoxEl) return;

  _formViewEl.classList.add("hidden");
  _shareBoxEl.classList.remove("hidden");
  if (_paneFooterEl) _paneFooterEl.classList.add("hidden");

  if (_createdTitleEl) {
    _createdTitleEl.textContent = challengeData.title || "Challenge Created!";
  }
  if (_createdUrlInput) {
    _createdUrlInput.value = challengeData.play_url;
  }

  if (_createdExpBadge) {
    if (challengeData.expires_at) {
      _createdExpBadge.textContent = `⏳ ${formatDate(challengeData.expires_at)}`;
    } else {
      _createdExpBadge.textContent = "♾️ Never expires";
    }
  }

  if (_createdModeBadge) {
    const modeEmoji = challengeData.game_mode === "album_shuffle" ? "🔀" : "📍";
    const modeName = challengeData.game_mode === "album_shuffle" ? t("mode.album_shuffle") : t("mode.pinpoint");
    _createdModeBadge.textContent = `${modeEmoji} ${challengeData.rounds} ${t("challenge.rounds")} (${modeName})`;
  }
}

/**
 * Reset form back to create view.
 */
function resetCreateForm() {
  if (_formViewEl) _formViewEl.classList.remove("hidden");
  if (_shareBoxEl) _shareBoxEl.classList.add("hidden");
  if (_paneFooterEl && _tabCreateBtn?.classList.contains("active")) {
    _paneFooterEl.classList.remove("hidden");
  }
  if (_titleInput) _titleInput.value = "";
  if (_generateBtn) _generateBtn.disabled = !_isPreflightValid;
}

/**
 * Copy created capability URL to clipboard.
 */
async function copyCreatedUrl() {
  const url = _createdUrlInput?.value;
  if (!url) return;

  try {
    await navigator.clipboard.writeText(url);
    showShareToast(t("challenge.link_copied"));
  } catch (_) {
    if (_createdUrlInput) {
      _createdUrlInput.select();
      document.execCommand("copy");
      showShareToast(t("challenge.link_copied"));
    }
  }
}

/**
 * Load and render active challenges for management.
 */
export async function loadActiveChallenges() {
  if (!_challengesListEl) return;

  _challengesListEl.innerHTML = `<div class="challenges-loading">${t("admin.loading_challenges")}</div>`;

  try {
    const res = await api("/api/challenge/list");
    const challenges = res.challenges || [];

    if (_activeCountBadge) {
      const activeCount = challenges.filter((c) => c.is_active).length;
      _activeCountBadge.textContent = String(activeCount);
      _activeCountBadge.classList.toggle("hidden", activeCount === 0);
    }

    if (challenges.length === 0) {
      _challengesListEl.innerHTML = `
        <div class="empty-challenges-state">
          <span class="empty-icon">📭</span>
          <p>${t("admin.no_active_challenges")}</p>
        </div>
      `;
      return;
    }

    let html = "";
    challenges.forEach((ch) => {
      const modeEmoji = ch.game_mode === "album_shuffle" ? "🔀" : "📍";
      const modeName = ch.game_mode === "album_shuffle" ? t("mode.album_shuffle") : t("mode.pinpoint");

      let statusBadge = `<span class="challenge-status-badge active">${t("admin.status_active")}</span>`;
      if (!ch.is_active) {
        statusBadge = `<span class="challenge-status-badge deactivated">${t("admin.status_deactivated")}</span>`;
      } else if (ch.expires_at && new Date(ch.expires_at) < new Date()) {
        statusBadge = `<span class="challenge-status-badge expired">${t("admin.status_expired")}</span>`;
      }

      const participantText = ch.total_participants === 1
        ? t("challenge.participants.one")
        : t("challenge.participants.other", { count: ch.total_participants });

      html += `
        <div class="active-challenge-card ${!ch.is_active ? "inactive" : ""}" data-id="${ch.challenge_id}">
          <div class="challenge-card-head">
            <div class="challenge-card-title-group">
              <strong class="challenge-card-title">${ch.title || "Challenge"}</strong>
              <div class="challenge-card-meta-pills">
                <span class="meta-pill">${modeEmoji} ${ch.rounds} ${t("challenge.rounds")} (${modeName})</span>
                <span class="meta-pill">👥 ${participantText}</span>
                ${statusBadge}
              </div>
            </div>
            <div class="challenge-card-actions">
              <button type="button" class="btn-icon-action btn-copy-challenge-url" data-url="${ch.play_url}" title="${t("challenge.copy_link")}">
                📋
              </button>
              ${
                ch.is_active
                  ? `<button type="button" class="btn-icon-action btn-deactivate-challenge" data-id="${ch.challenge_id}" data-title="${ch.title || "Challenge"}" title="${t("admin.deactivate_btn")}">
                      🚫
                    </button>`
                  : ""
              }
            </div>
          </div>
          <div class="challenge-card-footer">
            <span>${t("admin.created_at_label")}: ${formatDate(ch.created_at)}</span>
            <span>${ch.expires_at ? `${t("admin.expires_at_label")}: ${formatDate(ch.expires_at)}` : "♾️ Never"}</span>
          </div>
        </div>
      `;
    });

    _challengesListEl.innerHTML = html;

    // Bind item actions
    _challengesListEl.querySelectorAll(".btn-copy-challenge-url").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const url = btn.getAttribute("data-url");
        if (url) {
          try {
            await navigator.clipboard.writeText(url);
            showShareToast(t("challenge.link_copied"));
          } catch (_) {
            showShareToast(url);
          }
        }
      });
    });

    _challengesListEl.querySelectorAll(".btn-deactivate-challenge").forEach((btn) => {
      btn.addEventListener("click", () => {
        const id = btn.getAttribute("data-id");
        const title = btn.getAttribute("data-title");
        if (id) {
          confirmAndDeactivateChallenge(id, title);
        }
      });
    });
  } catch (err) {
    console.error("Failed to list active challenges:", err);
    _challengesListEl.innerHTML = `<div class="challenges-error">${err.message || "Failed to load challenges"}</div>`;
  }
}

/**
 * Confirm and deactivate challenge by ID.
 */
async function confirmAndDeactivateChallenge(challengeId, challengeTitle) {
  const confirmed = window.confirm(t("admin.deactivate_confirm", challengeTitle));
  if (!confirmed) return;

  try {
    await api(`/api/challenge/${challengeId}/deactivate`, {
      method: "POST",
    });
    showShareToast(t("admin.deactivate_success"));
    loadActiveChallenges();
  } catch (err) {
    console.error("Failed to deactivate challenge:", err);
    showShareToast(err.message || "Failed to deactivate challenge");
  }
}

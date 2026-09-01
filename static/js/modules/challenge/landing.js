/**
 * Challenge Landing & Error Screens Controller.
 *
 * Renders the initial challenge invite card with resume detection,
 * new player join form with avatar color preview, and error states.
 */

import { state, el } from "../state.js";
import { t, TRANSLATIONS, translateError } from "../i18n.js";
import { showCard } from "../screens/common.js";
import { navigate } from "../router.js";
import { playerColor, playerInitial, registerPlayerColor } from "../formatters.js";
import { buildMatchMetaHtml } from "../components/match_meta.js";
import { challengeSession } from "./session.js";

/**
 * Render the challenge landing / entry screen with resume detection.
 * @param {object} data Challenge metadata object
 * @param {object|null} savedSession Previously saved localStorage session
 * @param {Function} onStart Callback when user starts with name & color
 * @param {Function} onSeeResults Callback when user clicks to see results
 */
export function renderLandingScreen(data, savedSession, onStart, onSeeResults) {
  state.currentScreen = null;
  state.currentQuestion = null;
  challengeSession.lastRoundResult = null;
  if (!el.challengeCard) return;
  showCard(el.challengeCard);
  window.scrollTo({ top: 0, behavior: "smooth" });

  const totalParticipants = typeof data.total_participants === "number" ? data.total_participants : 0;
  const participantsList = data.participants || [];
  if (participantsList.length > 0) {
    state.players = participantsList;
  }
  const nextPlayerIndex = participantsList.length || totalParticipants;
  const nextPlayerColor = playerColor(nextPlayerIndex);

  const participantsText = t("challenge.participants", totalParticipants);
  let mainActionHtml = "";

  if (data.is_active === false) {
    mainActionHtml = `
      <div class="challenge-single-path">
        <div class="challenge-single-header">
          <h3 data-i18n="admin.status_expired">${t("admin.status_expired")}</h3>
          <p data-i18n="challenge.error_expired">${t("challenge.error_expired")}</p>
        </div>
        <button type="button" class="btn btn-primary btn-large challenge-path-btn" id="challenge-see-results-btn">
          <span>🏆 <span data-i18n="challenge.see_results">${t("challenge.see_results")}</span></span>
          <span class="btn-arrow" aria-hidden="true">→</span>
        </button>
      </div>
    `;
  } else if (savedSession) {
    const resumeColor = savedSession.playerColor || playerColor(savedSession.playerName);
    mainActionHtml = `
      <div class="challenge-paths-container">
        <!-- Path 1: Resume Active Session -->
        <div class="challenge-path-card challenge-path-resume">
          <div class="challenge-path-badge">
            <span class="pulse-dot"></span>
            ${t("challenge.path_active_badge")}
          </div>
          <div class="challenge-path-header">
            <span class="challenge-path-icon" aria-hidden="true">🔄</span>
            <div class="challenge-path-text">
              <h3 class="challenge-path-title">${t("challenge.path_resume_title")}</h3>
              <p class="challenge-path-desc">${t("challenge.path_resume_desc")}</p>
            </div>
          </div>
          <div class="challenge-player-pill">
            <span class="player-pill-avatar" style="background: ${resumeColor};">${playerInitial(savedSession.playerName)}</span>
            <span class="player-name">${savedSession.playerName}</span>
          </div>
          <button type="button" class="btn btn-primary btn-large challenge-path-btn" id="challenge-resume-btn">
            <span>${t("challenge.resume_button_as", savedSession.playerName)}</span>
            <span class="btn-arrow" aria-hidden="true">→</span>
          </button>
        </div>

        <!-- Divider -->
        <div class="challenge-paths-divider" role="separator" aria-label="${t("challenge.or_divider")}">
          <span class="divider-line"></span>
          <span class="divider-badge">${t("challenge.or_divider")}</span>
          <span class="divider-line"></span>
        </div>

        <!-- Path 2: Play as Someone Else / Join with New Name -->
        <div class="challenge-path-card challenge-path-new">
          <div class="challenge-path-header">
            <span class="challenge-path-icon" aria-hidden="true">✨</span>
            <div class="challenge-path-text">
              <h3 class="challenge-path-title">${t("challenge.path_new_title")}</h3>
              <p class="challenge-path-desc">${t("challenge.path_new_desc")}</p>
            </div>
          </div>
          <form id="challenge-join-form" class="challenge-form">
            <div class="challenge-input-group">
              <label for="player-name-input">${t("challenge.new_player_label")}</label>
              <div class="challenge-name-input-wrap">
                <span class="challenge-player-avatar-preview" id="challenge-avatar-preview" style="background: ${nextPlayerColor};">?</span>
                <input
                  type="text"
                  id="player-name-input"
                  class="input challenge-name-input"
                  placeholder="${t("challenge.new_player_placeholder")}"
                  maxlength="30"
                  required
                />
              </div>
            </div>
            <button type="submit" class="btn btn-secondary btn-large challenge-path-btn" id="challenge-start-btn">
              <span>${t("challenge.start_button")}</span>
              <span class="btn-arrow" aria-hidden="true">→</span>
            </button>
          </form>
        </div>
      </div>
    `;
  } else {
    mainActionHtml = `
      <div class="challenge-single-path">
        <div class="challenge-single-header">
          <h3>${t("challenge.join_heading")}</h3>
          <p>${t("challenge.join_desc")}</p>
        </div>
        <form id="challenge-join-form" class="challenge-form">
          <div class="challenge-input-group">
            <label for="player-name-input">${t("challenge.name_label")}</label>
            <div class="challenge-name-input-wrap">
              <span class="challenge-player-avatar-preview" id="challenge-avatar-preview" style="background: ${nextPlayerColor};">?</span>
              <input
                type="text"
                id="player-name-input"
                class="input challenge-name-input"
                placeholder="${t("challenge.name_placeholder")}"
                maxlength="30"
                required
                autofocus
              />
            </div>
          </div>
          <button type="submit" class="btn btn-primary btn-large challenge-path-btn" id="challenge-start-btn">
            <span>${t("challenge.start_button")}</span>
            <span class="btn-arrow" aria-hidden="true">→</span>
          </button>
        </form>
      </div>
    `;
  }

  el.challengeCard.innerHTML = `
    <div class="challenge-landing">
      <div class="challenge-header">
        <span class="badge badge-challenge">${t("challenge.badge")}</span>
        <h2>${data.title || `${data.creator_name}'s Challenge`}</h2>
      </div>

      <div class="challenge-participants">
        <span class="icon" aria-hidden="true">👥</span>
        <span>${participantsText}</span>
      </div>

      <div class="challenge-landing-specs">
        ${buildMatchMetaHtml(data)}
      </div>

      ${mainActionHtml}
    </div>
  `;

  const nameInput = document.getElementById("player-name-input");
  const avatarPreview = document.getElementById("challenge-avatar-preview");
  if (nameInput && avatarPreview) {
    nameInput.addEventListener("input", () => {
      const val = nameInput.value.trim();
      avatarPreview.textContent = val ? playerInitial(val) : "?";
    });
  }

  const form = document.getElementById("challenge-join-form");
  form?.addEventListener("submit", (e) => {
    e.preventDefault();
    const name = document.getElementById("player-name-input")?.value?.trim();
    if (name && onStart) {
      onStart(name, nextPlayerColor);
    }
  });

  const resumeBtn = document.getElementById("challenge-resume-btn");
  if (resumeBtn && savedSession) {
    resumeBtn.addEventListener("click", () => {
      challengeSession.sessionToken = savedSession.token;
      challengeSession.sessionPlayerName = savedSession.playerName;
      if (savedSession.playerColor) {
        registerPlayerColor(savedSession.playerName, savedSession.playerColor);
      }
      if (onStart) {
        onStart(savedSession.playerName, savedSession.playerColor);
      }
    });
  }

  const viewResultsBtn = document.getElementById("challenge-see-results-btn");
  if (viewResultsBtn && onSeeResults) {
    viewResultsBtn.addEventListener("click", () => {
      onSeeResults();
    });
  }
}

/**
 * Render error screen for invalid or expired challenges.
 * @param {string} message
 * @param {string|null} [i18nKey]
 */
export function renderErrorScreen(message, i18nKey = null) {
  state.currentScreen = null;
  state.currentQuestion = null;
  challengeSession.lastRoundResult = null;
  if (!el.challengeCard) return;

  let key = i18nKey;
  if (!key && typeof message === "string") {
    const trimmed = message.trim();
    const isExpiredMsg = Object.values(TRANSLATIONS).some(
      (dict) => dict && dict["challenge.error_expired"] === trimmed
    );
    if (trimmed === "challenge.error_expired" || isExpiredMsg) {
      key = "challenge.error_expired";
    } else if (Object.values(TRANSLATIONS).some((dict) => dict && trimmed in dict)) {
      key = trimmed;
    } else if (Object.values(TRANSLATIONS).some((dict) => dict && `error.${trimmed}` in dict)) {
      key = `error.${trimmed}`;
    } else if (trimmed.startsWith("Unknown album_id for library")) {
      key = "error.unknown_album";
    }
  }

  challengeSession.currentError = { message, i18nKey: key };
  const displayMsg = key ? t(key) : translateError(message);

  showCard(el.challengeCard);
  el.challengeCard.innerHTML = `
    <div class="challenge-error">
      <h2>⚠️ <span data-i18n="challenge.error_title">${t("challenge.error_title")}</span></h2>
      <p${key ? ` data-i18n="${key}"` : ""}>${displayMsg}</p>
      <button type="button" class="btn btn-primary" id="challenge-error-home-btn" data-i18n="challenge.back_home">
        ${t("challenge.back_home")}
      </button>
    </div>
  `;

  document.getElementById("challenge-error-home-btn")?.addEventListener("click", () => {
    navigate("/");
  });
}

/**
 * Dynamically refresh challenge screens (error, landing, invite counter)
 * whenever the application language is toggled.
 * @param {Function} onStart Callback for landing screen
 * @param {Function} onSeeResults Callback for landing screen
 */
export function refreshLanguage(onStart, onSeeResults) {
  if (!el.challengeCard || el.challengeCard.classList.contains("hidden")) {
    return;
  }

  // 1. Refresh error screen if currently displayed
  const errorEl = el.challengeCard.querySelector(".challenge-error");
  if (errorEl) {
    const msg = challengeSession.currentError?.message || t("challenge.error_expired");
    const key = challengeSession.currentError?.i18nKey || "challenge.error_expired";
    renderErrorScreen(msg, key);
    return;
  }

  // 2. Refresh landing / entry screen if currently displayed
  const landingEl = el.challengeCard.querySelector(".challenge-landing");
  if (landingEl && challengeSession.challengeData && !challengeSession.sessionToken) {
    const savedSessionRaw = challengeSession.challengeData.capability_token
      ? localStorage.getItem(challengeSession.sessionKey(challengeSession.challengeData.capability_token))
      : null;
    let savedSession = null;
    if (savedSessionRaw) {
      try {
        savedSession = JSON.parse(savedSessionRaw);
      } catch (_) {}
    }
    renderLandingScreen(challengeSession.challengeData, savedSession, onStart, onSeeResults);
  }

  // 3. Dynamically refresh invite screen counter language if visible
  const countTextEl = document.getElementById("finisher-count-text");
  if (countTextEl && challengeSession.cachedLeaderboardData && challengeSession.cachedLeaderboardData.leaderboard) {
    const finishedCount = challengeSession.cachedLeaderboardData.leaderboard.filter((e) => e.is_finished).length;
    const friendsCount = challengeSession.sessionPlayerName
      ? challengeSession.cachedLeaderboardData.leaderboard.filter((e) => e.is_finished && e.player_name !== challengeSession.sessionPlayerName).length
      : Math.max(0, finishedCount - 1);
    countTextEl.textContent = t("challenge.finisher_count", friendsCount);
  }
}

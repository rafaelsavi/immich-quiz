/**
 * Challenge Mode Controller for Immich Quiz.
 *
 * Handles async/hybrid multiplayer with round-by-round personal reveal,
 * 3-second polling social intermission with animated Leaflet pin drops,
 * "Invite Friends" intermission, and Grand Reveal summary with podium,
 * performance awards, and interactive round scatter-map carousel.
 *
 * Supports both Pinpoint and Album Shuffle game modes.
 */

import { api } from "./api.js";
import { state, el } from "./state.js";
import {
  createStandardMap,
  createPinIcon,
  createBadgePinIcon,
  fitMapToBounds,
  spawnPinPulseEffect,
  applySpiderfy,
  unregisterActiveMap,
} from "./maps.js";
import { playPinDropSound, playSubmitTone, playVictoryFanfare } from "./audio.js";
import { launchGoldConfetti, animateScoreRollup } from "./effects.js";
import {
  ACTUAL_COLOR,
  playerColor,
  playerInitial,
  formatPlace,
  formatDistance,
  formatMonth,
  renderRoundMeta,
  playerNameCell,
} from "./formatters.js";
import { t, getLocale, formatDate } from "./i18n.js";
import { renderPodium } from "./summary/podium.js";
import { renderAwards } from "./summary/awards.js";
import { startTimer, clearTimer, resetTimerBar } from "./timer.js";
import { getActiveMode } from "./modes/index.js";
import { showCard } from "./screens/common.js";
import { navigate } from "./router.js";


const POLL_INTERVAL_MS = 3000;
const SESSION_STORAGE_PREFIX = "immich_challenge_";

let challengeData = null;
let sessionToken = null;
let sessionPlayerName = null;
let currentRoundIndex = 0;
let totalRounds = 0;
let questionStartTime = null;
let pollingInterval = null;

let intermissionMap = null;
let intermissionMarkers = {};
let intermissionSpiderLines = {};
let intermissionTrueCoords = {};
let placedPinIds = new Set();

let carouselMap = null;
let carouselMarkers = {};
let carouselSpiderLines = {};
let carouselTrueCoords = {};
let carouselRoundIndex = 0;
let cachedLeaderboardData = null;

/**
 * Get localStorage key for persisting session token per challenge.
 * @param {string} capabilityToken
 * @returns {string}
 */
function sessionKey(capabilityToken) {
  return `${SESSION_STORAGE_PREFIX}${capabilityToken}`;
}

export const challenge = {
  /**
   * Initialize a challenge from a capability token in the URL.
   * @param {string} capabilityToken
   */
  async init(capabilityToken) {
    this.stopPolling();
    this.cleanupMaps();

    try {
      challengeData = await api(`/api/challenge/${encodeURIComponent(capabilityToken)}`);
      state.gameMode = challengeData.game_mode || "pinpoint";
      state.mapBounds = challengeData.map_bounds || null;

      // Check for existing session in localStorage
      const savedSessionRaw = localStorage.getItem(sessionKey(capabilityToken));
      let savedSession = null;
      if (savedSessionRaw) {
        try {
          savedSession = JSON.parse(savedSessionRaw);
        } catch (_) {
          localStorage.removeItem(sessionKey(capabilityToken));
        }
      }

      this.renderLandingScreen(challengeData, savedSession);
    } catch (err) {
      console.error("Failed to load challenge:", err);
      this.renderErrorScreen(t("challenge.error_expired"));
    }
  },

  /**
   * Render the challenge landing / entry screen with resume detection.
   */
  renderLandingScreen(data, savedSession) {
    if (!el.challengeCard) return;
    showCard(el.challengeCard);
    window.scrollTo({ top: 0, behavior: "smooth" });

    const totalParticipants = typeof data.total_participants === "number" ? data.total_participants : 0;
    const participantsText = t("challenge.participants", totalParticipants);
    const modeLabel = data.game_mode === "album_shuffle" ? t("mode.album_shuffle") : t("mode.pinpoint");
    const filterSummary = data.filter_summary || t("filters.full_library");

    const resumeSectionHtml = savedSession
      ? `<div class="challenge-resume-notice">
           <p>${t("challenge.resume_notice")} (<strong>${savedSession.playerName}</strong>)</p>
           <button type="button" class="btn btn-primary" id="challenge-resume-btn">
             ${t("challenge.resume_button")}
           </button>
         </div>`
      : "";

    el.challengeCard.innerHTML = `
      <div class="challenge-landing">
        <div class="challenge-header">
          <span class="badge badge-challenge">${t("challenge.badge")}</span>
          <h2>${data.title || `${data.creator_name}'s Challenge`}</h2>
          <p class="challenge-meta">
            ${data.rounds} ${t("challenge.rounds")} • ${modeLabel} • ${filterSummary}
          </p>
        </div>

        <div class="challenge-participants">
          <span class="icon" aria-hidden="true">👥</span>
          <span>${participantsText}</span>
        </div>

        ${resumeSectionHtml}

        <form id="challenge-join-form" class="challenge-form">
          <label for="player-name-input">${t("challenge.name_label")}</label>
          <input
            type="text"
            id="player-name-input"
            class="input"
            placeholder="${t("challenge.name_placeholder")}"
            maxlength="30"
            required
            autofocus
            value="${savedSession ? savedSession.playerName : ""}"
          />
          <button type="submit" class="btn btn-primary btn-large" id="challenge-start-btn">
            ${t("challenge.start_button")}
          </button>
        </form>
      </div>
    `;

    const form = document.getElementById("challenge-join-form");
    form?.addEventListener("submit", (e) => {
      e.preventDefault();
      const name = document.getElementById("player-name-input")?.value?.trim();
      if (name) {
        this.start(name);
      }
    });

    const resumeBtn = document.getElementById("challenge-resume-btn");
    if (resumeBtn && savedSession) {
      resumeBtn.addEventListener("click", () => {
        sessionToken = savedSession.token;
        sessionPlayerName = savedSession.playerName;
        this.start(savedSession.playerName);
      });
    }
  },

  /**
   * Start or resume a player challenge session.
   * @param {string} playerName
   */
  async start(playerName) {
    try {
      const res = await api(`/api/challenge/${encodeURIComponent(challengeData.capability_token)}/start`, {
        method: "POST",
        body: JSON.stringify({ player_name: playerName }),
      });

      sessionToken = res.session_token;
      sessionPlayerName = res.player_name;
      totalRounds = res.total_rounds;

      // Persist session in localStorage for resume
      localStorage.setItem(
        sessionKey(challengeData.capability_token),
        JSON.stringify({
          token: sessionToken,
          matchId: res.match_id,
          playerName: sessionPlayerName,
        })
      );

      if (res.is_resumed && res.current_round >= res.total_rounds) {
        this.showGrandReveal();
      } else if (res.is_resumed && res.current_round > 0) {
        this.loadRound(res.current_round);
      } else {
        this.loadRound(0);
      }
    } catch (err) {
      if (err.status === 409) {
        this.showGrandReveal();
        return;
      }
      alert(`${t("challenge.start_error")}: ${err.message || err}`);
    }
  },

  /**
   * Load and render question for round N.
   * @param {number} roundIndex
   */
  async loadRound(roundIndex) {
    this.stopPolling();
    this.cleanupMaps();

    currentRoundIndex = roundIndex;
    resetTimerBar();
    state.guessedLatLng = null;
    state.timedOut = false;
    state.submitting = false;

    try {
      const question = await api(
        `/api/challenge/${encodeURIComponent(challengeData.capability_token)}/question/${roundIndex}`,
        {
          headers: {
            "X-Player-Token": sessionToken,
          },
        }
      );

      state.currentQuestion = question;
      state.gameMode = question.game_mode || challengeData.game_mode || "pinpoint";
      state.mapBounds = question.map_bounds || challengeData.map_bounds || null;

      this.renderQuestionScreen(question);
    } catch (err) {
      if (err.status === 409) {
        this.showGrandReveal();
        return;
      }
      console.error("Failed to load challenge question:", err);
      alert(err.message || "Failed to load question");
    }
  },

  /**
   * Render question screen using existing game mode UI.
   * @param {object} question
   */
  renderQuestionScreen(question) {
    showCard(el.gameCard);
    if (el.guessingUi) el.guessingUi.classList.remove("hidden");
    if (el.revealUi) el.revealUi.classList.add("hidden");
    if (el.passOverlay) el.passOverlay.classList.add("hidden");

    // Standard round metadata banner
    if (el.roundMeta) {
      renderRoundMeta(el.roundMeta, {
        roundNum: currentRoundIndex + 1,
        totalRounds: question.total_rounds || totalRounds,
        playerNum: 1,
        totalPlayers: 1,
        playerName: sessionPlayerName,
        isReveal: false,
        showHelp: state.gameMode === "album_shuffle",
        onHelpClick: () => {
          getActiveMode().openHelp?.(question);
        },
      });
    }

    const activeMode = getActiveMode();
    activeMode.mount(el.guessingUi, challengeData);
    activeMode.renderQuestion(question);
    activeMode.onReady(question);
    activeMode.setDisabled(false);

    if (el.submitAnswer) {
      el.submitAnswer.textContent = t("game.submit_btn");
      el.submitAnswer.onclick = (e) => {
        e.preventDefault();
        this.submitAnswer(false);
      };
    }

    // Start countdown timer
    questionStartTime = performance.now();
    startTimer(
      question.round_length || challengeData.round_length,
      getActiveMode,
      null,
      () => this.submitAnswer(true)
    );

    window.scrollTo({ top: 0, behavior: "smooth" });
  },

  /**
   * Submit answer and transition to personal reveal.
   * @param {boolean} fromTimeout
   */
  async submitAnswer(fromTimeout = false) {
    if (state.submitting || !state.currentQuestion) return;
    state.submitting = true;
    clearTimer();
    playSubmitTone();

    const elapsedSeconds = Math.max(0.1, (performance.now() - (questionStartTime || performance.now())) / 1000);
    const activeMode = getActiveMode();
    const guessPayload = activeMode.buildAnswerPayload(state.currentQuestion, fromTimeout);

    const body = {
      round_index: currentRoundIndex,
      guessed_latitude: guessPayload.guessed_latitude ?? null,
      guessed_longitude: guessPayload.guessed_longitude ?? null,
      guessed_year: guessPayload.guessed_year ?? null,
      guessed_month: guessPayload.guessed_month ?? null,
      album_shuffle_answers: guessPayload.album_shuffle_answers ?? null,
      time_taken_seconds: elapsedSeconds,
      timed_out: fromTimeout || Boolean(guessPayload.timed_out),
    };

    try {
      const result = await api(
        `/api/challenge/${encodeURIComponent(challengeData.capability_token)}/answer`,
        {
          method: "POST",
          headers: {
            "X-Player-Token": sessionToken,
          },
          body: JSON.stringify(body),
        }
      );

      this.renderPersonalReveal(result, currentRoundIndex);
    } catch (err) {
      console.error("Failed to submit challenge answer:", err);
      alert(err.message || "Failed to submit answer");
    } finally {
      state.submitting = false;
    }
  },

  /**
   * Round-by-round Personal Reveal Screen.
   * Shows the player their own answer vs the true answer immediately.
   * @param {object} result
   * @param {number} roundIndex
   */
  renderPersonalReveal(result, roundIndex) {
    showCard(el.gameCard);
    if (el.guessingUi) el.guessingUi.classList.add("hidden");
    if (el.revealUi) el.revealUi.classList.remove("hidden");

    const formattedReveal = {
      round_number: roundIndex + 1,
      total_rounds: totalRounds,
      location_mode: challengeData.location_mode !== false,
      date_mode: challengeData.date_mode !== false,
      game_mode: result.game_mode || challengeData.game_mode,
      asset_id: state.currentQuestion?.asset_id || null,
      media_url: state.currentQuestion?.media_url || null,
      actual_latitude: result.actual_latitude,
      actual_longitude: result.actual_longitude,
      actual_date: result.actual_date,
      actual_year: result.actual_year,
      actual_month: result.actual_month,
      actual_city: result.actual_city,
      actual_country: result.actual_country,
      batch_reveal: result.batch_reveal || null,
      match_finished: result.is_game_over,
      results: [
        {
          player_name: sessionPlayerName,
          guessed_latitude: result.actual_latitude !== null ? (state.guessedLatLng?.lat ?? null) : null,
          guessed_longitude: result.actual_longitude !== null ? (state.guessedLatLng?.lng ?? null) : null,
          guessed_year: result.actual_year !== null && el.dateGuessYear ? Number(el.dateGuessYear.value) : null,
          guessed_month: result.actual_month !== null && el.dateGuessMonth ? Number(el.dateGuessMonth.value) : null,
          location_score: result.location_score,
          date_score: result.date_score,
          round_score: result.round_score,
          total_score: result.total_score,
          distance_km: result.distance_km,
          date_diff_days: result.date_diff_days,
          date_diff_months: result.date_diff_months,
          timed_out: result.timed_out || false,
          album_shuffle_guesses: state.albumShuffleState?.orderedPhotoIds?.map((pid, idx) => ({
            photo_id: pid,
            assigned_pin_id: state.albumShuffleState.pinAssignments[pid] || null,
            assigned_timeline_index: idx,
          })) || null,
        },
      ],
    };

    const activeMode = getActiveMode();
    activeMode.renderReveal(el.revealUi, formattedReveal);

    if (el.nextRound) {
      el.nextRound.textContent = result.is_game_over ? t("reveal.see_results_btn") : t("reveal.next_round_btn");
      el.nextRound.onclick = (e) => {
        e.preventDefault();
        if (result.is_game_over) {
          this.renderInviteFriendsScreen();
        } else {
          this.renderIntermissionScreen(result, roundIndex);
        }
      };
    }
  },

  /**
   * Social Intermission Screen with 3s Polling.
   * Shows friends' pins dropping dynamically on the map as they complete the round.
   * @param {object} roundResult
   * @param {number} roundIndex
   */
  renderIntermissionScreen(roundResult, roundIndex) {
    if (!el.challengeCard) return;
    showCard(el.challengeCard);
    window.scrollTo({ top: 0, behavior: "smooth" });

    placedPinIds = new Set();
    intermissionMarkers = {};
    intermissionSpiderLines = {};
    intermissionTrueCoords = {};

    const roundNum = roundIndex + 1;
    const titleText = t("challenge.intermission_title", roundNum);
    const subtitleText = t("challenge.intermission_subtitle");

    el.challengeCard.innerHTML = `
      <div class="challenge-intermission">
        <div class="intermission-head">
          <div class="intermission-title-wrap">
            <h2>${titleText}</h2>
            <p class="intermission-subtitle">${subtitleText}</p>
          </div>
          <div class="intermission-score-pills">
            <span class="score-pill highlight">${t("challenge.your_score", roundResult.round_score)}</span>
            <span class="score-pill">${t("challenge.running_total", roundResult.total_score)}</span>
          </div>
        </div>

        <div class="intermission-grid">
          <div class="intermission-map-shell" id="intermission-map-shell">
            <div id="intermission-map"></div>
          </div>
          <div class="intermission-sidebar">
            <div class="sidebar-header">
              <h3>${t("challenge.live_standings")}</h3>
              <div class="live-poll-indicator">
                <span class="live-poll-dot"></span>
                <span>Live</span>
              </div>
            </div>
            <div class="intermission-standings-list" id="intermission-standings-list">
              <div class="standing-item current-player">
                <div class="standing-player-info">
                  <span class="standing-rank">1</span>
                  <span class="standing-name">${sessionPlayerName}</span>
                </div>
                <div class="standing-score-wrap">
                  <span class="standing-score">${roundResult.total_score} pts</span>
                  <span class="standing-sub">${t("challenge.your_score", roundResult.round_score)}</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div class="intermission-actions">
          <button type="button" class="btn btn-primary btn-large" id="intermission-next-btn">
            ${t("challenge.next_round_btn")}
          </button>
        </div>
      </div>
    `;

    document.getElementById("intermission-next-btn")?.addEventListener("click", () => {
      this.stopPolling();
      this.loadRound(roundIndex + 1);
    });

    // Initialize intermission map
    const mapShell = document.getElementById("intermission-map-shell");
    if (mapShell && window.L) {
      intermissionMap = createStandardMap("intermission-map", {
        existingMap: intermissionMap,
        titleKey: "game.fullscreen_map_title",
      });

      const bounds = L.latLngBounds();

      // Add True location pin
      if (
        roundResult.actual_latitude !== null &&
        roundResult.actual_latitude !== undefined &&
        roundResult.actual_longitude !== null &&
        roundResult.actual_longitude !== undefined
      ) {
        const trueLatLng = [roundResult.actual_latitude, roundResult.actual_longitude];
        bounds.extend(trueLatLng);
        intermissionTrueCoords["__true__"] = { lat: roundResult.actual_latitude, lng: roundResult.actual_longitude };

        const trueIcon = createPinIcon("✓", ACTUAL_COLOR);
        const locLabel = formatPlace(roundResult);
        const trueMarker = L.marker(trueLatLng, { icon: trueIcon })
          .bindPopup(`<b>${t("challenge.true_location")}</b><br>${locLabel}`)
          .addTo(intermissionMap);
        intermissionMarkers["__true__"] = trueMarker;
      }

      // Add player's own guess pin
      if (state.guessedLatLng) {
        bounds.extend(state.guessedLatLng);
        const playerKey = `player_${sessionPlayerName}`;
        placedPinIds.add(playerKey);
        intermissionTrueCoords[playerKey] = { lat: state.guessedLatLng.lat, lng: state.guessedLatLng.lng };

        const color = playerColor(sessionPlayerName);
        const initial = playerInitial(sessionPlayerName);
        const pIcon = createPinIcon(initial, color);
        const pMarker = L.marker(state.guessedLatLng, { icon: pIcon })
          .bindPopup(`<b>${sessionPlayerName}</b><br>${roundResult.round_score} pts`)
          .addTo(intermissionMap);
        intermissionMarkers[playerKey] = pMarker;
      }

      if (bounds.isValid()) {
        fitMapToBounds(intermissionMap, bounds, { padding: [50, 50], maxZoom: 15 });
      }
    }

    this.startPolling(roundIndex);
  },

  /**
   * Start 3-second social polling for leaderboard updates.
   * @param {number} roundIndex
   */
  startPolling(roundIndex) {
    this.stopPolling();

    const poll = async () => {
      try {
        const data = await api(
          `/api/challenge/${encodeURIComponent(challengeData.capability_token)}/leaderboard`,
          {
            headers: {
              "X-Player-Token": sessionToken,
            },
          }
        );
        cachedLeaderboardData = data;
        this.updateIntermissionView(data, roundIndex);
      } catch (err) {
        console.warn("Challenge polling error:", err);
      }
    };

    poll();
    pollingInterval = setInterval(poll, POLL_INTERVAL_MS);
  },

  /**
   * Stop any active polling interval.
   */
  stopPolling() {
    if (pollingInterval) {
      clearInterval(pollingInterval);
      pollingInterval = null;
    }
  },

  /**
   * Update Intermission View with newly dropped friend pins and standings list.
   * @param {object} leaderboardData
   * @param {number} roundIndex
   */
  updateIntermissionView(leaderboardData, roundIndex) {
    // 1. Update live standings sidebar
    const listEl = document.getElementById("intermission-standings-list");
    if (listEl && leaderboardData.leaderboard) {
      listEl.innerHTML = leaderboardData.leaderboard
        .map((entry) => {
          const isCurrent = entry.player_name === sessionPlayerName;
          const finishedBadge = entry.is_finished ? "🏁 " : "";
          return `
            <div class="standing-item ${isCurrent ? "current-player" : ""}">
              <div class="standing-player-info">
                <span class="standing-rank">${entry.rank}</span>
                <span class="standing-name">${finishedBadge}${entry.player_name}</span>
              </div>
              <div class="standing-score-wrap">
                <span class="standing-score">${entry.total_score} pts</span>
                <span class="standing-sub">${entry.accuracy_pct}%</span>
              </div>
            </div>
          `;
        })
        .join("");
    }

    // 2. Drop newly completed friend pins onto the map dynamically
    if (intermissionMap && leaderboardData.round_guesses) {
      const currentGuesses = leaderboardData.round_guesses.filter((g) => g.round_index === roundIndex);
      let newPinDropped = false;
      const bounds = L.latLngBounds();

      Object.values(intermissionTrueCoords).forEach((c) => bounds.extend([c.lat, c.lng]));

      currentGuesses.forEach((guess) => {
        if (
          guess.guessed_latitude !== null &&
          guess.guessed_latitude !== undefined &&
          guess.guessed_longitude !== null &&
          guess.guessed_longitude !== undefined
        ) {
          const pinKey = `player_${guess.player_name}`;
          if (!placedPinIds.has(pinKey)) {
            placedPinIds.add(pinKey);
            newPinDropped = true;

            const latlng = [guess.guessed_latitude, guess.guessed_longitude];
            bounds.extend(latlng);
            intermissionTrueCoords[pinKey] = { lat: guess.guessed_latitude, lng: guess.guessed_longitude };

            const color = playerColor(guess.player_name);
            const initial = playerInitial(guess.player_name);
            const icon = createPinIcon(initial, color);

            const distStr = guess.distance_km !== null ? ` (${formatDistance(guess.distance_km)})` : "";
            const marker = L.marker(latlng, { icon })
              .bindPopup(`<b>${guess.player_name}</b><br>${guess.round_score} pts${distStr}`)
              .addTo(intermissionMap);
            intermissionMarkers[pinKey] = marker;

            // Trigger animation and sound for newly dropped friend pin
            spawnPinPulseEffect(intermissionMap, latlng, color);
            playPinDropSound();
          }
        }
      });

      if (newPinDropped && bounds.isValid()) {
        fitMapToBounds(intermissionMap, bounds, { padding: [50, 50], maxZoom: 15 });
      }
    }
  },

  /**
   * "Invite Friends" intermission shown after the final round.
   */
  renderInviteFriendsScreen() {
    this.stopPolling();
    this.cleanupMaps();

    if (!el.challengeCard) return;
    showCard(el.challengeCard);
    window.scrollTo({ top: 0, behavior: "smooth" });

    const playUrl = `${window.location.origin}/play/${challengeData.capability_token}`;

    el.challengeCard.innerHTML = `
      <div class="challenge-invite">
        <div class="challenge-invite-header">
          <h2>🎉 ${t("challenge.finished_title")}</h2>
          <p>${t("challenge.invite_message")}</p>
        </div>

        <div class="challenge-share-box">
          <input type="text" readonly value="${playUrl}" id="challenge-share-url" class="input" />
          <button type="button" class="btn btn-primary" id="challenge-copy-btn">
            📋 ${t("challenge.copy_link")}
          </button>
        </div>

        <div class="challenge-invite-counter" id="challenge-finisher-count">
          <span class="live-poll-dot"></span>
          <span id="finisher-count-text">${t("challenge.loading_count")}</span>
        </div>

        <button type="button" class="btn btn-large btn-primary" id="challenge-see-results-btn">
          ${t("challenge.see_results")}
        </button>
      </div>
    `;

    // Copy link handler
    document.getElementById("challenge-copy-btn")?.addEventListener("click", () => {
      navigator.clipboard.writeText(playUrl);
      const btn = document.getElementById("challenge-copy-btn");
      if (btn) {
        btn.textContent = `✅ ${t("challenge.link_copied")}`;
        setTimeout(() => {
          if (btn) btn.textContent = `📋 ${t("challenge.copy_link")}`;
        }, 2500);
      }
    });

    // See results handler
    document.getElementById("challenge-see-results-btn")?.addEventListener("click", () => {
      this.showGrandReveal();
    });

    this.startFinisherPolling();
  },

  /**
   * Poll for finished player count on invite screen and auto-transition if >= 2.
   */
  startFinisherPolling() {
    this.stopPolling();

    const poll = async () => {
      try {
        const data = await api(
          `/api/challenge/${encodeURIComponent(challengeData.capability_token)}/leaderboard`,
          {
            headers: {
              "X-Player-Token": sessionToken,
            },
          }
        );
        cachedLeaderboardData = data;
        const finishedCount = data.leaderboard.filter((e) => e.is_finished).length;
        const countTextEl = document.getElementById("finisher-count-text");
        if (countTextEl) {
          countTextEl.textContent = t("challenge.finisher_count", finishedCount);
        }

        // Auto-transition when >= 2 finishers
        if (finishedCount >= 2) {
          this.stopPolling();
          this.showGrandReveal();
        }
      } catch (err) {
        console.warn("Finisher polling error:", err);
      }
    };

    poll();
    pollingInterval = setInterval(poll, POLL_INTERVAL_MS);
  },

  /**
   * Grand Reveal Summary Screen at the end of the challenge.
   */
  async showGrandReveal() {
    this.stopPolling();
    this.cleanupMaps();

    if (!el.challengeCard) return;
    showCard(el.challengeCard);
    window.scrollTo({ top: 0, behavior: "smooth" });

    try {
      const data = await api(
        `/api/challenge/${encodeURIComponent(challengeData.capability_token)}/leaderboard`,
        {
          headers: {
            "X-Player-Token": sessionToken,
          },
        }
      );
      cachedLeaderboardData = data;

      launchGoldConfetti();
      playVictoryFanfare();

      const playUrl = `${window.location.origin}/play/${challengeData.capability_token}`;
      const totalRoundsCount = data.total_rounds || totalRounds;

      el.challengeCard.innerHTML = `
        <div class="challenge-grand-reveal">
          <div class="grand-reveal-header">
            <span class="badge badge-challenge">${t("challenge.badge")}</span>
            <h2>${data.title || `${challengeData.creator_name}'s Challenge`}</h2>
            <p class="grand-reveal-meta">
              ${totalRoundsCount} ${t("challenge.rounds")} • ${data.leaderboard.length} ${t("challenge.participants", data.leaderboard.length)}
            </p>
          </div>

          <div id="grand-reveal-podium" class="summary-winner"></div>

          <!-- Interactive Round Carousel Section -->
          <div class="challenge-carousel-card">
            <div class="carousel-nav-header">
              <h3 class="carousel-nav-title" id="carousel-title">${t("challenge.round_carousel_title")}</h3>
              <div class="carousel-nav-controls">
                <button type="button" class="carousel-nav-btn" id="carousel-prev-btn">◀ ${t("challenge.carousel_prev")}</button>
                <span id="carousel-indicator" style="font-weight:700;font-size:0.9rem;color:var(--ink);"></span>
                <button type="button" class="carousel-nav-btn" id="carousel-next-btn">${t("challenge.carousel_next")} ▶</button>
              </div>
            </div>

            <div class="carousel-round-content" id="carousel-round-content">
              <div class="scatter-map-shell" id="scatter-map-shell">
                <div id="scatter-map"></div>
              </div>
              <div id="carousel-round-extra"></div>
            </div>
          </div>

          <!-- Final Standings Table -->
          <div class="table-scroll">
            <table id="grand-reveal-table" style="width:100%;border-collapse:collapse;">
              <thead>
                <tr>
                  <th style="padding:0.75rem;text-align:left;border-bottom:2px solid var(--border);">${t("leaderboard.col_player")}</th>
                  <th style="padding:0.75rem;text-align:right;border-bottom:2px solid var(--border);">${t("summary.col_score")}</th>
                  <th style="padding:0.75rem;text-align:right;border-bottom:2px solid var(--border);">${t("leaderboard.col_accuracy")}</th>
                </tr>
              </thead>
              <tbody>
                ${data.leaderboard
                  .map(
                    (p) => `
                  <tr style="border-bottom:1px solid var(--border-light);">
                    <td style="padding:0.75rem;text-align:left;">
                      <strong>${p.rank}.</strong> ${p.player_name} ${p.is_winner ? "👑" : ""}
                    </td>
                    <td style="padding:0.75rem;text-align:right;font-weight:700;">${p.total_score} pts</td>
                    <td style="padding:0.75rem;text-align:right;">${p.accuracy_pct}%</td>
                  </tr>
                `
                  )
                  .join("")}
              </tbody>
            </table>
          </div>

          <div class="summary-actions">
            <button type="button" class="btn btn-primary" id="grand-reveal-share-btn">
              📋 ${t("challenge.copy_challenge_link")}
            </button>
            <button type="button" class="btn btn-secondary" id="grand-reveal-home-btn">
              🏠 ${t("challenge.back_home")}
            </button>
          </div>
        </div>
      `;

      // 1. Render Podium
      const podiumEl = document.getElementById("grand-reveal-podium");
      const winners = data.leaderboard.filter((p) => p.is_winner).map((p) => p.player_name);
      renderPodium(
        {
          players: data.leaderboard,
          winners: winners.length > 0 ? winners : [data.leaderboard[0]?.player_name].filter(Boolean),
        },
        podiumEl
      );

      // 2. Render Performance Awards
      const playerStats = this.buildPlayerStats(data);
      const grandRevealEl = el.challengeCard.querySelector(".challenge-grand-reveal");
      renderAwards(
        {
          game_mode: data.game_mode,
          location_mode: challengeData.location_mode !== false,
          date_mode: challengeData.date_mode !== false,
          players: data.leaderboard,
        },
        playerStats,
        grandRevealEl,
        podiumEl
      );

      // 3. Render Round Carousel
      carouselRoundIndex = 0;
      this.renderCarouselRound(data, carouselRoundIndex);

      document.getElementById("carousel-prev-btn")?.addEventListener("click", () => {
        if (carouselRoundIndex > 0) {
          carouselRoundIndex--;
          this.renderCarouselRound(data, carouselRoundIndex);
        }
      });

      document.getElementById("carousel-next-btn")?.addEventListener("click", () => {
        if (carouselRoundIndex < totalRoundsCount - 1) {
          carouselRoundIndex++;
          this.renderCarouselRound(data, carouselRoundIndex);
        }
      });

      // Share button
      document.getElementById("grand-reveal-share-btn")?.addEventListener("click", () => {
        navigator.clipboard.writeText(playUrl);
        const btn = document.getElementById("grand-reveal-share-btn");
        if (btn) {
          btn.textContent = `✅ ${t("challenge.link_copied")}`;
          setTimeout(() => {
            if (btn) btn.textContent = `📋 ${t("challenge.copy_challenge_link")}`;
          }, 2500);
        }
      });

      // Home button
      document.getElementById("grand-reveal-home-btn")?.addEventListener("click", () => {
        navigate("/");
      });
    } catch (err) {
      console.error("Failed to load grand reveal:", err);
      this.renderErrorScreen(err.message || "Failed to load summary");
    }
  },

  /**
   * Render a specific round inside the Grand Reveal Carousel with scatter map and date comparisons.
   * @param {object} data
   * @param {number} roundIdx
   */
  renderCarouselRound(data, roundIdx) {
    const totalRoundsCount = data.total_rounds || totalRounds;
    const indicatorEl = document.getElementById("carousel-indicator");
    if (indicatorEl) {
      indicatorEl.textContent = t("challenge.round_n_of_total", roundIdx + 1, totalRoundsCount);
    }

    const prevBtn = document.getElementById("carousel-prev-btn");
    const nextBtn = document.getElementById("carousel-next-btn");
    if (prevBtn) prevBtn.disabled = roundIdx === 0;
    if (nextBtn) nextBtn.disabled = roundIdx >= totalRoundsCount - 1;

    const roundGuesses = (data.round_guesses || []).filter((g) => g.round_index === roundIdx);
    const extraEl = document.getElementById("carousel-round-extra");

    // Initialize scatter map
    const mapShell = document.getElementById("scatter-map-shell");
    if (mapShell && window.L) {
      carouselMarkers = {};
      carouselSpiderLines = {};
      carouselTrueCoords = {};

      carouselMap = createStandardMap("scatter-map", {
        existingMap: carouselMap,
        titleKey: "game.fullscreen_map_title",
      });

      const bounds = L.latLngBounds();

      // Find first guess with actual coordinates
      const sampleGuess = roundGuesses.find((g) => g.actual_latitude !== null && g.actual_longitude !== null);
      if (sampleGuess) {
        const trueLatLng = [sampleGuess.actual_latitude, sampleGuess.actual_longitude];
        bounds.extend(trueLatLng);
        carouselTrueCoords["__true__"] = { lat: sampleGuess.actual_latitude, lng: sampleGuess.actual_longitude };

        const trueMarker = L.marker(trueLatLng, { icon: createPinIcon("✓", ACTUAL_COLOR) })
          .bindPopup(`<b>${t("challenge.true_location")}</b><br>${formatPlace(sampleGuess)}`)
          .addTo(carouselMap);
        carouselMarkers["__true__"] = trueMarker;
      }

      // Add all player pins
      roundGuesses.forEach((g) => {
        if (g.guessed_latitude !== null && g.guessed_longitude !== null) {
          const latlng = [g.guessed_latitude, g.guessed_longitude];
          bounds.extend(latlng);
          const pKey = `player_${g.player_name}`;
          carouselTrueCoords[pKey] = { lat: g.guessed_latitude, lng: g.guessed_longitude };

          const color = playerColor(g.player_name);
          const initial = playerInitial(g.player_name);
          const icon = createPinIcon(initial, color);

          const distStr = g.distance_km !== null ? ` (${formatDistance(g.distance_km)})` : "";
          const marker = L.marker(latlng, { icon })
            .bindPopup(`<b>${g.player_name}</b><br>${g.round_score} pts${distStr}`)
            .addTo(carouselMap);
          carouselMarkers[pKey] = marker;
        }
      });

      if (bounds.isValid()) {
        fitMapToBounds(carouselMap, bounds, { padding: [50, 50], maxZoom: 15 });
      }
    }

    // Render Date Comparison Chips
    if (extraEl) {
      const sampleWithDate = roundGuesses.find((g) => g.actual_date || g.actual_year);
      if (sampleWithDate && challengeData.date_mode !== false) {
        const actualDateStr = sampleWithDate.actual_date
          ? formatDate(sampleWithDate.actual_date, { year: "numeric", month: "short", day: "numeric" })
          : formatMonth(sampleWithDate.actual_year, sampleWithDate.actual_month);

        extraEl.innerHTML = `
          <div class="round-date-comparison">
            <div class="date-comp-head">
              <span>📅 ${t("game.date_guess_label")}</span>
            </div>
            <div class="date-chips-list">
              <span class="date-chip true-val">
                ✓ <strong>${t("challenge.true_location")}:</strong> ${actualDateStr}
              </span>
              ${roundGuesses
                .map((g) => {
                  if (!g.guessed_year || !g.guessed_month) return "";
                  const pDateStr = formatMonth(g.guessed_year, g.guessed_month);
                  const daysDiffStr = g.date_diff_days !== null ? ` (${g.date_diff_days}d)` : "";
                  return `
                    <span class="date-chip">
                      <strong>${g.player_name}:</strong> ${pDateStr}${daysDiffStr} • ${g.date_points || 0} pts
                    </span>
                  `;
                })
                .join("")}
            </div>
          </div>
        `;
      } else {
        extraEl.innerHTML = "";
      }
    }
  },

  /**
   * Build aggregated player statistics from round guesses for awards calculation.
   * @param {object} leaderboardData
   * @returns {Record<string, object>}
   */
  buildPlayerStats(leaderboardData) {
    const stats = {};
    const totalRoundsCount = leaderboardData.total_rounds || totalRounds;

    // Initialize stats for each player
    (leaderboardData.leaderboard || []).forEach((p) => {
      stats[p.player_name] = {
        totalDistanceKm: 0,
        distanceCount: 0,
        totalDateDiffDays: 0,
        dateCount: 0,
        perfectLocationCount: 0,
        perfectDateCount: 0,
        perfectRounds: 0,
        timedOutCount: 0,
        fastRoundCount: 0,
        totalDurationSec: p.total_time_seconds || 0,
      };
    });

    // Aggregate from round_guesses
    (leaderboardData.round_guesses || []).forEach((g) => {
      const pStats = stats[g.player_name];
      if (!pStats) return;

      if (g.distance_km !== null) {
        pStats.totalDistanceKm += g.distance_km;
        pStats.distanceCount++;
        if (g.distance_km < 1 || g.location_points === 100) {
          pStats.perfectLocationCount++;
        }
      }

      if (g.date_diff_days !== null) {
        pStats.totalDateDiffDays += g.date_diff_days;
        pStats.dateCount++;
        if (g.date_diff_days === 0 || g.date_points === 100) {
          pStats.perfectDateCount++;
        }
      }

      if (g.location_points === 100 && g.date_points === 100) {
        pStats.perfectRounds++;
      }

      // If average active response time is <= 30s per round, consider fast round
      if (g.time_taken_seconds > 0 && g.time_taken_seconds <= 30) {
        pStats.fastRoundCount++;
      }
    });

    return stats;
  },

  /**
   * Render error screen for invalid or expired challenges.
   * @param {string} message
   */
  renderErrorScreen(message) {
    if (!el.challengeCard) return;
    showCard(el.challengeCard);
    el.challengeCard.innerHTML = `
      <div class="challenge-error">
        <h2>⚠️ ${t("challenge.error_title")}</h2>
        <p>${message}</p>
        <button type="button" class="btn btn-primary" id="challenge-error-home-btn">
          ${t("challenge.back_home")}
        </button>
      </div>
    `;

    document.getElementById("challenge-error-home-btn")?.addEventListener("click", () => {
      navigate("/");
    });
  },

  /**
   * Cleanup any active Leaflet maps.
   */
  cleanupMaps() {
    if (intermissionMap) {
      try {
        unregisterActiveMap(intermissionMap);
        intermissionMap.remove();
      } catch (_) {}
      intermissionMap = null;
    }
    if (carouselMap) {
      try {
        unregisterActiveMap(carouselMap);
        carouselMap.remove();
      } catch (_) {}
      carouselMap = null;
    }
  },
};

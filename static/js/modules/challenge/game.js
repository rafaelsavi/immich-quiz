/**
 * Challenge Gameplay Controller for Immich Quiz.
 *
 * Coordinates question loading, active mode mounting, timer management,
 * and answer submission for async multiplayer challenge matches.
 */

import { api } from "../api.js";
import { state, el } from "../state.js";
import { t, showAlert } from "../i18n.js";
import { playSubmitTone } from "../audio.js";
import { playerColor, registerPlayerColor, renderRoundMeta } from "../formatters.js";
import { startTimer, clearTimer, resetTimerBar } from "../timer.js";
import { showCard } from "../screens/common.js";
import { updateSubmitState } from "../maps.js";
import { getActiveMode } from "../modes/index.js";
import { challengeSession } from "./session.js";
import { renderLandingScreen, renderErrorScreen } from "./landing.js";

export const challengeGame = {
  /**
   * Initialize a challenge from a capability token in the URL.
   * @param {string} capabilityToken
   * @param {Function} onStart
   * @param {Function} onSeeResults
   */
  async init(capabilityToken, onStart, onSeeResults) {
    challengeSession.reset();

    try {
      challengeSession.challengeData = await api(`/api/challenge/${encodeURIComponent(capabilityToken)}`);
      state.gameMode = challengeSession.challengeData.game_mode || "pinpoint";
      state.mapBounds = challengeSession.challengeData.map_bounds || null;

      // Check for existing session (prioritizes tab's sessionStorage, falls back to localStorage)
      const savedSession = challengeSession.loadSession(capabilityToken);

      renderLandingScreen(challengeSession.challengeData, savedSession, onStart, onSeeResults);
    } catch (err) {
      console.error("Failed to load challenge:", err);
      renderErrorScreen(t("challenge.error_expired"), "challenge.error_expired");
    }
  },

  /**
   * Initialize and display challenge summary directly (spectator/shared link or reload).
   * @param {string} capabilityToken
   * @param {Function} onShowSummary
   */
  async initSummary(capabilityToken, onShowSummary) {
    challengeSession.reset();

    try {
      challengeSession.challengeData = await api(`/api/challenge/${encodeURIComponent(capabilityToken)}`);
      state.gameMode = challengeSession.challengeData.game_mode || "pinpoint";
      state.mapBounds = challengeSession.challengeData.map_bounds || null;

      // Check for existing session in this tab first (strictly isolated per tab)
      const savedSession = challengeSession.loadSession(capabilityToken, { tabOnly: true });
      if (savedSession) {
        challengeSession.sessionToken = savedSession.token;
        challengeSession.sessionPlayerName = savedSession.playerName;
        if (savedSession.playerColor) {
          registerPlayerColor(savedSession.playerName, savedSession.playerColor);
        }
      }

      if (onShowSummary) {
        await onShowSummary({ updateUrl: false });
      }
    } catch (err) {
      console.error("Failed to load challenge summary:", err);
      renderErrorScreen(t("challenge.error_expired"), "challenge.error_expired");
    }
  },

  /**
   * Start or resume a player challenge session.
   * @param {string} playerName
   * @param {string|null} [preferredColor=null]
   * @param {Function} onLoadRound Callback to load a round index
   * @param {Function} onShowSummary Callback to show summary
   */
  async start(playerName, preferredColor = null, onLoadRound = null, onShowSummary = null) {
    try {
      const payload = { player_name: playerName };
      if (preferredColor) {
        payload.player_color = preferredColor;
      }

      const res = await api(`/api/challenge/${encodeURIComponent(challengeSession.challengeData.capability_token)}/start`, {
        method: "POST",
        body: JSON.stringify(payload),
      });

      challengeSession.sessionToken = res.session_token;
      challengeSession.sessionPlayerName = res.player_name;
      challengeSession.totalRounds = res.total_rounds;

      if (res.participants && res.participants.length > 0) {
        state.players = res.participants;
      } else if (!state.players || !state.players.includes(res.player_name)) {
        state.players = [res.player_name];
      }

      const activeColor = res.player_color || preferredColor || playerColor(res.player_name);
      registerPlayerColor(res.player_name, activeColor);

      // Persist session into tab-scoped sessionStorage and player-indexed localStorage
      challengeSession.saveSession(challengeSession.challengeData.capability_token, {
        token: challengeSession.sessionToken,
        matchId: res.match_id,
        playerName: challengeSession.sessionPlayerName,
        playerColor: activeColor,
      });

      if (res.is_resumed && res.current_round >= res.total_rounds) {
        if (onShowSummary) onShowSummary();
      } else if (res.is_resumed && res.current_round > 0) {
        if (onLoadRound) onLoadRound(res.current_round);
      } else {
        if (onLoadRound) onLoadRound(0);
      }
    } catch (err) {
      if (err.status === 409) {
        if (onShowSummary) onShowSummary();
        return;
      }
      if (err.status === 404 || String(err.message || "").toLowerCase().includes("not found") || String(err.message || "").toLowerCase().includes("expired")) {
        renderErrorScreen(t("challenge.error_expired"), "challenge.error_expired");
        return;
      }
      showAlert(`${t("challenge.start_error")}: ${err.message || err}`);
    }
  },

  /**
   * Load and render question for round N.
   * @param {number} roundIndex
   * @param {Function} [onShowSummary]
   */
  async loadRound(roundIndex, onShowSummary = null) {
    challengeSession.stopPolling();
    challengeSession.cleanupMaps();

    challengeSession.currentRoundIndex = roundIndex;
    resetTimerBar();
    state.guessedLatLng = null;
    state.timedOut = false;
    state.submitting = false;

    try {
      const question = await api(
        `/api/challenge/${encodeURIComponent(challengeSession.challengeData.capability_token)}/question/${roundIndex}`,
        {
          headers: {
            "X-Player-Token": challengeSession.sessionToken,
          },
        }
      );

      question.player_name = challengeSession.sessionPlayerName;
      state.currentQuestion = question;
      state.gameMode = question.game_mode || challengeSession.challengeData.game_mode || "pinpoint";
      state.mapBounds = question.map_bounds || challengeSession.challengeData.map_bounds || null;

      this.renderQuestionScreen(question);
    } catch (err) {
      if (err.status === 409) {
        if (onShowSummary) onShowSummary();
        return;
      }
      if (err.status === 404 || String(err.message || "").toLowerCase().includes("not found") || String(err.message || "").toLowerCase().includes("expired")) {
        renderErrorScreen(t("challenge.error_expired"), "challenge.error_expired");
        return;
      }
      console.error("Failed to load challenge question:", err);
      showAlert(err.message || "Failed to load question");
    }
  },

  /**
   * Render question screen using existing game mode UI.
   * @param {object} question
   */
  renderQuestionScreen(question) {
    state.currentScreen = "guessing";
    state.lastReveal = null;
    challengeSession.lastRoundResult = null;
    showCard(el.gameCard);
    if (el.gameRestartBtn) el.gameRestartBtn.classList.add("hidden");
    if (el.guessingUi) el.guessingUi.classList.remove("hidden");
    if (el.revealUi) el.revealUi.classList.add("hidden");
    if (el.passOverlay) el.passOverlay.classList.add("hidden");

    // Standard round metadata banner
    if (el.roundMeta) {
      renderRoundMeta(el.roundMeta, {
        roundNum: challengeSession.currentRoundIndex + 1,
        totalRounds: question.total_rounds || challengeSession.totalRounds,
        playerNum: 1,
        totalPlayers: 1,
        playerName: challengeSession.sessionPlayerName,
        isReveal: false,
        showHelp: state.gameMode === "album_shuffle",
        onHelpClick: () => {
          getActiveMode().openHelp?.(question);
        },
      });
    }

    const activeMode = getActiveMode();
    activeMode.mount(el.guessingUi, challengeSession.challengeData);
    activeMode.renderQuestion(question);
    activeMode.onReady(question);
    activeMode.setDisabled(false);

    if (el.submitAnswer) {
      el.submitAnswer.textContent = t("game.submit_btn");
      el.submitAnswer.onclick = null;
    }
    updateSubmitState();

    // Start countdown timer
    challengeSession.questionStartTime = performance.now();
    startTimer(
      question.round_length || challengeSession.challengeData.round_length,
      getActiveMode,
      null
    );

    window.scrollTo({ top: 0, behavior: "smooth" });
  },

  /**
   * Submit answer and transition to personal reveal.
   * @param {boolean} fromTimeout
   * @param {Function} [onPersonalReveal] Callback when answer succeeds
   */
  async submitAnswer(fromTimeout = false, onPersonalReveal = null) {
    if (state.submitting || !state.currentQuestion) return;
    state.submitting = true;
    updateSubmitState();
    clearTimer();
    playSubmitTone();

    const elapsedSeconds = Math.max(0.1, (performance.now() - (challengeSession.questionStartTime || performance.now())) / 1000);
    const activeMode = getActiveMode();
    const guessPayload = activeMode.buildAnswerPayload(state.currentQuestion, fromTimeout || state.timedOut);

    const body = {
      round_index: challengeSession.currentRoundIndex,
      guessed_latitude: guessPayload.guessed_latitude ?? null,
      guessed_longitude: guessPayload.guessed_longitude ?? null,
      guessed_year: guessPayload.guessed_year ?? null,
      guessed_month: guessPayload.guessed_month ?? null,
      album_shuffle_answers: guessPayload.album_shuffle_answers ?? null,
      time_taken_seconds: elapsedSeconds,
      timed_out: fromTimeout || state.timedOut || Boolean(guessPayload.timed_out),
    };

    try {
      const result = await api(
        `/api/challenge/${encodeURIComponent(challengeSession.challengeData.capability_token)}/answer`,
        {
          method: "POST",
          headers: {
            "X-Player-Token": challengeSession.sessionToken,
          },
          body: JSON.stringify(body),
        }
      );

      if (onPersonalReveal) {
        onPersonalReveal(result, challengeSession.currentRoundIndex);
      }
    } catch (err) {
      console.error("Failed to submit challenge answer:", err);
      if (err.status === 404 || String(err.message || "").toLowerCase().includes("not found") || String(err.message || "").toLowerCase().includes("expired")) {
        renderErrorScreen(t("challenge.error_expired"), "challenge.error_expired");
        return;
      }
      showAlert(err.message || "Failed to submit answer");
    } finally {
      state.submitting = false;
      updateSubmitState();
    }
  },
};

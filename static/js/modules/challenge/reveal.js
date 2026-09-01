/**
 * Challenge Round Reveal & Social Polling Controller.
 *
 * Displays player's personal answer and runs 3-second live polling to drop
 * newly submitted opponents' pins dynamically into the Leaflet map and score table.
 */

import { api } from "../api.js";
import { state, el } from "../state.js";
import { t } from "../i18n.js";
import { showCard } from "../screens/common.js";
import { registerPlayerColor } from "../formatters.js";
import { updateSubmitState } from "../maps.js";
import { getActiveMode } from "../modes/index.js";
import { challengeSession, POLL_INTERVAL_MS } from "./session.js";

export const challengeReveal = {
  /**
   * Round-by-round Reveal Screen in Challenge Mode.
   * Shows the player their own answer vs the true answer immediately,
   * while starting 3-second social polling to dynamically drop friends' pins
   * and update the round score table as friends submit.
   * @param {object} result Answer result from API
   * @param {number} roundIndex Zero-based round index
   * @param {Function} [onNextRound] Callback when next round button is clicked
   */
  renderPersonalReveal(result, roundIndex, onNextRound = null) {
    state.currentScreen = "reveal";
    challengeSession.lastRoundResult = result;
    challengeSession.lastRoundIndex = roundIndex;
    showCard(el.gameCard);
    if (el.revealRestartBtn) el.revealRestartBtn.classList.add("hidden");
    if (el.guessingUi) el.guessingUi.classList.add("hidden");
    if (el.revealUi) el.revealUi.classList.remove("hidden");

    challengeSession.placedPinIds = new Set([`player_${challengeSession.sessionPlayerName}`]);

    const formattedReveal = {
      round_number: roundIndex + 1,
      total_rounds: challengeSession.totalRounds,
      location_mode: challengeSession.challengeData.location_mode !== false,
      date_mode: challengeSession.challengeData.date_mode !== false,
      game_mode: result.game_mode || challengeSession.challengeData.game_mode,
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
          player_name: challengeSession.sessionPlayerName,
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

    challengeSession.currentRevealData = formattedReveal;
    state.lastReveal = formattedReveal;

    const activeMode = getActiveMode();
    activeMode.renderReveal(el.revealUi, formattedReveal);

    if (el.nextRound) {
      el.nextRound.textContent = result.is_game_over ? t("reveal.see_results_btn") : t("reveal.next_round_btn");
      el.nextRound.onclick = onNextRound || null;
    }
    updateSubmitState();

    // Start 3-second social polling to auto-update friends' answers live on this screen
    this.startPolling(roundIndex);
  },

  /**
   * Advance from round review directly to the next round or final invite screen.
   * @param {Function} onInvite Callback when game is over
   * @param {Function} onLoadRound Callback to load next round index
   */
  handleNextRound(onInvite, onLoadRound) {
    challengeSession.stopPolling();
    if (!challengeSession.lastRoundResult) return;
    const result = challengeSession.lastRoundResult;
    const roundIndex = challengeSession.lastRoundIndex;
    if (result.is_game_over) {
      if (onInvite) onInvite();
    } else {
      if (onLoadRound) onLoadRound(roundIndex + 1);
    }
  },

  /**
   * Start 3-second social polling for leaderboard and opponent round updates.
   * @param {number} roundIndex
   */
  startPolling(roundIndex) {
    challengeSession.stopPolling();

    const poll = async () => {
      if (document.hidden || !challengeSession.challengeData) return;
      try {
        const data = await api(
          `/api/challenge/${encodeURIComponent(challengeSession.challengeData.capability_token)}/leaderboard`,
          {
            headers: {
              "X-Player-Token": challengeSession.sessionToken,
            },
          }
        );
        challengeSession.cachedLeaderboardData = data;
        this.updateRoundReveal(data, roundIndex);
      } catch (err) {
        console.warn("Challenge polling error:", err);
      }
    };

    poll();
    challengeSession.pollingInterval = setInterval(poll, POLL_INTERVAL_MS);
  },

  /**
   * Dynamically update round review map and table as friends submit their answers for roundIndex.
   * @param {object} leaderboardData
   * @param {number} roundIndex
   */
  updateRoundReveal(leaderboardData, roundIndex) {
    if (state.currentScreen !== "reveal" || !challengeSession.currentRevealData) {
      return;
    }

    if (leaderboardData.leaderboard) {
      const participantNames = leaderboardData.leaderboard.map((p) => p.player_name);
      if (participantNames.length > 0) {
        state.players = participantNames;
      }
      leaderboardData.leaderboard.forEach((p) => {
        if (p.player_color) {
          registerPlayerColor(p.player_name, p.player_color);
        }
      });
    }

    const currentGuesses = (leaderboardData.round_guesses || []).filter((g) => g.round_index === roundIndex);
    const existingNames = new Set(challengeSession.currentRevealData.results.map((r) => r.player_name));
    const newOpponents = [];
    const updatedResults = [...challengeSession.currentRevealData.results];

    currentGuesses.forEach((guess) => {
      if (guess.player_name !== challengeSession.sessionPlayerName) {
        const pinKey = `player_${guess.player_name}`;
        const opponentResult = {
          player_name: guess.player_name,
          guessed_latitude: guess.guessed_latitude,
          guessed_longitude: guess.guessed_longitude,
          guessed_year: guess.guessed_year,
          guessed_month: guess.guessed_month,
          location_score: guess.location_points,
          date_score: guess.date_points,
          round_score: guess.round_score,
          total_score: (leaderboardData.leaderboard?.find((p) => p.player_name === guess.player_name)?.total_score) ?? guess.round_score,
          distance_km: guess.distance_km,
          date_diff_days: guess.date_diff_days,
          timed_out: guess.timed_out || false,
          album_shuffle_guesses: guess.album_shuffle_guesses || null,
        };

        if (!existingNames.has(guess.player_name)) {
          existingNames.add(guess.player_name);
          updatedResults.push(opponentResult);
          newOpponents.push(opponentResult);
          challengeSession.placedPinIds.add(pinKey);
        }
      }
    });

    if (newOpponents.length > 0) {
      challengeSession.currentRevealData.results = updatedResults;
      const activeMode = getActiveMode();
      if (typeof activeMode.addOpponentReveal === "function") {
        activeMode.addOpponentReveal(el.revealUi, challengeSession.currentRevealData, newOpponents);
      } else {
        activeMode.renderReveal(el.revealUi, challengeSession.currentRevealData);
      }
    }
  },
};

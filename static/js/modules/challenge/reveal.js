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
import { registerPlayerColor, playerColor, playerInitial } from "../formatters.js";
import { updateSubmitState } from "../maps.js";
import { getActiveMode } from "../modes/index.js";
import { challengeSession, POLL_INTERVAL_MS } from "./session.js";
import { showActivityToast } from "../components/activity_toast.js";

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
    if (el.leaderboardCard) {
      el.leaderboardCard.classList.add("hidden");
    }
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

    // Ensure live social status pill in reveal-actual-row
    this.ensureLivePill(roundIndex);

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
    let isInitial = true;

    const poll = async () => {
      if (!challengeSession.challengeData) return;
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
        this.updateRoundReveal(data, roundIndex, { isInitial });
        isInitial = false;
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
  updateRoundReveal(leaderboardData, roundIndex, { isInitial = false } = {}) {
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

    // Defensively ensure local player's album_shuffle_guesses is populated if missing
    const myResult = updatedResults.find((r) => r.player_name === challengeSession.sessionPlayerName);
    if (myResult && (!myResult.album_shuffle_guesses || myResult.album_shuffle_guesses.length === 0)) {
      const myGuesses = currentGuesses.filter((g) => g.player_name === challengeSession.sessionPlayerName);
      if (myGuesses.length > 0 && myGuesses.some((g) => g.asset_id)) {
        myResult.album_shuffle_guesses = myGuesses
          .filter((g) => g.asset_id)
          .map((g) => ({
            photo_id: g.asset_id,
            assigned_pin_id: g.assigned_pin_id || null,
            assigned_timeline_index:
              g.assigned_timeline_index !== null && g.assigned_timeline_index !== undefined
                ? g.assigned_timeline_index
                : null,
          }));
      }
    }

    const guessesByPlayer = new Map();
    currentGuesses.forEach((guess) => {
      if (guess.player_name === challengeSession.sessionPlayerName) return;
      if (!guessesByPlayer.has(guess.player_name)) {
        guessesByPlayer.set(guess.player_name, []);
      }
      guessesByPlayer.get(guess.player_name).push(guess);
    });

    guessesByPlayer.forEach((playerGuesses, playerName) => {
      if (existingNames.has(playerName)) return;

      const pinKey = `player_${playerName}`;
      const isAlbumShuffle =
        leaderboardData.game_mode === "album_shuffle" ||
        playerGuesses.some(
          (g) =>
            g.game_mode === "album_shuffle" ||
            Boolean(g.asset_id) ||
            g.assigned_pin_id !== undefined ||
            g.assigned_timeline_index !== undefined
        );

      let opponentResult;
      if (isAlbumShuffle) {
        const totalRoundScore = playerGuesses.reduce((sum, g) => sum + (g.round_score || 0), 0);
        const totalLocationScore = playerGuesses.reduce((sum, g) => sum + (g.location_points || 0), 0);
        const totalDateScore = playerGuesses.reduce((sum, g) => sum + (g.date_points || 0), 0);
        const albumShuffleGuesses = playerGuesses
          .filter((g) => g.asset_id)
          .map((g) => ({
            photo_id: g.asset_id,
            assigned_pin_id: g.assigned_pin_id || null,
            assigned_timeline_index:
              g.assigned_timeline_index !== null && g.assigned_timeline_index !== undefined
                ? g.assigned_timeline_index
                : null,
          }));

        opponentResult = {
          player_name: playerName,
          location_score: totalLocationScore,
          date_score: totalDateScore,
          round_score: totalRoundScore,
          total_score:
            leaderboardData.leaderboard?.find((p) => p.player_name === playerName)?.total_score ?? totalRoundScore,
          timed_out: playerGuesses.some((g) => g.timed_out),
          album_shuffle_guesses: albumShuffleGuesses.length > 0 ? albumShuffleGuesses : null,
        };
      } else {
        const guess = playerGuesses[0];
        opponentResult = {
          player_name: playerName,
          guessed_latitude: guess.guessed_latitude,
          guessed_longitude: guess.guessed_longitude,
          guessed_year: guess.guessed_year,
          guessed_month: guess.guessed_month,
          location_score: guess.location_points,
          date_score: guess.date_points,
          round_score: guess.round_score,
          total_score:
            leaderboardData.leaderboard?.find((p) => p.player_name === playerName)?.total_score ?? guess.round_score,
          distance_km: guess.distance_km,
          date_diff_days: guess.date_diff_days,
          timed_out: guess.timed_out || false,
          album_shuffle_guesses: null,
        };
      }

      existingNames.add(playerName);
      updatedResults.push(opponentResult);
      newOpponents.push(opponentResult);
      challengeSession.placedPinIds.add(pinKey);
    });

    if (newOpponents.length > 0) {
      challengeSession.currentRevealData.results = updatedResults;
      const activeMode = getActiveMode();
      if (typeof activeMode.addOpponentReveal === "function") {
        activeMode.addOpponentReveal(el.revealUi, challengeSession.currentRevealData, newOpponents);
      } else {
        activeMode.renderReveal(el.revealUi, challengeSession.currentRevealData);
      }

      // Only notify and flash for live arrivals while on this screen (not past submissions during initial hydration)
      if (!isInitial) {
        // 1. Flash highlight table rows for newly arrived opponents (Option 2)
        this.flashOpponentRows(newOpponents);

        // 2. Toast notification for each new opponent answer (Option 1)
        newOpponents.forEach((opponent) => {
          showActivityToast({
            icon: "🎯",
            playerName: opponent.player_name,
            score: opponent.round_score,
            title: t("challenge.player_submitted_round", opponent.player_name, roundIndex + 1, opponent.round_score),
          });
        });
      }
    }

    // 3. Live status pill update (Option 3)
    this.updateLivePill(leaderboardData, roundIndex, isInitial);
  },

  /**
   * Ensure the ambient live status pill is rendered inside the reveal header.
   * @param {number} roundIndex
   */
  ensureLivePill(roundIndex) {
    const actualRow = el.revealUi?.querySelector(".reveal-actual-row");
    if (!actualRow) return;

    let pill = document.getElementById("challenge-round-live-pill");
    if (!pill) {
      pill = document.createElement("span");
      pill.id = "challenge-round-live-pill";
      pill.className = "challenge-live-pill";
      pill.innerHTML = `
        <span class="live-poll-dot" aria-hidden="true"></span>
        <span id="challenge-round-live-status"></span>
      `;
      const reportBtn = actualRow.querySelector("#reveal-report-btn");
      if (reportBtn) {
        actualRow.insertBefore(pill, reportBtn);
      } else {
        actualRow.appendChild(pill);
      }
    }
    this.updateLivePill(challengeSession.cachedLeaderboardData, roundIndex, true);
  },

  /**
   * Update the ambient live status pill tally.
   * @param {object} leaderboardData
   * @param {number} roundIndex
   * @param {boolean} [isInitial=false]
   */
  updateLivePill(leaderboardData, roundIndex, isInitial = false) {
    const statusEl = document.getElementById("challenge-round-live-status");
    const pill = document.getElementById("challenge-round-live-pill");
    if (!statusEl || !pill) return;

    const participants = leaderboardData?.leaderboard || challengeSession.challengeData?.participants || [];
    const totalCount = Math.max(participants.length, 1);
    const answeredCount =
      (leaderboardData?.round_guesses || []).filter((g) => g.round_index === roundIndex).length ||
      challengeSession.currentRevealData?.results?.length ||
      1;

    const prevTally = statusEl.textContent;
    const newTally = t("challenge.live_answered_tally", answeredCount, totalCount);
    statusEl.textContent = newTally;

    if (!isInitial && prevTally && prevTally !== newTally) {
      pill.classList.remove("bump");
      void pill.offsetWidth;
      pill.classList.add("bump");
    }
  },

  /**
   * Apply animated arrival glow to table rows belonging to newly detected opponents.
   * @param {Array} newOpponents
   */
  flashOpponentRows(newOpponents) {
    if (!newOpponents || newOpponents.length === 0) return;
    const newNames = new Set(newOpponents.map((o) => o.player_name));
    const tableBody = el.revealUi?.querySelector("#reveal-table tbody") || document.querySelector("#reveal-table tbody");
    if (!tableBody) return;

    Array.from(tableBody.children).forEach((tr) => {
      const text = tr.textContent;
      for (const name of newNames) {
        if (text.includes(name)) {
          const color = playerColor(name);
          tr.classList.remove("row-arrival-flash");
          tr.style.setProperty("--player-accent", color);
          tr.style.setProperty("--player-accent-alpha", `${color}33`);
          void tr.offsetWidth;
          tr.classList.add("row-arrival-flash");
        }
      }
    });
  },
};

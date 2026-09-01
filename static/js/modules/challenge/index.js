/**
 * Challenge Mode Controller for Immich Quiz (Unified Facade).
 *
 * Assembles challenge sub-modules (session, landing, game, reveal, intermission, summary)
 * into a single cohesive facade matching the existing challenge singleton API.
 */

import { challengeSession } from "./session.js";
import { renderLandingScreen, renderErrorScreen, refreshLanguage } from "./landing.js";
import { challengeGame } from "./game.js";
import { challengeReveal } from "./reveal.js";
import { challengeIntermission } from "./intermission.js";
import { challengeSummary } from "./summary.js";

export { challengeSession } from "./session.js";
export { renderLandingScreen, renderErrorScreen, refreshLanguage } from "./landing.js";
export { challengeGame } from "./game.js";
export { challengeReveal } from "./reveal.js";
export { challengeIntermission } from "./intermission.js";
export { challengeSummary } from "./summary.js";

export const challenge = {

  /**
   * Check if challenge mode is currently active (data and session initialized).
   * @returns {boolean}
   */
  isActive() {
    return challengeSession.isActive();
  },

  /**
   * Check if challenge gameplay is active on a question or reveal.
   * @returns {boolean}
   */
  isGameActive() {
    return challengeSession.isGameActive();
  },

  /**
   * Dynamically refresh challenge screens whenever language changes.
   */
  refreshLanguage() {
    refreshLanguage(
      (name, color) => this.start(name, color),
      () => this.showGrandReveal()
    );
  },

  /**
   * Reset all challenge state when leaving challenge mode.
   */
  reset() {
    challengeSession.reset();
  },

  /**
   * Stop any active polling interval.
   */
  stopPolling() {
    challengeSession.stopPolling();
  },

  /**
   * Cleanup any active Leaflet maps.
   */
  cleanupMaps() {
    challengeSession.cleanupMaps();
  },

  /**
   * Initialize a challenge from a capability token in the URL.
   * @param {string} capabilityToken
   */
  async init(capabilityToken) {
    return challengeGame.init(
      capabilityToken,
      (name, color) => this.start(name, color),
      () => this.showGrandReveal()
    );
  },

  /**
   * Initialize and display challenge summary directly (spectator/shared link or reload).
   * @param {string} capabilityToken
   */
  async initSummary(capabilityToken) {
    return challengeGame.initSummary(
      capabilityToken,
      (opts) => this.showGrandReveal(opts)
    );
  },

  /**
   * Render landing / entry screen with resume detection.
   * @param {object} data
   * @param {object|null} savedSession
   */
  renderLandingScreen(data, savedSession) {
    return renderLandingScreen(
      data,
      savedSession,
      (name, color) => this.start(name, color),
      () => this.showGrandReveal()
    );
  },

  /**
   * Render error screen for invalid or expired challenges.
   * @param {string} message
   * @param {string} [i18nKey]
   */
  renderErrorScreen(message, i18nKey = null) {
    return renderErrorScreen(message, i18nKey);
  },

  /**
   * Start or resume a player challenge session.
   * @param {string} playerName
   * @param {string|null} [preferredColor=null]
   */
  async start(playerName, preferredColor = null) {
    return challengeGame.start(
      playerName,
      preferredColor,
      (roundIndex) => this.loadRound(roundIndex),
      () => this.showGrandReveal()
    );
  },

  /**
   * Load and render question for round N.
   * @param {number} roundIndex
   */
  async loadRound(roundIndex) {
    return challengeGame.loadRound(
      roundIndex,
      () => this.showGrandReveal()
    );
  },

  /**
   * Render question screen using existing game mode UI.
   * @param {object} question
   */
  renderQuestionScreen(question) {
    return challengeGame.renderQuestionScreen(question);
  },

  /**
   * Submit answer and transition to personal reveal.
   * @param {boolean} fromTimeout
   */
  async submitAnswer(fromTimeout = false) {
    return challengeGame.submitAnswer(
      fromTimeout,
      (result, roundIndex) => this.renderPersonalReveal(result, roundIndex)
    );
  },

  /**
   * Round-by-round Reveal Screen in Challenge Mode.
   * @param {object} result
   * @param {number} roundIndex
   */
  renderPersonalReveal(result, roundIndex) {
    return challengeReveal.renderPersonalReveal(
      result,
      roundIndex,
      () => this.handleNextRound()
    );
  },

  /**
   * Advance from round review directly to the next round or final invite screen.
   */
  handleNextRound() {
    return challengeReveal.handleNextRound(
      () => this.renderInviteFriendsScreen(),
      (nextRoundIdx) => this.loadRound(nextRoundIdx)
    );
  },

  /**
   * Start 3-second social polling for leaderboard and opponent round updates.
   * @param {number} roundIndex
   */
  startPolling(roundIndex) {
    return challengeReveal.startPolling(roundIndex);
  },

  /**
   * Dynamically update round review map and table as friends submit their answers for roundIndex.
   * @param {object} leaderboardData
   * @param {number} roundIndex
   */
  updateRoundReveal(leaderboardData, roundIndex) {
    return challengeReveal.updateRoundReveal(leaderboardData, roundIndex);
  },

  /**
   * "Invite Friends" intermission shown after the final round.
   */
  renderInviteFriendsScreen() {
    return challengeIntermission.renderInviteFriendsScreen(
      () => this.showGrandReveal()
    );
  },

  /**
   * Poll for finished player count on invite screen.
   */
  startFinisherPolling() {
    return challengeIntermission.startFinisherPolling();
  },

  /**
   * Grand Reveal Summary Screen at the end of the challenge.
   * @param {object} [options]
   */
  async showGrandReveal(options = {}) {
    return challengeSummary.showGrandReveal(options);
  },

  /**
   * Render a specific round inside the Grand Reveal Carousel with scatter map and date comparisons.
   * @param {object} data
   * @param {number} roundIdx
   */
  renderCarouselRound(data, roundIdx) {
    return challengeSummary.renderCarouselRound(data, roundIdx);
  },

  /**
   * Build aggregated player statistics from round guesses for awards calculation.
   * @param {object} leaderboardData
   * @returns {Record<string, object>}
   */
  buildPlayerStats(leaderboardData) {
    return challengeSummary.buildPlayerStats(leaderboardData);
  },
};

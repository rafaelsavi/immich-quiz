/**
 * Challenge Mode Session & State Store.
 *
 * Manages capability tokens, player session tokens, active game state,
 * polling intervals, and Leaflet map instances for challenge gameplay.
 */

import { state, el } from "../state.js";
import { unregisterActiveMap } from "../maps.js";

export const POLL_INTERVAL_MS = 3000;
export const SESSION_STORAGE_PREFIX = "immich_challenge_";

export const challengeSession = {
  challengeData: null,
  sessionToken: null,
  sessionPlayerName: null,
  currentRoundIndex: 0,
  totalRounds: 0,
  questionStartTime: null,
  pollingInterval: null,
  lastRoundResult: null,
  lastRoundIndex: 0,
  currentRevealData: null,
  cachedLeaderboardData: null,
  currentError: null,

  // Map references
  intermissionMap: null,
  intermissionMarkers: {},
  intermissionSpiderLines: {},
  intermissionTrueCoords: {},
  placedPinIds: new Set(),

  carouselMap: null,
  carouselMarkers: {},
  carouselSpiderLines: {},
  carouselTrueCoords: {},
  carouselRoundIndex: 0,
  challengeJourneyMap: null,

  /**
   * Get localStorage key for persisting session token per challenge.
   * @param {string} capabilityToken
   * @returns {string}
   */
  sessionKey(capabilityToken) {
    return `${SESSION_STORAGE_PREFIX}${capabilityToken}`;
  },

  /**
   * Check if challenge mode is currently active (data and session initialized).
   * @returns {boolean}
   */
  isActive() {
    return Boolean(this.challengeData && this.sessionToken);
  },

  /**
   * Check if challenge gameplay is active on a question or reveal.
   * @returns {boolean}
   */
  isGameActive() {
    return Boolean(this.challengeData && this.sessionToken && state.currentQuestion);
  },

  /**
   * Stop any active polling interval.
   */
  stopPolling() {
    if (this.pollingInterval) {
      clearInterval(this.pollingInterval);
      this.pollingInterval = null;
    }
  },

  /**
   * Cleanup any active Leaflet maps.
   */
  cleanupMaps() {
    if (this.intermissionMap) {
      try {
        unregisterActiveMap(this.intermissionMap);
        this.intermissionMap.remove();
      } catch (_) {}
      this.intermissionMap = null;
    }
    if (this.carouselMap) {
      try {
        unregisterActiveMap(this.carouselMap);
        this.carouselMap.remove();
      } catch (_) {}
      this.carouselMap = null;
    }
    if (this.challengeJourneyMap) {
      try {
        unregisterActiveMap(this.challengeJourneyMap);
        this.challengeJourneyMap.remove();
      } catch (_) {}
      this.challengeJourneyMap = null;
    }
  },

  /**
   * Reset all challenge state when leaving challenge mode.
   */
  reset() {
    this.stopPolling();
    this.cleanupMaps();
    if (el.gameRestartBtn) el.gameRestartBtn.classList.remove("hidden");
    if (el.revealRestartBtn) el.revealRestartBtn.classList.remove("hidden");
    this.challengeData = null;
    this.sessionToken = null;
    this.sessionPlayerName = null;
    this.currentRoundIndex = 0;
    this.totalRounds = 0;
    this.questionStartTime = null;
    this.lastRoundResult = null;
    this.lastRoundIndex = 0;
    this.currentRevealData = null;
    this.cachedLeaderboardData = null;
    this.currentError = null;
    this.placedPinIds.clear();
  },
};

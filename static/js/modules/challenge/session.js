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
   * Get storage key for challenge session persistence.
   * @param {string} capabilityToken
   * @returns {string}
   */
  sessionKey(capabilityToken) {
    return `${SESSION_STORAGE_PREFIX}${capabilityToken}`;
  },

  /**
   * Persist active player session into sessionStorage (tab-scoped) and localStorage (player dictionary).
   * @param {string} capabilityToken
   * @param {object} sessionData { token, matchId, playerName, playerColor }
   */
  saveSession(capabilityToken, sessionData) {
    if (!capabilityToken || !sessionData) return;
    const key = this.sessionKey(capabilityToken);

    // 1. Save in sessionStorage for strict current-tab isolation
    try {
      sessionStorage.setItem(key, JSON.stringify(sessionData));
    } catch (e) {
      console.warn("Failed to persist challenge session to sessionStorage:", e);
    }

    // 2. Save in localStorage under player-indexed dictionary for multi-player device persistence
    try {
      let store = { lastPlayer: null, players: {} };
      const raw = localStorage.getItem(key);
      if (raw) {
        try {
          const parsed = JSON.parse(raw);
          if (parsed && typeof parsed === "object") {
            if (parsed.players && typeof parsed.players === "object") {
              store = parsed;
            } else if (parsed.playerName && parsed.token) {
              // Migrate legacy single-session format
              store.players[parsed.playerName] = parsed;
              store.lastPlayer = parsed.playerName;
            }
          }
        } catch (_) {}
      }

      if (sessionData.playerName) {
        store.players[sessionData.playerName] = sessionData;
        store.lastPlayer = sessionData.playerName;
      }
      localStorage.setItem(key, JSON.stringify(store));
    } catch (e) {
      console.warn("Failed to persist challenge session to localStorage:", e);
    }
  },

  /**
   * Load session for challenge, prioritizing the current tab's sessionStorage first.
   * If sessionStorage is empty, falls back to localStorage (e.g. fresh tab resume).
   * @param {string} capabilityToken
   * @param {object} [options]
   * @param {boolean} [options.tabOnly=false] Only check sessionStorage (e.g. for spectator view)
   * @param {string|null} [options.preferredPlayerName=null]
   * @returns {object|null} { token, matchId, playerName, playerColor }
   */
  loadSession(capabilityToken, { tabOnly = false, preferredPlayerName = null } = {}) {
    if (!capabilityToken) return null;
    const key = this.sessionKey(capabilityToken);

    // 1. Always prioritize current tab's sessionStorage (prevents cross-tab leaks)
    try {
      const tabRaw = sessionStorage.getItem(key);
      if (tabRaw) {
        const tabSession = JSON.parse(tabRaw);
        if (tabSession && tabSession.token) {
          return tabSession;
        }
      }
    } catch (_) {}

    if (tabOnly) return null;

    // 2. Fall back to localStorage dictionary (e.g. opening fresh tab after browser restart)
    try {
      const localRaw = localStorage.getItem(key);
      if (!localRaw) return null;
      const parsed = JSON.parse(localRaw);
      if (!parsed || typeof parsed !== "object") return null;

      // Handle dictionary format { lastPlayer, players: { ... } }
      if (parsed.players && typeof parsed.players === "object") {
        if (preferredPlayerName && parsed.players[preferredPlayerName]) {
          return parsed.players[preferredPlayerName];
        }
        if (parsed.lastPlayer && parsed.players[parsed.lastPlayer]) {
          return parsed.players[parsed.lastPlayer];
        }
        const playerNames = Object.keys(parsed.players);
        if (playerNames.length > 0) {
          return parsed.players[playerNames[playerNames.length - 1]];
        }
      }

      // Handle legacy single-session format { token, playerName, ... }
      if (parsed.token && parsed.playerName) {
        return parsed;
      }
    } catch (_) {}

    return null;
  },

  /**
   * Clear session for challenge from sessionStorage (and optionally localStorage).
   * @param {string} capabilityToken
   * @param {string|null} [playerName=null]
   */
  clearSession(capabilityToken, playerName = null) {
    if (!capabilityToken) return;
    const key = this.sessionKey(capabilityToken);
    try {
      sessionStorage.removeItem(key);
    } catch (_) {}

    if (playerName) {
      try {
        const localRaw = localStorage.getItem(key);
        if (localRaw) {
          const parsed = JSON.parse(localRaw);
          if (parsed?.players?.[playerName]) {
            delete parsed.players[playerName];
            if (parsed.lastPlayer === playerName) {
              const remaining = Object.keys(parsed.players);
              parsed.lastPlayer = remaining.length > 0 ? remaining[remaining.length - 1] : null;
            }
            localStorage.setItem(key, JSON.stringify(parsed));
          }
        }
      } catch (_) {}
    }
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

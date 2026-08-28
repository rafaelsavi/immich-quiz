function getInitialLanguagePreference() {
  try {
    const stored = localStorage.getItem("immich_quiz_language");
    if (stored) {
      const s = String(stored).trim().toLowerCase().replace("_", "-");
      if (s.startsWith("pt")) return "pt-BR";
      if (s.startsWith("en")) return "en-US";
    }
  } catch (_) {}
  if (typeof navigator !== "undefined") {
    const browserLang = navigator.language || (navigator.languages && navigator.languages[0]);
    if (browserLang) {
      const s = String(browserLang).trim().toLowerCase().replace("_", "-");
      if (s.startsWith("pt")) return "pt-BR";
    }
  }
  return "en-US";
}

export const state = {
  matchId: null,
  gameMode: "pinpoint",
  players: [],
  language: getInitialLanguagePreference(),
  audioEnabled: true,
  scoreMaxPoints: 100,
  lastMatchConfig: null,
  lastSummary: null,
  playedAssetIds: [],
  currentQuestion: null,
  guessedLatLng: null,
  mapBounds: null,
  filters: {
    albumMultiSelect: null,
    countryMultiSelect: null,
    cityMultiSelect: null,
    peopleMultiSelect: null,
    dateRangeSlider: null,
  },
  albumShuffleState: {
    selectedPhotoId: null,
    assignments: {}, // photoId -> { pinId: string|null, timelineIndex: number|null }
  },
  guessMap: null,
  revealMap: null,
  journeyMap: null,
  guessMarker: null,
  revealLayers: [],
  journeyLayers: [],
  roundHistory: [],
  revealAnimationTimeoutId: null,
  revealAnimationFrameId: null,
  timerRef: null,
  timedOut: false,
  submitting: false,
  startingMatch: false,
  matchFinished: false,
  justFinishedMatch: false,
  leaderboardRows: [],
  leaderboardSort: { key: "accuracy_pct", asc: false },
  timerTotalSeconds: 0,
  timerRemainingSeconds: 0,
  timerEndTimeMs: null,
  timerPaused: false,
  timerPausedRemainingMs: null,
  timerRafId: null,
  timerLastTickedSec: null,
  /** @type {Record<string, number>} Total perfect rounds per player in current match */
  perfectCounts: {},
  /** @type {Record<string, {totalDistanceKm: number, distanceCount: number, totalDateDiffDays: number, dateCount: number, perfectLocationCount: number, perfectDateCount: number, perfectRounds: number, timedOutCount: number, fastRoundCount: number, totalDurationSec: number}>} */
  playerStats: {},
  /** @type {"pass_device" | "guessing" | "reveal" | null} Currently active screen/overlay */
  currentScreen: null,
  /** @type {any} Last completed round reveal payload */
  lastReveal: null,
  /** @type {boolean} Whether the current player has clicked ready on pass overlay */
  passConfirmed: false,
};

export const el = {
  langToggleBtn: document.getElementById("lang-toggle-btn"),
  langIcon: document.getElementById("lang-icon"),
  audioToggleBtn: document.getElementById("audio-toggle-btn"),
  audioIcon: document.getElementById("audio-icon"),
  setupCard: document.getElementById("setup-card"),
  gameCard: document.getElementById("game-card"),
  summaryCard: document.getElementById("summary-card"),
  leaderboardCard: document.getElementById("leaderboard-card"),
  guessingUi: document.getElementById("guessing-ui"),
  revealUi: document.getElementById("reveal-ui"),
  setupForm: document.getElementById("setup-form"),
  setupSubmitBtn: document.getElementById("start-match-btn"),
  players: document.getElementById("players"),
  roundCount: document.getElementById("round-count"),
  roundLength: document.getElementById("round-length"),
  get goalLocation() {
    return document.getElementById("goal-location");
  },
  get goalDate() {
    return document.getElementById("goal-date");
  },
  libraryMultiSelect: document.getElementById("library-multi-select"),
  syncLibraryBtn: document.getElementById("sync-library-btn"),
  syncBtnLabel: document.getElementById("sync-btn-label"),
  albumMultiSelect: document.getElementById("album-multi-select"),
  includeSharedCheckbox: document.getElementById("include-shared-checkbox"),
  labelIncludeShared: document.getElementById("label-include-shared"),
  filtersAccordion: document.getElementById("filters-accordion"),
  filtersAccordionHeader: document.getElementById("filters-accordion-header"),
  filtersToggleBtn: document.getElementById("filters-toggle-btn"),
  filtersSummaryBadge: document.getElementById("filters-summary-badge"),
  filtersAccordionContent: document.getElementById("filters-accordion-content"),
  countryMultiSelect: document.getElementById("country-multi-select"),
  cityMultiSelect: document.getElementById("city-multi-select"),
  peopleMultiSelect: document.getElementById("people-multi-select"),
  peopleModeToggle: document.getElementById("people-mode-toggle"),
  resetFiltersBtn: document.getElementById("reset-filters-btn"),
  roundMeta: document.getElementById("round-meta"),
  passOverlay: document.getElementById("pass-overlay"),
  overlayTitle: document.getElementById("overlay-title"),
  overlaySubtitle: document.getElementById("overlay-subtitle"),
  readyBtn: document.getElementById("ready-btn"),
  get mediaFrame() {
    return document.getElementById("media-frame");
  },
  get quizImage() {
    return document.getElementById("quiz-image");
  },
  get quizImageFullscreen() {
    return document.getElementById("quiz-image-fullscreen");
  },
  get mediaPlaceholder() {
    return document.getElementById("media-placeholder");
  },
  get mapGuessWrap() {
    return document.getElementById("map-guess-wrap");
  },
  get guessMapShell() {
    return document.getElementById("guess-map-shell");
  },
  get guessMapFullscreen() {
    return document.getElementById("guess-map-fullscreen");
  },
  get dateGuessWrap() {
    return document.getElementById("date-guess-wrap");
  },
  get dateGuessYear() {
    return document.getElementById("date-guess-year");
  },
  get dateGuessMonth() {
    return document.getElementById("date-guess-month");
  },
  submitAnswer: document.getElementById("submit-answer"),
  timerLabel: document.getElementById("timer-label"),
  timerRemaining: document.getElementById("timer-remaining"),
  timerTrack: document.getElementById("timer-track"),
  timerFill: document.getElementById("timer-fill"),
  timeoutNotice: document.getElementById("timeout-notice"),
  revealActual: document.getElementById("reveal-actual"),
  revealLegend: document.getElementById("reveal-legend"),
  revealTableHead: document.querySelector("#reveal-table thead"),
  revealTableBody: document.querySelector("#reveal-table tbody"),
  revealMapShell: document.getElementById("reveal-map-shell"),
  revealMapHead: document.getElementById("reveal-map-head"),
  revealMapFullscreen: document.getElementById("reveal-map-fullscreen"),
  nextRound: document.getElementById("next-round"),
  summaryWinner: document.getElementById("summary-winner"),
  summaryMeta: document.getElementById("summary-meta"),
  summaryTableHead: document.querySelector("#summary-table thead"),
  summaryTableBody: document.querySelector("#summary-table tbody"),
  newMatch: document.getElementById("new-match"),
  shareSummaryBtn: document.getElementById("share-summary-btn"),
  journeyMapShell: document.getElementById("journey-map-shell"),
  journeyMapHead: document.getElementById("journey-map-head"),
  journeyMapFullscreen: document.getElementById("journey-map-fullscreen"),
  polaroidGallery: document.getElementById("polaroid-gallery"),
  gameRestartBtn: document.getElementById("game-restart-btn"),
  gameExitBtn: document.getElementById("game-exit-btn"),
  revealRestartBtn: document.getElementById("reveal-restart-btn"),
  revealExitBtn: document.getElementById("reveal-exit-btn"),
  refreshLeaderboard: document.getElementById("refresh-leaderboard"),
  leaderboardScopePill: document.getElementById("leaderboard-scope-pill"),
  leaderboardBody: document.querySelector("#leaderboard-table tbody"),
  leaderboardHead: document.querySelector("#leaderboard-table thead"),
  gameEndedCard: document.getElementById("game-ended-card"),
  gameEndedSummaryBtn: document.getElementById("game-ended-summary-btn"),
  gameEndedLobbyBtn: document.getElementById("game-ended-lobby-btn"),
};

const SESSION_STORAGE_KEY = "immich_quiz_active_match";

export function saveActiveMatchSession() {
  if (!state.matchId || state.matchFinished) {
    clearActiveMatchSession();
    return;
  }
  try {
    const payload = {
      v: 1,
      matchId: state.matchId,
      gameMode: state.gameMode,
      players: state.players,
      mapBounds: state.mapBounds,
      lastMatchConfig: state.lastMatchConfig,
      playedAssetIds: state.playedAssetIds,
      roundHistory: state.roundHistory,
      perfectCounts: state.perfectCounts,
      playerStats: state.playerStats,
      matchFinished: state.matchFinished,
      currentScreen: state.currentScreen ?? null,
      lastReveal: state.lastReveal ?? null,
      passConfirmed: Boolean(state.passConfirmed),
      activeQuestionId: state.currentQuestion?.question_id ?? null,
      activePlayerName: state.currentQuestion?.player_name ?? null,
      activeTurnNumber: state.currentQuestion?.turn_number ?? null,
      activePlayerRoundNumber: state.currentQuestion?.player_round_number ?? null,
      activePlayerNumber: state.currentQuestion?.player_number ?? null,
      timerEndTimeMs: typeof state.timerEndTimeMs === "number" ? state.timerEndTimeMs : null,
      timerTotalSeconds: typeof state.timerTotalSeconds === "number" ? state.timerTotalSeconds : null,
      savedAt: Date.now(),
    };
    sessionStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify(payload));
  } catch (err) {
    console.warn("Failed to persist match session:", err);
  }
}

export function clearActiveMatchSession() {
  try {
    sessionStorage.removeItem(SESSION_STORAGE_KEY);
  } catch (_) {}
}

export function loadActiveMatchSession() {
  try {
    const raw = sessionStorage.getItem(SESSION_STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (!parsed || parsed.matchFinished || !parsed.matchId) {
      clearActiveMatchSession();
      return null;
    }
    return parsed;
  } catch (_) {
    clearActiveMatchSession();
    return null;
  }
}

/**
 * Hydrate in-memory state from an active match session snapshot.
 * @param {object} session
 * @returns {boolean}
 */
export function restoreActiveMatchSession(session) {
  if (!session || !session.matchId) return false;
  state.matchId = session.matchId;
  state.players = session.players ?? [];
  state.gameMode = session.gameMode ?? "pinpoint";
  state.mapBounds = session.mapBounds ?? null;
  state.lastMatchConfig = session.lastMatchConfig ?? null;
  state.playedAssetIds = session.playedAssetIds ?? [];
  state.roundHistory = session.roundHistory ?? [];
  state.perfectCounts = session.perfectCounts ?? {};
  state.playerStats = session.playerStats ?? {};
  state.currentScreen = session.currentScreen ?? null;
  state.lastReveal = session.lastReveal ?? null;
  state.passConfirmed = Boolean(session.passConfirmed);
  state.matchFinished = false;
  return true;
}


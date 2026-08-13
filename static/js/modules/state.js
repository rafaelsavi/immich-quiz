function getInitialLanguagePreference() {
  try {
    const stored = localStorage.getItem("immich_quiz_language");
    if (stored === "PT" || stored === "EN") return stored;
  } catch (_) {}
  return "EN";
}

export const state = {
  matchId: null,
  gameMode: "pinpoint",
  players: [],
  language: getInitialLanguagePreference(),
  audioEnabled: true,
  scoreMaxPoints: 100,
  lastMatchConfig: null,
  lastReveal: null,
  lastSummary: null,
  playedAssetIds: [],
  currentQuestion: null,
  guessedLatLng: null,
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
  matchFinished: false,
  leaderboardRows: [],
  leaderboardSort: { key: "total_score", asc: false },
  timerTotalSeconds: 0,
  timerRemainingSeconds: 0,
  /** @type {Record<string, number>} Total perfect rounds per player in current match */
  perfectCounts: {},
  /** @type {Record<string, {totalDistanceKm: number, distanceCount: number, totalDateDiffDays: number, dateCount: number, perfectLocationCount: number, perfectDateCount: number, perfectRounds: number, timedOutCount: number, fastRoundCount: number, totalDurationSec: number}>} */
  playerStats: {},
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
  players: document.getElementById("players"),
  roundCount: document.getElementById("round-count"),
  roundLength: document.getElementById("round-length"),
  get goalLocation() {
    return document.getElementById("goal-location");
  },
  get goalDate() {
    return document.getElementById("goal-date");
  },
  library: document.getElementById("library"),
  album: document.getElementById("album"),
  get albumMultiSelect() { return document.getElementById("album-multi-select"); },
  get albumSelectTrigger() { return document.getElementById("album-select-trigger"); },
  get albumSelectValue() { return document.getElementById("album-select-value"); },
  get albumSelectClear() { return document.getElementById("album-select-clear"); },
  get albumSelectDropdown() { return document.getElementById("album-select-dropdown"); },
  get albumSearchInput() { return document.getElementById("album-search-input"); },
  get albumSearchClear() { return document.getElementById("album-search-clear"); },
  get albumSelectAll() { return document.getElementById("album-select-all"); },
  get albumDeselectAll() { return document.getElementById("album-deselect-all"); },
  get albumOptionsList() { return document.getElementById("album-options-list"); },
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
  leaderboardBody: document.querySelector("#leaderboard-table tbody"),
  leaderboardHead: document.querySelector("#leaderboard-table thead"),
};

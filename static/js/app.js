import {
  state,
  el,
  clearActiveMatchSession,
  loadActiveMatchSession,
  restoreActiveMatchSession,
} from "./modules/state.js";
import {
  navigate,
  initRouter,
  setNavigationGuard,
  RouteType,
  parseRoute,
} from "./modules/router.js";
import {
  t,
  translateError,
  showAlert,
  applyLanguage,
  getInitialLanguagePreference,
  updateLanguageUi,
  toggleLanguage,
  getLocale,
  normalizeLanguage,
} from "./modules/i18n.js";
import { toggleAudio, updateAudioUi } from "./modules/audio.js";
import { api } from "./modules/api.js";
import {
  toggleMapFullscreen,
  syncFullscreenButtons,
  updateMapLayerControls,
  refitAllMaps,
} from "./modules/maps.js";
import { loadLeaderboard, handleSortClick } from "./modules/leaderboard.js";
import { renderSyncStatus, getLastSyncStatus } from "./modules/sync.js";
import { clearTimer, startTimer } from "./modules/timer.js";
import { bindGlobalShortcuts, markShortcutCooldown } from "./modules/shortcuts.js";
import { shareMatchSummary } from "./modules/summary/share.js";
import {
  initPlayerInput,
  initLibraries,
  initWheelScrolls,
  refreshFilterComponentsLanguage,
  setGetActiveModeFn,
} from "./modules/setup_filters.js";
import { getActiveMode } from "./modules/modes/index.js";
import {
  showCard,
  resetGameUi,
  isGameActive,
  handleBeforeUnload,
} from "./modules/screens/common.js";
import {
  startMatch,
  returnToSetup,
  restartSameGame,
  handleAbandonGame,
  setEnsureLobbyInitializedFn,
} from "./modules/screens/setup.js";
import { loadQuestion, submitAnswer } from "./modules/screens/game.js";
import { handleNextRound } from "./modules/screens/reveal.js";
import {
  showMatchSummaryByMatchId,
  showGameEndedCard,
} from "./modules/screens/summary.js";

// Re-export / configure global mode accessor
setGetActiveModeFn(getActiveMode);

/* ----------------------------------------------------------------- router */

async function routeToActiveGame(matchId) {
  if (state.matchId === matchId && !state.matchFinished && isGameActive()) {
    showCard(el.gameCard);
    el.leaderboardCard.classList.add("hidden");
    return;
  }

  const session = loadActiveMatchSession();
  if (session && session.matchId === matchId && !session.matchFinished) {
    restoreActiveMatchSession(session);

    el.leaderboardCard.classList.add("hidden");
    showCard(el.gameCard);

    const activeMode = getActiveMode();
    activeMode.mount(el.guessingUi, state.lastMatchConfig || {});
    applyLanguage();

    // 1. If user was on Round Reveal when reloading, restore it without advancing round
    if (session.currentScreen === "reveal" && session.lastReveal) {
      el.guessingUi.classList.add("hidden");
      el.revealUi.classList.remove("hidden");
      activeMode.renderReveal(el.revealUi, session.lastReveal);
      el.nextRound.textContent = session.lastReveal.match_finished
        ? t("reveal.see_results_btn")
        : t("reveal.next_round_btn");
      return;
    }

    // 2. Otherwise restore question for current active player
    try {
      await loadQuestion();
    } catch (err) {
      console.warn("Failed to resume active question:", err);
      showGameEndedCard(
        null,
        t("game_ended.message"),
        t("game_ended.heading"),
        "🏁"
      );
    }
    return;
  }

  // Check if match summary exists in permanent SQLite storage
  try {
    const lang = getLocale();
    const summary = await api(
      `/api/match/${encodeURIComponent(matchId)}/summary?lang=${encodeURIComponent(lang)}`
    );
    if (summary) {
      navigate(`/game/${encodeURIComponent(matchId)}/summary`, { replace: true, force: true });
      return;
    }
  } catch (_) {}

  // Match does not exist in local session or backend -> 404 Match Not Found
  showGameEndedCard(
    null,
    t("game_ended.match_not_found_msg", matchId),
    t("game_ended.match_not_found_title"),
    "🔍"
  );
}

async function handleRoute(route) {
  document.documentElement.classList.remove("route-non-lobby");
  switch (route.type) {
    case RouteType.GAME_ACTIVE: {
      await routeToActiveGame(route.params.matchId);
      break;
    }

    case RouteType.GAME_SUMMARY: {
      const matchId = route.params.matchId;
      clearActiveMatchSession();
      await showMatchSummaryByMatchId(matchId);
      break;
    }

    case RouteType.CHALLENGE: {
      clearActiveMatchSession();
      returnToSetup({ updateUrl: false });
      showAlert(t("game_ended.challenge_notice"));
      navigate("/", { replace: true, force: true });
      break;
    }

    case RouteType.UNKNOWN: {
      clearActiveMatchSession();
      const notFoundPath = route.path || window.location.pathname;
      showGameEndedCard(
        null,
        t("game_ended.not_found_msg", notFoundPath),
        t("game_ended.not_found_title"),
        "🔍"
      );
      break;
    }

    case RouteType.LOBBY:
    default: {
      clearActiveMatchSession();
      returnToSetup({ updateUrl: false });
      break;
    }
  }
}

/* ----------------------------------------------------------------- events */

el.setupForm.addEventListener("submit", (event) => {
  startMatch(event).catch((err) => showAlert(err.message || err));
});

el.readyBtn.addEventListener("click", () => {
  if (!state.currentQuestion) return;
  state.currentScreen = "guessing";
  state.passConfirmed = true;
  el.passOverlay.classList.add("hidden");
  const activeMode = getActiveMode();
  activeMode.onReady(state.currentQuestion);

  let remainingSeconds =
    typeof state.currentQuestion.remaining_seconds === "number"
      ? state.currentQuestion.remaining_seconds
      : null;
  const session = loadActiveMatchSession();
  if (
    session &&
    session.activeQuestionId === state.currentQuestion.question_id &&
    session.timerEndTimeMs
  ) {
    const clientRemaining = Math.max(0, (session.timerEndTimeMs - Date.now()) / 1000);
    if (remainingSeconds !== null) {
      remainingSeconds = Math.min(remainingSeconds, clientRemaining);
    } else {
      remainingSeconds = clientRemaining;
    }
  }

  startTimer(state.currentQuestion.round_length, getActiveMode, remainingSeconds);
  saveActiveMatchSession();
  markShortcutCooldown(20);
});

el.submitAnswer.addEventListener("click", () => {
  submitAnswer(false).catch((err) => showAlert(err.message || err));
});

el.nextRound.addEventListener("click", () => {
  handleNextRound().catch((err) => showAlert(err.message || err));
});

el.summaryLobbyBtn.addEventListener("click", () => {
  returnToSetup();
});

el.summaryPlayAgainBtn.addEventListener("click", () => {
  restartSameGame().catch((err) => showAlert(err.message || err));
});

if (el.shareMatchBtn) {
  el.shareMatchBtn.addEventListener("click", () => {
    shareMatchSummary();
  });
}

el.langToggle.addEventListener("click", () => {
  toggleLanguage();
  refreshActiveScreenLanguage();
});

el.audioToggle.addEventListener("click", () => {
  toggleAudio();
  updateAudioUi();
});

if (el.toggleMapFsBtn) {
  el.toggleMapFsBtn.addEventListener("click", (e) => {
    e.preventDefault();
    e.stopPropagation();
    toggleMapFullscreen();
  });
}

if (el.toggleQuizImageFsBtn) {
  el.toggleQuizImageFsBtn.addEventListener("click", (e) => {
    e.preventDefault();
    e.stopPropagation();
    getActiveMode()?.togglePhotoFullscreen?.();
  });
}

el.returnSetupBtn.addEventListener("click", () => {
  handleAbandonGame("exit");
});

el.restartGameBtn.addEventListener("click", () => {
  handleAbandonGame("restart");
});

if (el.revealExitBtn) {
  el.revealExitBtn.addEventListener("click", () => {
    handleAbandonGame("exit");
  });
}

if (el.refreshLeaderboard) {
  el.refreshLeaderboard.addEventListener("click", () => {
    loadLeaderboard().catch((err) => showAlert(err.message || err));
  });
}

if (el.leaderboardHead) {
  el.leaderboardHead.addEventListener("click", handleSortClick);
}

window.addEventListener("resize", () => {
  refitAllMaps();
  syncFullscreenButtons();
});

window.addEventListener("beforeunload", handleBeforeUnload);

[el.roundCount, el.roundLength].forEach((control) => {
  if (control) {
    control.addEventListener("change", () => {
      loadLeaderboard().catch((err) => console.warn("Leaderboard refresh error:", err));
    });
  }
});

bindGlobalShortcuts({
  onSubmitAnswer: () => {
    submitAnswer(false).catch((err) => showAlert(err.message || err));
  },
  onNextRound: () => {
    handleNextRound().catch((err) => showAlert(err.message || err));
  },
  onPlayerReady: () => {
    if (!el.passOverlay.classList.contains("hidden")) {
      el.readyBtn.click();
    }
  },
  onToggleFullscreen: () => {
    if (state.currentScreen === "reveal") {
      toggleMapFullscreen();
    } else if (state.currentScreen === "guessing") {
      const mode = getActiveMode();
      if (state.gameMode === "album_shuffle" && mode.isShuffleMapFullscreenActive?.()) {
        mode.toggleShuffleMapFullscreen?.();
      } else {
        toggleMapFullscreen();
      }
    }
  },
  onTogglePhotoFullscreen: () => {
    const activeMode = getActiveMode();
    activeMode?.togglePhotoFullscreen?.();
  },
  onToggleAudio: () => {
    toggleAudio();
    updateAudioUi();
  },
  onToggleLanguage: () => {
    toggleLanguage();
    refreshActiveScreenLanguage();
  },
  onReturnToLobby: () => {
    if (isGameActive()) {
      handleAbandonGame("exit");
    } else if (!el.summaryCard.classList.contains("hidden")) {
      returnToSetup();
    }
  },
  onRestartMatch: () => {
    if (isGameActive()) {
      handleAbandonGame("restart");
    } else if (!el.summaryCard.classList.contains("hidden")) {
      restartSameGame().catch((err) => showAlert(err.message || err));
    }
  },
  onToggleMapLayer: (layerType) => {
    updateMapLayerControls(layerType);
  },
  onSelectPhotoSlot: (slotIndex) => {
    if (state.currentScreen === "guessing" && state.gameMode === "album_shuffle") {
      const mode = getActiveMode();
      mode.selectPhotoBySlotIndex?.(slotIndex);
    }
  },
  onAssignPin: (pinLetter) => {
    if (state.currentScreen === "guessing" && state.gameMode === "album_shuffle") {
      const mode = getActiveMode();
      mode.assignPinToSelectedPhoto?.(pinLetter);
    }
  },
  onAssignTimeline: (rankIndex) => {
    if (state.currentScreen === "guessing" && state.gameMode === "album_shuffle") {
      const mode = getActiveMode();
      mode.assignTimelineRankToSelectedPhoto?.(rankIndex);
    }
  },
});

function refreshActiveScreenLanguage() {
  applyLanguage();
  updateLanguageUi();
  refreshFilterComponentsLanguage();
  if (state.lastSummary && !el.summaryCard.classList.contains("hidden")) {
    const lang = getLocale();
    api(`/api/match/${encodeURIComponent(state.matchId)}/summary?lang=${encodeURIComponent(lang)}`)
      .then((summary) => {
        state.lastSummary = summary;
        renderSummaryContent(summary);
      })
      .catch((err) => console.warn("Failed to refresh summary language:", err));
  }
}

async function initUiConfig() {
  try {
    const config = await api("/api/config");
    applyUiConfig(config);
  } catch (err) {
    console.warn("Using default UI config:", err);
  }
}

function applyUiConfig(config) {
  if (!config) return;
  if (config.language && !localStorage.getItem("immich_quiz_lang")) {
    const lang = normalizeLanguage(config.language);
    localStorage.setItem("immich_quiz_lang", lang);
    updateLanguageUi();
  }
  applyLanguage();
}

let isLobbyInitialized = false;
let lobbyInitPromise = null;

async function ensureLobbyInitialized() {
  if (isLobbyInitialized) return;
  if (lobbyInitPromise) return lobbyInitPromise;

  lobbyInitPromise = (async () => {
    try {
      initPlayerInput();
      initWheelScrolls();
      await initLibraries();
      await loadLeaderboard();
      isLobbyInitialized = true;
    } catch (err) {
      console.error("Lobby initialization failed:", err);
    } finally {
      lobbyInitPromise = null;
    }
  })();

  return lobbyInitPromise;
}

setEnsureLobbyInitializedFn(ensureLobbyInitialized);

(async function bootstrap() {
  refreshActiveScreenLanguage();
  syncFullscreenButtons();

  setNavigationGuard((toRoute, fromRoute) => {
    if (fromRoute.type === RouteType.GAME_ACTIVE && isGameActive()) {
      if (toRoute.path !== fromRoute.path) {
        const label = t("game.abandon_exit");
        if (confirm(t("game.abandon_confirm", label))) {
          clearTimer();
          clearActiveMatchSession();
          return true;
        }
        return false;
      }
    }
    return true;
  });

  // Fast background config sync
  initUiConfig().catch((err) => console.warn("UI config error:", err));

  // Initialize router immediately so non-lobby routes display instantly without flash of lobby
  initRouter(handleRoute);

  const initialRoute = parseRoute(window.location.pathname);
  if (initialRoute.type === RouteType.LOBBY) {
    ensureLobbyInitialized().catch((err) => console.warn("Lobby startup error:", err));
  }

  if ("serviceWorker" in navigator) {
    navigator.serviceWorker
      .register("/sw.js")
      .then((reg) => {
        reg.addEventListener("updatefound", () => {
          const installing = reg.installing;
          if (installing) {
            installing.addEventListener("statechange", () => {
              if (
                installing.state === "installed" &&
                navigator.serviceWorker.controller
              ) {
                console.info("New service worker version available.");
              }
            });
          }
        });
      })
      .catch((err) => console.warn("Service worker registration failed:", err));
  }
})();

import { state, el, clearActiveMatchSession } from "../state.js";
import { clearTimer } from "../timer.js";
import { unregisterActiveMap } from "../maps.js";
import { getActiveMode } from "../modes/index.js";
import { t } from "../i18n.js";
import { challenge } from "../challenge/index.js";

export function clearRevealAnimation() {
  if (state.revealAnimationFrameId !== null) {
    cancelAnimationFrame(state.revealAnimationFrameId);
    state.revealAnimationFrameId = null;
  }
  if (state.revealAnimationTimeoutId !== null) {
    clearTimeout(state.revealAnimationTimeoutId);
    state.revealAnimationTimeoutId = null;
  }
}

export function showCard(cardEl) {
  clearRevealAnimation();
  [el.setupCard, el.gameCard, el.summaryCard, el.gameEndedCard, el.challengeCard, el.challengesPageCard].forEach((c) => {
    if (c) c.classList.add("hidden");
  });
  if (cardEl) cardEl.classList.remove("hidden");
}


export function resetGameUi() {
  clearRevealAnimation();
  clearTimer();

  state.matchId = null;
  state.currentQuestion = null;
  state.lastReveal = null;
  state.lastSummary = null;
  state.guessedLatLng = null;
  state.mapBounds = null;
  state.playedAssetIds = [];
  state.roundHistory = [];
  state.perfectCounts = {};
  state.playerStats = {};
  state.matchFinished = false;
  state.timedOut = false;
  state.submitting = false;

  try {
    getActiveMode().unmount();
  } catch (_) {}

  if (el.roundMeta) el.roundMeta.replaceChildren();
  if (el.passOverlay) el.passOverlay.classList.add("hidden");
  if (el.guessingUi) el.guessingUi.classList.add("hidden");
  if (el.revealUi) el.revealUi.classList.add("hidden");
  if (el.gameRestartBtn) el.gameRestartBtn.classList.remove("hidden");
  if (el.revealRestartBtn) el.revealRestartBtn.classList.remove("hidden");
  if (el.timeoutNotice) {
    el.timeoutNotice.classList.add("hidden");
    el.timeoutNotice.textContent = "";
  }

  if (el.quizImage) {
    el.quizImage.classList.add("hidden");
    el.quizImage.removeAttribute("src");
    el.quizImage.onerror = null;
  }
  if (el.quizImageFullscreen) {
    el.quizImageFullscreen.classList.add("hidden");
  }
  if (el.mediaPlaceholder) el.mediaPlaceholder.classList.remove("hidden");
  if (el.mediaFrame) el.mediaFrame.classList.add("hidden");

  if (el.revealActual) el.revealActual.replaceChildren();
  if (el.revealLegend) el.revealLegend.replaceChildren();
  if (el.revealTableHead) el.revealTableHead.replaceChildren();
  if (el.revealTableBody) el.revealTableBody.replaceChildren();
  if (el.revealMapShell) el.revealMapShell.classList.add("hidden");
  if (el.revealMapHead) el.revealMapHead.classList.add("hidden");

  if (state.revealLayers && Array.isArray(state.revealLayers)) {
    state.revealLayers.forEach((l) => {
      try {
        if (state.revealMap) state.revealMap.removeLayer(l);
      } catch (_) {}
    });
    state.revealLayers = [];
  }
  if (state.revealMap) {
    try {
      unregisterActiveMap(state.revealMap);
      state.revealMap.remove();
    } catch (_) {}
    state.revealMap = null;
  }

  if (state.journeyLayers && Array.isArray(state.journeyLayers)) {
    state.journeyLayers.forEach((l) => {
      try {
        if (state.journeyMap) state.journeyMap.removeLayer(l);
      } catch (_) {}
    });
    state.journeyLayers = [];
  }
  if (state.journeyMap) {
    try {
      unregisterActiveMap(state.journeyMap);
      state.journeyMap.remove();
    } catch (_) {}
    state.journeyMap = null;
  }
  if (el.journeyMapShell) el.journeyMapShell.classList.add("hidden");
  if (el.journeyMapHead) el.journeyMapHead.classList.add("hidden");

  if (el.summaryWinner) el.summaryWinner.replaceChildren();
  if (el.summaryMeta) el.summaryMeta.textContent = "";
  if (el.summaryTableHead) el.summaryTableHead.replaceChildren();
  if (el.summaryTableBody) el.summaryTableBody.replaceChildren();
  if (el.polaroidGallery) el.polaroidGallery.replaceChildren();
  if (el.summaryCard) {
    const existingAwards = el.summaryCard.querySelector(".awards-row");
    if (existingAwards) existingAwards.remove();
  }
}

export function isGameActive() {
  if (challenge && typeof challenge.isActive === "function" && challenge.isActive()) {
    return challenge.isGameActive();
  }
  return Boolean(state.matchId && !state.matchFinished && !state.lastSummary);
}

export function handleBeforeUnload(event) {
  if (isGameActive()) {
    event.preventDefault();
    event.returnValue = "";
    return "";
  }
}

export function confirmAbandonMatch(action = "exit") {
  if (state.startingMatch) return false;
  if (action === "restart" && challenge && typeof challenge.isActive === "function" && challenge.isActive()) {
    return false;
  }
  if (!isGameActive()) return true;

  const label = action === "restart" ? t("game.abandon_restart") : t("game.abandon_exit");
  if (!confirm(t("game.abandon_confirm", label))) {
    return false;
  }
  clearTimer();
  clearActiveMatchSession();
  return true;
}

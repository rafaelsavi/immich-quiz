import { state, el } from "./state.js";
import { t } from "./i18n.js";
import { playTick, playBuzzer } from "./audio.js";
import { updateSubmitState } from "./maps.js";

let _getActiveModeFn = null;
let _visibilityBound = false;

export function clearTimer() {
  if (state.timerRef) {
    clearInterval(state.timerRef);
    state.timerRef = null;
  }
  state.timerEndTimeMs = null;
}

export function resetTimerBar() {
  clearTimer();
  if (el.timerFill) {
    el.timerFill.style.width = "100%";
    el.timerFill.classList.remove("is-warning", "is-critical");
  }
  if (el.timerTrack) {
    el.timerTrack.classList.add("is-idle");
  }
  if (el.timerLabel) {
    el.timerLabel.textContent = "";
  }
  if (el.timerRemaining) {
    el.timerRemaining.textContent = "";
    el.timerRemaining.classList.remove("is-critical-text");
  }
  if (el.timeoutNotice) {
    el.timeoutNotice.classList.add("hidden");
    el.timeoutNotice.textContent = "";
  }

  const timerRow = el.timerTrack ? el.timerTrack.closest(".timer-row") : null;
  if (timerRow) timerRow.classList.remove("is-pulsing");

  document.querySelectorAll(".fullscreen-timer").forEach((ft) => {
    const fill = ft.querySelector(".fs-timer-fill");
    const label = ft.querySelector(".fs-timer-label");
    const remaining = ft.querySelector(".fs-timer-remaining");
    if (fill) {
      fill.style.width = "100%";
      fill.className = "fs-timer-fill";
    }
    if (label) label.textContent = "";
    if (remaining) remaining.textContent = "";
  });
}

export function syncFullscreenTimers(seconds, ratio, isWarning, isCritical) {
  document.querySelectorAll(".fullscreen-timer").forEach((ft) => {
    const fill = ft.querySelector(".fs-timer-fill");
    const label = ft.querySelector(".fs-timer-label");
    const remaining = ft.querySelector(".fs-timer-remaining");
    if (fill) {
      fill.style.width = `${ratio * 100}%`;
      fill.classList.toggle("is-warning", isWarning);
      fill.classList.toggle("is-critical", isCritical);
    }
    if (label && el.timerLabel) label.textContent = el.timerLabel.textContent;
    if (remaining) remaining.textContent = `${seconds}s`;
  });
}

export function handleTimeout(activeMode = null) {
  if (state.timedOut || state.submitting || !state.currentQuestion) {
    return;
  }
  state.timedOut = true;
  clearTimer();
  if (el.timerLabel) el.timerLabel.textContent = t("game.timer_time_up_label");
  if (el.timerRemaining) el.timerRemaining.textContent = "0s";
  if (activeMode && activeMode.setDisabled) {
    activeMode.setDisabled(true);
  }

  if (el.timeoutNotice) {
    el.timeoutNotice.textContent = t("game.timer_time_up_notice");
    el.timeoutNotice.classList.remove("hidden");
  }

  if (el.submitAnswer) {
    el.submitAnswer.textContent = t("game.continue_btn");
  }
  updateSubmitState();
}

function updateTimerUi(clamped, total, shouldPlayTick = true) {
  const ratio = total > 0 ? clamped / total : 0;
  const isCritical = ratio <= 0.2 || clamped <= 5;
  const isWarning = ratio <= 0.5 && ratio > 0.2 && clamped > 5;

  if (el.timerRemaining) el.timerRemaining.textContent = `${clamped}s`;
  if (el.timerFill) {
    el.timerFill.style.width = `${ratio * 100}%`;
    el.timerFill.classList.toggle("is-warning", isWarning);
    el.timerFill.classList.toggle("is-critical", isCritical);
  }

  const timerRow = el.timerTrack ? el.timerTrack.closest(".timer-row") : null;
  if (timerRow) timerRow.classList.toggle("is-pulsing", clamped <= 5 && clamped > 0);
  if (el.timerRemaining) el.timerRemaining.classList.toggle("is-critical-text", clamped <= 5 && clamped > 0);

  syncFullscreenTimers(clamped, ratio, isWarning, isCritical);

  if (shouldPlayTick && clamped <= 5 && clamped > 0) {
    playTick(clamped);
  }

  if (clamped <= 0) {
    clearTimer();
    playBuzzer();
    const activeMode = _getActiveModeFn ? _getActiveModeFn() : null;
    handleTimeout(activeMode);
  }
}

function tick() {
  if (!state.timerEndTimeMs || state.timedOut || state.submitting || !state.currentQuestion) {
    return;
  }
  const now = Date.now();
  const remainingMs = state.timerEndTimeMs - now;
  const clamped = Math.max(0, Math.ceil(remainingMs / 1000));
  state.timerRemainingSeconds = clamped;
  updateTimerUi(clamped, state.timerTotalSeconds, true);
}

function syncOnVisibilityChange() {
  if (
    document.visibilityState === "visible" &&
    state.timerRef &&
    state.timerEndTimeMs &&
    !state.timedOut &&
    !state.submitting &&
    state.currentQuestion
  ) {
    const now = Date.now();
    const remainingMs = state.timerEndTimeMs - now;
    const clamped = Math.max(0, Math.ceil(remainingMs / 1000));
    state.timerRemainingSeconds = clamped;
    updateTimerUi(clamped, state.timerTotalSeconds, false);
  }
}

function bindVisibilityListener() {
  if (_visibilityBound) return;
  _visibilityBound = true;
  document.addEventListener("visibilitychange", syncOnVisibilityChange);
  window.addEventListener("focus", syncOnVisibilityChange);
}

export function startTimer(roundLength, getActiveModeFn = null) {
  resetTimerBar();
  state.timedOut = false;
  _getActiveModeFn = getActiveModeFn;
  bindVisibilityListener();

  if (roundLength === "unlimited") {
    if (el.timerLabel) el.timerLabel.textContent = t("game.timer_unlimited");
    return;
  }

  let total = 60;
  if (roundLength === "30s") total = 30;
  else if (roundLength === "1m") total = 60;
  else if (roundLength === "2m") total = 120;
  else if (roundLength === "5m") total = 300;

  state.timerTotalSeconds = total;
  state.timerRemainingSeconds = total;
  state.timerEndTimeMs = Date.now() + total * 1000;

  if (el.timerTrack) el.timerTrack.classList.remove("is-idle");
  if (el.timerLabel) el.timerLabel.textContent = t("game.timer_time_left");
  if (el.timerRemaining) el.timerRemaining.textContent = `${total}s`;

  state.timerRef = setInterval(tick, 1000);
}

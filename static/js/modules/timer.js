import { state, el } from "./state.js";
import { t } from "./i18n.js";
import { playTick, playBuzzer } from "./audio.js";
import { updateSubmitState } from "./maps.js";

let _getActiveModeFn = null;
let _visibilityBound = false;

function interpolateRgb(rgb1, rgb2, factor) {
  const f = Math.max(0, Math.min(1, factor));
  const r = Math.round(rgb1[0] + (rgb2[0] - rgb1[0]) * f);
  const g = Math.round(rgb1[1] + (rgb2[1] - rgb1[1]) * f);
  const b = Math.round(rgb1[2] + (rgb2[2] - rgb1[2]) * f);
  return `rgb(${r}, ${g}, ${b})`;
}

// Continuous color keyframes for uniform progression
const COLOR_START_1 = [15, 124, 127];   // #0f7c7f (Teal primary)
const COLOR_START_2 = [75, 179, 182];   // #4bb3b6 (Teal secondary)

const COLOR_MID_1 = [217, 119, 6];      // #d97706 (Amber primary)
const COLOR_MID_2 = [245, 158, 11];     // #f59e0b (Amber secondary)

const COLOR_END_1 = [220, 38, 38];      // #dc2626 (Crimson primary)
const COLOR_END_2 = [239, 68, 68];      // #ef4444 (Crimson secondary)

/**
 * Calculates continuous uniform gradient and glow for remaining time ratio [1.0 -> 0.0].
 * Transitions smoothly from Teal (100%) to Amber (50%) to Crimson (0%).
 *
 * @param {number} ratio
 * @returns {{ background: string, glow: string }}
 */
export function getTimerGradient(ratio) {
  const clamped = Math.max(0, Math.min(1, ratio));
  let c1, c2, glow;
  if (clamped >= 0.5) {
    const f = (1.0 - clamped) / 0.5;
    c1 = interpolateRgb(COLOR_START_1, COLOR_MID_1, f);
    c2 = interpolateRgb(COLOR_START_2, COLOR_MID_2, f);
    glow = interpolateRgb([15, 124, 127], [217, 119, 6], f);
  } else {
    const f = (0.5 - clamped) / 0.5;
    c1 = interpolateRgb(COLOR_MID_1, COLOR_END_1, f);
    c2 = interpolateRgb(COLOR_MID_2, COLOR_END_2, f);
    glow = interpolateRgb([217, 119, 6], [220, 38, 38], f);
  }
  return {
    background: `linear-gradient(90deg, ${c1}, ${c2})`,
    glow,
  };
}

/**
 * Format remaining seconds into a clean display string.
 * Uses M:SS format for durations >= 60s (e.g. "2:00", "1:15")
 * and Xs format for < 60s (e.g. "45s", "5s").
 *
 * @param {number} seconds
 * @returns {string}
 */
export function formatTimeDisplay(seconds) {
  const s = Math.max(0, Math.round(seconds));
  if (s < 60) {
    return `${s}s`;
  }
  const mins = Math.floor(s / 60);
  const remSecs = s % 60;
  return `${mins}:${remSecs < 10 ? "0" : ""}${remSecs}`;
}

export function clearTimer() {
  if (state.timerRafId) {
    cancelAnimationFrame(state.timerRafId);
    state.timerRafId = null;
  }
  if (state.timerRef) {
    clearInterval(state.timerRef);
    state.timerRef = null;
  }
  state.timerEndTimeMs = null;
  state.timerPaused = false;
  state.timerPausedRemainingMs = null;
  state.timerLastTickedSec = null;
}

export function pauseTimer() {
  if (!state.timerEndTimeMs || state.timerPaused || state.timedOut || state.submitting) {
    return;
  }
  const now = Date.now();
  state.timerPausedRemainingMs = Math.max(0, state.timerEndTimeMs - now);
  state.timerPaused = true;

  if (state.timerRafId) {
    cancelAnimationFrame(state.timerRafId);
    state.timerRafId = null;
  }
  if (state.timerRef) {
    clearInterval(state.timerRef);
    state.timerRef = null;
  }

  const timerRow = el.timerTrack ? el.timerTrack.closest(".timer-row") : null;
  if (timerRow) {
    timerRow.classList.add("is-paused");
  }
}

export function resumeTimer() {
  if (!state.timerPaused || !state.timerPausedRemainingMs || state.timedOut || state.submitting || !state.currentQuestion) {
    return;
  }
  state.timerEndTimeMs = Date.now() + state.timerPausedRemainingMs;
  state.timerPaused = false;
  state.timerPausedRemainingMs = null;

  const timerRow = el.timerTrack ? el.timerTrack.closest(".timer-row") : null;
  if (timerRow) {
    timerRow.classList.remove("is-paused");
  }

  startAnimationLoops();
}

export function resetTimerBar() {
  clearTimer();
  if (el.timerFill) {
    el.timerFill.style.width = "100%";
    el.timerFill.style.background = "";
    el.timerFill.style.removeProperty("--timer-glow");
    el.timerFill.classList.remove("is-critical");
  }
  if (el.timerTrack) {
    el.timerTrack.classList.add("is-idle");
  }
  if (el.timerLabel) {
    el.timerLabel.textContent = "";
  }
  if (el.timerRemaining) {
    el.timerRemaining.textContent = "";
    el.timerRemaining.classList.remove("is-critical-text", "is-ticking");
  }
  if (el.timeoutNotice) {
    el.timeoutNotice.classList.add("hidden");
    el.timeoutNotice.textContent = "";
  }

  const timerRow = el.timerTrack ? el.timerTrack.closest(".timer-row") : null;
  if (timerRow) {
    timerRow.classList.remove("is-pulsing", "is-paused");
  }

  document.querySelectorAll(".fullscreen-timer").forEach((ft) => {
    const fill = ft.querySelector(".fs-timer-fill");
    const label = ft.querySelector(".fs-timer-label");
    const remaining = ft.querySelector(".fs-timer-remaining");
    if (fill) {
      fill.style.width = "100%";
      fill.style.background = "";
      fill.style.removeProperty("--timer-glow");
      fill.className = "fs-timer-fill";
    }
    if (label) label.textContent = "";
    if (remaining) {
      remaining.textContent = "";
      remaining.classList.remove("is-critical-text", "is-ticking");
    }
  });
}

export function syncFullscreenTimers(seconds, ratio, isWarning, isCritical, isTicking = false, gradient = null) {
  const formatted = formatTimeDisplay(seconds);
  const grad = gradient || getTimerGradient(ratio);
  document.querySelectorAll(".fullscreen-timer").forEach((ft) => {
    const fill = ft.querySelector(".fs-timer-fill");
    const label = ft.querySelector(".fs-timer-label");
    const remaining = ft.querySelector(".fs-timer-remaining");
    if (fill) {
      fill.style.width = `${ratio * 100}%`;
      fill.style.background = grad.background;
      fill.style.setProperty("--timer-glow", grad.glow);
      fill.classList.toggle("is-critical", isCritical);
    }
    if (label && el.timerLabel) {
      label.textContent = el.timerLabel.textContent;
    }
    if (remaining) {
      remaining.textContent = formatted;
      remaining.classList.toggle("is-critical-text", seconds <= 5 && seconds > 0);
      if (isTicking) {
        remaining.classList.remove("is-ticking");
        void remaining.offsetWidth;
        remaining.classList.add("is-ticking");
      }
    }
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
  if (el.timerFill) {
    el.timerFill.style.width = "0%";
    el.timerFill.style.background = `linear-gradient(90deg, rgb(${COLOR_END_1.join(",")}), rgb(${COLOR_END_2.join(",")}))`;
    el.timerFill.classList.add("is-critical");
  }

  const timerRow = el.timerTrack ? el.timerTrack.closest(".timer-row") : null;
  if (timerRow) {
    timerRow.classList.remove("is-pulsing", "is-paused");
  }

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

function updateTimerUi(remainingMs, totalSec, shouldPlayTick = true) {
  const totalMs = totalSec * 1000;
  const ratio = totalMs > 0 ? Math.max(0, Math.min(1, remainingMs / totalMs)) : 0;
  const clampedSec = Math.max(0, Math.ceil(remainingMs / 1000));
  const isCritical = ratio <= 0.2 || clampedSec <= 5;
  const isWarning = ratio <= 0.5 && !isCritical && clampedSec > 5;
  const gradient = getTimerGradient(ratio);

  // 1. Continuous 60fps smooth progress fill & uniform color transition
  if (el.timerFill) {
    el.timerFill.style.width = `${ratio * 100}%`;
    el.timerFill.style.background = gradient.background;
    el.timerFill.style.setProperty("--timer-glow", gradient.glow);
    el.timerFill.classList.toggle("is-critical", isCritical);
  }

  const timerRow = el.timerTrack ? el.timerTrack.closest(".timer-row") : null;
  if (timerRow) {
    timerRow.classList.toggle("is-pulsing", clampedSec <= 5 && clampedSec > 0);
  }

  // 2. Integer second updates (text, audio ticks, micro-animations)
  const isNewSec = state.timerLastTickedSec !== clampedSec;
  if (isNewSec) {
    const isTickBoundary = state.timerLastTickedSec !== null && state.timerLastTickedSec > clampedSec;
    state.timerLastTickedSec = clampedSec;
    state.timerRemainingSeconds = clampedSec;

    const formatted = formatTimeDisplay(clampedSec);
    if (el.timerRemaining) {
      el.timerRemaining.textContent = formatted;
      el.timerRemaining.classList.toggle("is-critical-text", clampedSec <= 5 && clampedSec > 0);

      if (isTickBoundary && clampedSec <= 5 && clampedSec > 0) {
        el.timerRemaining.classList.remove("is-ticking");
        void el.timerRemaining.offsetWidth;
        el.timerRemaining.classList.add("is-ticking");
      }
    }

    syncFullscreenTimers(clampedSec, ratio, isWarning, isCritical, isTickBoundary && clampedSec <= 5 && clampedSec > 0, gradient);

    if (shouldPlayTick && isTickBoundary && clampedSec <= 10 && clampedSec > 0) {
      playTick(clampedSec);
    }
  } else {
    // Keep fullscreen timer fill widths & continuous gradient in sync on sub-second frames
    document.querySelectorAll(".fullscreen-timer").forEach((ft) => {
      const fill = ft.querySelector(".fs-timer-fill");
      if (fill) {
        fill.style.width = `${ratio * 100}%`;
        fill.style.background = gradient.background;
        fill.style.setProperty("--timer-glow", gradient.glow);
        fill.classList.toggle("is-critical", isCritical);
      }
    });
  }

  // 3. Time's up handling
  if (remainingMs <= 0) {
    clearTimer();
    playBuzzer();
    const activeMode = _getActiveModeFn ? _getActiveModeFn() : null;
    handleTimeout(activeMode);
  }
}

function timerLoop() {
  if (!state.timerEndTimeMs || state.timerPaused || state.timedOut || state.submitting || !state.currentQuestion) {
    state.timerRafId = null;
    return;
  }
  const remainingMs = Math.max(0, state.timerEndTimeMs - Date.now());
  updateTimerUi(remainingMs, state.timerTotalSeconds, true);

  if (remainingMs > 0 && !state.timedOut && !state.submitting && !state.timerPaused) {
    state.timerRafId = requestAnimationFrame(timerLoop);
  } else {
    state.timerRafId = null;
  }
}

function backgroundTick() {
  if (!state.timerEndTimeMs || state.timerPaused || state.timedOut || state.submitting || !state.currentQuestion) {
    return;
  }
  const remainingMs = Math.max(0, state.timerEndTimeMs - Date.now());
  updateTimerUi(remainingMs, state.timerTotalSeconds, true);
}

function startAnimationLoops() {
  if (state.timerRafId) {
    cancelAnimationFrame(state.timerRafId);
  }
  if (state.timerRef) {
    clearInterval(state.timerRef);
  }

  state.timerRafId = requestAnimationFrame(timerLoop);
  // Backup 500ms interval for background tab throttling
  state.timerRef = setInterval(backgroundTick, 500);
}

function syncOnVisibilityChange() {
  if (
    state.timerEndTimeMs &&
    !state.timerPaused &&
    !state.timedOut &&
    !state.submitting &&
    state.currentQuestion
  ) {
    const remainingMs = Math.max(0, state.timerEndTimeMs - Date.now());
    updateTimerUi(remainingMs, state.timerTotalSeconds, false);
    if (remainingMs > 0 && !state.timerRafId) {
      state.timerRafId = requestAnimationFrame(timerLoop);
    }
  }
}

function bindVisibilityListener() {
  if (_visibilityBound) return;
  _visibilityBound = true;
  document.addEventListener("visibilitychange", syncOnVisibilityChange);
  window.addEventListener("focus", syncOnVisibilityChange);
}

const ROUND_LENGTH_SECONDS_MAP = {
  "30s": 30,
  "1m": 60,
  "2m": 120,
  "5m": 300,
};

/**
 * Parse round length duration string to total seconds, or null if unlimited.
 * @param {string} roundLength
 * @returns {number|null}
 */
export function parseRoundDurationSeconds(roundLength) {
  if (roundLength === "unlimited") return null;
  return ROUND_LENGTH_SECONDS_MAP[roundLength] ?? 60;
}

export function startTimer(roundLength, getActiveModeFn = null, initialRemainingSeconds = null) {
  resetTimerBar();
  state.timedOut = false;
  state.timerPaused = false;
  state.timerPausedRemainingMs = null;
  _getActiveModeFn = getActiveModeFn;
  bindVisibilityListener();

  const total = parseRoundDurationSeconds(roundLength);
  if (total === null) {
    if (el.timerLabel) el.timerLabel.textContent = t("game.timer_unlimited");
    return;
  }

  state.timerTotalSeconds = total;

  let remaining = total;
  if (typeof initialRemainingSeconds === "number" && !isNaN(initialRemainingSeconds)) {
    remaining = Math.max(0, Math.min(total, initialRemainingSeconds));
  }

  state.timerRemainingSeconds = remaining;
  state.timerLastTickedSec = Math.ceil(remaining);
  state.timerEndTimeMs = Date.now() + remaining * 1000;

  if (el.timerTrack) el.timerTrack.classList.remove("is-idle");
  if (el.timerLabel) el.timerLabel.textContent = t("game.timer_time_left");
  if (el.timerRemaining) el.timerRemaining.textContent = formatTimeDisplay(remaining);

  const initialRatio = total > 0 ? remaining / total : 0;
  const isCritical = remaining <= 5 && remaining > 0;
  syncFullscreenTimers(remaining, initialRatio, remaining <= 10, isCritical);

  if (remaining <= 0) {
    handleTimeout(_getActiveModeFn ? _getActiveModeFn() : null);
  } else {
    startAnimationLoops();
  }
}

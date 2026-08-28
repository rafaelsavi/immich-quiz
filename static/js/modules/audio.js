import { state, el } from "./state.js";
import { t } from "./i18n.js";

let audioCtx = null;

function getInitialAudioPreference() {
  try {
    const stored = localStorage.getItem("immich_quiz_audio");
    if (stored === null) return true;
    return stored === "1";
  } catch (_) {
    return true;
  }
}

function initializeAudioState() {
  state.audioEnabled = getInitialAudioPreference();
  updateAudioUi();
}

initializeAudioState();

const UNLOCK_EVENTS = ["click", "keydown", "touchend"];

function removeUnlockListeners() {
  UNLOCK_EVENTS.forEach((evt) => {
    document.removeEventListener(evt, handleUserGesture, { capture: true });
  });
}

function handleUserGesture() {
  unlockAudioContext();
  if (audioCtx && audioCtx.state === "running") {
    removeUnlockListeners();
  }
}

export function unlockAudioContext() {
  if (!audioCtx) {
    const AudioContextClass = window.AudioContext || window.webkitAudioContext;
    if (AudioContextClass) {
      audioCtx = new AudioContextClass();
    }
  }
  if (audioCtx && audioCtx.state === "suspended") {
    audioCtx
      .resume()
      .then(() => {
        if (audioCtx && audioCtx.state === "running") {
          removeUnlockListeners();
        }
      })
      .catch(() => { });
  }
}

UNLOCK_EVENTS.forEach((evt) => {
  document.addEventListener(evt, handleUserGesture, { capture: true });
});

export function getAudioContext() {
  unlockAudioContext();
  return audioCtx;
}

export function playTone(freq, type, duration, gainValue = 0.22) {
  if (!state || !state.audioEnabled) return;
  try {
    const ctx = getAudioContext();
    if (!ctx) return;

    if (ctx.state === "suspended") {
      ctx.resume().catch(() => { });
    }

    const osc = ctx.createOscillator();
    const gain = ctx.createGain();

    osc.type = type;
    osc.frequency.setValueAtTime(freq, ctx.currentTime);

    gain.gain.setValueAtTime(gainValue, ctx.currentTime);
    gain.gain.linearRampToValueAtTime(0.0001, ctx.currentTime + duration);

    osc.connect(gain);
    gain.connect(ctx.destination);

    osc.start(ctx.currentTime);
    osc.stop(ctx.currentTime + duration);
  } catch (_) {
    // Ignore audio restrictions
  }
}

export function haptic(pattern = 15) {
  if (typeof navigator !== "undefined" && "vibrate" in navigator && state && state.audioEnabled) {
    try {
      navigator.vibrate(pattern);
    } catch (_) { }
  }
}

export function playSubmitTone() {
  if (!state || !state.audioEnabled) return;
  haptic(15);
  playTone(480, "sine", 0.08, 0.12);
}

export function playTick(clampedSec = 5) {
  if (!state || !state.audioEnabled) return;
  const clamped = Math.max(1, Math.min(5, Number(clampedSec) || 5));
  const step = 5 - clamped; // 0 (at 5s) to 4 (at 1s)

  // Gentle pitch rise: 520Hz at 5s up to 720Hz at 1s
  const freq = 520 + step * 50;
  // Moderate volume rise: 0.15 at 5s up to 0.25 at 1s
  const gain = 0.15 + step * 0.025;

  haptic(18);
  playTone(freq, "sine", 0.09, gain);
}

export function playBuzzer() {
  if (!state || !state.audioEnabled) return;
  haptic([120, 60, 200]);
  try {
    const ctx = getAudioContext();
    if (!ctx) return;

    if (ctx.state === "suspended") {
      ctx.resume().catch(() => { });
    }

    // Dramatic double-pulse buzzer (BUZZ - BUZZ!)
    [0, 0.22].forEach((delay) => {
      setTimeout(() => {
        [140, 210].forEach((freq) => {
          const osc = ctx.createOscillator();
          const gain = ctx.createGain();

          osc.type = "sawtooth";
          osc.frequency.setValueAtTime(freq, ctx.currentTime);

          gain.gain.setValueAtTime(0.22, ctx.currentTime);
          gain.gain.linearRampToValueAtTime(0.0001, ctx.currentTime + 0.18);

          osc.connect(gain);
          gain.connect(ctx.destination);

          osc.start(ctx.currentTime);
          osc.stop(ctx.currentTime + 0.18);
        });
      }, delay * 1000);
    });
  } catch (_) { }
}

export function playChime() {
  if (!state || !state.audioEnabled) return;
  haptic([25, 40, 25, 40, 50]);
  try {
    const ctx = getAudioContext();
    if (!ctx) return;
    const notes = [523.25, 659.25, 783.99, 1046.5];
    notes.forEach((freq, idx) => {
      setTimeout(() => {
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.type = "triangle";
        osc.frequency.setValueAtTime(freq, ctx.currentTime);
        gain.gain.setValueAtTime(0.18, ctx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + 0.35);
        osc.connect(gain);
        gain.connect(ctx.destination);
        osc.start();
        osc.stop(ctx.currentTime + 0.35);
      }, idx * 100);
    });
  } catch (_) { }
}

export function playPinDropSound() {
  if (!state || !state.audioEnabled) return;
  haptic(12);
  try {
    const ctx = getAudioContext();
    if (!ctx) return;
    if (ctx.state === "suspended") {
      ctx.resume().catch(() => { });
    }
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.type = "sine";
    osc.frequency.setValueAtTime(440, ctx.currentTime);
    osc.frequency.exponentialRampToValueAtTime(180, ctx.currentTime + 0.08);

    gain.gain.setValueAtTime(0.25, ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.08);

    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.start(ctx.currentTime);
    osc.stop(ctx.currentTime + 0.08);
  } catch (_) { }
}

let lastScoreTickAudioTime = 0;

export function playScoreRollupTick(progress = 0) {
  if (!state || !state.audioEnabled) return;
  const now = typeof performance !== "undefined" ? performance.now() : Date.now();
  if (now - lastScoreTickAudioTime < 35) return;
  lastScoreTickAudioTime = now;

  try {
    const ctx = getAudioContext();
    if (!ctx) return;
    if (ctx.state === "suspended") {
      ctx.resume().catch(() => { });
    }
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.type = "triangle";
    const clampedProgress = Math.max(0, Math.min(1, Number(progress) || 0));
    const baseFreq = 580 + clampedProgress * 520;
    osc.frequency.setValueAtTime(baseFreq, ctx.currentTime);

    gain.gain.setValueAtTime(0.08, ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.035);

    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.start(ctx.currentTime);
    osc.stop(ctx.currentTime + 0.035);
  } catch (_) { }
}

export function playVictoryFanfare() {
  if (!state || !state.audioEnabled) return;
  haptic([35, 70, 35, 70, 100]);
  try {
    const ctx = getAudioContext();
    if (!ctx) return;

    const notes = [
      { freq: 349.23, delay: 0, duration: 0.18 },
      { freq: 440.0, delay: 0.10, duration: 0.18 },
      { freq: 523.25, delay: 0.24, duration: 0.18 },
      { freq: 698.46, delay: 0.36, duration: 0.65 },
    ];

    notes.forEach((n) => {
      setTimeout(() => {
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.type = "triangle";
        osc.frequency.setValueAtTime(n.freq, ctx.currentTime);

        gain.gain.setValueAtTime(0.20, ctx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + n.duration);

        osc.connect(gain);
        gain.connect(ctx.destination);

        osc.start();
        osc.stop(ctx.currentTime + n.duration);
      }, n.delay * 1000);
    });
  } catch (_) { }
}

export function toggleAudio() {
  unlockAudioContext();
  state.audioEnabled = !state.audioEnabled;
  localStorage.setItem("immich_quiz_audio", state.audioEnabled ? "1" : "0");
  updateAudioUi();
  if (state.audioEnabled) {
    playTone(600, "sine", 0.08, 0.1);
  }
}

export function updateAudioUi() {
  if (el.audioIcon) {
    el.audioIcon.textContent = state.audioEnabled ? "🔊" : "🔇";
  }
  if (el.audioToggleBtn) {
    const titleText = state.audioEnabled ? t("audio.enabled") : t("audio.muted");
    el.audioToggleBtn.setAttribute("title", titleText);
    el.audioToggleBtn.setAttribute("aria-label", titleText);
  }
}

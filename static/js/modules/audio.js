import { state, el } from "./state.js";

let audioCtx = null;

export function unlockAudioContext() {
  if (!audioCtx) {
    const AudioContextClass = window.AudioContext || window.webkitAudioContext;
    if (AudioContextClass) {
      audioCtx = new AudioContextClass();
    }
  }
  if (audioCtx && audioCtx.state === "suspended") {
    audioCtx.resume().catch(() => {});
  }
}

document.addEventListener("pointerdown", unlockAudioContext, { capture: true });
document.addEventListener("keydown", unlockAudioContext, { capture: true });

export function getAudioContext() {
  unlockAudioContext();
  return audioCtx;
}

export function playTone(freq, type, duration, gainValue = 0.15) {
  if (!state || !state.audioEnabled) return;
  try {
    const ctx = getAudioContext();
    if (!ctx) return;
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();

    osc.type = type;
    osc.frequency.setValueAtTime(freq, ctx.currentTime);

    gain.gain.setValueAtTime(gainValue, ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + duration);

    osc.connect(gain);
    gain.connect(ctx.destination);

    osc.start();
    osc.stop(ctx.currentTime + duration);
  } catch (_) {
    // Ignore audio autoplay restrictions
  }
}

export function playTick() {
  playTone(800, "sine", 0.05, 0.08);
}

export function playBuzzer() {
  playTone(220, "sawtooth", 0.4, 0.12);
}

export function playChime() {
  if (!state || !state.audioEnabled) return;
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
  } catch (_) {}
}

export function playVictoryFanfare() {
  if (!state || !state.audioEnabled) return;
  try {
    const ctx = getAudioContext();
    if (!ctx) return;

    const notes = [
      { freq: 349.23, delay: 0, duration: 0.18 },
      { freq: 440.0, delay: 0.12, duration: 0.18 },
      { freq: 523.25, delay: 0.24, duration: 0.18 },
      { freq: 698.46, delay: 0.36, duration: 0.65 },
    ];

    notes.forEach((n) => {
      setTimeout(() => {
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.type = "triangle";
        osc.frequency.setValueAtTime(n.freq, ctx.currentTime);

        gain.gain.setValueAtTime(0.22, ctx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + n.duration);

        osc.connect(gain);
        gain.connect(ctx.destination);

        osc.start();
        osc.stop(ctx.currentTime + n.duration);
      }, n.delay * 1000);
    });
  } catch (_) {}
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
    el.audioToggleBtn.setAttribute(
      "title",
      state.audioEnabled ? "Sound Effects: Enabled" : "Sound Effects: Muted"
    );
  }
}

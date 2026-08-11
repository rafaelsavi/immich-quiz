import { state, el } from "./modules/state.js";
import {
  playTone,
  playSubmitTone,
  playTick,
  playBuzzer,
  playChime,
  playVictoryFanfare,
  playPinDropSound,
  playScoreRollupTick,
  toggleAudio,
  unlockAudioContext,
  getAudioContext,
  updateAudioUi,
} from "./modules/audio.js";

// DOM Elements
const audioEnabledBadge = document.getElementById("audio-enabled-badge");
const audioCtxBadge = document.getElementById("audio-ctx-badge");
const unlockAudioBtn = document.getElementById("unlock-audio-btn");

const playTickBtn = document.getElementById("play-tick-btn");
const playSubmitBtn = document.getElementById("play-submit-btn");
const playBuzzerBtn = document.getElementById("play-buzzer-btn");
const playChimeBtn = document.getElementById("play-chime-btn");
const playFanfareBtn = document.getElementById("play-fanfare-btn");
const playPinBtn = document.getElementById("play-pin-btn");
const playRollupBtn = document.getElementById("play-rollup-btn");

const synthFreq = document.getElementById("synth-freq");
const synthFreqNum = document.getElementById("synth-freq-num");
const synthType = document.getElementById("synth-type");
const synthDuration = document.getElementById("synth-duration");
const synthDurationNum = document.getElementById("synth-duration-num");
const synthGain = document.getElementById("synth-gain");
const synthGainNum = document.getElementById("synth-gain-num");
const playCustomBtn = document.getElementById("play-custom-btn");

const simClickBtn = document.getElementById("sim-click");
const simWrongBtn = document.getElementById("sim-wrong");
const simCorrectBtn = document.getElementById("sim-correct");
const simVictoryBtn = document.getElementById("sim-victory");
const simToggleBtn = document.getElementById("sim-toggle");

const countdownSecondsInput = document.getElementById("countdown-seconds");
const startCountdownBtn = document.getElementById("start-countdown-btn");
const resetCountdownBtn = document.getElementById("reset-countdown-btn");
const countdownDisplay = document.getElementById("countdown-display");
const countdownStatus = document.getElementById("countdown-status");
const countdownFill = document.getElementById("countdown-fill");

const logBody = document.getElementById("log-body");
const clearLogBtn = document.getElementById("clear-log-btn");

const visualizerCanvas = document.getElementById("visualizer-canvas");
const canvasCtx = visualizerCanvas.getContext("2d");

// State & Animation
let logCount = 0;
let visualPulse = 0;
let visualFreq = 440;
let visualType = "sine";
let countdownTimerId = null;
let countdownTotalSeconds = 10;
let countdownRemainingSeconds = 10;

function logEvent(fnName, details) {
  if (!logBody) return;
  if (logCount === 0) {
    logBody.innerHTML = "";
  }
  logCount++;

  const timeStr = new Date().toLocaleTimeString([], {
    hour12: false,
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    fractionalSecondDigits: 3,
  });

  const isMuted = !state.audioEnabled;
  const row = document.createElement("tr");
  row.innerHTML = `
    <td>${timeStr}</td>
    <td><strong>${fnName}</strong></td>
    <td>${details}</td>
    <td>${isMuted ? '<span style="color:#c5221f;">🔇 Muted</span>' : '<span style="color:#107c41;">🔊 Active</span>'}</td>
  `;

  logBody.prepend(row);
  updateStatusBadges();
}

function updateStatusBadges() {
  const isEnabled = state.audioEnabled;
  if (audioEnabledBadge) {
    audioEnabledBadge.className = `badge ${isEnabled ? "badge-running" : "badge-muted"}`;
    audioEnabledBadge.textContent = isEnabled ? "🔊 Enabled" : "🔇 Muted";
  }

  const ctx = getAudioContext();
  const ctxState = ctx ? ctx.state : "uninitialized";
  if (audioCtxBadge) {
    if (ctxState === "running") {
      audioCtxBadge.className = "badge badge-running";
      audioCtxBadge.textContent = `AudioContext: running (${ctx.sampleRate}Hz)`;
    } else {
      audioCtxBadge.className = "badge badge-suspended";
      audioCtxBadge.textContent = `AudioContext: ${ctxState}`;
    }
  }
}

// Visualizer animation
function triggerVisualizer(freq = 440, type = "sine", duration = 0.3) {
  visualPulse = Math.max(visualPulse, duration * 60);
  visualFreq = freq;
  visualType = type;
}

function drawVisualizer() {
  requestAnimationFrame(drawVisualizer);
  if (!canvasCtx || !visualizerCanvas) return;

  const width = visualizerCanvas.width;
  const height = visualizerCanvas.height;

  canvasCtx.fillStyle = "#0f1522";
  canvasCtx.fillRect(0, 0, width, height);

  // Grid lines
  canvasCtx.strokeStyle = "rgba(255, 255, 255, 0.05)";
  canvasCtx.lineWidth = 1;
  for (let x = 0; x < width; x += 40) {
    canvasCtx.beginPath();
    canvasCtx.moveTo(x, 0);
    canvasCtx.lineTo(x, height);
    canvasCtx.stroke();
  }

  // Baseline
  canvasCtx.strokeStyle = "rgba(124, 232, 226, 0.2)";
  canvasCtx.beginPath();
  canvasCtx.moveTo(0, height / 2);
  canvasCtx.lineTo(width, height / 2);
  canvasCtx.stroke();

  if (visualPulse <= 0) return;
  visualPulse -= 1;

  const amplitude = Math.min(60, visualPulse * 2.5);
  canvasCtx.lineWidth = 2.5;
  canvasCtx.strokeStyle = visualType === "sawtooth" ? "#f25f5c" : "#7ce8e2";
  canvasCtx.beginPath();

  const cycles = Math.max(2, Math.min(25, visualFreq / 80));
  for (let x = 0; x < width; x++) {
    const t = (x / width) * cycles * Math.PI * 2;
    let y = height / 2;

    if (visualType === "sine") {
      y += Math.sin(t) * amplitude;
    } else if (visualType === "square") {
      y += (Math.sin(t) >= 0 ? 1 : -1) * amplitude;
    } else if (visualType === "sawtooth") {
      y += (((t / (Math.PI * 2)) % 1) - 0.5) * 2 * amplitude;
    } else if (visualType === "triangle") {
      y += (Math.abs(((t / (Math.PI * 2)) % 1) - 0.5) * 4 - 1) * amplitude;
    }

    if (x === 0) {
      canvasCtx.moveTo(x, y);
    } else {
      canvasCtx.lineTo(x, y);
    }
  }

  canvasCtx.stroke();
}

// Preset sound triggers
function setupPresets() {
  if (playTickBtn) {
    playTickBtn.addEventListener("click", () => {
      unlockAudioContext();
      playTick();
      triggerVisualizer(620, "sine", 0.09);
      logEvent("playTick()", "520 ➔ 720 Hz • Sine • 0.09s");
    });
  }

  if (playSubmitBtn) {
    playSubmitBtn.addEventListener("click", () => {
      unlockAudioContext();
      playSubmitTone();
      triggerVisualizer(480, "sine", 0.08);
      logEvent("playSubmitTone()", "480 Hz • Sine • 0.08s • Gain 0.12");
    });
  }

  if (playBuzzerBtn) {
    playBuzzerBtn.addEventListener("click", () => {
      unlockAudioContext();
      playBuzzer();
      triggerVisualizer(220, "sawtooth", 0.4);
      logEvent("playBuzzer()", "220 Hz • Sawtooth • 0.4s");
    });
  }

  if (playChimeBtn) {
    playChimeBtn.addEventListener("click", () => {
      unlockAudioContext();
      playChime();
      triggerVisualizer(659, "triangle", 0.65);
      logEvent("playChime()", "Arpeggio [523, 659, 783, 1046 Hz] • Triangle");
    });
  }

  if (playFanfareBtn) {
    playFanfareBtn.addEventListener("click", () => {
      unlockAudioContext();
      playVictoryFanfare();
      triggerVisualizer(523, "triangle", 1.0);
      logEvent("playVictoryFanfare()", "Fanfare [349, 440, 523, 698 Hz] • Triangle");
    });
  }

  if (playPinBtn) {
    playPinBtn.addEventListener("click", () => {
      unlockAudioContext();
      playPinDropSound();
      triggerVisualizer(320, "sine", 0.08);
      logEvent("playPinDropSound()", "440 ➔ 180 Hz • Sine • 0.08s");
    });
  }

  if (playRollupBtn) {
    playRollupBtn.addEventListener("click", () => {
      unlockAudioContext();
      let stepCount = 0;
      const interval = setInterval(() => {
        const progress = stepCount / 10;
        playScoreRollupTick(progress);
        triggerVisualizer(580 + progress * 520, "triangle", 0.035);
        stepCount++;
        if (stepCount > 10) clearInterval(interval);
      }, 50);
      logEvent("playScoreRollupTick()", "580 ➔ 1100 Hz • Ascending ticker sequence");
    });
  }
}

// Custom Synthesizer Controls
function setupSynth() {
  function syncInputs(slider, numInput) {
    slider.addEventListener("input", () => {
      numInput.value = slider.value;
    });
    numInput.addEventListener("input", () => {
      slider.value = numInput.value;
    });
  }

  if (synthFreq && synthFreqNum) syncInputs(synthFreq, synthFreqNum);
  if (synthDuration && synthDurationNum) syncInputs(synthDuration, synthDurationNum);
  if (synthGain && synthGainNum) syncInputs(synthGain, synthGainNum);

  document.querySelectorAll(".pitch-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      const freq = btn.getAttribute("data-freq");
      if (freq && synthFreq && synthFreqNum) {
        synthFreq.value = freq;
        synthFreqNum.value = freq;
      }
    });
  });

  if (playCustomBtn) {
    playCustomBtn.addEventListener("click", () => {
      unlockAudioContext();
      const freq = parseFloat(synthFreqNum.value) || 440;
      const type = synthType.value || "sine";
      const duration = parseFloat(synthDurationNum.value) || 0.25;
      const gain = parseFloat(synthGainNum.value) || 0.15;

      playTone(freq, type, duration, gain);
      triggerVisualizer(freq, type, duration);
      logEvent("playTone()", `${freq} Hz • ${type} • ${duration}s • Vol ${gain}`);
    });
  }
}

// Simulator Actions
function updateCountdownUi() {
  if (!countdownDisplay || !countdownStatus || !countdownFill) return;

  const remaining = Math.max(countdownRemainingSeconds, 0);
  countdownDisplay.textContent = `${remaining}s`;
  const ratio = countdownTotalSeconds > 0 ? remaining / countdownTotalSeconds : 1;
  countdownFill.style.width = `${Math.max(0, ratio * 100)}%`;
  countdownFill.classList.toggle("is-warning", remaining > 0 && remaining <= 5);
  countdownFill.classList.toggle("is-critical", remaining <= 0);

  if (remaining <= 0) {
    countdownStatus.textContent = "Time is up";
  } else if (countdownTimerId) {
    countdownStatus.textContent = "Running";
  } else {
    countdownStatus.textContent = "Idle";
  }
}

function stopCountdownTimer() {
  if (countdownTimerId) {
    clearInterval(countdownTimerId);
    countdownTimerId = null;
  }
}

function resetCountdownTimer() {
  stopCountdownTimer();
  const parsed = parseInt(countdownSecondsInput?.value || "10", 10);
  countdownTotalSeconds = Number.isFinite(parsed) ? Math.max(1, Math.min(60, parsed)) : 10;
  countdownRemainingSeconds = countdownTotalSeconds;
  updateCountdownUi();
}

function setupCountdownTimer() {
  if (startCountdownBtn) {
    startCountdownBtn.addEventListener("click", () => {
      unlockAudioContext();
      stopCountdownTimer();
      resetCountdownTimer();
      countdownStatus.textContent = "Running";
      countdownTimerId = setInterval(() => {
        countdownRemainingSeconds -= 1;
        const clamped = Math.max(countdownRemainingSeconds, 0);
        updateCountdownUi();

        if (clamped > 0) {
          playTick(clamped);
          triggerVisualizer(520 + (5 - clamped) * 50, "sine", 0.09);
        } else {
          stopCountdownTimer();
          playBuzzer();
          triggerVisualizer(220, "sawtooth", 0.4);
          logEvent("Countdown Demo", "Timer reached zero");
        }
      }, 1000);
      logEvent("Countdown Demo", `Started ${countdownTotalSeconds}s countdown`);
    });
  }

  if (resetCountdownBtn) {
    resetCountdownBtn.addEventListener("click", () => {
      resetCountdownTimer();
      logEvent("Countdown Demo", "Reset countdown");
    });
  }

  if (countdownSecondsInput) {
    countdownSecondsInput.addEventListener("change", () => {
      resetCountdownTimer();
    });
  }

  resetCountdownTimer();
}

function setupSimulators() {
  if (simClickBtn) {
    simClickBtn.addEventListener("click", () => {
      unlockAudioContext();
      playTick();
      triggerVisualizer(800, "sine", 0.05);
      logEvent("Simulated Click", "Selection sound triggered");
    });
  }

  if (simWrongBtn) {
    simWrongBtn.addEventListener("click", () => {
      unlockAudioContext();
      playBuzzer();
      triggerVisualizer(220, "sawtooth", 0.4);
      logEvent("Simulated Wrong Answer", "Buzzer sound triggered");
    });
  }

  if (simCorrectBtn) {
    simCorrectBtn.addEventListener("click", () => {
      unlockAudioContext();
      playChime();
      triggerVisualizer(659, "triangle", 0.65);
      logEvent("Simulated Perfect Answer", "Chime chord sequence triggered");
    });
  }

  if (simVictoryBtn) {
    simVictoryBtn.addEventListener("click", () => {
      unlockAudioContext();
      playVictoryFanfare();
      triggerVisualizer(523, "triangle", 1.0);
      logEvent("Simulated Game Won", "Victory fanfare sequence triggered");
    });
  }

  if (simToggleBtn) {
    simToggleBtn.addEventListener("click", () => {
      toggleAudio();
      logEvent("toggleAudio()", `Audio state toggled to ${state.audioEnabled ? "Enabled" : "Muted"}`);
    });
  }
}

// Global UI setup
function setupGlobal() {
  if (el.audioToggleBtn) {
    el.audioToggleBtn.addEventListener("click", () => {
      toggleAudio();
      logEvent("toggleAudio()", `Global audio toggled to ${state.audioEnabled ? "Enabled" : "Muted"}`);
    });
  }

  if (unlockAudioBtn) {
    unlockAudioBtn.addEventListener("click", () => {
      unlockAudioContext();
      const ctx = getAudioContext();
      if (ctx && ctx.state === "suspended") {
        ctx.resume();
      }
      logEvent("unlockAudioContext()", "Explicit AudioContext resume requested");
    });
  }

  if (clearLogBtn) {
    clearLogBtn.addEventListener("click", () => {
      logCount = 0;
      if (logBody) {
        logBody.innerHTML = '<tr><td colspan="4" style="text-align: center; color: #888;">Log cleared.</td></tr>';
      }
    });
  }

  updateAudioUi();
  updateStatusBadges();

  document.addEventListener("pointerdown", updateStatusBadges);
  document.addEventListener("keydown", updateStatusBadges);
}

// Initialize on DOM ready
document.addEventListener("DOMContentLoaded", () => {
  setupPresets();
  setupSynth();
  setupCountdownTimer();
  setupSimulators();
  setupGlobal();
  drawVisualizer();
});

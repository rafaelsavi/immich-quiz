import { state, el } from "./state.js";
import { t, showAlert } from "./i18n.js";
import { playerInitial, playerColor, ACTUAL_COLOR } from "./formatters.js";

export function updateSubmitState() {
  if (state.submitting) {
    el.submitAnswer.disabled = true;
    return;
  }

  // After a timeout the answers are frozen, but the player still has to
  // acknowledge the reveal before the screen moves on.
  if (state.timedOut) {
    el.submitAnswer.disabled = false;
    el.submitAnswer.removeAttribute("title");
    return;
  }

  const needsPin = Boolean(state.currentQuestion && state.currentQuestion.location_mode);
  const missingPin = needsPin && !state.guessedLatLng;
  el.submitAnswer.disabled = !state.currentQuestion || missingPin;
  if (missingPin) {
    el.submitAnswer.title = t("game.pin_required");
  } else {
    el.submitAnswer.removeAttribute("title");
  }
}

export function createPinIcon(label, color) {
  return L.divIcon({
    className: "player-pin",
    html: `<span style="background:${color}"><b>${label}</b></span>`,
    iconSize: [28, 28],
    iconAnchor: [14, 28],
    popupAnchor: [0, -26],
  });
}

export function ensureGuessMap() {
  if (state.guessMap) {
    state.guessMap.invalidateSize();
    return;
  }

  state.guessMap = L.map("guess-map", { worldCopyJump: true }).setView([20, 0], 2);
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19,
    attribution: "&copy; OpenStreetMap",
  }).addTo(state.guessMap);

  state.guessMap.on("click", (event) => {
    if (state.timedOut || state.submitting) {
      return;
    }
    // Normalize longitude to [-180, 180] so clicks on repeated world copies
    // always resolve to canonical coordinates, avoiding mismatched pin placement.
    const lat = event.latlng.lat;
    const lng = (((event.latlng.lng + 180) % 360) + 360) % 360 - 180;
    state.guessedLatLng = L.latLng(lat, lng);
    const player = state.currentQuestion ? state.currentQuestion.player_name : "";
    const icon = createPinIcon(playerInitial(player), playerColor(player));
    if (state.guessMarker) {
      state.guessMarker.remove();
    }
    state.guessMarker = L.marker([lat, lng], { icon }).addTo(state.guessMap);
    updateSubmitState();
  });

  // The container was hidden while Leaflet measured it, so re-measure once
  // the browser has painted the visible layout.
  requestAnimationFrame(() => state.guessMap.invalidateSize());
}

export function ensureRevealMap() {
  if (!state.revealMap) {
    state.revealMap = L.map("reveal-map").setView([20, 0], 2);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
      attribution: "&copy; OpenStreetMap",
    }).addTo(state.revealMap);
  }
  requestAnimationFrame(() => state.revealMap.invalidateSize());
}

export function toggleMapFullscreen(shell) {
  const request =
    document.fullscreenElement === shell ? document.exitFullscreen() : shell.requestFullscreen();
  Promise.resolve(request).catch((err) => showAlert(t("game.fullscreen_error", err.message)));
}

export function syncFullscreenButtons() {
  [
    [el.mediaFrame, el.quizImageFullscreen],
    [el.guessMapShell, el.guessMapFullscreen],
    [el.revealMapShell, el.revealMapFullscreen],
  ].forEach(([shell, button]) => {
    const isActive = document.fullscreenElement === shell;
    button.textContent = isActive ? t("game.fullscreen_exit_btn") : t("game.fullscreen_btn");
    button.setAttribute("aria-pressed", isActive ? "true" : "false");
  });
}

import { state, el } from "./state.js";
import { t, showAlert } from "./i18n.js";
import { playerInitial, playerColor, ACTUAL_COLOR } from "./formatters.js";
import { playPinDropSound } from "./audio.js";

export function createBaseTileLayers() {
  const streets = L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19,
    attribution: "&copy; OpenStreetMap",
  });
  const satellite = L.tileLayer(
    "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
    {
      maxZoom: 19,
      attribution:
        "Tiles &copy; Esri &mdash; Source: Esri, i-cubed, USDA, USGS, AEX, GeoEye, Getmapping, Aerogrid, IGN, IGP, UPR-EGP, and GIS User Community",
    }
  );
  return { streets, satellite };
}

export function addLayerControl(map, baseLayers) {
  L.control
    .layers({
      [t("map.layer_streets")]: baseLayers.streets,
      [t("map.layer_satellite")]: baseLayers.satellite,
    })
    .addTo(map);
}

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

  if (state.currentQuestion && state.currentQuestion.game_mode === "album_shuffle") {
    const pinAssignments = state.albumShuffleState ? state.albumShuffleState.pinAssignments || {} : {};
    const totalPhotos = (state.currentQuestion.batch_photos || []).length;
    const assignedCount = Object.values(pinAssignments).filter(Boolean).length;
    const missingPin = totalPhotos > 0 && assignedCount < totalPhotos;
    el.submitAnswer.disabled = !state.currentQuestion || missingPin;
    if (missingPin) {
      el.submitAnswer.title = t("game.pin_required");
    } else {
      el.submitAnswer.removeAttribute("title");
    }
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

export function spawnPinPulseEffect(map, latlng, color) {
  if (!map) return;
  const circle = L.circleMarker(latlng, {
    radius: 10,
    color: color || "#2563eb",
    fillColor: color || "#2563eb",
    fillOpacity: 0.5,
    weight: 3,
  }).addTo(map);

  let start = null;
  const duration = 550;
  function animatePulse(timestamp) {
    if (!start) start = timestamp;
    const progress = (timestamp - start) / duration;
    if (progress < 1) {
      circle.setRadius(10 + progress * 25);
      circle.setStyle({ fillOpacity: 0.6 * (1 - progress), opacity: 1 - progress });
      requestAnimationFrame(animatePulse);
    } else {
      circle.remove();
    }
  }
  requestAnimationFrame(animatePulse);
}

export function ensureGuessMap() {
  if (state.guessMap) {
    state.guessMap.invalidateSize();
    return;
  }

  const base = createBaseTileLayers();
  state.guessMap = L.map("guess-map", { worldCopyJump: true, layers: [base.streets] }).setView([20, 0], 2);
  addLayerControl(state.guessMap, base);

  state.guessMap.on("click", (event) => {
    if (state.timedOut || state.submitting) {
      return;
    }
    // Normalize longitude to [-180, 180] so clicks on repeated world copies
    // always resolve to canonical coordinates, avoiding mismatched pin placement.
    const lat = event.latlng.lat;
    const lng = (((event.latlng.lng + 180) % 360) + 360) % 360 - 180;
    const clickLatLng = L.latLng(lat, lng);
    state.guessedLatLng = clickLatLng;
    const player = state.currentQuestion ? state.currentQuestion.player_name : "";
    const color = playerColor(player);
    const icon = createPinIcon(playerInitial(player), color);
    if (state.guessMarker) {
      state.guessMarker.remove();
    }
    state.guessMarker = L.marker([lat, lng], { icon }).addTo(state.guessMap);

    playPinDropSound();
    spawnPinPulseEffect(state.guessMap, clickLatLng, color);

    updateSubmitState();
  });

  // The container was hidden while Leaflet measured it, so re-measure once
  // the browser has painted the visible layout.
  requestAnimationFrame(() => state.guessMap.invalidateSize());
}

export function ensureRevealMap() {
  if (!state.revealMap) {
    const base = createBaseTileLayers();
    state.revealMap = L.map("reveal-map", { layers: [base.streets] }).setView([20, 0], 2);
    addLayerControl(state.revealMap, base);
  }
  requestAnimationFrame(() => state.revealMap.invalidateSize());
}

export function ensureJourneyMap() {
  if (!state.journeyMap) {
    const base = createBaseTileLayers();
    state.journeyMap = L.map("journey-map", { layers: [base.streets] }).setView([20, 0], 2);
    addLayerControl(state.journeyMap, base);
  }
  requestAnimationFrame(() => state.journeyMap.invalidateSize());
}

export function renderJourneyMap(roundHistory) {
  const validRounds = (roundHistory || []).filter(
    (r) => r.actual_latitude !== null && r.actual_longitude !== null
  );

  if (!el.journeyMapShell || !el.journeyMapHead) return;

  if (validRounds.length === 0) {
    el.journeyMapShell.classList.add("hidden");
    el.journeyMapHead.classList.add("hidden");
    return;
  }

  el.journeyMapShell.classList.remove("hidden");
  el.journeyMapHead.classList.remove("hidden");
  ensureJourneyMap();

  // Clear old layers
  state.journeyLayers.forEach((layer) => state.journeyMap.removeLayer(layer));
  state.journeyLayers = [];

  const points = [];
  validRounds.forEach((round) => {
    const latLng = L.latLng(round.actual_latitude, round.actual_longitude);
    points.push(latLng);

    const marker = L.marker(latLng, {
      icon: createPinIcon(String(round.round_number), ACTUAL_COLOR),
    })
      .addTo(state.journeyMap)
      .bindPopup(
        `<b>${t("summary.journey_round", round.round_number)}</b><br>${round.location_string || ""}`
      );
    state.journeyLayers.push(marker);
  });

  if (points.length > 0) {
    const bounds = L.latLngBounds(points);
    state.journeyMap.fitBounds(bounds, { padding: [40, 40] });
  }

  requestAnimationFrame(() => state.journeyMap.invalidateSize());
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
    [el.journeyMapShell, el.journeyMapFullscreen],
  ].forEach(([shell, button]) => {
    if (!shell || !button) return;
    const isActive = document.fullscreenElement === shell;
    button.textContent = isActive ? t("game.fullscreen_exit_btn") : t("game.fullscreen_btn");
    button.setAttribute("aria-pressed", isActive ? "true" : "false");
  });
}

import { state, el } from "./state.js";
import { t, showAlert } from "./i18n.js";
import { playerInitial, playerColor, ACTUAL_COLOR, formatPlace } from "./formatters.js";
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
  if (!map) return null;

  if (map._layerControl) {
    try {
      map.removeControl(map._layerControl);
    } catch (_) {}
    map._layerControl = null;
  }

  const base = baseLayers || map._baseLayers;
  if (!base) return null;
  map._baseLayers = base;

  const control = L.control
    .layers({
      [t("map.layer_streets")]: base.streets,
      [t("map.layer_satellite")]: base.satellite,
    })
    .addTo(map);

  map._layerControl = control;

  if (control._container) {
    const toggleBtn = control._container.querySelector(".leaflet-control-layers-toggle");
    if (toggleBtn) {
      const titleText = t("map.layer_control_title");
      toggleBtn.title = titleText;
      toggleBtn.setAttribute("aria-label", titleText);
    }

    const updateActiveLabels = () => {
      const labels = control._container.querySelectorAll(".leaflet-control-layers-expanded label");
      labels.forEach((label) => {
        const input = label.querySelector("input");
        if (input && input.checked) {
          label.classList.add("active");
        } else {
          label.classList.remove("active");
        }
      });
    };

    control._container.addEventListener("change", updateActiveLabels);
    control._container.addEventListener("click", updateActiveLabels);
    setTimeout(updateActiveLabels, 0);
  }

  return control;
}

export function updateSubmitState() {
  const nextRoundBtns = document.querySelectorAll("#next-round, button.next-round-btn");
  if (state.submitting) {
    if (el.submitAnswer) el.submitAnswer.disabled = true;
    nextRoundBtns.forEach((btn) => (btn.disabled = true));
    return;
  }
  nextRoundBtns.forEach((btn) => (btn.disabled = false));

  // After a timeout the answers are frozen, but the player still has to
  // acknowledge the reveal before the screen moves on.
  if (state.timedOut) {
    if (el.submitAnswer) {
      el.submitAnswer.disabled = false;
      el.submitAnswer.removeAttribute("title");
    }
    return;
  }

  if (state.currentQuestion && state.currentQuestion.game_mode === "album_shuffle") {
    const needsPin = Boolean(state.currentQuestion.location_mode);
    const pinAssignments = state.albumShuffleState ? state.albumShuffleState.pinAssignments || {} : {};
    const totalPhotos = (state.currentQuestion.batch_photos || []).length;
    const assignedCount = Object.values(pinAssignments).filter(Boolean).length;
    const missingPin = needsPin && totalPhotos > 0 && assignedCount < totalPhotos;
    if (el.submitAnswer) {
      el.submitAnswer.disabled = !state.currentQuestion || missingPin;
      if (missingPin) {
        el.submitAnswer.title = t("game.pin_required");
      } else {
        el.submitAnswer.removeAttribute("title");
      }
    }
    return;
  }

  const needsPin = Boolean(state.currentQuestion && state.currentQuestion.location_mode);
  const missingPin = needsPin && !state.guessedLatLng;
  if (el.submitAnswer) {
    el.submitAnswer.disabled = !state.currentQuestion || missingPin;
    if (missingPin) {
      el.submitAnswer.title = t("game.pin_required");
    } else {
      el.submitAnswer.removeAttribute("title");
    }
  }
}

export function createPinIcon(label, color) {
  const isLong = String(label).length > 2;
  const fontSize = isLong ? (String(label).length > 3 ? "0.7rem" : "0.75rem") : "0.85rem";
  const size = isLong ? 32 : 28;
  const anchor = size / 2;
  return L.divIcon({
    className: "player-pin",
    html: `<span style="background:${color};width:${size}px;height:${size}px;font-size:${fontSize};"><b>${label}</b></span>`,
    iconSize: [size, size],
    iconAnchor: [anchor, size],
    popupAnchor: [0, -size + 2],
  });
}

export function createPopPinIcon(label, color) {
  return L.divIcon({
    className: "player-pin player-pin-pop",
    html: `<span style="background:${color};"><b>${label}</b></span>`,
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

export function ensureMapFullscreenButton(shell, titleKey = "game.fullscreen_map_title") {
  if (!shell) return null;
  let btn = shell.querySelector(".map-fullscreen-btn");
  if (!btn) {
    btn = createMapFullscreenButton(shell, titleKey);
    shell.appendChild(btn);
  } else {
    const hasIcon = btn.querySelector(".fs-icon");
    if (!hasIcon) {
      btn.innerHTML = `
        <svg class="fs-icon" viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round">
          <polyline points="15 3 21 3 21 9"></polyline>
          <polyline points="9 21 3 21 3 15"></polyline>
          <line x1="21" y1="3" x2="14" y2="10"></line>
          <line x1="3" y1="21" x2="10" y2="14"></line>
        </svg>
      `;
    } else {
      const textSpan = btn.querySelector("[data-i18n]");
      if (textSpan) textSpan.remove();
    }
  }
  btn.classList.add("leaflet-control");
  const tryMove = () => {
    const rightCorner = shell.querySelector(".leaflet-top.leaflet-right");
    if (rightCorner && btn.parentElement !== rightCorner) {
      rightCorner.prepend(btn);
    }
  };
  tryMove();
  requestAnimationFrame(tryMove);
  setTimeout(tryMove, 50);
  return btn;
}

export function ensureGuessMap() {
  const container = document.getElementById("guess-map");
  if (!container) return;

  const shell = container.closest(".map-shell");

  if (!state.guessMap) {
    const base = createBaseTileLayers();
    state.guessMap = L.map(container, { worldCopyJump: true, zoomControl: false, layers: [base.streets] }).setView([20, 0], 2);
    L.control.zoom({ position: "topright" }).addTo(state.guessMap);
    addLayerControl(state.guessMap, base);

    state.guessMap.on("click", (event) => {
      if (state.timedOut || state.submitting) {
        return;
      }
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
  }

  if (shell) ensureMapFullscreenButton(shell, "game.fullscreen_map_title");

  requestAnimationFrame(() => {
    if (state.guessMap) state.guessMap.invalidateSize();
  });
}

export function ensureRevealMap() {
  const container = document.getElementById("reveal-map");
  if (!container) return;

  const shell = container.closest(".map-shell");

  if (!state.revealMap) {
    const base = createBaseTileLayers();
    state.revealMap = L.map(container, { zoomControl: false, layers: [base.streets] }).setView([20, 0], 2);
    L.control.zoom({ position: "topright" }).addTo(state.revealMap);
    addLayerControl(state.revealMap, base);
  }

  if (shell) ensureMapFullscreenButton(shell, "game.fullscreen_map_title");

  requestAnimationFrame(() => {
    if (state.revealMap) state.revealMap.invalidateSize();
  });
}

export function ensureJourneyMap() {
  const container = document.getElementById("journey-map");
  if (!container) return;

  const shell = container.closest(".map-shell");

  if (!state.journeyMap) {
    const base = createBaseTileLayers();
    state.journeyMap = L.map(container, { zoomControl: false, layers: [base.streets] }).setView([20, 0], 2);
    L.control.zoom({ position: "topright" }).addTo(state.journeyMap);
    addLayerControl(state.journeyMap, base);
  }

  if (shell) ensureMapFullscreenButton(shell, "game.fullscreen_map_title");

  requestAnimationFrame(() => {
    if (state.journeyMap) state.journeyMap.invalidateSize();
  });
}

export function renderJourneyMap(roundHistory, locationMode = true) {
  if (!el.journeyMapShell || !el.journeyMapHead) return;

  if (!locationMode) {
    el.journeyMapShell.classList.add("hidden");
    el.journeyMapHead.classList.add("hidden");
    return;
  }

  const allPins = [];
  (roundHistory || []).forEach((r) => {
    if (r.batch_reveal && Array.isArray(r.batch_reveal) && r.batch_reveal.length > 0) {
      r.batch_reveal.forEach((item) => {
        if (
          item.actual_latitude !== null &&
          item.actual_latitude !== undefined &&
          item.actual_longitude !== null &&
          item.actual_longitude !== undefined &&
          !(Math.abs(item.actual_latitude) < 1e-6 && Math.abs(item.actual_longitude) < 1e-6)
        ) {
          const locStr = formatPlace(item);
          const dateStr = item.actual_date
            ? new Date(item.actual_date).toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" })
            : "";
          allPins.push({
            label: `${r.round_number}-${item.true_pin_id}`,
            lat: item.actual_latitude,
            lon: item.actual_longitude,
            popupText: `<b>${t("summary.journey_round", r.round_number)} - Pin ${item.true_pin_id}</b><br>${locStr}${dateStr ? `<br>📅 ${dateStr}` : ""}`,
          });
        }
      });
    } else if (
      r.actual_latitude !== null &&
      r.actual_latitude !== undefined &&
      r.actual_longitude !== null &&
      r.actual_longitude !== undefined &&
      !(Math.abs(r.actual_latitude) < 1e-6 && Math.abs(r.actual_longitude) < 1e-6)
    ) {
      allPins.push({
        label: String(r.round_number),
        lat: r.actual_latitude,
        lon: r.actual_longitude,
        popupText: `<b>${t("summary.journey_round", r.round_number)}</b><br>${r.location_string || ""}`,
      });
    }
  });

  if (allPins.length === 0) {
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

  // Group near-duplicate coordinates to apply a small visual offset if pins share exact locations
  const coordCounts = {};
  const processedPins = allPins.map((pin) => {
    const key = `${pin.lat.toFixed(4)},${pin.lon.toFixed(4)}`;
    coordCounts[key] = (coordCounts[key] || 0) + 1;
    const occurrence = coordCounts[key];
    let displayLat = pin.lat;
    let displayLon = pin.lon;
    if (occurrence > 1) {
      const angle = (occurrence - 1) * ((2 * Math.PI) / 5);
      const radius = 0.00025 * Math.sqrt(occurrence);
      displayLat = pin.lat + radius * Math.cos(angle);
      displayLon = pin.lon + radius * Math.sin(angle);
    }
    return { ...pin, displayLat, displayLon };
  });

  const points = [];
  processedPins.forEach((pin) => {
    const latLng = L.latLng(pin.displayLat, pin.displayLon);
    points.push(L.latLng(pin.lat, pin.lon));

    const marker = L.marker(latLng, {
      icon: createPinIcon(pin.label, ACTUAL_COLOR),
    })
      .addTo(state.journeyMap)
      .bindPopup(pin.popupText);
    state.journeyLayers.push(marker);
  });

  if (points.length > 0) {
    fitMapToBounds(state.journeyMap, points, { padding: [50, 50], maxZoom: 15 });
  }
}

export function refitMap(map) {
  if (map && map._lastFitBounds && typeof map._lastFitBounds.isValid === "function" && map._lastFitBounds.isValid()) {
    map.invalidateSize();
    const padding = (map._lastFitOptions && map._lastFitOptions.padding) || [50, 50];
    const maxZoom = (map._lastFitOptions && map._lastFitOptions.maxZoom !== undefined) ? map._lastFitOptions.maxZoom : 15;
    map.fitBounds(map._lastFitBounds, { padding, maxZoom });
  }
}

export function fitMapToBounds(map, pointsOrBounds, options = {}) {
  if (!map || !pointsOrBounds) return;

  let bounds;
  if (Array.isArray(pointsOrBounds)) {
    if (pointsOrBounds.length === 0) return;
    bounds = L.latLngBounds(pointsOrBounds);
  } else if (
    pointsOrBounds instanceof L.LatLngBounds ||
    (typeof pointsOrBounds.isValid === "function" && pointsOrBounds.isValid())
  ) {
    bounds = pointsOrBounds;
  } else {
    return;
  }

  if (!bounds || typeof bounds.isValid !== "function" || !bounds.isValid()) return;

  map._lastFitBounds = bounds;
  map._lastFitOptions = options;

  const padding = options.padding || [50, 50];
  const maxZoom = options.maxZoom !== undefined ? options.maxZoom : 15;

  const doFit = () => {
    if (!map) return;
    map.invalidateSize();
    map.fitBounds(bounds, { padding, maxZoom });
  };

  doFit();
  requestAnimationFrame(() => doFit());
  setTimeout(() => doFit(), 250);
}

export function toggleMapFullscreen(shell) {
  const request =
    document.fullscreenElement === shell ? document.exitFullscreen() : shell.requestFullscreen();
  Promise.resolve(request).catch((err) => showAlert(t("game.fullscreen_error", err.message)));
}

export function updateMapLayerControls(extraMaps = []) {
  const maps = [state.guessMap, state.revealMap, state.journeyMap, ...extraMaps].filter(Boolean);
  maps.forEach((map) => {
    addLayerControl(map);
  });
}

export function createMapFullscreenButton(shell, titleKey = "game.fullscreen_map_title") {
  const btn = document.createElement("button");
  btn.type = "button";
  btn.className = "map-fullscreen-btn leaflet-control";
  btn.setAttribute("aria-pressed", "false");
  btn.title = t(titleKey);
  btn.setAttribute("data-i18n-title", titleKey);
  btn.innerHTML = `
    <svg class="fs-icon" viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round">
      <polyline points="15 3 21 3 21 9"></polyline>
      <polyline points="9 21 3 21 3 15"></polyline>
      <line x1="21" y1="3" x2="14" y2="10"></line>
      <line x1="3" y1="21" x2="10" y2="14"></line>
    </svg>
  `;
  btn.addEventListener("click", () => toggleMapFullscreen(shell));
  return btn;
}

export function syncFullscreenButtons() {
  document.querySelectorAll(".map-fullscreen-btn").forEach((button) => {
    const shell = button.closest(".map-shell, .media-frame");
    const isActive = Boolean(shell && document.fullscreenElement === shell);
    const titleKey = isActive ? "game.fullscreen_exit_btn" : "game.fullscreen_btn";
    button.title = t(titleKey);
    button.setAttribute("data-i18n-title", titleKey);
    button.setAttribute("aria-pressed", isActive ? "true" : "false");
    const textEl = button.querySelector("[data-i18n]");
    if (textEl) textEl.remove();
  });
}

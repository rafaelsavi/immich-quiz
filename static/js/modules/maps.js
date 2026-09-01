import { state, el } from "./state.js";
import { t, showAlert, formatDate } from "./i18n.js";
import { playerInitial, playerColor, ACTUAL_COLOR, formatPlace, formatMonth } from "./formatters.js";
import { playPinDropSound } from "./audio.js";

let journeySpiderLines = {}; // pinLabel -> L.polyline connector line
let journeyTrueCoords = {};  // pinLabel -> { lat, lng } original coordinates

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

/**
 * Update submit and next-round button states according to active game mode
 * and current question answering progress.
 */
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
  let circle;
  try {
    circle = L.circleMarker(latlng, {
      radius: 10,
      color: color || "#2563eb",
      fillColor: color || "#2563eb",
      fillOpacity: 0.5,
      weight: 3,
    }).addTo(map);
  } catch (_) {
    return;
  }

  let start = null;
  const duration = 550;
  function animatePulse(timestamp) {
    if (!circle || !circle._map) return;
    if (!start) start = timestamp;
    const progress = (timestamp - start) / duration;
    if (progress < 1) {
      try {
        circle.setRadius(10 + progress * 25);
        circle.setStyle({ fillOpacity: 0.6 * (1 - progress), opacity: 1 - progress });
        requestAnimationFrame(animatePulse);
      } catch (_) {
        try { circle.remove(); } catch (_) {}
      }
    } else {
      try { circle.remove(); } catch (_) {}
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
  }
  btn.classList.add("leaflet-control");
  if (window.L && L.DomEvent) {
    L.DomEvent.disableClickPropagation(btn);
    L.DomEvent.disableScrollPropagation(btn);
  }
  btn.onclick = (e) => {
    if (e && e.stopPropagation) e.stopPropagation();
    toggleMapFullscreen(shell);
  };
  const tryMove = () => {
    const rightCorner = shell.querySelector(".leaflet-top.leaflet-right");
    if (rightCorner && btn.parentElement !== rightCorner) {
      rightCorner.prepend(btn);
    }
  };
  tryMove();
  requestAnimationFrame(tryMove);
  setTimeout(tryMove, 50);
  syncFullscreenButtons();
  return btn;
}

const activeMapRegistry = new Set();

export function registerActiveMap(map) {
  if (map) {
    activeMapRegistry.add(map);
  }
}

export function unregisterActiveMap(map) {
  if (map) {
    if (map._resizeObserver) {
      try {
        map._resizeObserver.disconnect();
      } catch (_) {}
      map._resizeObserver = null;
    }
    activeMapRegistry.delete(map);
  }
}

export function getActiveMaps() {
  const result = [];
  activeMapRegistry.forEach((map) => {
    if (map && map.getContainer) {
      try {
        const container = map.getContainer();
        if (container && document.body.contains(container)) {
          result.push(map);
        }
      } catch (_) {}
    }
  });
  return result;
}

export function refitAllMaps() {
  getActiveMaps().forEach((map) => {
    refitMap(map);
  });
}

/**
 * Calculates and updates the minimum zoom level so the world map height
 * (256 * 2^zoom) is never smaller than the map canvas/container's pixel height.
 * This prevents the map from zooming out so far that grey bars or vertical
 * repetition appear above and below the world map.
 */
export function updateMapMinZoom(map) {
  if (!map || !map.getContainer) return;
  try {
    const container = map.getContainer();
    if (!container) return;
    const height = container.clientHeight || container.offsetHeight || 0;
    if (height <= 0) return;
    const minZoom = Math.max(1, Math.ceil(Math.log2(height / 256)));
    if (map.getMinZoom() !== minZoom) {
      map.setMinZoom(minZoom);
      if (map.getZoom() < minZoom) {
        map.setZoom(minZoom);
      }
    }
  } catch (_) {}
}

/**
 * Standard factory for instantiating Leaflet maps across the application.
 * Ensures uniform options (worldCopyJump: true, zoomControl: false, dynamic minZoom, maxBounds),
 * top-right zoom control, base layer controls, fullscreen toggle, and registration in activeMapRegistry.
 */
export function createStandardMap(containerOrEl, options = {}) {
  if (!window.L) return null;

  const containerEl = typeof containerOrEl === "string" ? document.getElementById(containerOrEl) : containerOrEl;
  if (!containerEl) return null;

  if (options.existingMap) {
    try {
      if (options.existingMap._resizeObserver) {
        options.existingMap._resizeObserver.disconnect();
      }
      options.existingMap.remove();
      unregisterActiveMap(options.existingMap);
    } catch (_) {}
  }

  const containerHeight = containerEl.clientHeight || containerEl.offsetHeight || 400;
  const initialMinZoom = Math.max(1, Math.ceil(Math.log2(containerHeight / 256)));

  const base = createBaseTileLayers();
  const mapOptions = {
    worldCopyJump: true,
    zoomControl: false,
    minZoom: initialMinZoom,
    maxBounds: [[-85.05112878, -Infinity], [85.05112878, Infinity]],
    layers: [base.streets],
    ...options.leafletOptions,
  };

  const center = options.center || [20, 0];
  const zoom = options.zoom !== undefined ? Math.max(initialMinZoom, options.zoom) : Math.max(initialMinZoom, 2);

  const map = L.map(containerEl, mapOptions).setView(center, zoom);
  map._initialCenter = center;
  map._initialZoom = zoom;

  updateMapMinZoom(map);

  map.on("resize", () => {
    updateMapMinZoom(map);
  });

  if (window.ResizeObserver) {
    const ro = new ResizeObserver(() => {
      updateMapMinZoom(map);
    });
    ro.observe(containerEl);
    map._resizeObserver = ro;
  }

  if (options.zoomControl !== false) {
    L.control.zoom({ position: "topright" }).addTo(map);
  }

  if (options.layerControl !== false) {
    addLayerControl(map, base);
  }

  if (options.resetZoomControl !== false) {
    ensureMapResetZoomButton(map);
  }

  const shell = containerEl.closest ? containerEl.closest(".map-shell") || containerEl : containerEl;
  if (options.fullscreenControl !== false && shell) {
    ensureMapFullscreenButton(shell, options.titleKey || "game.fullscreen_map_title");
  }

  registerActiveMap(map);

  return map;
}

export function createBadgePinIcon(badgeText, color, options = {}) {
  const {
    id = "",
    isTaken = true,
    className = "shuffle-pin-marker",
    extraClasses = "",
    size = 36,
  } = options;

  const isAssignedClass = isTaken ? "assigned" : "unassigned";
  const styleStr = isTaken
    ? `background:${color};color:#ffffff;border:2px solid #ffffff;opacity:1;box-shadow:0 3px 8px rgba(0,0,0,0.35);`
    : `background:#ffffff;color:${color};border:2px solid ${color};opacity:1;box-shadow:0 2px 6px rgba(0,0,0,0.2);`;

  const idAttr = id ? `id="${id}"` : "";
  const anchor = Math.round(size / 2);

  return L.divIcon({
    className: "custom-pin-icon",
    html: `<div ${idAttr} class="${className} ${isAssignedClass} ${extraClasses}" style="${styleStr}">${badgeText}</div>`,
    iconSize: [size, size],
    iconAnchor: [anchor, anchor],
    popupAnchor: [0, -anchor],
  });
}

export function ensureGuessMap() {
  const container = document.getElementById("guess-map");
  if (!container) return;

  const shell = container.closest(".map-shell");

  if (state.guessMap && (!state.guessMap.getContainer || state.guessMap.getContainer() !== container)) {
    try {
      unregisterActiveMap(state.guessMap);
      state.guessMap.remove();
    } catch (_) {}
    state.guessMap = null;
  }

  if (!state.guessMap) {
    state.guessMap = createStandardMap(container, { titleKey: "game.fullscreen_map_title" });

    if (state.guessMap) {
      state.guessMap.on("click", (event) => {
        if (state.timedOut || state.submitting) {
          return;
        }
        const origTarget = event.originalEvent && event.originalEvent.target;
        if (
          origTarget &&
          origTarget.closest(
            "button, a, input, select, label, .leaflet-control, .leaflet-bar, .fullscreen-timer, .map-fullscreen-btn, .map-reset-zoom-btn"
          )
        ) {
          return;
        }
        const lat = event.latlng.lat;
        const lng = (((event.latlng.lng + 180) % 360) + 360) % 360 - 180;
        const clickLatLng = L.latLng(lat, lng);
        state.guessedLatLng = clickLatLng;
        const player = state.currentQuestion?.player_name || (state.players && state.players[0]) || "";
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
  }

  if (shell) ensureMapFullscreenButton(shell, "game.fullscreen_map_title");

  requestAnimationFrame(() => {
    if (state.guessMap && state.guessMap._container && state.guessMap._loaded) {
      try { state.guessMap.invalidateSize(); } catch (_) {}
    }
  });
}

export function ensureRevealMap() {
  const container = document.getElementById("reveal-map");
  if (!container) return;

  const shell = container.closest(".map-shell");

  if (state.revealMap && (!state.revealMap.getContainer || state.revealMap.getContainer() !== container)) {
    try {
      unregisterActiveMap(state.revealMap);
      state.revealMap.remove();
    } catch (_) {}
    state.revealMap = null;
  }

  if (!state.revealMap) {
    state.revealMap = createStandardMap(container, { titleKey: "game.fullscreen_map_title" });
  }

  if (shell) ensureMapFullscreenButton(shell, "game.fullscreen_map_title");

  requestAnimationFrame(() => {
    if (state.revealMap && state.revealMap._container && state.revealMap._loaded) {
      try { state.revealMap.invalidateSize(); } catch (_) {}
    }
  });
}

export function ensureJourneyMap() {
  const container = document.getElementById("journey-map");
  if (!container) return;

  const shell = container.closest(".map-shell");

  if (!state.journeyMap) {
    state.journeyMap = createStandardMap(container, { titleKey: "game.fullscreen_map_title" });
  }

  if (shell) ensureMapFullscreenButton(shell, "game.fullscreen_map_title");

  requestAnimationFrame(() => {
    if (state.journeyMap && state.journeyMap._container && state.journeyMap._loaded) {
      try { state.journeyMap.invalidateSize(); } catch (_) {}
    }
  });
}

/**
 * Zoom-aware pin spiderfy — shared utility for all maps.
 *
 * Converts each pin's true lat/lng to screen pixels at the current zoom level,
 * groups pins whose centres are within `overlapThreshold` px of each other, then:
 *  - Isolated pins  → snapped back to their true position; stale line removed.
 *  - Grouped pins   → spread in a circle of `spiderRadius` px and connected to
 *                     their true location by a thin polyline.
 *
 * @param {L.Map}     map             - Leaflet map instance
 * @param {Object}    trueCoords      - { [key]: { lat, lng } }
 * @param {Object}    markerByKey     - { [key]: L.Marker }
 * @param {Object}    spiderLines     - { [key]: L.Polyline } — mutated in place
 * @param {Function}  getColor        - (key) => CSS colour string for connector lines
 * @param {number}    [overlapThreshold=18] - px distance below which pins are grouped
 * @param {number}    [spiderRadius=30]     - spread radius in screen pixels
 */
export function applySpiderfy(
  map, trueCoords, markerByKey, spiderLines, getColor,
  overlapThreshold = 18, spiderRadius = 30,
) {
  if (!map) return;

  const pinEntries = Object.entries(trueCoords);
  if (pinEntries.length === 0) return;

  // Convert every pin's true coordinate to screen pixels.
  const pinPixels = pinEntries.map(([key, coord]) => ({
    key,
    point: map.latLngToLayerPoint([coord.lat, coord.lng]),
    coord,
  }));

  // Single-pass greedy grouping by pixel proximity.
  const assigned = new Set();
  const groups = [];
  for (let i = 0; i < pinPixels.length; i++) {
    if (assigned.has(i)) continue;
    const group = [i];
    assigned.add(i);
    for (let j = i + 1; j < pinPixels.length; j++) {
      if (assigned.has(j)) continue;
      const dx = pinPixels[i].point.x - pinPixels[j].point.x;
      const dy = pinPixels[i].point.y - pinPixels[j].point.y;
      if (Math.sqrt(dx * dx + dy * dy) < overlapThreshold) {
        group.push(j);
        assigned.add(j);
      }
    }
    groups.push(group);
  }

  groups.forEach((group) => {
    if (group.length === 1) {
      // Isolated pin — restore true position and remove any stale connector.
      const { key, coord } = pinPixels[group[0]];
      const marker = markerByKey[key];
      if (marker) marker.setLatLng([coord.lat, coord.lng]);
      if (spiderLines[key]) {
        if (spiderLines[key]._anchor) map.removeLayer(spiderLines[key]._anchor);
        map.removeLayer(spiderLines[key]);
        delete spiderLines[key];
      }
    } else {
      // Overlapping group — spread each pin along the vector it already has
      // relative to the group centroid in pixel space.
      const centerX = group.reduce((s, i) => s + pinPixels[i].point.x, 0) / group.length;
      const centerY = group.reduce((s, i) => s + pinPixels[i].point.y, 0) / group.length;

      group.forEach((idx, groupIdx) => {
        const { key, coord } = pinPixels[idx];
        const marker = markerByKey[key];
        if (!marker) return;

        // Displacement of this pin's true position from the centroid.
        const dx = pinPixels[idx].point.x - centerX;
        const dy = pinPixels[idx].point.y - centerY;
        const dist = Math.sqrt(dx * dx + dy * dy);

        let spreadX, spreadY;
        if (dist > 0.5) {
          // Push along the existing radial vector, scaled to spiderRadius.
          spreadX = centerX + (dx / dist) * spiderRadius;
          spreadY = centerY + (dy / dist) * spiderRadius;
        } else {
          // All pins at identical true position — fall back to even circle.
          const angle = (groupIdx / group.length) * 2 * Math.PI - Math.PI / 2;
          spreadX = centerX + spiderRadius * Math.cos(angle);
          spreadY = centerY + spiderRadius * Math.sin(angle);
        }

        const spreadLatLng = map.layerPointToLatLng([spreadX, spreadY]);

        marker.setLatLng(spreadLatLng);

        const trueLatLng = [coord.lat, coord.lng];
        if (spiderLines[key]) {
          spiderLines[key].setLatLngs([trueLatLng, spreadLatLng]);
        } else {
          spiderLines[key] = L.polyline([trueLatLng, spreadLatLng], {
            color: getColor(key),
            weight: 2,
            opacity: 0.75,
            className: "spider-line",
          }).addTo(map);
          spiderLines[key].bringToBack();
          // Small dot anchoring the line to the true geographic location.
          spiderLines[key]._anchor = L.circleMarker(trueLatLng, {
            radius: 4,
            color: "#ffffff",
            fillColor: getColor(key),
            fillOpacity: 1,
            weight: 1.5,
            className: "spider-anchor",
          }).addTo(map);
          spiderLines[key]._anchor.bringToBack();
        }
      });
    }
  });
}

export function renderJourneyMap(roundHistory, locationMode = true, options = {}) {
  const mapShell = options.mapShell || el.journeyMapShell;
  const mapHead = options.mapHead || el.journeyMapHead;
  if (!mapShell || !mapHead) return null;

  if (!locationMode) {
    mapShell.classList.add("hidden");
    mapHead.classList.add("hidden");
    return null;
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
            ? formatDate(item.actual_date, { year: "numeric", month: "short", day: "numeric" })
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
      const locStr = formatPlace(r);
      const dateStr = r.actual_date
        ? formatDate(r.actual_date, { year: "numeric", month: "short", day: "numeric" })
        : (r.actual_year && r.actual_month ? formatMonth(r.actual_year, r.actual_month) : "");
      allPins.push({
        label: String(r.round_number),
        lat: r.actual_latitude,
        lon: r.actual_longitude,
        popupText: `<b>${t("summary.journey_round", r.round_number)}</b><br>${locStr}${dateStr ? `<br>📅 ${dateStr}` : ""}`,
      });
    }
  });

  if (allPins.length === 0) {
    mapShell.classList.add("hidden");
    mapHead.classList.add("hidden");
    return null;
  }

  mapShell.classList.remove("hidden");
  mapHead.classList.remove("hidden");

  let mapInstance;
  let spiderLinesObj;
  let trueCoordsObj;
  let layersArr;

  const container = options.container || document.getElementById(options.containerId || "journey-map");
  if (!container) return null;

  if (options.container || options.containerId) {
    if (options.existingMap) {
      mapInstance = options.existingMap;
      mapInstance.eachLayer((layer) => {
        if (!(layer instanceof L.TileLayer)) {
          mapInstance.removeLayer(layer);
        }
      });
    } else {
      mapInstance = createStandardMap(container, { titleKey: "game.fullscreen_map_title" });
    }
    const shell = container.closest(".map-shell");
    if (shell) ensureMapFullscreenButton(shell, "game.fullscreen_map_title");
    spiderLinesObj = {};
    trueCoordsObj = {};
    layersArr = [];
  } else {
    ensureJourneyMap();
    mapInstance = state.journeyMap;
    state.journeyLayers.forEach((layer) => state.journeyMap.removeLayer(layer));
    state.journeyLayers = [];
    Object.values(journeySpiderLines).forEach((line) => state.journeyMap.removeLayer(line));
    journeySpiderLines = {};
    journeyTrueCoords = {};
    spiderLinesObj = journeySpiderLines;
    trueCoordsObj = journeyTrueCoords;
    layersArr = state.journeyLayers;
  }

  if (!mapInstance) return null;

  mapInstance.off("zoomend");

  const points = [];
  allPins.forEach((pin) => {
    trueCoordsObj[pin.label] = { lat: pin.lat, lng: pin.lon };
    points.push(L.latLng(pin.lat, pin.lon));

    const marker = L.marker([pin.lat, pin.lon], {
      icon: createPinIcon(pin.label, ACTUAL_COLOR),
      _trueLabel: pin.label,
    })
      .addTo(mapInstance)
      .bindPopup(pin.popupText);
    layersArr.push(marker);
  });

  const buildMarkerByKey = () => {
    const m = {};
    layersArr.forEach((layer) => {
      if (layer instanceof L.Marker && layer.options._trueLabel !== undefined) {
        m[layer.options._trueLabel] = layer;
      }
    });
    return m;
  };

  mapInstance.on("zoomend", () =>
    applySpiderfy(mapInstance, trueCoordsObj, buildMarkerByKey(), spiderLinesObj, () => ACTUAL_COLOR)
  );

  if (points.length > 0) {
    fitMapToBounds(mapInstance, points, { padding: [50, 50], maxZoom: 15 });
    mapInstance.once("moveend", () =>
      applySpiderfy(mapInstance, trueCoordsObj, buildMarkerByKey(), spiderLinesObj, () => ACTUAL_COLOR)
    );
  }

  requestAnimationFrame(() => {
    if (mapInstance && mapInstance._container && mapInstance._loaded) {
      try { mapInstance.invalidateSize(); } catch (_) {}
    }
  });

  return mapInstance;
}

export function refitMap(map, forceRefitBounds = false) {
  if (!map || !map._container || !map._loaded) return;
  try {
    map.invalidateSize();
    updateMapMinZoom(map);
    if (forceRefitBounds && map._lastFitBounds && typeof map._lastFitBounds.isValid === "function" && map._lastFitBounds.isValid()) {
      const padding = (map._lastFitOptions && map._lastFitOptions.padding) || [50, 50];
      const maxZoom = (map._lastFitOptions && map._lastFitOptions.maxZoom !== undefined) ? map._lastFitOptions.maxZoom : 15;
      map.fitBounds(map._lastFitBounds, { padding, maxZoom });
    }
  } catch (_) {}
}

export function fitMapToBounds(map, pointsOrBounds, options = {}) {
  if (!map || !map._container || !pointsOrBounds) return;

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
    if (!map || !map._container || !map._loaded) return;
    try {
      map.invalidateSize();
      map.fitBounds(bounds, { padding, maxZoom });
    } catch (_) {}
  };

  doFit();
  requestAnimationFrame(() => doFit());
  setTimeout(() => doFit(), 250);
}

export function toggleMapFullscreen(shell) {
  const targetShell =
    shell ||
    document.fullscreenElement ||
    (state.currentScreen === "reveal" ? el.revealMapShell : null) ||
    (state.currentScreen === "summary" ? el.journeyMapShell : null) ||
    (state.currentScreen === "guessing" ? el.guessMapShell : null) ||
    document.querySelector(".map-shell:not(.hidden)");

  if (!targetShell && !document.fullscreenElement) return;

  const isFullscreen = Boolean(
    document.fullscreenElement &&
      (document.fullscreenElement === targetShell ||
        (targetShell && (targetShell.contains(document.fullscreenElement) || document.fullscreenElement.contains(targetShell))))
  );

  const request = isFullscreen
    ? (document.exitFullscreen ? document.exitFullscreen() : null)
    : (targetShell && targetShell.requestFullscreen ? targetShell.requestFullscreen() : null);

  if (request) {
    Promise.resolve(request).catch((err) => showAlert(t("game.fullscreen_error", err.message)));
  }
}

export function updateMapLayerControls(extraMaps = []) {
  const maps = [...new Set([...getActiveMaps(), state.guessMap, state.revealMap, state.journeyMap, ...extraMaps])].filter(Boolean);
  maps.forEach((map) => {
    addLayerControl(map);
  });
}

export const ENTER_FS_SVG = `<svg class="fs-icon" viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round">
  <polyline points="15 3 21 3 21 9"></polyline>
  <polyline points="9 21 3 21 3 15"></polyline>
  <line x1="21" y1="3" x2="14" y2="10"></line>
  <line x1="3" y1="21" x2="10" y2="14"></line>
</svg>`;

export const EXIT_FS_SVG = `<svg class="fs-icon" viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round">
  <polyline points="14 4 14 10 20 10"></polyline>
  <polyline points="10 20 10 14 4 14"></polyline>
  <line x1="21" y1="3" x2="14" y2="10"></line>
  <line x1="3" y1="21" x2="10" y2="14"></line>
</svg>`;

export function createMapFullscreenButton(shell, titleKey = "game.fullscreen_map_title") {
  const btn = document.createElement("button");
  btn.type = "button";
  btn.className = "map-fullscreen-btn leaflet-control";
  btn.setAttribute("aria-pressed", "false");
  btn.title = t(titleKey);
  btn.setAttribute("data-i18n-title", titleKey);
  btn.innerHTML = ENTER_FS_SVG;
  if (window.L && L.DomEvent) {
    L.DomEvent.disableClickPropagation(btn);
    L.DomEvent.disableScrollPropagation(btn);
  }
  btn.onclick = (e) => {
    if (e && e.stopPropagation) e.stopPropagation();
    toggleMapFullscreen(shell);
  };
  return btn;
}

export function syncFullscreenButtons() {
  document.querySelectorAll(".map-fullscreen-btn").forEach((button) => {
    const shell = button.closest(".map-shell, .media-frame");
    const isActive = Boolean(
      document.fullscreenElement &&
      (document.fullscreenElement === shell || (shell && shell.contains(document.fullscreenElement)))
    );
    const titleKey = isActive ? "game.fullscreen_exit_btn" : "game.fullscreen_btn";
    button.title = t(titleKey);
    button.setAttribute("data-i18n-title", titleKey);
    button.setAttribute("aria-pressed", isActive ? "true" : "false");
    button.classList.toggle("is-active", isActive);
    button.innerHTML = isActive ? EXIT_FS_SVG : ENTER_FS_SVG;
  });
}

export function handleFullscreenChange() {
  syncFullscreenButtons();
  refitAllMaps(true);
  requestAnimationFrame(() => refitAllMaps(true));
  setTimeout(() => refitAllMaps(true), 100);
  setTimeout(() => refitAllMaps(true), 300);
}

if (typeof document !== "undefined") {
  document.addEventListener("fullscreenchange", handleFullscreenChange);
  document.addEventListener("webkitfullscreenchange", handleFullscreenChange);
}

export function initMapFullscreenControls() {
  if (el.revealMapFullscreen && el.revealMapShell) {
    if (window.L && L.DomEvent) {
      L.DomEvent.disableClickPropagation(el.revealMapFullscreen);
      L.DomEvent.disableScrollPropagation(el.revealMapFullscreen);
    }
    el.revealMapFullscreen.onclick = (e) => {
      if (e && e.stopPropagation) e.stopPropagation();
      toggleMapFullscreen(el.revealMapShell);
    };
  }
  if (el.journeyMapFullscreen && el.journeyMapShell) {
    if (window.L && L.DomEvent) {
      L.DomEvent.disableClickPropagation(el.journeyMapFullscreen);
      L.DomEvent.disableScrollPropagation(el.journeyMapFullscreen);
    }
    el.journeyMapFullscreen.onclick = (e) => {
      if (e && e.stopPropagation) e.stopPropagation();
      toggleMapFullscreen(el.journeyMapShell);
    };
  }
  if (el.guessMapFullscreen && el.guessMapShell) {
    if (window.L && L.DomEvent) {
      L.DomEvent.disableClickPropagation(el.guessMapFullscreen);
      L.DomEvent.disableScrollPropagation(el.guessMapFullscreen);
    }
    el.guessMapFullscreen.onclick = (e) => {
      if (e && e.stopPropagation) e.stopPropagation();
      toggleMapFullscreen(el.guessMapShell);
    };
  }
  if (el.quizImageFullscreen && el.mediaFrame) {
    el.quizImageFullscreen.onclick = (e) => {
      if (e && e.stopPropagation) e.stopPropagation();
      toggleMapFullscreen(el.mediaFrame);
    };
  }
  syncFullscreenButtons();
}

export const RESET_ZOOM_SVG = `<svg class="reset-zoom-icon" viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
  <circle cx="12" cy="12" r="8"></circle>
  <line x1="12" y1="2" x2="12" y2="5"></line>
  <line x1="12" y1="19" x2="12" y2="22"></line>
  <line x1="2" y1="12" x2="5" y2="12"></line>
  <line x1="19" y1="12" x2="22" y2="12"></line>
  <circle cx="12" cy="12" r="1.5" fill="currentColor"></circle>
</svg>`;

export function resetMapZoom(map) {
  if (!map) return;
  if (map._regionalBounds && typeof map._regionalBounds.isValid === "function" && map._regionalBounds.isValid()) {
    const padding = (map._regionalOptions && map._regionalOptions.padding) || [40, 40];
    const maxZoom = (map._regionalOptions && map._regionalOptions.maxZoom !== undefined) ? map._regionalOptions.maxZoom : 6;
    fitMapToBounds(map, map._regionalBounds, { padding, maxZoom });
  } else if (map._lastFitBounds && typeof map._lastFitBounds.isValid === "function" && map._lastFitBounds.isValid()) {
    const padding = (map._lastFitOptions && map._lastFitOptions.padding) || [50, 50];
    const maxZoom = (map._lastFitOptions && map._lastFitOptions.maxZoom !== undefined) ? map._lastFitOptions.maxZoom : 15;
    map.fitBounds(map._lastFitBounds, { padding, maxZoom });
  } else if (map._initialCenter && map._initialZoom !== undefined) {
    map.setView(map._initialCenter, map._initialZoom);
  } else {
    map.setView([20, 0], 2);
  }
}

export function createMapResetZoomButton(map) {
  const btn = document.createElement("button");
  btn.type = "button";
  btn.className = "map-reset-zoom-btn leaflet-control";
  const titleKey = map && map._regionalBounds ? "map.focus_region_title" : "map.reset_zoom_title";
  btn.title = t(titleKey);
  btn.setAttribute("data-i18n-title", titleKey);
  btn.setAttribute("aria-label", t(titleKey));
  btn.innerHTML = RESET_ZOOM_SVG;
  if (window.L && L.DomEvent) {
    L.DomEvent.disableClickPropagation(btn);
    L.DomEvent.disableScrollPropagation(btn);
  }
  btn.addEventListener("click", (e) => {
    e.stopPropagation();
    resetMapZoom(map);
  });
  return btn;
}

export function ensureMapResetZoomButton(map) {
  if (!map) return null;
  const containerEl = map.getContainer ? map.getContainer() : null;
  const shell = containerEl ? containerEl.closest(".map-shell") || containerEl : null;
  if (!shell) return null;

  let btn = shell.querySelector(".map-reset-zoom-btn");
  if (!btn) {
    btn = createMapResetZoomButton(map);
  }
  btn.classList.add("leaflet-control");
  if (window.L && L.DomEvent) {
    L.DomEvent.disableClickPropagation(btn);
    L.DomEvent.disableScrollPropagation(btn);
  }
  const tryMove = () => {
    const rightCorner = shell.querySelector(".leaflet-top.leaflet-right");
    if (rightCorner && btn.parentElement !== rightCorner) {
      const zoomControl = rightCorner.querySelector(".leaflet-control-zoom");
      if (zoomControl && zoomControl.nextSibling) {
        rightCorner.insertBefore(btn, zoomControl.nextSibling);
      } else {
        rightCorner.appendChild(btn);
      }
    }
  };
  tryMove();
  requestAnimationFrame(tryMove);
  setTimeout(tryMove, 50);
  return btn;
}

import { state } from "../../state.js";
import { createBaseTileLayers, addLayerControl } from "../../maps.js";

let shuffleMap = null;
let revealShuffleMap = null;
let shuffleMarkers = {}; // pinId -> Leaflet marker

export function getPinMarkerDetails(pinId) {
  const pinAssignments = state.albumShuffleState ? state.albumShuffleState.pinAssignments || {} : {};
  const orderedIds = state.albumShuffleState ? state.albumShuffleState.orderedPhotoIds || [] : [];
  const assignedPhotoId = Object.keys(pinAssignments).find(
    (photoId) => pinAssignments[photoId] === pinId
  );

  if (assignedPhotoId) {
    const cardIndex = orderedIds.indexOf(assignedPhotoId);
    if (cardIndex !== -1) {
      return {
        isTaken: true,
        badgeText: `${pinId}-${cardIndex + 1}`,
        bgColor: "#f59f00",
      };
    }
  }

  return {
    isTaken: false,
    badgeText: pinId,
    bgColor: "#0f7c7f",
  };
}

export function updateShuffleMapMarkers(pins) {
  if (!pins) return;
  pins.forEach((pin) => {
    const { badgeText, bgColor } = getPinMarkerDetails(pin.pin_id);
    const markerEl = document.getElementById(`pin-marker-${pin.pin_id}`);
    if (markerEl) {
      markerEl.style.background = bgColor;
      markerEl.textContent = badgeText;
    }
  });
}

export function highlightMapMarker(pinId) {
  Object.keys(shuffleMarkers).forEach((pid) => {
    const markerEl = document.getElementById(`pin-marker-${pid}`);
    if (markerEl) {
      if (pinId && pid === pinId) {
        markerEl.style.transform = "scale(1.3)";
        markerEl.style.boxShadow = "0 0 0 4px rgba(245, 159, 0, 0.6), 0 4px 12px rgba(0,0,0,0.4)";
        markerEl.style.borderColor = "#f59f00";
      } else {
        markerEl.style.transform = "scale(1)";
        markerEl.style.boxShadow = "0 3px 8px rgba(0,0,0,0.35)";
        markerEl.style.borderColor = "#fff";
      }
    }
  });
}

export function renderShuffleMap(containerEl, pins, questionData, onPinClick) {
  if (!window.L) return;
  if (shuffleMap) {
    shuffleMap.remove();
    shuffleMap = null;
  }
  shuffleMarkers = {};

  const mapShell = containerEl.id ? containerEl : document.getElementById("shuffle-map-shell");
  const base = createBaseTileLayers();
  const map = L.map(mapShell, { layers: [base.streets] }).setView([20, 0], 2);
  addLayerControl(map, base);

  shuffleMap = map;
  const bounds = L.latLngBounds();

  // Group near-duplicate coordinates to apply a small visual offset if pins share exact locations
  const coordCounts = {};
  const processedPins = pins.map((pin) => {
    const key = `${pin.latitude.toFixed(4)},${pin.longitude.toFixed(4)}`;
    coordCounts[key] = (coordCounts[key] || 0) + 1;
    const occurrence = coordCounts[key];
    let displayLat = pin.latitude;
    let displayLon = pin.longitude;
    if (occurrence > 1) {
      const angle = (occurrence - 1) * ((2 * Math.PI) / 5);
      const radius = 0.00025 * Math.sqrt(occurrence);
      displayLat = pin.latitude + radius * Math.cos(angle);
      displayLon = pin.longitude + radius * Math.sin(angle);
    }
    return { ...pin, displayLat, displayLon };
  });

  processedPins.forEach((pin) => {
    const lat = pin.displayLat;
    const lon = pin.displayLon;
    bounds.extend([pin.latitude, pin.longitude]);

    const { badgeText, bgColor } = getPinMarkerDetails(pin.pin_id);

    const icon = L.divIcon({
      className: "custom-pin-icon",
      html: `<div id="pin-marker-${pin.pin_id}" style="background:${bgColor};color:#fff;width:36px;height:36px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-weight:bold;font-size:0.85rem;border:2px solid #fff;box-shadow:0 3px 8px rgba(0,0,0,0.35);transition:all 0.25s ease;">${badgeText}</div>`,
      iconSize: [36, 36],
      iconAnchor: [18, 18],
    });

    const marker = L.marker([lat, lon], { icon }).addTo(map);
    shuffleMarkers[pin.pin_id] = marker;

    marker.on("click", () => {
      if (onPinClick) onPinClick(pin);
    });
  });

  if (pins.length > 0) {
    map.fitBounds(bounds, { padding: [50, 50] });
  }

  setTimeout(() => map.invalidateSize(), 150);
}

export function renderBatchRevealMap(containerEl, batchItems) {
  if (!window.L) return;
  if (revealShuffleMap) {
    revealShuffleMap.remove();
    revealShuffleMap = null;
  }

  const validItems = (batchItems || []).filter(
    (item) =>
      item.actual_latitude !== null &&
      item.actual_latitude !== undefined &&
      item.actual_longitude !== null &&
      item.actual_longitude !== undefined &&
      !(Math.abs(item.actual_latitude) < 1e-6 && Math.abs(item.actual_longitude) < 1e-6)
  );

  if (validItems.length === 0) {
    if (containerEl) containerEl.style.display = "none";
    const prev = containerEl ? containerEl.previousElementSibling : null;
    if (prev && prev.classList.contains("field-head")) {
      prev.style.display = "none";
    }
    return;
  }

  containerEl.style.display = "block";

  const base = createBaseTileLayers();
  const map = L.map(containerEl, { layers: [base.streets] }).setView([20, 0], 2);
  addLayerControl(map, base);

  revealShuffleMap = map;
  const bounds = L.latLngBounds();

  validItems.forEach((item) => {
    const lat = item.actual_latitude;
    const lon = item.actual_longitude;
    bounds.extend([lat, lon]);

    const icon = L.divIcon({
      className: "custom-pin-icon",
      html: `<div style="background:#0f7c7f;color:#fff;width:36px;height:36px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-weight:bold;border:2px solid #fff;box-shadow:0 3px 8px rgba(0,0,0,0.35);">${item.true_pin_id}</div>`,
      iconSize: [36, 36],
      iconAnchor: [18, 18],
    });

    const dateStr = item.actual_date
      ? new Date(item.actual_date).toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" })
      : "";
    L.marker([lat, lon], { icon })
      .bindPopup(`<b>${item.true_pin_id}</b><br>${dateStr}`)
      .addTo(map);
  });

  if (validItems.length > 0) {
    map.fitBounds(bounds, { padding: [50, 50] });
  }

  setTimeout(() => map.invalidateSize(), 150);
}

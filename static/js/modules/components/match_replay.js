/**
 * Match Replay Viewer & Review Strategy Component.
 *
 * Provides a standardized, self-contained multi-round replay viewer:
 * - Strategy Pattern: Pluggable mode replay strategies (PinpointReplayStrategy, UnshuffleReplayStrategy)
 * - Round stepper navigation (prev / next round controls, indicator, keyboard arrows)
 * - RoundStage (photo canvas with tabs/lightbox/fullscreen/caption/report button + Leaflet map shell)
 * - Reveal Table (consolidated player guesses and scores)
 *
 * Reused across:
 * 1. Dedicated Match Replay screen (/game/:id/replay, /replays/:id)
 * 2. Local Match Summary screen (#summary-card)
 * 3. Challenge Grand Reveal screen (#challenge-card)
 */

import { t, formatDate } from "../i18n.js";
import {
  escapeHtml,
  formatDistance,
  playerColor,
  playerInitial,
  registerPlayerColor,
  clearPlayerColors,
  PLAYER_COLORS,
  ACTUAL_COLOR,
} from "../formatters.js";
import {
  createStandardMap,
  createPinIcon,
  createBadgePinIcon,
  fitMapToBounds,
  applySpiderfy,
  unregisterActiveMap,
} from "../maps.js";
import { getPinColor } from "../modes/unshuffle.js";
import { openReportModal } from "./report_modal.js";
import { renderRevealTableHeaders, renderRevealTableRows } from "./reveal_table.js";
import { RoundStage } from "./round_stage.js";

/**
 * Strategy contract for rendering round replay maps and scoring tables.
 */
export class PinpointReplayStrategy {
  renderMap({ map, roundStage, round, matchData, mapMarkers, mapPolylines }) {
    if (!map || !window.L) return;

    const photos = round.batch_photos && round.batch_photos.length > 0 ? round.batch_photos : [
      {
        asset_id: round.asset_id,
        actual_latitude: round.actual_latitude,
        actual_longitude: round.actual_longitude,
        actual_date: round.actual_date,
        actual_city: round.actual_city,
        actual_country: round.actual_country,
        actual_year: round.actual_year,
        actual_month: round.actual_month,
      },
    ];
    const curPhoto = photos[0];
    const hasCoordinates = curPhoto.actual_latitude != null && curPhoto.actual_longitude != null;
    const isLocationMode =
      matchData?.location_mode !== false &&
      (hasCoordinates || (round.player_guesses || []).some((g) => g.guess_latitude != null));

    if (roundStage) {
      roundStage.setMapVisible(isLocationMode);
    }
    if (!isLocationMode) return;

    const boundsPoints = [];

    // Actual location pin (★)
    if (curPhoto.actual_latitude != null && curPhoto.actual_longitude != null) {
      const actualPt = [Number(curPhoto.actual_latitude), Number(curPhoto.actual_longitude)];
      boundsPoints.push(actualPt);

      const actualIcon = createPinIcon("\u2605", ACTUAL_COLOR);
      const locParts = [curPhoto.actual_city, curPhoto.actual_country].filter(Boolean);
      const locText = locParts.length > 0 ? locParts.join(", ") : "";

      const actualMarker = L.marker(actualPt, { icon: actualIcon, zIndexOffset: 1000 })
        .addTo(map)
        .bindPopup(
          `<strong>★ ${escapeHtml(t("reveal.popup_actual"))}</strong>${locText ? `<br>${escapeHtml(locText)}` : ""}`
        );
      mapMarkers.push(actualMarker);
    }

    // Player guesses pins & spider lines
    const guesses = round.player_guesses || [];
    const coordsSeen = {};

    guesses.forEach((g) => {
      if (g.guess_latitude == null || g.guess_longitude == null) return;

      let lat = Number(g.guess_latitude);
      let lng = Number(g.guess_longitude);
      if (!Number.isFinite(lat) || !Number.isFinite(lng)) return;

      const key = `${lat.toFixed(4)},${lng.toFixed(4)}`;
      if (coordsSeen[key]) {
        coordsSeen[key]++;
        const angle = (coordsSeen[key] * (2 * Math.PI)) / 6;
        lat += 0.0025 * Math.sin(angle);
        lng += 0.0025 * Math.cos(angle);
      } else {
        coordsSeen[key] = 1;
      }

      const guessPt = [lat, lng];
      boundsPoints.push(guessPt);

      const initial = playerInitial(g.player_name);
      const pColor = g.player_color || playerColor(g.player_name);
      const guessIcon = createPinIcon(initial, pColor);

      const marker = L.marker(guessPt, { icon: guessIcon, zIndexOffset: 500 })
        .addTo(map)
        .bindPopup(`
          <div style="font-size: 0.86rem;">
            <strong style="color: ${escapeHtml(pColor)};">${escapeHtml(g.player_name)}</strong><br>
            ${escapeHtml(t("reveal.col_points"))}: <strong>+${g.round_score} pts</strong><br>
            ${g.distance_km != null ? `${escapeHtml(t("reveal.col_location"))}: ${formatDistance(g.distance_km)}<br>` : ""}
            ${g.time_taken_seconds != null ? `⏱️ ${g.time_taken_seconds}s` : ""}
          </div>
        `);
      mapMarkers.push(marker);

      if (curPhoto.actual_latitude != null && curPhoto.actual_longitude != null) {
        const line = L.polyline(
          [guessPt, [Number(curPhoto.actual_latitude), Number(curPhoto.actual_longitude)]],
          {
            color: pColor,
            weight: 3,
            dashArray: "8, 8",
            opacity: 0.85,
          }
        ).addTo(map);
        mapPolylines.push(line);
      }
    });

    if (boundsPoints.length === 1) {
      try {
        map.invalidateSize();
        map.setView(boundsPoints[0], 12);
        map._lastFitBounds = L.latLngBounds([boundsPoints[0], boundsPoints[0]]);
      } catch (_) {}
    } else if (boundsPoints.length > 1) {
      fitMapToBounds(map, boundsPoints, { padding: [40, 40], maxZoom: 15 });
    }
  }

  renderTable({ table, round, matchData }) {
    if (!table) return;
    const guesses = round.player_guesses || [];
    if (guesses.length === 0) {
      const tbody = table.querySelector("tbody");
      if (tbody) {
        tbody.innerHTML = `<tr><td colspan="99" style="color: var(--text-muted); font-size: 0.85rem; padding: 0.75rem;">${t("replay.no_guesses")}</td></tr>`;
      }
      return;
    }

    const locationMode = matchData?.location_mode !== false;
    const dateMode = matchData?.date_mode !== false;

    renderRevealTableHeaders(table, {
      locationMode,
      dateMode,
      gameMode: "pinpoint",
      showRank: guesses.length > 1,
    });

    const formattedResults = guesses.map((g) => ({
      player_name: g.player_name,
      timed_out: g.timed_out,
      round_score: g.round_score,
      cumulative_score: g.cumulative_score,
      total_score: g.cumulative_score,
      location_score: g.location_score,
      date_score: g.date_score,
      pinpoint: {
        distance_km: g.distance_km,
        guessed_latitude: g.guess_latitude,
        guessed_longitude: g.guess_longitude,
        date_diff_days: g.date_diff_days,
        guessed_year: g.guessed_year,
        guessed_month: g.guessed_month,
      },
    }));

    renderRevealTableRows(table, formattedResults, {
      locationMode,
      dateMode,
      gameMode: "pinpoint",
      showRank: guesses.length > 1,
      skipEffects: true,
    });
  }

  onPhotoChange() {}
}

export class UnshuffleReplayStrategy {
  renderMap({ map, roundStage, round, matchData, mapMarkers, mapPolylines, markersByPin }) {
    if (!map || !window.L) return;

    const batchPhotos = (roundStage && Array.isArray(roundStage.photos) && roundStage.photos.length > 0)
      ? roundStage.photos
      : (round.batch_photos || []);
    const validPhotos = batchPhotos.filter((p) => {
      const lat = Number(p.actual_latitude);
      const lon = Number(p.actual_longitude);
      return Number.isFinite(lat) && Number.isFinite(lon) && !(Math.abs(lat) < 1e-6 && Math.abs(lon) < 1e-6);
    });

    const isLocationMode = matchData?.location_mode !== false && validPhotos.length > 0;
    if (roundStage) {
      roundStage.setMapVisible(isLocationMode);
    }
    if (!isLocationMode) return;

    const bounds = L.latLngBounds();
    const trueCoords = {};
    const spiderLines = {};

    validPhotos.forEach((photo, idx) => {
      let pinId = photo.true_pin_id;
      if (!pinId) {
        const rawIdx = photo.photo_index != null ? Number(photo.photo_index) : idx;
        pinId = String.fromCharCode(65 + rawIdx);
      }
      const lat = Number(photo.actual_latitude);
      const lon = Number(photo.actual_longitude);
      bounds.extend([lat, lon]);
      trueCoords[pinId] = { lat, lng: lon };

      const pinColor = getPinColor(pinId);
      const photoUrl = photo.media_url || (photo.photo_id ? `/api/media/${photo.photo_id}` : (photo.asset_id ? `/api/media/${encodeURIComponent(photo.asset_id)}` : ""));
      const icon = createBadgePinIcon(pinId, pinColor, {
        id: `replay-pin-marker-${pinId}`,
        isTaken: true,
        size: 36,
        photoUrl,
      });

      const locParts = [photo.actual_city, photo.actual_country].filter(Boolean);
      const locText = locParts.length > 0 ? locParts.join(", ") : "";
      let dateText = "";
      if (photo.actual_date) {
        dateText = formatDate(photo.actual_date, { year: "numeric", month: "short", day: "numeric" });
      }

      const marker = L.marker([lat, lon], { icon, zIndexOffset: 700 })
        .addTo(map)
        .bindPopup(`
          <div style="font-size: 0.88rem;">
            <strong style="color: ${escapeHtml(pinColor)}; font-size: 1rem;">Pin ${escapeHtml(pinId)}</strong><br>
            ${locText ? `<span>📍 ${escapeHtml(locText)}</span><br>` : ""}
            ${dateText ? `<span>📅 ${escapeHtml(dateText)}</span>` : ""}
          </div>
        `);

      const selectPhotoForMarker = () => {
        if (roundStage && Array.isArray(roundStage.photos)) {
          const pIdx = roundStage.photos.findIndex((p) => String(p.true_pin_id) === String(pinId));
          if (pIdx >= 0) {
            roundStage.setActivePhoto(pIdx);
          }
        }
      };

      marker.on("click", selectPhotoForMarker);
      marker.on("popupopen", selectPhotoForMarker);

      const markerEl = marker.getElement();
      if (markerEl) {
        markerEl.addEventListener("click", selectPhotoForMarker);
        const innerPin = markerEl.querySelector(`#replay-pin-marker-${pinId}`);
        if (innerPin) {
          innerPin.addEventListener("click", selectPhotoForMarker);
        }
      }

      markersByPin[pinId] = marker;
      mapMarkers.push(marker);
    });

    if (bounds.isValid()) {
      fitMapToBounds(map, bounds, { padding: [40, 40], maxZoom: 15 });
    }

    // Spiderfy support for co-located pins
    const updateSpiderfy = () => {
      applySpiderfy(map, trueCoords, markersByPin, spiderLines, getPinColor);
    };
    updateSpiderfy();
    map.on("zoomend", updateSpiderfy);
    map.on("moveend", updateSpiderfy);
    mapMarkers._cleanupSpiderfy = () => {
      map.off("zoomend", updateSpiderfy);
      map.off("moveend", updateSpiderfy);
      Object.keys(spiderLines).forEach((key) => {
        const line = spiderLines[key];
        if (line) {
          if (line._anchor) {
            try { map.removeLayer(line._anchor); } catch (_) {}
          }
          try { map.removeLayer(line); } catch (_) {}
        }
        delete spiderLines[key];
      });
    };

    // If active photo selected, open its popup
    const curPhoto = roundStage?.getCurrentPhoto();
    if (curPhoto?.true_pin_id && markersByPin[curPhoto.true_pin_id]) {
      try {
        markersByPin[curPhoto.true_pin_id].openPopup();
      } catch (_) {}
    }
  }

  renderTable({ table, round, matchData }) {
    if (!table) return;
    const guesses = round.player_guesses || [];
    if (guesses.length === 0) {
      const tbody = table.querySelector("tbody");
      if (tbody) {
        tbody.innerHTML = `<tr><td colspan="99" style="color: var(--text-muted); font-size: 0.85rem; padding: 0.75rem;">${t("replay.no_guesses")}</td></tr>`;
      }
      return;
    }

    const locationMode = matchData?.location_mode !== false;
    const dateMode = matchData?.date_mode !== false;
    const batchPhotos = round.batch_photos || [];
    const totalPhotos = batchPhotos.length;

    const sortedTrueBatch = [...batchPhotos].sort((a, b) => {
      const dateA = a.actual_date ? new Date(a.actual_date).getTime() : 0;
      const dateB = b.actual_date ? new Date(b.actual_date).getTime() : 0;
      return dateA - dateB;
    });

    const trueRankMap = {};
    sortedTrueBatch.forEach((item, idx) => {
      trueRankMap[item.asset_id || item.photo_id] = idx;
    });

    const playerAccuracy = {};
    guesses.forEach((g) => {
      let correctPins = 0;
      let correctRanks = 0;
      if (Array.isArray(g.unshuffle_guesses) && g.unshuffle_guesses.length > 0) {
        g.unshuffle_guesses.forEach((ug) => {
          const photo = batchPhotos.find((p) => String(p.asset_id || p.photo_id) === String(ug.photo_id || ug.asset_id));
          if (photo) {
            if (ug.assigned_pin_id && String(ug.assigned_pin_id) === String(photo.true_pin_id)) {
              correctPins++;
            }
            const trueRank = trueRankMap[photo.asset_id || photo.photo_id];
            if (ug.assigned_timeline_index !== null && ug.assigned_timeline_index === trueRank) {
              correctRanks++;
            }
          }
        });
      } else {
        if (g.is_correct_location) correctPins++;
        if (g.is_correct_date_order) correctRanks++;
      }
      playerAccuracy[g.player_name] = { correctPins, correctRanks };
    });

    renderRevealTableHeaders(table, {
      locationMode,
      dateMode,
      gameMode: "unshuffle",
      showRank: guesses.length > 1,
    });

    const formattedResults = guesses.map((g) => ({
      player_name: g.player_name,
      timed_out: g.timed_out,
      round_score: g.round_score,
      cumulative_score: g.cumulative_score,
      total_score: g.cumulative_score,
      location_score: g.location_score,
      date_score: g.date_score,
      unshuffle_guesses: g.unshuffle_guesses || [],
    }));

    renderRevealTableRows(table, formattedResults, {
      locationMode,
      dateMode,
      gameMode: "unshuffle",
      showRank: guesses.length > 1,
      totalPhotos,
      playerAccuracy,
      skipEffects: true,
    });
  }

  onPhotoChange({ photo, map, markersByPin }) {
    if (!photo || !photo.true_pin_id || !markersByPin) return;
    const marker = markersByPin[photo.true_pin_id];
    if (marker && map) {
      try {
        marker.openPopup();
        map.panTo(marker.getLatLng(), { animate: true, duration: 0.4 });
      } catch (_) {}
    }
  }
}

export const REPLAY_STRATEGIES = {
  pinpoint: new PinpointReplayStrategy(),
  unshuffle: new UnshuffleReplayStrategy(),
};

/**
 * Retrieve the active Replay strategy for the given game mode.
 * @param {string} gameMode
 * @returns {PinpointReplayStrategy | UnshuffleReplayStrategy}
 */
export function getReplayStrategy(gameMode) {
  return REPLAY_STRATEGIES[gameMode] || REPLAY_STRATEGIES.pinpoint;
}

export class MatchReplayViewer {
  /**
   * @param {HTMLElement} containerEl - Outer container hosting the replay grid
   * @param {object} [options]
   * @param {Function} [options.onRoundChange] - Callback (roundIndex, roundData)
   * @param {boolean} [options.showReportButton=true]
   */
  constructor(containerEl, { idPrefix = "replay-", onRoundChange = null, showReportButton = true } = {}) {
    this.containerEl = containerEl;
    this.idPrefix = idPrefix;
    this.onRoundChange = onRoundChange;
    this.showReportButton = showReportButton;

    this.matchData = null;
    this.currentRoundIndex = 0;
    this.currentRound = null;
    this.roundStage = null;
    this.map = null;
    this.mapMarkers = [];
    this.mapPolylines = [];
    this.markersByPin = {};

    this._initMarkup();
  }

  _initMarkup() {
    this.containerEl.classList.add("replay-content-grid");

    // Discover or generate stepper, stage mount, and reveal table
    let stepper = this.containerEl.querySelector(".replay-round-stepper");
    let stageMount = this.containerEl.querySelector(".replay-content-container");
    let table = this.containerEl.querySelector(".reveal-table, .replay-reveal-table");

    const p = this.idPrefix || "replay-";
    if (!stepper || !stageMount || !table) {
      this.containerEl.innerHTML = `
        <div class="replay-header-controls">
          <div class="replay-round-stepper">
            <button type="button" id="${p}prev-round-btn" class="btn-icon-control replay-prev-round-btn" title="${escapeHtml(t("replay.prev_round"))}"
              aria-label="${escapeHtml(t("replay.prev_round"))}" data-i18n-title="replay.prev_round">
              <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2.5"
                stroke-linecap="round" stroke-linejoin="round">
                <polyline points="16 20 8 12 16 4"></polyline>
              </svg>
            </button>
            <span id="${p}round-indicator" class="replay-round-indicator"></span>
            <button type="button" id="${p}next-round-btn" class="btn-icon-control replay-next-round-btn" title="${escapeHtml(t("replay.next_round"))}"
              aria-label="${escapeHtml(t("replay.next_round"))}" data-i18n-title="replay.next_round">
              <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2.5"
                stroke-linecap="round" stroke-linejoin="round">
                <polyline points="8 20 16 12 8 4"></polyline>
              </svg>
            </button>
          </div>
        </div>
        <div id="${p}content-container" class="replay-content-container round-stage replay-stage"></div>
        <div class="replay-guesses-card">
          <div class="replay-guesses-header">
            <h4>
              <span>👥 <span data-i18n="replay.player_guess_heading">${escapeHtml(t("replay.player_guess_heading"))}</span></span>
              <span id="${p}scoreboard-round-tag" class="replay-round-tag"></span>
            </h4>
          </div>
          <div id="${p}guesses-list" class="table-scroll reveal-table-scroll">
            <table id="${p}reveal-table" class="reveal-table replay-reveal-table">
              <thead></thead>
              <tbody></tbody>
            </table>
          </div>
        </div>
      `;
    }

    this.prevBtn = this.containerEl.querySelector(".replay-prev-round-btn, #replay-prev-round-btn");
    this.nextBtn = this.containerEl.querySelector(".replay-next-round-btn, #replay-next-round-btn");
    this.indicatorEl = this.containerEl.querySelector(".replay-round-indicator, #replay-round-indicator");
    this.stageMount = this.containerEl.querySelector(".replay-content-container");
    this.table = this.containerEl.querySelector(".reveal-table, .replay-reveal-table, #replay-reveal-table");

    if (this.prevBtn) {
      this.prevBtn.addEventListener("click", () => {
        this.goToRound(this.currentRoundIndex - 1);
      });
    }
    if (this.nextBtn) {
      this.nextBtn.addEventListener("click", () => {
        this.goToRound(this.currentRoundIndex + 1);
      });
    }

    // Keyboard navigation (ArrowLeft, ArrowRight)
    this._handleKeyDown = (e) => {
      if (!this.containerEl.offsetParent && !this.containerEl.closest(":not(.hidden)")) return;
      if (e.target && e.target.matches("input, textarea, select, [contenteditable]")) return;

      if (e.key === "ArrowLeft") {
        if (this.currentRoundIndex > 0) {
          e.preventDefault();
          this.goToRound(this.currentRoundIndex - 1);
        }
      } else if (e.key === "ArrowRight") {
        const rounds = this.matchData?.rounds_data || [];
        if (this.currentRoundIndex < rounds.length - 1) {
          e.preventDefault();
          this.goToRound(this.currentRoundIndex + 1);
        }
      }
    };
    document.addEventListener("keydown", this._handleKeyDown);

    // Mount RoundStage on the stage mount point
    if (this.stageMount) {
      this.roundStage = new RoundStage(this.stageMount, {
        idPrefix: this.idPrefix,
        showReportButton: this.showReportButton,
        onPhotoChange: (idx, photo) => {
          if (this.currentRound) {
            const strategy = this.getStrategy(this.currentRound);
            strategy.onPhotoChange({
              photo,
              map: this.map,
              markersByPin: this.markersByPin,
            });
          }
        },
        onReportPhoto: (assetId, previewUrl) => {
          openReportModal(assetId, previewUrl);
        },
      });
    }

    // Initialize Leaflet Map on RoundStage's generated map container
    const mapEl = this.roundStage?.getMapElement();
    if (mapEl && window.L) {
      this.map = createStandardMap(mapEl, {
        existingMap: this.map,
        titleKey: "game.fullscreen_map_title",
        fullscreenControl: true,
        resetZoomControl: true,
        layerControl: true,
      });
      this.mapMarkers = [];
      this.mapPolylines = [];
      this.markersByPin = {};
    }
  }

  getStrategy(round = null) {
    const mode = (round && round.game_mode) || this.matchData?.game_mode || "pinpoint";
    return getReplayStrategy(mode);
  }

  /**
   * Load match dataset into viewer and render the initial round.
   * @param {object} matchData Full MatchReplayResponse payload
   * @param {number} [initialRoundIndex=0]
   */
  setMatchData(matchData, initialRoundIndex = 0) {
    if (!matchData) return;
    this.matchData = matchData;
    this.currentRoundIndex = Math.max(
      0,
      Math.min(initialRoundIndex, (matchData.rounds_data || []).length - 1)
    );

    // Register player colors in standard sequence
    clearPlayerColors();
    if (Array.isArray(matchData.players)) {
      matchData.players.forEach((p, idx) => {
        const color = p.player_color || PLAYER_COLORS[idx % PLAYER_COLORS.length];
        registerPlayerColor(p.player_name, color);
      });
    }
    if (Array.isArray(matchData.rounds_data)) {
      matchData.rounds_data.forEach((r) => {
        (r.player_guesses || []).forEach((g) => {
          if (g.player_name && g.player_color) {
            registerPlayerColor(g.player_name, g.player_color);
          }
        });
      });
    }

    // Stabilize map dimensions
    if (this.map) {
      setTimeout(() => {
        try {
          this.map.invalidateSize();
        } catch (_) {}
      }, 50);
    }

    this.renderCurrentRound();
  }

  goToRound(idx) {
    if (!this.matchData || !Array.isArray(this.matchData.rounds_data)) return;
    if (idx < 0 || idx >= this.matchData.rounds_data.length) return;

    this.currentRoundIndex = idx;
    this.renderCurrentRound();

    if (this.onRoundChange) {
      this.onRoundChange(this.currentRoundIndex, this.currentRound);
    }
  }

  renderCurrentRound() {
    if (
      !this.matchData ||
      !this.matchData.rounds_data ||
      !this.matchData.rounds_data[this.currentRoundIndex]
    ) {
      return;
    }

    const round = this.matchData.rounds_data[this.currentRoundIndex];
    this.currentRound = round;
    const totalRounds = this.matchData.rounds || this.matchData.rounds_data.length;

    // 1. Update stepper indicators & button titles
    if (this.indicatorEl) {
      this.indicatorEl.textContent = t("replay.round_counter", round.round_number, totalRounds);
    }
    const roundTag = this.containerEl.querySelector("#replay-scoreboard-round-tag, .replay-round-tag") || document.getElementById("replay-scoreboard-round-tag");
    if (roundTag) {
      roundTag.textContent = t("replay.after_round", round.round_number);
    }
    if (this.prevBtn) {
      this.prevBtn.disabled = this.currentRoundIndex === 0;
      this.prevBtn.title = t("replay.prev_round");
      this.prevBtn.setAttribute("aria-label", t("replay.prev_round"));
    }
    if (this.nextBtn) {
      this.nextBtn.disabled = this.currentRoundIndex === this.matchData.rounds_data.length - 1;
      this.nextBtn.title = t("replay.next_round");
      this.nextBtn.setAttribute("aria-label", t("replay.next_round"));
    }

    // 2. Render photo canvas via RoundStage
    if (this.roundStage) {
      const isLocMode = this.matchData?.location_mode !== false;
      const isDateMode = this.matchData?.date_mode !== false;
      this.roundStage.setModes({ locationMode: isLocMode, dateMode: isDateMode });
      const batchPhotos = this._getBatchPhotos(round);
      this.roundStage.setPhotos(batchPhotos, 0);
    }

    // 3. Render map via Strategy
    this.renderRoundMap(round);

    // 4. Render scores table via Strategy
    this.renderPlayerGuesses(round);
  }

  _getBatchPhotos(round) {
    if (round.batch_photos && round.batch_photos.length > 0) {
      const usedLetters = new Set();
      const photos = round.batch_photos.map((p, idx) => {
        let pinId = p.true_pin_id ? String(p.true_pin_id).trim().toUpperCase() : "";
        if (!pinId || usedLetters.has(pinId)) {
          const rawIdx = p.photo_index != null ? Number(p.photo_index) : idx;
          let candidate = String.fromCharCode(65 + rawIdx);
          let offset = 0;
          while (usedLetters.has(candidate)) {
            offset++;
            candidate = String.fromCharCode(65 + ((rawIdx + offset) % 26));
          }
          pinId = candidate;
        }
        usedLetters.add(pinId);
        return {
          ...p,
          true_pin_id: pinId,
        };
      });
      return photos.sort((a, b) => {
        const pa = a.true_pin_id || "";
        const pb = b.true_pin_id || "";
        return pa < pb ? -1 : pa > pb ? 1 : 0;
      });
    }
    return [
      {
        asset_id: round.asset_id,
        actual_latitude: round.actual_latitude,
        actual_longitude: round.actual_longitude,
        actual_date: round.actual_date,
        actual_city: round.actual_city,
        actual_country: round.actual_country,
        actual_year: round.actual_year,
        actual_month: round.actual_month,
      },
    ];
  }

  renderRoundMap(round) {
    if (!this.map || !window.L) return;

    if (typeof this.mapMarkers._cleanupSpiderfy === "function") {
      try {
        this.mapMarkers._cleanupSpiderfy();
      } catch (_) {}
    }
    this.mapMarkers.forEach((m) => {
      try {
        m.remove();
      } catch (_) {}
    });
    this.mapPolylines.forEach((l) => {
      try {
        l.remove();
      } catch (_) {}
    });
    this.mapMarkers = [];
    this.mapPolylines = [];
    this.markersByPin = {};

    // Purge any residual spider lines or origin anchors directly from the map
    if (typeof this.map.eachLayer === "function") {
      this.map.eachLayer((layer) => {
        if (
          layer.options &&
          (layer.options.className === "spider-line" || layer.options.className === "spider-anchor")
        ) {
          try {
            this.map.removeLayer(layer);
          } catch (_) {}
        }
      });
    }

    const strategy = this.getStrategy(round);
    strategy.renderMap({
      map: this.map,
      roundStage: this.roundStage,
      round,
      matchData: this.matchData,
      mapMarkers: this.mapMarkers,
      mapPolylines: this.mapPolylines,
      markersByPin: this.markersByPin,
    });
  }

  renderPlayerGuesses(round) {
    const strategy = this.getStrategy(round);
    strategy.renderTable({
      table: this.table,
      round,
      matchData: this.matchData,
    });
  }

  destroy() {
    if (this._handleKeyDown) {
      document.removeEventListener("keydown", this._handleKeyDown);
      this._handleKeyDown = null;
    }
    if (typeof this.mapMarkers._cleanupSpiderfy === "function") {
      try {
        this.mapMarkers._cleanupSpiderfy();
      } catch (_) {}
    }
    this.mapMarkers.forEach((m) => {
      try {
        m.remove();
      } catch (_) {}
    });
    this.mapPolylines.forEach((l) => {
      try {
        l.remove();
      } catch (_) {}
    });
    this.mapMarkers = [];
    this.mapPolylines = [];
    this.markersByPin = {};

    if (this.map) {
      if (typeof this.map.eachLayer === "function") {
        this.map.eachLayer((layer) => {
          if (
            layer.options &&
            (layer.options.className === "spider-line" || layer.options.className === "spider-anchor")
          ) {
            try {
              this.map.removeLayer(layer);
            } catch (_) {}
          }
        });
      }
      try {
        unregisterActiveMap(this.map);
        this.map.remove();
      } catch (_) {}
      this.map = null;
    }
  }
}

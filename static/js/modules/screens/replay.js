/**
 * Interactive Match Replay Screen Controller
 * Steps through match history round-by-round with synchronized media-frame photos,
 * Leaflet maps showing actual vs player guesses, and running scoreboards.
 * Reuses standard map-shell and media-frame components and lightbox.
 */

import { state, el } from "../state.js";
import { t, formatDateTime } from "../i18n.js";
import { showCard } from "./common.js";
import { navigate } from "../router.js";
import {
  PLAYER_COLORS,
  playerColor,
  playerInitial,
  escapeHtml,
  ACTUAL_COLOR,
  formatDistance,
  formatMonthError,
  formatRankBadge,
  registerPlayerColor,
  clearPlayerColors,
} from "../formatters.js";
import {
  createStandardMap,
  unregisterActiveMap,
  createPinIcon,
  fitMapToBounds,
  toggleMapFullscreen,
} from "../maps.js";
import { openPhotoLightbox } from "../components/lightbox.js";
import { renderMatchMeta } from "../components/match_meta.js";

let _matchData = null;
let _currentRoundIndex = 0;
let _currentPhotoIndex = 0;
let _replayMap = null;
let _mapMarkers = [];
let _mapPolylines = [];
let _listenersBound = false;

export function initReplay() {
  if (_listenersBound) return;
  _listenersBound = true;

  const backBtn = document.getElementById("replay-back-btn");
  if (backBtn) {
    backBtn.addEventListener("click", () => {
      navigate("/stats/replays");
    });
  }

  const errBackBtn = document.getElementById("replay-error-back-btn");
  if (errBackBtn) {
    errBackBtn.addEventListener("click", () => {
      navigate("/stats/replays");
    });
  }

  const prevBtn = document.getElementById("replay-prev-round-btn");
  if (prevBtn) {
    prevBtn.addEventListener("click", () => {
      goToRound(_currentRoundIndex - 1);
    });
  }

  const nextBtn = document.getElementById("replay-next-round-btn");
  if (nextBtn) {
    nextBtn.addEventListener("click", () => {
      goToRound(_currentRoundIndex + 1);
    });
  }

  // Wire photo click to lightbox and fullscreen button to toggleMapFullscreen
  const photoImg = document.getElementById("replay-photo-img");
  if (photoImg) {
    photoImg.addEventListener("click", () => {
      if (photoImg.src) {
        openPhotoLightbox(photoImg.src);
      }
    });
  }

  const photoFullscreen = document.getElementById("replay-photo-fullscreen");
  const mediaFrame = document.getElementById("replay-media-frame");
  if (photoFullscreen && mediaFrame) {
    photoFullscreen.addEventListener("click", (e) => {
      e.stopPropagation();
      toggleMapFullscreen(mediaFrame);
    });
  }
}

export async function showMatchReplay(matchId) {
  showCard(el.replayPageCard);

  const loadingEl = document.getElementById("replay-loading-state");
  const errorEl = document.getElementById("replay-error-state");
  const contentGrid = document.getElementById("replay-content-grid");

  if (loadingEl) loadingEl.classList.remove("hidden");
  if (errorEl) errorEl.classList.add("hidden");
  if (contentGrid) contentGrid.classList.add("hidden");

  try {
    const res = await fetch(`/api/match/${encodeURIComponent(matchId)}/replay`);
    if (!res.ok) throw new Error("Failed to load match replay");
    _matchData = await res.json();
    _currentRoundIndex = 0;
    _currentPhotoIndex = 0;

    // Reset and register player colors in standard sequence
    clearPlayerColors();
    if (Array.isArray(_matchData.players)) {
      state.players = _matchData.players.map((p) => p.player_name);
      _matchData.players.forEach((p, idx) => {
        const color = p.player_color || PLAYER_COLORS[idx % PLAYER_COLORS.length];
        registerPlayerColor(p.player_name, color);
      });
    }
    if (Array.isArray(_matchData.rounds_data)) {
      _matchData.rounds_data.forEach((r) => {
        (r.player_guesses || []).forEach((g) => {
          if (g.player_name && g.player_color) {
            registerPlayerColor(g.player_name, g.player_color);
          }
        });
      });
    }

    if (loadingEl) loadingEl.classList.add("hidden");
    if (contentGrid) contentGrid.classList.remove("hidden");

    renderReplayShell();
    renderCurrentRound();
  } catch (err) {
    console.error("Error loading match replay:", err);
    if (loadingEl) loadingEl.classList.add("hidden");
    if (contentGrid) contentGrid.classList.add("hidden");
    if (errorEl) {
      errorEl.classList.remove("hidden");
      const errText = document.getElementById("replay-error-text");
      if (errText) errText.textContent = t("replay.not_found");
    }
  }
}

function renderReplayShell() {
  if (!_matchData) return;

  const modeBadge = document.getElementById("replay-mode-badge");
  const typeBadge = document.getElementById("replay-type-badge");
  const titleEl = document.getElementById("replay-match-title");

  const modeIcon = _matchData.game_mode === "album_shuffle" ? "🔀" : "🎯";
  const modeLabel = _matchData.game_mode === "album_shuffle" ? t("mode.album_shuffle") : t("mode.pinpoint");
  const isChallenge = _matchData.play_mode === "challenge";
  const typeLabel = isChallenge ? t("replay.play_mode_challenge") : t("replay.play_mode_local");
  const typeIcon = isChallenge ? "⚔️" : "👥";

  if (modeBadge) {
    modeBadge.textContent = `${modeIcon} ${modeLabel}`;
    modeBadge.className = "badge-tag badge-mode";
  }
  if (typeBadge) {
    typeBadge.textContent = `${typeIcon} ${typeLabel}`;
    typeBadge.className = `badge-tag badge-type${isChallenge ? " badge-challenge" : ""}`;
  }
  if (titleEl) {
    const totalCount = _matchData.rounds || (_matchData.rounds_data ? _matchData.rounds_data.length : 0);
    titleEl.textContent = `${t("stats.rounds_count", totalCount)} • ${formatDateTime(_matchData.played_at)}`;
  }

  const metaContainer = document.getElementById("replay-match-meta-container");
  if (metaContainer) {
    renderMatchMeta(metaContainer, _matchData);
  }

  // Initialize or reuse standard Leaflet Map
  const mapEl = document.getElementById("replay-leaflet-map");
  if (mapEl && window.L) {
    const needsNewMap =
      !_replayMap ||
      !_replayMap.getContainer ||
      _replayMap.getContainer() !== mapEl;

    if (needsNewMap) {
      _replayMap = createStandardMap(mapEl, {
        existingMap: _replayMap,
        titleKey: "game.fullscreen_map_title",
        fullscreenControl: true,
        resetZoomControl: true,
        layerControl: true,
      });
      _mapMarkers = [];
      _mapPolylines = [];
    } else {
      setTimeout(() => {
        try {
          _replayMap.invalidateSize();
        } catch (_) {}
      }, 50);
    }
  }
}

function goToRound(idx) {
  if (!_matchData || !Array.isArray(_matchData.rounds_data)) return;
  if (idx < 0 || idx >= _matchData.rounds_data.length) return;

  _currentRoundIndex = idx;
  _currentPhotoIndex = 0;
  renderCurrentRound();
}

function renderCurrentRound() {
  if (!_matchData || !_matchData.rounds_data || !_matchData.rounds_data[_currentRoundIndex]) return;

  const round = _matchData.rounds_data[_currentRoundIndex];
  const totalRounds = _matchData.rounds || _matchData.rounds_data.length;

  // Update round indicator & stepper buttons
  const ind = document.getElementById("replay-round-indicator");
  if (ind) ind.textContent = t("replay.round_counter", round.round_number, totalRounds);

  const prevBtn = document.getElementById("replay-prev-round-btn");
  const nextBtn = document.getElementById("replay-next-round-btn");
  if (prevBtn) prevBtn.disabled = _currentRoundIndex === 0;
  if (nextBtn) nextBtn.disabled = _currentRoundIndex === _matchData.rounds_data.length - 1;

  const roundTag = document.getElementById("replay-scoreboard-round-tag");
  if (roundTag) roundTag.textContent = t("replay.after_round", round.round_number);

  // Render Image Canvas / Photo frame
  renderPhotoCanvas(round);

  // Render Map markers & polylines
  renderRoundMap(round);

  // Render player guesses & standings list
  renderPlayerGuesses(round);
}

function renderPhotoCanvas(round) {
  const imgEl = document.getElementById("replay-photo-img");
  const locEl = document.getElementById("replay-photo-loc");
  const dateEl = document.getElementById("replay-photo-date");
  const tabsContainer = document.getElementById("replay-photo-tabs-container");

  // Determine active photo
  const photos = round.batch_photos && round.batch_photos.length > 0
    ? round.batch_photos
    : [{
        asset_id: round.asset_id,
        actual_latitude: round.actual_latitude,
        actual_longitude: round.actual_longitude,
        actual_date: round.actual_date,
        actual_city: round.actual_city,
        actual_country: round.actual_country,
      }];

  if (tabsContainer) {
    if (photos.length > 1) {
      tabsContainer.innerHTML = `
        <div class="replay-photo-tabs">
          ${photos
            .map(
              (p, idx) => `
              <button type="button" class="replay-photo-tab-btn ${idx === _currentPhotoIndex ? "active" : ""}" data-idx="${idx}">
                ${t("replay.photo_label", idx + 1, photos.length)}
              </button>
            `
            )
            .join("")}
        </div>
      `;
      tabsContainer.querySelectorAll(".replay-photo-tab-btn").forEach((btn) => {
        btn.addEventListener("click", () => {
          _currentPhotoIndex = parseInt(btn.getAttribute("data-idx"), 10);
          renderPhotoCanvas(round);
          renderRoundMap(round);
        });
      });
    } else {
      tabsContainer.innerHTML = "";
    }
  }

  const curPhoto = photos[_currentPhotoIndex] || photos[0];
  if (imgEl && curPhoto.asset_id) {
    imgEl.src = `/api/media/${encodeURIComponent(curPhoto.asset_id)}`;
  }

  const locParts = [curPhoto.actual_city, curPhoto.actual_country].filter(Boolean);
  const locStr = locParts.length > 0
    ? locParts.join(", ")
    : (curPhoto.actual_latitude != null
        ? `${curPhoto.actual_latitude.toFixed(3)}, ${curPhoto.actual_longitude.toFixed(3)}`
        : t("stats.location_unknown"));

  if (locEl) locEl.textContent = locStr;
  if (dateEl) dateEl.textContent = curPhoto.actual_date ? formatDateTime(curPhoto.actual_date) : "";
}

function renderRoundMap(round) {
  if (!_replayMap || !window.L) return;

  // Clear existing markers & lines without re-instantiating Leaflet
  _mapMarkers.forEach((m) => {
    try {
      m.remove();
    } catch (_) {}
  });
  _mapPolylines.forEach((l) => {
    try {
      l.remove();
    } catch (_) {}
  });
  _mapMarkers = [];
  _mapPolylines = [];

  const photos = round.batch_photos && round.batch_photos.length > 0
    ? round.batch_photos
    : [{
        actual_latitude: round.actual_latitude,
        actual_longitude: round.actual_longitude,
        actual_city: round.actual_city,
        actual_country: round.actual_country,
      }];
  const curPhoto = photos[_currentPhotoIndex] || photos[0];

  const mapShell = document.getElementById("replay-map-shell");
  const mediaRow = document.getElementById("replay-media-map-row");

  const hasCoordinates = curPhoto.actual_latitude != null && curPhoto.actual_longitude != null;
  const isLocationMode = _matchData?.location_mode !== false && (hasCoordinates || (round.player_guesses || []).some((g) => g.guess_latitude != null));

  if (!isLocationMode) {
    if (mapShell) mapShell.classList.add("hidden");
    if (mediaRow) mediaRow.classList.add("single-col");
    return;
  }

  if (mapShell) mapShell.classList.remove("hidden");
  if (mediaRow) mediaRow.classList.remove("single-col");

  const boundsPoints = [];

  // Actual location pin
  if (curPhoto.actual_latitude != null && curPhoto.actual_longitude != null) {
    const actualPt = [curPhoto.actual_latitude, curPhoto.actual_longitude];
    boundsPoints.push(actualPt);

    const actualIcon = createPinIcon("\u2605", ACTUAL_COLOR);

    const locParts = [curPhoto.actual_city, curPhoto.actual_country].filter(Boolean);
    const locText = locParts.length > 0 ? locParts.join(", ") : "";

    const actualMarker = L.marker(actualPt, { icon: actualIcon, zIndexOffset: 1000 })
      .addTo(_replayMap)
      .bindPopup(`<strong>★ ${escapeHtml(t("reveal.popup_actual"))}</strong>${locText ? `<br>${escapeHtml(locText)}` : ""}`);

    _mapMarkers.push(actualMarker);
  }

  // Player guesses pins
  const guesses = round.player_guesses || [];
  const coordsSeen = {};

  guesses.forEach((g) => {
    if (g.guess_latitude == null || g.guess_longitude == null) return;

    let lat = g.guess_latitude;
    let lng = g.guess_longitude;

    // Spiderfy / Jitter slightly if duplicate coordinates
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
      .addTo(_replayMap)
      .bindPopup(`
        <div style="font-size: 0.86rem;">
          <strong style="color: ${escapeHtml(pColor)};">${escapeHtml(g.player_name)}</strong><br>
          ${escapeHtml(t("summary.col_total"))}: <strong>+${g.round_score} pts</strong><br>
          ${g.distance_km != null ? `${escapeHtml(t("summary.col_location"))}: ${formatDistance(g.distance_km)}<br>` : ""}
          ${g.time_taken_seconds != null ? `⏱️ ${g.time_taken_seconds}s` : ""}
        </div>
      `);

    _mapMarkers.push(marker);

    // Dashed polyline connecting guess to actual
    if (curPhoto.actual_latitude != null && curPhoto.actual_longitude != null) {
      const line = L.polyline([guessPt, [curPhoto.actual_latitude, curPhoto.actual_longitude]], {
        color: pColor,
        weight: 3,
        dashArray: "8, 8",
        opacity: 0.85,
      }).addTo(_replayMap);
      _mapPolylines.push(line);
    }
  });

  // Fit bounds using standard map utility and enable reset-zoom
  if (boundsPoints.length === 1) {
    try {
      _replayMap.invalidateSize();
      _replayMap.setView(boundsPoints[0], 12);
      _replayMap._lastFitBounds = L.latLngBounds([boundsPoints[0], boundsPoints[0]]);
    } catch (_) {}
  } else if (boundsPoints.length > 1) {
    fitMapToBounds(_replayMap, boundsPoints, { padding: [35, 35], maxZoom: 15 });
  }
}

function renderPlayerGuesses(round) {
  const container = document.getElementById("replay-guesses-list");
  if (!container) return;

  const guesses = round.player_guesses || [];
  if (guesses.length === 0) {
    container.innerHTML = `<div style="color: var(--text-muted); font-size: 0.85rem;">${t("replay.no_guesses")}</div>`;
    return;
  }

  // Sort by cumulative score descending (with round_score as secondary tie-breaker)
  const sorted = [...guesses].sort((a, b) => {
    const diff = (b.cumulative_score ?? 0) - (a.cumulative_score ?? 0);
    if (diff !== 0) return diff;
    return (b.round_score ?? 0) - (a.round_score ?? 0);
  });

  const isMultiplayer = sorted.length > 1;

  container.innerHTML = sorted
    .map((g, idx) => {
      const rank = idx + 1;
      const rankBadgeHtml = isMultiplayer ? formatRankBadge(rank, { showNumber: false }) : "";
      const initial = playerInitial(g.player_name);
      const pColor = g.player_color || playerColor(g.player_name);
      const distStr = g.distance_km != null ? formatDistance(g.distance_km) : "";
      const dateStr = g.date_diff_days != null ? formatMonthError({ date_diff_days: g.date_diff_days }) : "";
      const timeStr = g.time_taken_seconds != null ? `${Number(g.time_taken_seconds).toFixed(1)}s` : "";
      const cumulativeScore = g.cumulative_score != null ? g.cumulative_score.toLocaleString() : null;

      return `
        <div class="replay-guess-row ${isMultiplayer && rank === 1 ? "rank-1" : ""}">
          <div class="replay-guess-player">
            ${isMultiplayer ? `<span class="replay-standing-rank">${rankBadgeHtml}</span>` : ""}
            <span class="legend-badge replay-guess-avatar" style="background:${escapeHtml(pColor)};">
              ${escapeHtml(initial)}
            </span>
            <span class="replay-guess-name">${escapeHtml(g.player_name)}</span>
            ${g.timed_out ? `<span class="timed-out-tag">${t("fmt.timed_out_tag")}</span>` : ""}
          </div>

          <div class="replay-guess-metrics">
            ${distStr ? `<span class="replay-guess-metric-item" title="${escapeHtml(t("stats.best_distance"))}">📍 ${escapeHtml(distStr)}</span>` : ""}
            ${dateStr ? `<span class="replay-guess-metric-item" title="${escapeHtml(t("game.date_label"))}">📅 ${escapeHtml(dateStr)}</span>` : ""}
            ${timeStr ? `<span class="replay-guess-metric-item" title="${escapeHtml(t("stats.response_time"))}">⏱️ ${escapeHtml(timeStr)}</span>` : ""}
          </div>

          <div class="replay-guess-score-col">
            <span class="replay-guess-score">+${g.round_score.toLocaleString()}</span>
            ${cumulativeScore != null ? `<span class="replay-guess-cumulative">${escapeHtml(t("summary.col_total"))}: ${cumulativeScore}</span>` : ""}
          </div>
        </div>
      `;
    })
    .join("");
}

/**
 * Refresh replay screen in realtime when language toggle changes.
 */
export function refreshReplayPageLanguage() {
  const card = el.replayPageCard || document.getElementById("replay-page-card");
  if (!card || card.classList.contains("hidden")) return;

  if (_matchData) {
    const modeBadge = document.getElementById("replay-mode-badge");
    const typeBadge = document.getElementById("replay-type-badge");
    const titleEl = document.getElementById("replay-match-title");

    const modeIcon = _matchData.game_mode === "album_shuffle" ? "🔀" : "🎯";
    const modeLabel = _matchData.game_mode === "album_shuffle" ? t("mode.album_shuffle") : t("mode.pinpoint");
    const isChallenge = _matchData.play_mode === "challenge";
    const typeLabel = isChallenge ? t("replay.play_mode_challenge") : t("replay.play_mode_local");
    const typeIcon = isChallenge ? "⚔️" : "👥";

    if (modeBadge) {
      modeBadge.textContent = `${modeIcon} ${modeLabel}`;
      modeBadge.className = "badge-tag badge-mode";
    }
    if (typeBadge) {
      typeBadge.textContent = `${typeIcon} ${typeLabel}`;
      typeBadge.className = `badge-tag badge-type${isChallenge ? " badge-challenge" : ""}`;
    }
    if (titleEl) {
      const totalCount = _matchData.rounds || (_matchData.rounds_data ? _matchData.rounds_data.length : 0);
      titleEl.textContent = `${t("stats.rounds_count", totalCount)} • ${formatDateTime(_matchData.played_at)}`;
    }

    const metaContainer = document.getElementById("replay-match-meta-container");
    if (metaContainer) {
      renderMatchMeta(metaContainer, _matchData);
    }

    renderCurrentRound();
  }
}

import { t } from "../i18n.js";
import { el, state } from "../state.js";
import { ensureGuessMap, ensureRevealMap, createPinIcon, createPopPinIcon, toggleMapFullscreen, fitMapToBounds, spawnPinPulseEffect, unregisterActiveMap } from "../maps.js";
import { renderGuessingModeSettings } from "./common.js";
import { openPhotoLightbox } from "../components/lightbox.js";
import {
  ACTUAL_COLOR,
  playerColor,
  playerInitial,
  formatMonth,
  formatPlace,
  formatDistance,
  formatMonthError,
  buildCell,
  playerBadge,
  playerNameCell,
  renderRoundMeta,
} from "../formatters.js";
import {
  createPerfectBadge,
  animateScoreRollup,
  launchGoldConfetti,
  launchStarBurst,
} from "../effects.js";
import { playChime, playPinDropSound } from "../audio.js";
import { renderRevealTableHeaders, renderRevealTableRows } from "../components/reveal_table.js";
import { challenge } from "../challenge/index.js";

const EARLIEST_YEAR = 1930;
const SMART_MAP_MAX_INITIAL_ZOOM = 13;

function stepSelectOption(selectEl, direction) {
  if (!selectEl || selectEl.disabled || selectEl.options.length === 0) {
    return;
  }
  const current = selectEl.selectedIndex;
  const next = Math.max(0, Math.min(selectEl.options.length - 1, current + direction));
  if (next === current) {
    return;
  }
  selectEl.selectedIndex = next;
  selectEl.dispatchEvent(new Event("change", { bubbles: true }));
}

function bindDateWheelScroll(yearSelect, monthSelect) {
  if (!yearSelect || !monthSelect) return;

  if (!yearSelect.dataset.wheelBound) {
    yearSelect.dataset.wheelBound = "true";
    yearSelect.addEventListener(
      "wheel",
      (event) => {
        event.preventDefault();
        if (yearSelect.disabled) return;
        const direction = event.deltaY > 0 ? 1 : -1;
        stepSelectOption(yearSelect, direction);
      },
      { passive: false }
    );
  }

  if (!monthSelect.dataset.wheelBound) {
    monthSelect.dataset.wheelBound = "true";
    monthSelect.addEventListener(
      "wheel",
      (event) => {
        event.preventDefault();
        if (monthSelect.disabled) return;

        const currentYear = new Date().getFullYear();
        const deltaDir = event.deltaY > 0 ? -1 : 1;
        const currentMonthIdx = monthSelect.selectedIndex;
        const maxMonthIdx = monthSelect.options.length - 1;

        if (deltaDir === 1) {
          if (currentMonthIdx < maxMonthIdx) {
            monthSelect.selectedIndex = currentMonthIdx + 1;
            monthSelect.dispatchEvent(new Event("change", { bubbles: true }));
          } else {
            const selectedYear = Number(yearSelect.value);
            if (selectedYear < currentYear) {
              yearSelect.value = String(selectedYear + 1);
              renderMonthOptions(false);
              monthSelect.value = "1";
              yearSelect.dispatchEvent(new Event("change", { bubbles: true }));
              monthSelect.dispatchEvent(new Event("change", { bubbles: true }));
            }
          }
        } else if (deltaDir === -1) {
          if (currentMonthIdx > 0) {
            monthSelect.selectedIndex = currentMonthIdx - 1;
            monthSelect.dispatchEvent(new Event("change", { bubbles: true }));
          } else {
            const selectedYear = Number(yearSelect.value);
            if (selectedYear > EARLIEST_YEAR) {
              yearSelect.value = String(selectedYear - 1);
              renderMonthOptions(false);
              monthSelect.value = String(monthSelect.options.length);
              yearSelect.dispatchEvent(new Event("change", { bubbles: true }));
              monthSelect.dispatchEvent(new Event("change", { bubbles: true }));
            }
          }
        }
      },
      { passive: false }
    );
  }
}

function initDateDropdowns() {
  if (!el.dateGuessYear || !el.dateGuessMonth) return;
  const currentYear = new Date().getFullYear();

  el.dateGuessYear.replaceChildren();
  for (let year = currentYear; year >= EARLIEST_YEAR; year -= 1) {
    const option = document.createElement("option");
    option.value = String(year);
    option.textContent = String(year);
    el.dateGuessYear.appendChild(option);
  }

  el.dateGuessYear.value = String(currentYear);
  renderMonthOptions();

  bindDateWheelScroll(el.dateGuessYear, el.dateGuessMonth);

  if (!el.dateGuessYear.dataset.changeBound) {
    el.dateGuessYear.dataset.changeBound = "true";
    el.dateGuessYear.addEventListener("change", () => renderMonthOptions(true));
  }
}

function renderMonthOptions(keepSelection = true) {
  if (!el.dateGuessYear || !el.dateGuessMonth) return;
  const now = new Date();
  const currentYear = now.getFullYear();
  const currentMonth = now.getMonth() + 1;
  const selectedYear = Number(el.dateGuessYear.value);
  const maxMonth = selectedYear >= currentYear ? currentMonth : 12;
  const previous = Number(el.dateGuessMonth.value);

  el.dateGuessMonth.replaceChildren();
  for (let month = 1; month <= maxMonth; month += 1) {
    const option = document.createElement("option");
    option.value = String(month);
    option.textContent = String(month).padStart(2, "0");
    el.dateGuessMonth.appendChild(option);
  }

  const keep = keepSelection && previous >= 1 && previous <= maxMonth;
  el.dateGuessMonth.value = String(keep ? previous : maxMonth);
}

function resetDateGuess() {
  if (!el.dateGuessYear || !el.dateGuessMonth) return;
  const now = new Date();
  el.dateGuessYear.value = String(now.getFullYear());
  renderMonthOptions(false);
}

function clearRevealAnimation() {
  if (state.revealAnimationFrameId !== null) {
    cancelAnimationFrame(state.revealAnimationFrameId);
    state.revealAnimationFrameId = null;
  }
  if (state.revealAnimationTimeoutId !== null) {
    clearTimeout(state.revealAnimationTimeoutId);
    state.revealAnimationTimeoutId = null;
  }
}


function renderRevealSummary(reveal, skipEffects = false) {
  const activePlayer = challenge && challenge.isActive() ? challenge.challengeSession?.sessionPlayerName : null;
  renderRoundMeta(el.roundMeta, {
    roundNum: reveal.round_number,
    totalRounds: reveal.total_rounds,
    isReveal: true,
    playerName: activePlayer,
  });

  el.revealActual.replaceChildren();

  const pr = reveal.pinpoint_reveal;
  if (reveal.date_mode && pr) {
    const dateChip = document.createElement("span");
    dateChip.className = "reveal-actual-chip reveal-chip-date";

    const dateIcon = document.createElement("span");
    dateIcon.className = "reveal-chip-icon";
    dateIcon.setAttribute("aria-hidden", "true");
    dateIcon.textContent = "📅";

    const labelSpan = document.createElement("span");
    labelSpan.className = "reveal-chip-label";
    labelSpan.setAttribute("data-i18n", "reveal.actual_date");
    labelSpan.textContent = t("reveal.actual_date");

    const valSpan = document.createElement("strong");
    valSpan.className = "reveal-chip-val";
    valSpan.textContent = ` ${formatMonth(pr.actual_year, pr.actual_month)}`;

    dateChip.append(dateIcon, labelSpan, valSpan);
    el.revealActual.appendChild(dateChip);
  }
  if (reveal.location_mode && pr) {
    const locChip = document.createElement("span");
    locChip.className = "reveal-actual-chip reveal-chip-location";

    const locIcon = document.createElement("span");
    locIcon.className = "reveal-chip-icon";
    locIcon.setAttribute("aria-hidden", "true");
    locIcon.textContent = "🗺️";

    const labelSpan = document.createElement("span");
    labelSpan.className = "reveal-chip-label";
    labelSpan.setAttribute("data-i18n", "reveal.actual_location");
    labelSpan.textContent = t("reveal.actual_location");

    const valSpan = document.createElement("strong");
    valSpan.className = "reveal-chip-val";
    valSpan.textContent = ` ${formatPlace(pr)}`;

    locChip.append(locIcon, labelSpan, valSpan);
    el.revealActual.appendChild(locChip);
  }

  // Update persistent player stats
  const maxPoints = reveal.score_max_points || state.scoreMaxPoints || 100;
  const maxRoundPoints = (reveal.location_mode ? maxPoints : 0) + (reveal.date_mode ? maxPoints : 0);

  (reveal.results || []).forEach((result) => {
    const p = result.pinpoint || result;
    const isPerfectLocation = reveal.location_mode && (result.location_score === maxPoints || p.distance_km === 0);
    const isPerfectDate = reveal.date_mode && (result.date_score === maxPoints || p.date_diff_days === 0);
    const isPerfectRound = maxRoundPoints > 0 && result.round_score === maxRoundPoints;
    const isPerfectPlayer = isPerfectLocation || isPerfectDate || isPerfectRound;

    if (isPerfectPlayer) {
      state.perfectCounts[result.player_name] = (state.perfectCounts[result.player_name] || 0) + 1;
    }

    if (!state.playerStats[result.player_name]) {
      state.playerStats[result.player_name] = {
        totalDistanceKm: 0, distanceCount: 0,
        totalDateDiffDays: 0, dateCount: 0,
        perfectLocationCount: 0, perfectDateCount: 0,
        perfectRounds: 0, timedOutCount: 0, fastRoundCount: 0, totalDurationSec: 0,
      };
    }
    const ps = state.playerStats[result.player_name];
    if (p.distance_km !== null && p.distance_km !== undefined) {
      ps.totalDistanceKm += p.distance_km;
      ps.distanceCount += 1;
    }
    if (p.date_diff_days !== null && p.date_diff_days !== undefined) {
      ps.totalDateDiffDays += p.date_diff_days;
      ps.dateCount += 1;
    }
    if (isPerfectLocation) ps.perfectLocationCount += 1;
    if (isPerfectDate) ps.perfectDateCount += 1;
    if (isPerfectPlayer) ps.perfectRounds += 1;
    if (result.timed_out) ps.timedOutCount += 1;
  });

  const table = el.revealTable || document.getElementById("reveal-table");
  renderRevealTableHeaders(table, {
    locationMode: Boolean(reveal.location_mode),
    dateMode: Boolean(reveal.date_mode),
    gameMode: "pinpoint",
    showRank: false,
  });

  const hasAnyPerfectInRound = renderRevealTableRows(table, reveal.results, {
    locationMode: Boolean(reveal.location_mode),
    dateMode: Boolean(reveal.date_mode),
    gameMode: "pinpoint",
    maxPoints,
    skipEffects,
    showRank: false,
  });

  if (!skipEffects && hasAnyPerfectInRound) {
    playChime();
    launchStarBurst();
    launchGoldConfetti();
  }
}

function renderRevealMap(reveal) {
  const mediaRow = document.getElementById("pinpoint-media-map-row");
  if (!reveal.location_mode) {
    if (el.revealMapShell) el.revealMapShell.classList.add("hidden");
    if (mediaRow) mediaRow.classList.add("single-col");
    clearRevealAnimation();
    return;
  }
  if (el.revealMapShell) el.revealMapShell.classList.remove("hidden");
  if (mediaRow) mediaRow.classList.remove("single-col");

  ensureRevealMap();
  clearRevealAnimation();

  state.revealLayers.forEach((layer) => state.revealMap.removeLayer(layer));
  state.revealLayers = [];

  const pr = reveal.pinpoint_reveal;
  const actualLat = pr && pr.actual_latitude != null ? Number(pr.actual_latitude) : NaN;
  const actualLng = pr && pr.actual_longitude != null ? Number(pr.actual_longitude) : NaN;
  if (!pr || !Number.isFinite(actualLat) || !Number.isFinite(actualLng)) {
    return;
  }

  const actual = L.latLng(actualLat, actualLng);
  if (!actual || typeof actual.lat !== "number" || typeof actual.lng !== "number" || isNaN(actual.lat) || isNaN(actual.lng)) {
    return;
  }

  const actualMarker = L.marker(actual, {
    icon: createPinIcon("\u2605", ACTUAL_COLOR),
    zIndexOffset: 1000,
  })
    .addTo(state.revealMap)
    .bindPopup(t("reveal.popup_actual"));
  state.revealLayers.push(actualMarker);

  const points = [actual];
  const playerGuesses = [];

  (reveal.results || []).forEach((result) => {
    const p = result.pinpoint || result;
    if (!p || p.guessed_latitude == null || p.guessed_longitude == null) {
      return;
    }
    const gLat = Number(p.guessed_latitude);
    const gLng = Number(p.guessed_longitude);
    if (!Number.isFinite(gLat) || !Number.isFinite(gLng)) {
      return;
    }
    const guessed = L.latLng(gLat, gLng);
    if (!guessed || typeof guessed.lat !== "number" || typeof guessed.lng !== "number" || isNaN(guessed.lat) || isNaN(guessed.lng)) {
      return;
    }
    points.push(guessed);
    playerGuesses.push({ result, guessed, distance_km: p.distance_km });
  });

  fitMapToBounds(state.revealMap, points, { padding: [50, 50], maxZoom: 15 });

  if (playerGuesses.length === 0) {
    return;
  }

  const lineDuration = 1300;

  state.revealAnimationTimeoutId = window.setTimeout(() => {
    state.revealAnimationTimeoutId = null;
    if (!state.revealMap) return;
    const lineEntries = playerGuesses
      .filter(({ guessed }) => guessed && typeof guessed.lat === "number" && typeof guessed.lng === "number")
      .map(({ result, guessed, distance_km }) => {
        const color = playerColor(result.player_name);
        const line = L.polyline([actual, actual], {
          color,
          weight: 3,
          dashArray: "8, 8",
          opacity: 0.85,
        }).addTo(state.revealMap);
        state.revealLayers.push(line);
        return { result, guessed, color, line, distance_km };
      });

    const startTime = performance.now();

    function animateAllLines(now) {
      if (!state.revealMap) {
        state.revealAnimationFrameId = null;
        return;
      }
      const elapsed = now - startTime;
      const progress = Math.min(1, elapsed / lineDuration);

      lineEntries.forEach(({ guessed, line }) => {
        if (!line._map || !guessed || typeof guessed.lat !== "number" || typeof actual.lat !== "number") return;
        const curLat = actual.lat + (guessed.lat - actual.lat) * progress;
        const curLng = actual.lng + (guessed.lng - actual.lng) * progress;
        line.setLatLngs([actual, [curLat, curLng]]);
      });

      if (progress < 1) {
        state.revealAnimationFrameId = window.requestAnimationFrame(animateAllLines);
      } else {
        state.revealAnimationFrameId = null;
        if (!state.revealMap) return;
        lineEntries.forEach(({ result, guessed, color, distance_km }) => {
          if (!guessed || typeof guessed.lat !== "number" || typeof guessed.lng !== "number") return;
          const icon = createPopPinIcon(playerInitial(result.player_name), color);
          const marker = L.marker(guessed, { icon })
            .addTo(state.revealMap)
            .bindPopup(t("reveal.popup_guess", result.player_name, formatDistance(distance_km)));
          state.revealLayers.push(marker);
        });
      }
    }

    state.revealAnimationFrameId = window.requestAnimationFrame(animateAllLines);
  }, 350);
}

let helpModalInitialized = false;

function ensurePinpointHelpModal() {
  const modal = el.pinpointHelpModal || document.getElementById("pinpoint-help-modal");
  if (!modal) return null;

  if (!helpModalInitialized) {
    helpModalInitialized = true;
    const closeBtn = el.pinpointHelpCloseBtn || modal.querySelector(".modal-close-btn");
    if (closeBtn) {
      closeBtn.addEventListener("click", () => {
        modal.classList.add("hidden");
        modal.setAttribute("aria-hidden", "true");
      });
    }

    let isBackdropPress = false;
    modal.addEventListener("pointerdown", (event) => {
      isBackdropPress = (event.target === modal);
    });
    modal.addEventListener("click", (event) => {
      if (isBackdropPress && event.target === modal) {
        modal.classList.add("hidden");
        modal.setAttribute("aria-hidden", "true");
      }
      isBackdropPress = false;
    });

    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape" && !modal.classList.contains("hidden")) {
        modal.classList.add("hidden");
        modal.setAttribute("aria-hidden", "true");
      }
    });
  }

  return modal;
}

function openPinpointHelpModal(questionData) {
  const modal = ensurePinpointHelpModal();
  if (!modal) return;

  const titleEl = modal.querySelector("#pinpoint-help-title");
  if (titleEl) titleEl.textContent = t("game.pinpoint_help_title");

  const body = modal.querySelector(".pinpoint-help-body, .mode-help-body");
  if (!body) return;

  const locationMode = questionData?.location_mode !== false;
  const dateMode = questionData?.date_mode !== false;

  const sections = [];
  if (locationMode) {
    const locItems = [
      t("game.pinpoint_help_location_item1"),
      t("game.pinpoint_help_location_item2"),
      t("game.pinpoint_help_location_item3"),
    ].filter(s => s && s.trim());
    sections.push(`
      <div class="mode-help-section pinpoint-help-section">
        <h4>${t("game.pinpoint_help_location_title")}</h4>
        <ul>
          ${locItems.map(item => `<li>${item}</li>`).join("")}
        </ul>
      </div>
    `);
  }

  if (dateMode) {
    const dateItems = [
      t("game.pinpoint_help_date_item1"),
      t("game.pinpoint_help_date_item2"),
      t("game.pinpoint_help_date_item3"),
    ].filter(s => s && s.trim());
    sections.push(`
      <div class="mode-help-section pinpoint-help-section">
        <h4>${t("game.pinpoint_help_date_title")}</h4>
        <ul>
          ${dateItems.map(item => `<li>${item}</li>`).join("")}
        </ul>
      </div>
    `);
  }

  sections.push(`
    <div class="mode-help-section pinpoint-help-section">
      <h4>${t("game.pinpoint_help_photo_title")}</h4>
      <ul>
        <li>${t("game.pinpoint_help_photo_item1")}</li>
      </ul>
    </div>
  `);

  body.innerHTML = sections.join("");
  modal.classList.remove("hidden");
  modal.setAttribute("aria-hidden", "false");
}

export const pinpointMode = {
  name: "pinpoint",

  renderSettings(containerEl) {
    renderGuessingModeSettings(containerEl, "pinpoint");
  },

  getModePayload() {
    const locCard = document.getElementById("card-goal-location");
    const locCheckbox = document.getElementById("goal-location");
    const dateCard = document.getElementById("card-goal-date");
    const dateCheckbox = document.getElementById("goal-date");

    let locationMode = locCheckbox ? locCheckbox.checked : (locCard ? locCard.classList.contains("active") : true);
    let dateMode = dateCheckbox ? dateCheckbox.checked : (dateCard ? dateCard.classList.contains("active") : true);

    if (!locationMode && !dateMode) {
      locationMode = true;
      dateMode = true;
    }

    return {
      game_mode: "pinpoint",
      location_mode: locationMode,
      date_mode: dateMode,
    };
  },

  mount(hostEl, matchConfig) {
    this.hostEl = hostEl;
    const host = document.getElementById("mode-active-host") || hostEl;
    if (host) {
      host.replaceChildren();
      const tmpl = document.getElementById("tmpl-mode-pinpoint");
      if (tmpl) {
        host.appendChild(tmpl.content.cloneNode(true));
      }
    }
    const pinpointUi = document.getElementById("pinpoint-ui");
    if (pinpointUi) {
      pinpointUi.classList.remove("hidden");
    }

    initDateDropdowns();

    if (el.quizImage) {
      el.quizImage.onclick = () => {
        if (el.quizImage.src) {
          openPhotoLightbox(el.quizImage.src);
        }
      };
    }

    if (el.quizImageFullscreen) {
      el.quizImageFullscreen.onclick = (e) => {
        e.stopPropagation();
        toggleMapFullscreen(el.mediaFrame);
      };
    }
    if (el.guessMapFullscreen) {
      if (window.L && L.DomEvent) {
        L.DomEvent.disableClickPropagation(el.guessMapFullscreen);
        L.DomEvent.disableScrollPropagation(el.guessMapFullscreen);
      }
      el.guessMapFullscreen.onclick = (e) => {
        e.stopPropagation();
        toggleMapFullscreen(el.guessMapShell);
      };
    }
    if (el.revealMapFullscreen) {
      if (window.L && L.DomEvent) {
        L.DomEvent.disableClickPropagation(el.revealMapFullscreen);
        L.DomEvent.disableScrollPropagation(el.revealMapFullscreen);
      }
      el.revealMapFullscreen.onclick = (e) => {
        e.stopPropagation();
        toggleMapFullscreen(el.revealMapShell);
      };
    }
  },

  toggleMapFullscreen() {
    toggleMapFullscreen(el.guessMapShell);
  },

  togglePhotoFullscreen() {
    if (state.currentScreen === "reveal") {
      const stageMediaFrame = document.getElementById("pinpoint-reveal-media-frame");
      if (stageMediaFrame) {
        toggleMapFullscreen(stageMediaFrame);
        return;
      }
    }
    if (el.mediaFrame) {
      toggleMapFullscreen(el.mediaFrame);
    }
  },

  setDisabled(disabled) {
    if (el.dateGuessYear) el.dateGuessYear.disabled = disabled;
    if (el.dateGuessMonth) el.dateGuessMonth.disabled = disabled;
  },

  unmount() {
    clearRevealAnimation();
    if (el.mediaFrame) {
      el.mediaFrame.classList.add("hidden");
    }
    if (el.quizImage) {
      el.quizImage.onclick = null;
    }
    if (el.quizImageFullscreen) {
      el.quizImageFullscreen.classList.add("hidden");
    }
    if (state.guessMap) {
      try { unregisterActiveMap(state.guessMap); state.guessMap.remove(); } catch (_) { }
      state.guessMap = null;
    }
    if (state.guessMarker) {
      try { state.guessMarker.remove(); } catch (_) { }
      state.guessMarker = null;
    }
    if (state.revealMap) {
      (state.revealLayers || []).forEach((l) => {
        try { state.revealMap.removeLayer(l); } catch (_) { }
      });
      state.revealLayers = [];
      try { unregisterActiveMap(state.revealMap); state.revealMap.remove(); } catch (_) { }
      state.revealMap = null;
    }
    const host = document.getElementById("mode-active-host");
    if (host) {
      host.replaceChildren();
    }
    const pinpointReveal = document.getElementById("pinpoint-reveal-ui");
    if (pinpointReveal) {
      pinpointReveal.classList.add("hidden");
    }
  },

  renderQuestion(questionData) {
    const pinpointUi = document.getElementById("pinpoint-ui");
    if (pinpointUi) {
      pinpointUi.classList.remove("hidden");
    }

    if (el.mediaFrame) el.mediaFrame.classList.remove("hidden");
    if (el.mapGuessWrap) el.mapGuessWrap.classList.toggle("hidden", !questionData.location_mode);
    if (el.dateGuessWrap) el.dateGuessWrap.classList.toggle("hidden", !questionData.date_mode);

    const hasMapOnly = Boolean(questionData.location_mode) && !Boolean(questionData.date_mode);
    if (hasMapOnly) {
      document.documentElement.style.setProperty("--round-guess-layout-columns", "minmax(0, 1fr)");
    } else {
      document.documentElement.style.setProperty("--round-guess-layout-columns", "minmax(0, 67fr) minmax(0, 33fr)");
    }

    // Reset photo frame state
    if (el.quizImage) {
      el.quizImage.classList.add("hidden");
      el.quizImage.removeAttribute("src");
      el.quizImage.onerror = null;
    }
    if (el.quizImageFullscreen) {
      el.quizImageFullscreen.classList.add("hidden");
    }
    if (el.mediaPlaceholder) el.mediaPlaceholder.classList.remove("hidden");

    resetDateGuess();

    if (state.guessMarker) {
      state.guessMarker.remove();
      state.guessMarker = null;
    }

    if (questionData.location_mode) {
      ensureGuessMap();
    }

    if (state.guessMap) {
      if (state.mapBounds) {
        const bounds = L.latLngBounds(
          [state.mapBounds.min_lat, state.mapBounds.min_lng],
          [state.mapBounds.max_lat, state.mapBounds.max_lng]
        );
        state.guessMap._regionalBounds = bounds;
        state.guessMap._regionalOptions = { padding: [40, 40], maxZoom: SMART_MAP_MAX_INITIAL_ZOOM };
        fitMapToBounds(state.guessMap, bounds, { padding: [40, 40], maxZoom: SMART_MAP_MAX_INITIAL_ZOOM });
      } else {
        state.guessMap._regionalBounds = null;
        state.guessMap.setView([20, 0], 2);
      }
    }
  },

  onReady(questionData) {
    if (el.quizImage && questionData && questionData.media_url) {
      el.quizImage.src = questionData.media_url;
      el.quizImage.classList.remove("hidden");
      if (el.quizImageFullscreen) el.quizImageFullscreen.classList.remove("hidden");
      if (el.mediaPlaceholder) el.mediaPlaceholder.classList.add("hidden");
    }
    if (questionData && questionData.location_mode) {
      ensureGuessMap();
      if (state.guessMap && state.mapBounds) {
        const bounds = L.latLngBounds(
          [state.mapBounds.min_lat, state.mapBounds.min_lng],
          [state.mapBounds.max_lat, state.mapBounds.max_lng]
        );
        fitMapToBounds(state.guessMap, bounds, { padding: [40, 40], maxZoom: SMART_MAP_MAX_INITIAL_ZOOM });
      }
    }
  },

  buildAnswerPayload(questionData, timedOut) {
    return {
      match_id: state.matchId,
      question_id: questionData.question_id,
      timed_out: timedOut,
      pinpoint: {
        guessed_latitude: state.guessedLatLng ? state.guessedLatLng.lat : null,
        guessed_longitude: state.guessedLatLng ? state.guessedLatLng.lng : null,
        guessed_year: questionData.date_mode && el.dateGuessYear ? Number(el.dateGuessYear.value) : null,
        guessed_month: questionData.date_mode && el.dateGuessMonth ? Number(el.dateGuessMonth.value) : null,
      },
    };
  },

  renderReveal(revealUi, revealData) {
    const pinpointReveal = document.getElementById("pinpoint-reveal-ui");
    const shuffleReveal = document.getElementById("album-shuffle-reveal-ui");
    if (pinpointReveal) pinpointReveal.classList.remove("hidden");
    if (shuffleReveal) shuffleReveal.classList.add("hidden");

    if (el.mediaFrame) el.mediaFrame.classList.add("hidden");

    const mediaUrl = revealData?.pinpoint_reveal?.media_url || revealData?.media_url || (state.currentQuestion ? state.currentQuestion.media_url : null);
    if (el.quizImage && mediaUrl) {
      el.quizImage.src = mediaUrl;
    }

    const stageImg = document.getElementById("pinpoint-reveal-img");
    if (stageImg && mediaUrl) {
      stageImg.src = mediaUrl;
      stageImg.onclick = () => openPhotoLightbox(mediaUrl);
    }

    const stageFsBtn = document.getElementById("pinpoint-photo-fullscreen");
    const stageMediaFrame = document.getElementById("pinpoint-reveal-media-frame");
    if (stageFsBtn && stageMediaFrame) {
      stageFsBtn.onclick = (e) => {
        e.stopPropagation();
        toggleMapFullscreen(stageMediaFrame);
      };
    }

    renderRevealSummary(revealData);
    renderRevealMap(revealData);
  },

  refreshRevealText(revealUi, revealData) {
    // Re-render text-only parts of the reveal without touching the map or triggering effects.
    renderRevealSummary(revealData, true);
  },

  addOpponentReveal(revealUi, revealData, newOpponents) {
    renderRevealSummary(revealData, true);

    const pr = revealData.pinpoint_reveal;
    const actualLat = pr && pr.actual_latitude != null ? Number(pr.actual_latitude) : NaN;
    const actualLng = pr && pr.actual_longitude != null ? Number(pr.actual_longitude) : NaN;
    if (
      revealData.location_mode &&
      state.revealMap &&
      Number.isFinite(actualLat) &&
      Number.isFinite(actualLng)
    ) {
      const actual = L.latLng(actualLat, actualLng);
      if (!actual || typeof actual.lat !== "number" || typeof actual.lng !== "number") return;

      (newOpponents || []).forEach((opponent) => {
        const op = opponent.pinpoint || opponent;
        if (!op || op.guessed_latitude == null || op.guessed_longitude == null) return;
        const gLat = Number(op.guessed_latitude);
        const gLng = Number(op.guessed_longitude);
        if (!Number.isFinite(gLat) || !Number.isFinite(gLng)) return;

        const guessed = L.latLng(gLat, gLng);
        if (!guessed || typeof guessed.lat !== "number" || typeof guessed.lng !== "number") return;

        const color = playerColor(opponent.player_name);
        const line = L.polyline([actual, guessed], {
          color,
          weight: 3,
          dashArray: "8, 8",
          opacity: 0.85,
        }).addTo(state.revealMap);
        state.revealLayers.push(line);

        const icon = createPopPinIcon(playerInitial(opponent.player_name), color);
        const marker = L.marker(guessed, { icon })
          .addTo(state.revealMap)
          .bindPopup(t("reveal.popup_guess", opponent.player_name, formatDistance(op.distance_km)));
        state.revealLayers.push(marker);

        spawnPinPulseEffect(state.revealMap, guessed, color);
        playPinDropSound();
      });

      const allPoints = [actual];
      (revealData.results || []).forEach((r) => {
        const rp = r.pinpoint || r;
        if (!rp || rp.guessed_latitude == null || rp.guessed_longitude == null) return;
        const rLat = Number(rp.guessed_latitude);
        const rLng = Number(rp.guessed_longitude);
        if (Number.isFinite(rLat) && Number.isFinite(rLng)) {
          const pt = L.latLng(rLat, rLng);
          if (pt && typeof pt.lat === "number" && typeof pt.lng === "number") {
            allPoints.push(pt);
          }
        }
      });
      if (allPoints.length > 0) {
        fitMapToBounds(state.revealMap, allPoints, { padding: [50, 50], maxZoom: 15 });
      }
    }
  },

  openHelp(questionData) {
    openPinpointHelpModal(questionData);
  },

  refreshHelpModal(questionData) {
    const modal = document.getElementById("pinpoint-help-modal");
    if (modal && !modal.classList.contains("hidden")) {
      openPinpointHelpModal(questionData);
    }
  },

  refreshQuestionLanguage(questionData) {
    this.refreshHelpModal(questionData);
    if (el.mapGuessWrap) {
      const label = el.mapGuessWrap.querySelector("label");
      if (label) label.textContent = t("game.location_guess_label");
    }
    if (el.dateGuessWrap) {
      const label = el.dateGuessWrap.querySelector("label");
      if (label) label.textContent = t("game.date_guess_label");
    }
  },
};

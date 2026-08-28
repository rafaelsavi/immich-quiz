import { t } from "../i18n.js";
import { el, state } from "../state.js";
import { ensureGuessMap, ensureRevealMap, createPinIcon, createPopPinIcon, toggleMapFullscreen, fitMapToBounds, unregisterActiveMap } from "../maps.js";
import { renderGuessingModeSettings } from "./common.js";
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
import { playChime } from "../audio.js";

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
  renderRoundMeta(el.roundMeta, {
    roundNum: reveal.round_number,
    totalRounds: reveal.total_rounds,
    isReveal: true,
  });

  el.revealActual.replaceChildren();
  const heading = document.createElement("div");
  heading.textContent = t("reveal.correct_answer");
  el.revealActual.appendChild(heading);

  if (reveal.date_mode) {
    const dateLine = document.createElement("span");
    dateLine.textContent = `${t("reveal.actual_date")} ${formatMonth(reveal.actual_year, reveal.actual_month)}`;
    el.revealActual.appendChild(dateLine);
  }
  if (reveal.location_mode) {
    const locLine = document.createElement("span");
    locLine.textContent = `${t("reveal.actual_location")} ${formatPlace(reveal)}`;
    el.revealActual.appendChild(locLine);
  }

  el.revealLegend.replaceChildren();
  if (reveal.location_mode) {
    const actualItem = document.createElement("span");
    actualItem.className = "legend-item";
    const actualBadge = document.createElement("span");
    actualBadge.className = "legend-badge";
    actualBadge.style.background = ACTUAL_COLOR;
    actualBadge.textContent = "\u2605";
    actualItem.append(actualBadge, document.createTextNode(t("reveal.actual_location_legend")));
    el.revealLegend.appendChild(actualItem);

    reveal.results.forEach((result) => {
      const item = document.createElement("span");
      item.className = "legend-item";
      item.append(
        playerBadge(result.player_name),
        document.createTextNode(`${playerInitial(result.player_name)} = ${result.player_name}`)
      );
      el.revealLegend.appendChild(item);
    });
  }

  const groups = [];
  if (reveal.location_mode) {
    groups.push({
      label: t("reveal.col_location"),
      columns: [
        { label: t("reveal.col_points"), mobileLabel: t("reveal.col_location"), class: "" },
        { label: t("reveal.col_distance_error"), class: "hide-on-mobile" },
      ],
    });
  }
  if (reveal.date_mode) {
    groups.push({
      label: t("reveal.col_date"),
      columns: [
        { label: t("reveal.col_points"), mobileLabel: t("reveal.col_date"), class: "" },
        { label: t("reveal.col_guessed"), class: "hide-on-mobile" },
        { label: t("reveal.col_date_error"), class: "hide-on-mobile" },
      ],
    });
  }
  groups.push({
    label: t("reveal.col_score"),
    columns: [
      { label: t("reveal.col_round"), class: "hide-on-mobile" },
      { label: t("reveal.col_total"), mobileLabel: t("reveal.col_score"), class: "group-start-mobile" },
    ],
  });

  const groupRow = document.createElement("tr");
  groupRow.className = "group-head-row";
  const playerHead = buildCell(t("reveal.col_player"), true);
  playerHead.rowSpan = 2;
  groupRow.appendChild(playerHead);
  groups.forEach((group) => {
    const cell = buildCell(group.label, true);
    cell.colSpan = group.columns.length;
    cell.className = "group-head group-start";
    groupRow.appendChild(cell);
  });

  const columnRow = document.createElement("tr");
  columnRow.className = "column-head-row";
  const playerSubHead = buildCell(t("reveal.col_player"), true);
  playerSubHead.className = "player-subhead hide-on-desktop";
  columnRow.appendChild(playerSubHead);

  groups.forEach((group) => {
    group.columns.forEach((col, index) => {
      const cell = buildCell("", true);
      const labelSpan = document.createElement("span");
      labelSpan.className = "desktop-head-label";
      labelSpan.textContent = col.label;
      cell.appendChild(labelSpan);

      if (col.mobileLabel) {
        cell.setAttribute("data-mobile-label", col.mobileLabel);
      }

      const classes = [];
      if (index === 0) classes.push("group-start");
      if (col.class) classes.push(col.class);
      if (classes.length > 0) cell.className = classes.join(" ");
      columnRow.appendChild(cell);
    });
  });
  el.revealTableHead.replaceChildren(groupRow, columnRow);

  const maxPoints = reveal.score_max_points || state.scoreMaxPoints || 100;
  const maxRoundPoints = (reveal.location_mode ? maxPoints : 0) + (reveal.date_mode ? maxPoints : 0);
  let hasAnyPerfectInRound = false;

  const ordered = [...reveal.results].sort((a, b) => b.round_score - a.round_score);
  el.revealTableBody.replaceChildren();

  ordered.forEach((result, rIdx) => {
    const isPerfectLocation = reveal.location_mode && (result.location_score === maxPoints || result.distance_km === 0);
    const isPerfectDate = reveal.date_mode && (result.date_score === maxPoints || result.date_diff_days === 0);
    const isPerfectRound = maxRoundPoints > 0 && result.round_score === maxRoundPoints;
    const isPerfectPlayer = isPerfectLocation || isPerfectDate || isPerfectRound;

    if (isPerfectPlayer) {
      hasAnyPerfectInRound = true;
    }

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
    if (result.distance_km !== null && result.distance_km !== undefined) {
      ps.totalDistanceKm += result.distance_km;
      ps.distanceCount += 1;
    }
    if (result.date_diff_days !== null && result.date_diff_days !== undefined) {
      ps.totalDateDiffDays += result.date_diff_days;
      ps.dateCount += 1;
    }
    if (isPerfectLocation) ps.perfectLocationCount += 1;
    if (isPerfectDate) ps.perfectDateCount += 1;
    if (isPerfectPlayer) ps.perfectRounds += 1;
    if (result.timed_out) ps.timedOutCount += 1;

    const row = document.createElement("tr");
    if (isPerfectPlayer) {
      row.className = "is-perfect-row";
    }

    const nameCell = playerNameCell(result.player_name, result.timed_out);
    const count = state.perfectCounts[result.player_name] || 0;
    if (count > 0) {
      const countBadge = document.createElement("span");
      countBadge.className = "perfect-count-badge";
      countBadge.textContent = t("fmt.perfect_count", count);
      nameCell.appendChild(countBadge);
    }
    row.appendChild(buildCell(nameCell));

    const valueGroups = [];
    if (reveal.location_mode) {
      const distStr = result.guessed_latitude === null ? t("fmt.no_guess") : formatDistance(result.distance_km);
      valueGroups.push({
        isPerfect: isPerfectLocation,
        items: [
          {
            value: result.location_score === null ? "-" : String(result.location_score),
            scoreNum: result.location_score,
            isScore: result.location_score !== null && result.location_score !== undefined,
            maxScore: maxPoints,
            subtext: distStr !== t("fmt.no_guess") ? distStr : null,
            class: "",
          },
          {
            value: distStr,
            class: "hide-on-mobile",
          },
        ],
      });
    }
    if (reveal.date_mode) {
      const dateErrStr = formatMonthError(result);
      const guessedDateStr = formatMonth(result.guessed_year, result.guessed_month);
      valueGroups.push({
        isPerfect: isPerfectDate,
        items: [
          {
            value: result.date_score === null ? "-" : String(result.date_score),
            scoreNum: result.date_score,
            isScore: result.date_score !== null && result.date_score !== undefined,
            maxScore: maxPoints,
            subtext: dateErrStr !== "-" ? dateErrStr : null,
            class: "",
          },
          {
            value: guessedDateStr,
            class: "hide-on-mobile",
          },
          {
            value: dateErrStr,
            class: "hide-on-mobile",
          },
        ],
      });
    }

    valueGroups.push({
      isPerfect: isPerfectRound,
      items: [
        {
          value: String(result.round_score ?? 0),
          scoreNum: result.round_score ?? 0,
          isScore: true,
          maxScore: maxRoundPoints,
          class: "hide-on-mobile",
        },
        {
          value: String(result.total_score ?? 0),
          scoreNum: result.total_score ?? 0,
          startScore: Math.max(0, (result.total_score ?? 0) - (result.round_score ?? 0)),
          isScore: true,
          maxScore: maxRoundPoints,
          class: "group-start-mobile",
        },
      ],
    });

    valueGroups.forEach((group) => {
      group.items.forEach((itemObj, index) => {
        const cell = buildCell(itemObj.value);
        if (itemObj.class) {
          cell.classList.add(...itemObj.class.split(" ").filter(Boolean));
        }
        if (itemObj.subtext) {
          const subSpan = document.createElement("span");
          subSpan.className = "subtext-mobile-only";
          subSpan.textContent = `(${itemObj.subtext})`;
          cell.appendChild(subSpan);
        }
        if (index === 0) {
          cell.classList.add("group-start");
          if (group.isPerfect) {
            cell.classList.add("is-perfect-cell");
            cell.appendChild(createPerfectBadge());
          }
        }
        if (itemObj.isScore) {
          animateScoreRollup(cell, itemObj.scoreNum, itemObj.maxScore, "", skipEffects, itemObj.startScore || 0);
        }
        row.appendChild(cell);
      });
    });

    el.revealTableBody.appendChild(row);
  });

  if (!skipEffects && hasAnyPerfectInRound) {
    playChime();
    launchStarBurst();
    launchGoldConfetti();
  }
}

function renderRevealMap(reveal) {
  el.revealMapShell.classList.toggle("hidden", !reveal.location_mode);
  el.revealMapHead.classList.toggle("hidden", !reveal.location_mode);
  if (!reveal.location_mode) {
    clearRevealAnimation();
    return;
  }

  ensureRevealMap();
  clearRevealAnimation();

  state.revealLayers.forEach((layer) => state.revealMap.removeLayer(layer));
  state.revealLayers = [];

  if (reveal.actual_latitude === null || reveal.actual_longitude === null) {
    return;
  }

  const actual = L.latLng(reveal.actual_latitude, reveal.actual_longitude);
  const actualMarker = L.marker(actual, {
    icon: createPinIcon("\u2605", ACTUAL_COLOR),
    zIndexOffset: 1000,
  })
    .addTo(state.revealMap)
    .bindPopup(t("reveal.popup_actual"));
  state.revealLayers.push(actualMarker);

  const points = [actual];
  const playerGuesses = [];

  reveal.results.forEach((result) => {
    if (result.guessed_latitude === null || result.guessed_longitude === null) {
      return;
    }
    const guessed = L.latLng(result.guessed_latitude, result.guessed_longitude);
    points.push(guessed);
    playerGuesses.push({ result, guessed });
  });

  fitMapToBounds(state.revealMap, points, { padding: [50, 50], maxZoom: 15 });

  if (playerGuesses.length === 0) {
    return;
  }

  const lineDuration = 1300;

  state.revealAnimationTimeoutId = window.setTimeout(() => {
    state.revealAnimationTimeoutId = null;
    const lineEntries = playerGuesses.map(({ result, guessed }) => {
      const color = playerColor(result.player_name);
      const line = L.polyline([actual, actual], {
        color,
        weight: 3,
        dashArray: "8, 8",
        opacity: 0.85,
      }).addTo(state.revealMap);
      state.revealLayers.push(line);
      return { result, guessed, color, line };
    });

    const startTime = performance.now();

    function animateAllLines(now) {
      const elapsed = now - startTime;
      const progress = Math.min(1, elapsed / lineDuration);

      lineEntries.forEach(({ guessed, line }) => {
        const curLat = actual.lat + (guessed.lat - actual.lat) * progress;
        const curLng = actual.lng + (guessed.lng - actual.lng) * progress;
        line.setLatLngs([actual, [curLat, curLng]]);
      });

      if (progress < 1) {
        state.revealAnimationFrameId = window.requestAnimationFrame(animateAllLines);
      } else {
        state.revealAnimationFrameId = null;
        lineEntries.forEach(({ result, guessed, color }) => {
          const icon = createPopPinIcon(playerInitial(result.player_name), color);
          const marker = L.marker(guessed, { icon })
            .addTo(state.revealMap)
            .bindPopup(t("reveal.popup_guess", result.player_name, formatDistance(result.distance_km)));
          state.revealLayers.push(marker);
        });
      }
    }

    state.revealAnimationFrameId = window.requestAnimationFrame(animateAllLines);
  }, 350);
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
  },

  setDisabled(disabled) {
    if (el.dateGuessYear) el.dateGuessYear.disabled = disabled;
    if (el.dateGuessMonth) el.dateGuessMonth.disabled = disabled;
  },

  unmount() {
    if (el.mediaFrame) {
      el.mediaFrame.classList.add("hidden");
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
      guessed_latitude: state.guessedLatLng ? state.guessedLatLng.lat : null,
      guessed_longitude: state.guessedLatLng ? state.guessedLatLng.lng : null,
      guessed_year: questionData.date_mode && el.dateGuessYear ? Number(el.dateGuessYear.value) : null,
      guessed_month: questionData.date_mode && el.dateGuessMonth ? Number(el.dateGuessMonth.value) : null,
      timed_out: timedOut,
    };
  },

  renderReveal(revealUi, revealData) {
    const pinpointReveal = document.getElementById("pinpoint-reveal-ui");
    const shuffleReveal = document.getElementById("album-shuffle-reveal-ui");
    if (pinpointReveal) pinpointReveal.classList.remove("hidden");
    if (shuffleReveal) shuffleReveal.classList.add("hidden");

    if (el.mediaFrame) el.mediaFrame.classList.remove("hidden");
    if (el.quizImage) el.quizImage.classList.remove("hidden");
    if (el.quizImageFullscreen) el.quizImageFullscreen.classList.remove("hidden");
    if (el.mediaPlaceholder) el.mediaPlaceholder.classList.add("hidden");
    renderRevealSummary(revealData);
    renderRevealMap(revealData);
  },

  refreshRevealText(revealUi, revealData) {
    // Re-render text-only parts of the reveal without touching the map or triggering effects.
    renderRevealSummary(revealData, true);
  },

  openHelp(questionData) { },
};

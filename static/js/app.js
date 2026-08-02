import { state, el } from "./modules/state.js";
import { t, translateError, showAlert, applyLanguage } from "./modules/i18n.js";
import {
  playTone,
  playTick,
  playBuzzer,
  playChime,
  playVictoryFanfare,
  playScoreRollupTick,
  toggleAudio,
  updateAudioUi,
} from "./modules/audio.js";
import { api } from "./modules/api.js";
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
} from "./modules/formatters.js";
import { launchGoldConfetti, createPerfectBadge, launchStarBurst, spawnFloatingScorePop, animateScoreRollup } from "./modules/effects.js";
import {
  updateSubmitState,
  createPinIcon,
  ensureGuessMap,
  ensureRevealMap,
  renderJourneyMap,
  toggleMapFullscreen,
  syncFullscreenButtons,
} from "./modules/maps.js";
import { loadLeaderboard, handleSortClick } from "./modules/leaderboard.js";
import { pinpointMode } from "./modules/modes/pinpoint.js";
import { albumShuffleMode } from "./modules/modes/album_shuffle.js";

const GAME_MODES = {
  pinpoint: pinpointMode,
  album_shuffle: albumShuffleMode,
};

function getActiveMode() {
  return GAME_MODES[state.gameMode] || pinpointMode;
}


const EARLIEST_YEAR = 1950;
const DEFAULT_MAP_WIDTH_PCT = 67;

/* -------------------------------------------------------- setup + lookups */

async function initLibraries() {
  const data = await api("/api/libraries");
  el.library.replaceChildren();
  data.libraries.forEach((name) => {
    const option = document.createElement("option");
    option.value = name;
    option.textContent = name;
    el.library.appendChild(option);
  });

  if (data.libraries.length > 0) {
    await initAlbums(data.libraries[0]);
  }
}

async function initAlbums(libraryName) {
  const data = await api(`/api/albums?library_name=${encodeURIComponent(libraryName)}`);
  const allPhotos = document.createElement("option");
  allPhotos.value = "";
  allPhotos.setAttribute("data-i18n", "setup.all_photos");
  allPhotos.textContent = t("setup.all_photos");
  el.album.replaceChildren(allPhotos);
  const albums = [...data.albums].sort((a, b) =>
    a.name.localeCompare(b.name, undefined, { sensitivity: "base", numeric: true })
  );
  albums.forEach((album) => {
    const option = document.createElement("option");
    option.value = album.id;
    option.textContent = album.name;
    el.album.appendChild(option);
  });
}

/* ------------------------------------------------- year / month dropdowns */

function initDateDropdowns() {
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

  bindSelectWheelScroll(el.dateGuessYear, true);
  bindSelectWheelScroll(el.dateGuessMonth, false);
  bindSelectWheelScroll(el.roundCount, false);
  bindSelectWheelScroll(el.roundLength, false);
  bindSelectWheelScroll(el.library, false);
  bindSelectWheelScroll(el.album, false);
}

function renderMonthOptions(keepSelection = true) {
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

  // Default to (and clamp at) the newest selectable month.
  const keep = keepSelection && previous >= 1 && previous <= maxMonth;
  el.dateGuessMonth.value = String(keep ? previous : maxMonth);
}

async function initUiConfig() {
  const data = await api("/api/ui-config");
  applyUiConfig(data);
}

function applyUiConfig(config) {
  const heightPxRaw = Number(config.quiz_image_max_height_px);
  const heightPx = Number.isFinite(heightPxRaw) ? Math.min(1600, Math.max(200, heightPxRaw)) : 420;
  document.documentElement.style.setProperty("--quiz-image-max-height", `${heightPx}px`);

  if (config.language && (config.language === "PT" || config.language === "EN")) {
    state.language = config.language;
  }
  if (config.score_max_points) {
    state.scoreMaxPoints = Number(config.score_max_points);
  }
  applyLanguage();
}

function applyGuessLayout(locationMode, dateMode) {
  const hasMapOnly = Boolean(locationMode) && !Boolean(dateMode);
  if (hasMapOnly) {
    document.documentElement.style.setProperty("--round-guess-layout-columns", "minmax(0, 1fr)");
    return;
  }

  const mapWidthPct = DEFAULT_MAP_WIDTH_PCT;
  const dateWidthPct = 100 - mapWidthPct;
  document.documentElement.style.setProperty(
    "--round-guess-layout-columns",
    `minmax(0, ${mapWidthPct}fr) minmax(0, ${dateWidthPct}fr)`
  );
}

function resetDateGuess() {
  const now = new Date();
  el.dateGuessYear.value = String(now.getFullYear());
  renderMonthOptions(false);
}

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

function bindSelectWheelScroll(selectEl, invertScroll = false) {
  if (!selectEl || selectEl.dataset.wheelBound) {
    return;
  }
  selectEl.dataset.wheelBound = "true";

  selectEl.addEventListener(
    "wheel",
    (event) => {
      event.preventDefault();
      let direction = event.deltaY > 0 ? 1 : -1;
      if (invertScroll) direction = -direction;
      stepSelectOption(selectEl, direction);
    },
    { passive: false }
  );
}

/* ------------------------------------------------------------------ timer */

function clearTimer() {
  if (state.timerRef) {
    clearInterval(state.timerRef);
    state.timerRef = null;
  }
}

function resetTimerBar() {
  clearTimer();
  el.timerFill.style.width = "100%";
  el.timerFill.classList.remove("is-warning", "is-critical");
  el.timerTrack.classList.add("is-idle");
  el.timerLabel.textContent = "";
  el.timerRemaining.textContent = "";
  el.timeoutNotice.classList.add("hidden");
  el.timeoutNotice.textContent = "";

  // Feature 6: remove timer pulse
  const timerRow = el.timerTrack.closest(".timer-row");
  if (timerRow) timerRow.classList.remove("is-pulsing");
  el.timerRemaining.classList.remove("is-critical-text");
  if (el.mediaFrame) el.mediaFrame.classList.remove("timer-tension");

  // Feature 7: reset all fullscreen timer overlays
  document.querySelectorAll(".fullscreen-timer").forEach((ft) => {
    const fill = ft.querySelector(".fs-timer-fill");
    const label = ft.querySelector(".fs-timer-label");
    const remaining = ft.querySelector(".fs-timer-remaining");
    if (fill) { fill.style.width = "100%"; fill.className = "fs-timer-fill"; }
    if (label) label.textContent = "";
    if (remaining) remaining.textContent = "";
  });
}

function startTimer(roundLength) {
  resetTimerBar();
  state.timedOut = false;

  if (roundLength === "unlimited") {
    el.timerLabel.textContent = t("game.timer_unlimited");
    return;
  }

  let total = 60;
  if (roundLength === "30s") total = 30;
  else if (roundLength === "1m") total = 60;
  else if (roundLength === "2m") total = 120;
  else if (roundLength === "5m") total = 300;

  let remaining = total;
  state.timerTotalSeconds = total;
  state.timerRemainingSeconds = remaining;
  el.timerTrack.classList.remove("is-idle");
  el.timerLabel.textContent = t("game.timer_time_left");
  el.timerRemaining.textContent = `${remaining}s`;


  state.timerRef = setInterval(() => {
    remaining -= 1;
    const clamped = Math.max(remaining, 0);
    state.timerRemainingSeconds = clamped;
    const ratio = clamped / total;
    const isCritical = ratio <= 0.2 || clamped <= 5;
    const isWarning = ratio <= 0.5 && ratio > 0.2 && clamped > 5;

    el.timerRemaining.textContent = `${clamped}s`;
    el.timerFill.style.width = `${ratio * 100}%`;
    el.timerFill.classList.toggle("is-warning", isWarning);
    el.timerFill.classList.toggle("is-critical", isCritical);

    // Feature 6: pulsing timer warning
    const timerRow = el.timerTrack.closest(".timer-row");
    if (timerRow) timerRow.classList.toggle("is-pulsing", clamped <= 5 && clamped > 0);
    el.timerRemaining.classList.toggle("is-critical-text", clamped <= 5 && clamped > 0);
    if (el.mediaFrame) el.mediaFrame.classList.toggle("timer-tension", clamped <= 5 && clamped > 0);

    // Feature 7: sync fullscreen timer overlays
    syncFullscreenTimers(clamped, ratio, isWarning, isCritical);

    if (clamped <= 5 && clamped > 0) {
      playTick(clamped);
    }

    if (clamped <= 0) {
      clearTimer();
      playBuzzer();
      handleTimeout();
    }
  }, 1000);
}

function handleTimeout() {
  if (state.timedOut || state.submitting || !state.currentQuestion) {
    return;
  }
  state.timedOut = true;
  el.timerLabel.textContent = t("game.timer_time_up_label");
  el.timerRemaining.textContent = "0s";
  el.dateGuessYear.disabled = true;
  el.dateGuessMonth.disabled = true;

  el.timeoutNotice.textContent = t("game.timer_time_up_notice");
  el.timeoutNotice.classList.remove("hidden");

  // Nothing is submitted until the player acknowledges the timeout.
  el.submitAnswer.textContent = t("game.continue_btn");
  updateSubmitState();
}

/* ------------------------------------------------------------- game cycle */

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

function showCard(cardEl) {
  clearRevealAnimation();
  [el.setupCard, el.gameCard, el.summaryCard].forEach((c) => {
    c.classList.add("hidden");
  });
  cardEl.classList.remove("hidden");
}

async function startMatch(event) {
  event.preventDefault();

  const players = el.players.value
    .split(",")
    .map((name) => name.trim())
    .filter(Boolean);

  const activeMode = getActiveMode();
  const modePayload = activeMode.getModePayload();

  const albumId = el.album.value || null;
  const payload = {
    players,
    round_count: Number(el.roundCount.value),
    round_length: el.roundLength.value,
    library_name: el.library.value,
    album_id: albumId,
    album_name: albumId ? el.album.options[el.album.selectedIndex].text : "-",
    ...modePayload,
  };

  try {
    const preflight = await api("/api/game/preflight", {
      method: "POST",
      body: JSON.stringify(payload),
    });

    if (!preflight.ok) {
      const filterNames = (preflight.active_filters || [])
        .map((f) => t(`setup.filter_${f}`, preflight.min_date, preflight.max_date))
        .join(", ");
      alert(
        t("setup.not_enough_media", preflight.eligible_count, preflight.required, filterNames)
      );
      return;
    }
  } catch (err) {
    showAlert(err.message || err);
    return;
  }

  state.lastMatchConfig = payload;

  const response = await api("/api/game/setup", {
    method: "POST",
    body: JSON.stringify(payload),
  });

  state.matchId = response.match_id;
  state.players = response.players;
  state.playedAssetIds = [];
  state.matchFinished = false;
  state.perfectCounts = {};
  state.playerStats = {};
  state.roundHistory = [];

  // Standings stay secret while a match is in progress.
  el.leaderboardCard.classList.add("hidden");
  showCard(el.gameCard);

  await loadQuestion();
}

async function loadQuestion() {
  resetTimerBar();
  state.guessedLatLng = null;
  state.timedOut = false;
  state.currentQuestion = null;
  el.guessingUi.classList.remove("hidden");
  el.revealUi.classList.add("hidden");
  window.scrollTo({ top: 0, behavior: "smooth" });
  el.submitAnswer.textContent = t("game.submit_btn");
  el.dateGuessYear.disabled = false;
  el.dateGuessMonth.disabled = false;
  updateSubmitState();

  if (state.guessMarker) {
    state.guessMarker.remove();
    state.guessMarker = null;
  }
  if (state.guessMap) {
    state.guessMap.setView([20, 0], 2);
  }
  resetDateGuess();

  // Clear the image immediately so the previous round's photo never shows
  // through the pass-device overlay while the API call is in flight.
  el.quizImage.classList.add("hidden");
  el.quizImage.removeAttribute("src");
  if (el.mediaErrorCard) {
    el.mediaErrorCard.classList.add("hidden");
  }
  el.mediaPlaceholder.classList.remove("hidden");

  el.quizImage.onerror = () => {
    el.quizImage.classList.add("hidden");
    el.mediaPlaceholder.classList.add("hidden");
    if (el.mediaErrorCard) {
      el.mediaErrorCard.classList.remove("hidden");
    }
  };

  const data = await api("/api/question", {
    method: "POST",
    body: JSON.stringify({
      match_id: state.matchId,
      played_asset_ids: state.playedAssetIds,
    }),
  });

  state.currentQuestion = data;
  state.gameMode = data.game_mode || "pinpoint";
  if (data.asset_id && !state.playedAssetIds.includes(data.asset_id)) {
    state.playedAssetIds.push(data.asset_id);
  }

  el.roundMeta.textContent = t(
    "game.round_meta",
    data.player_round_number,
    data.total_rounds_per_player,
    data.player_number,
    data.total_players,
    data.player_name
  );

  const activeMode = getActiveMode();
  activeMode.renderQuestion(el.guessingUi, data);
  updateSubmitState();

  if (data.total_players > 1) {
    el.overlayTitle.textContent = t(
      "game.pass_device_title",
      data.player_name,
      data.player_number,
      data.total_players
    );
    el.overlaySubtitle.textContent = t("game.pass_device_subtitle", data.player_round_number, data.total_rounds_per_player);
    el.passOverlay.classList.remove("hidden");
  } else {
    el.passOverlay.classList.add("hidden");
    if (data.game_mode === "pinpoint") {
      el.quizImage.src = data.media_url;
      el.quizImage.classList.remove("hidden");
      el.mediaPlaceholder.classList.add("hidden");
      if (data.location_mode) {
        ensureGuessMap();
      }
    }
    startTimer(data.round_length);
  }
}

async function submitAnswer(fromTimeout = false) {
  if (!state.currentQuestion || state.submitting) {
    return;
  }
  state.submitting = true;
  updateSubmitState();
  playTone(480, "sine", 0.08, 0.12);

  try {
    const question = state.currentQuestion;
    const playerName = question ? question.player_name : null;
    const totalSec = state.timerTotalSeconds || 0;
    const remainingSec = state.timerRemainingSeconds || 0;
    const elapsedSec = fromTimeout ? totalSec : Math.max(0, totalSec - remainingSec);

    if (playerName && totalSec > 0) {
      if (!state.playerStats[playerName]) {
        state.playerStats[playerName] = {
          totalDistanceKm: 0, distanceCount: 0,
          totalDateDiffDays: 0, dateCount: 0,
          perfectLocationCount: 0, perfectDateCount: 0,
          perfectRounds: 0, timedOutCount: 0, fastRoundCount: 0, totalDurationSec: 0,
        };
      }
      state.playerStats[playerName].totalDurationSec = (state.playerStats[playerName].totalDurationSec || 0) + elapsedSec;
      if (!fromTimeout && elapsedSec <= totalSec / 2) {
        state.playerStats[playerName].fastRoundCount = (state.playerStats[playerName].fastRoundCount || 0) + 1;
      }
    }

    const activeMode = getActiveMode();
    const payload = activeMode.buildAnswerPayload(question, fromTimeout);


    const result = await api("/api/answer", {
      method: "POST",
      body: JSON.stringify(payload),
    });

    clearTimer();
    state.matchFinished = result.match_finished;

    // Release the lock before the next screen loads, otherwise the submit gate
    // and the map click handler stay frozen for the following player.
    state.submitting = false;

    if (result.round_complete) {
      await showRoundReveal(result.round_number);
      return;
    }

    // Hand over to the next player without leaking any result.
    await loadQuestion();
  } finally {
    state.submitting = false;
    updateSubmitState();
  }
}

/* ----------------------------------------------------------------- reveal */

async function showRoundReveal(roundNumber) {
  const reveal = await api("/api/round/result", {
    method: "POST",
    body: JSON.stringify({ match_id: state.matchId, round_number: roundNumber }),
  });

  // Record round history for end-game recap (World Journey Map & Polaroid Cards)
  const existingIdx = state.roundHistory.findIndex((r) => r.round_number === reveal.round_number);
  const entry = {
    round_number: reveal.round_number,
    media_url: state.currentQuestion ? state.currentQuestion.media_url : null,
    actual_latitude: reveal.actual_latitude,
    actual_longitude: reveal.actual_longitude,
    actual_year: reveal.actual_year,
    actual_month: reveal.actual_month,
    actual_city: reveal.actual_city,
    actual_country: reveal.actual_country,
    location_string: formatPlace(reveal),
    results: reveal.results,
  };
  if (existingIdx >= 0) {
    state.roundHistory[existingIdx] = entry;
  } else {
    state.roundHistory.push(entry);
  }

  showCard(el.gameCard);
  el.guessingUi.classList.add("hidden");
  el.revealUi.classList.remove("hidden");

  const activeMode = getActiveMode();
  if (activeMode && typeof activeMode.renderReveal === "function") {
    if (el.mediaFrame) el.mediaFrame.classList.add("hidden");
    activeMode.renderReveal(el.revealUi, reveal);
  } else {
    if (el.mediaFrame) el.mediaFrame.classList.remove("hidden");
    renderRevealSummary(reveal);
    renderRevealMap(reveal);
  }

  el.nextRound.textContent = reveal.match_finished ? t("reveal.see_results_btn") : t("reveal.next_round_btn");

  const targetScrollEl = reveal.location_mode ? el.revealMapShell : el.nextRound;
  if (targetScrollEl) {
    targetScrollEl.scrollIntoView({ behavior: "smooth", block: "center" });
  }
}



function renderRevealSummary(reveal) {
  el.roundMeta.textContent = t("reveal.title", reveal.round_number, reveal.total_rounds);

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
    groups.push({ label: t("reveal.col_location"), columns: [t("reveal.col_points"), t("reveal.col_distance_error")] });
  }
  if (reveal.date_mode) {
    groups.push({ label: t("reveal.col_date"), columns: [t("reveal.col_points"), t("reveal.col_guessed"), t("reveal.col_date_error")] });
  }
  groups.push({ label: t("reveal.col_score"), columns: [t("reveal.col_round"), t("reveal.col_total")] });

  const groupRow = document.createElement("tr");
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
  groups.forEach((group) => {
    group.columns.forEach((label, index) => {
      const cell = buildCell(label, true);
      if (index === 0) {
        cell.className = "group-start";
      }
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

    // Feature 1: track perfect count for any perfect guess or round
    if (isPerfectPlayer) {
      state.perfectCounts[result.player_name] = (state.perfectCounts[result.player_name] || 0) + 1;
    }

    // Feature 4: accumulate player stats for awards
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

    // Build player name cell with perfect count badge
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
      valueGroups.push({
        isPerfect: isPerfectLocation,
        items: [
          result.location_score === null ? "-" : String(result.location_score),
          result.guessed_latitude === null ? t("fmt.no_guess") : formatDistance(result.distance_km),
        ],
      });
    }
    if (reveal.date_mode) {
      valueGroups.push({
        isPerfect: isPerfectDate,
        items: [
          result.date_score === null ? "-" : String(result.date_score),
          formatMonth(result.guessed_year, result.guessed_month),
          formatMonthError(result),
        ],
      });
    }

    const isTotalScoreGroup = true;
    valueGroups.push({
      isPerfect: isPerfectRound,
      isScoreGroup: isTotalScoreGroup,
      roundScoreNum: result.round_score,
      items: [String(result.round_score), String(result.total_score)],
    });

    valueGroups.forEach((group) => {
      group.items.forEach((value, index) => {
        const cell = buildCell(value);
        if (index === 0) {
          cell.classList.add("group-start");
          if (group.isPerfect) {
            cell.classList.add("is-perfect-cell");
            cell.appendChild(createPerfectBadge());
          }
        }
        if (group.isScoreGroup && index === 0) {
          // Only animate the points gained in this round (round_score), NOT the total score.
          animateScoreRollup(cell, group.roundScoreNum, maxRoundPoints);
        }
        row.appendChild(cell);
      });
    });

    el.revealTableBody.appendChild(row);

    // Floating Score Pops per player row
    setTimeout(() => {
      if (isPerfectLocation) {
        spawnFloatingScorePop(row, `🎯 BULLSEYE! +${result.location_score}`, "bullseye");
      } else if (isPerfectDate) {
        spawnFloatingScorePop(row, `⏳ TIME TRAVELER! +${result.date_score}`, "perfect");
      } else if (result.round_score > 0) {
        spawnFloatingScorePop(row, `+${result.round_score} pts`, "good");
      }
    }, rIdx * 250);
  });

  if (hasAnyPerfectInRound) {
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

  // 1. Plot the actual (correct) pinpoint star marker immediately
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

  if (points.length > 1) {
    state.revealMap.fitBounds(L.latLngBounds(points).pad(0.3));
  } else {
    state.revealMap.setView(actual, 4);
  }

  if (playerGuesses.length === 0) {
    return;
  }

  // 2. Expand ALL lines simultaneously from actual location to player guess points!
  const lineDuration = 800; // ms for line expansion

  state.revealAnimationTimeoutId = window.setTimeout(() => {
    state.revealAnimationTimeoutId = null;
    // Create all polylines anchored at actual location
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
        // All lines reached their guess points! Pop in all player markers together!
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

function createPopPinIcon(label, color) {
  return L.divIcon({
    className: "player-pin player-pin-pop",
    html: `<span style="background:${color}"><b>${label}</b></span>`,
    iconSize: [28, 28],
    iconAnchor: [14, 28],
    popupAnchor: [0, -26],
  });
}

async function handleNextRound() {
  if (state.matchFinished) {
    await showMatchSummary();
    return;
  }
  showCard(el.gameCard);
  await loadQuestion();
}

/* ------------------------------------------------------- match conclusion */

async function showMatchSummary() {
  const summary = await api(`/api/match/${encodeURIComponent(state.matchId)}/summary`);
  showCard(el.summaryCard);
  playVictoryFanfare();

  // Feature 3: Winner Podium
  renderPodium(summary);

  const modes = [];
  if (summary.location_mode) {
    modes.push(t("summary.mode_location"));
  }
  if (summary.date_mode) {
    modes.push(t("summary.mode_date"));
  }
  el.summaryMeta.textContent = t(
    "summary.meta",
    summary.rounds_played,
    modes.join(" + "),
    summary.library_name,
    summary.album_name
  );

  // Feature 4: Fun Performance Awards
  renderAwards(summary);

  const columns = [t("summary.col_rank"), t("summary.col_player")];
  if (summary.location_mode) {
    columns.push(t("summary.col_location"));
  }
  if (summary.date_mode) {
    columns.push(t("summary.col_date"));
  }
  columns.push(t("summary.col_total"), t("summary.col_accuracy"));

  const headRow = document.createElement("tr");
  columns.forEach((label) => headRow.appendChild(buildCell(label, true)));
  el.summaryTableHead.replaceChildren(headRow);

  el.summaryTableBody.replaceChildren();
  summary.players.forEach((player) => {
    const row = document.createElement("tr");
    row.classList.toggle("is-winner", player.is_winner);

    row.appendChild(buildCell(String(player.rank)));

    // Feature 1: show perfect count in summary table
    const nameCell = playerNameCell(player.player_name);
    const count = state.perfectCounts[player.player_name] || 0;
    if (count > 0) {
      const countBadge = document.createElement("span");
      countBadge.className = "perfect-count-badge";
      countBadge.textContent = t("fmt.perfect_count", count);
      nameCell.appendChild(countBadge);
    }
    row.appendChild(buildCell(nameCell));

    if (summary.location_mode) {
      row.appendChild(buildCell(String(player.location_score ?? 0)));
    }
    if (summary.date_mode) {
      row.appendChild(buildCell(String(player.date_score ?? 0)));
    }
    row.appendChild(buildCell(`${player.total_score}/${player.max_possible_score}`));
    row.appendChild(buildCell(String(player.accuracy_pct)));

    el.summaryTableBody.appendChild(row);
  });

  state.lastSummary = summary;

  // Render World Journey Map
  renderJourneyMap(state.roundHistory);

  // Render Polaroid Memory Cards
  renderPolaroidGallery(state.roundHistory);

  el.leaderboardCard.classList.remove("hidden");
  await loadLeaderboard();
}

function renderPolaroidGallery(roundHistory) {
  if (!el.polaroidGallery) return;
  el.polaroidGallery.replaceChildren();

  (roundHistory || []).forEach((round) => {
    const card = document.createElement("div");
    card.className = "polaroid-card";

    const imgWrap = document.createElement("div");
    imgWrap.className = "polaroid-img-wrap";

    if (round.media_url) {
      const img = document.createElement("img");
      img.className = "polaroid-img";
      img.src = round.media_url;
      img.alt = `Round ${round.round_number}`;
      imgWrap.appendChild(img);
    }

    const caption = document.createElement("div");
    caption.className = "polaroid-caption";

    const badge = document.createElement("span");
    badge.className = "polaroid-round-badge";
    badge.textContent = t("summary.journey_round", round.round_number);

    const loc = document.createElement("span");
    loc.className = "polaroid-location";
    loc.textContent = round.location_string || t("fmt.unknown_place");

    const date = document.createElement("span");
    date.className = "polaroid-date";
    date.textContent = formatMonth(round.actual_year, round.actual_month);

    caption.append(badge, loc, date);
    card.append(imgWrap, caption);
    el.polaroidGallery.appendChild(card);
  });
}

async function shareMatchSummary() {
  if (!state.lastSummary) return;
  const summary = state.lastSummary;

  const winnerText =
    summary.winners.length > 1
      ? t("summary.tie", summary.winners.join(" & "))
      : t("summary.winner", summary.winners[0]);

  let text = `🏆 Immich Quiz - ${winnerText}\n`;
  text += `📍 ${summary.library_name} | ${summary.rounds_played} rounds\n\n`;
  text += `Scores:\n`;
  summary.players.forEach((p) => {
    text += `${p.rank}. ${p.player_name}: ${p.total_score}/${p.max_possible_score} (${p.accuracy_pct}%)\n`;
  });

  try {
    if (navigator.share && navigator.canShare && navigator.canShare({ text })) {
      await navigator.share({ title: "Immich Quiz Results", text });
    } else {
      await navigator.clipboard.writeText(text);
      showShareToast(t("summary.share_copied"));
    }
  } catch (err) {
    if (err.name !== "AbortError") {
      try {
        await navigator.clipboard.writeText(text);
        showShareToast(t("summary.share_copied"));
      } catch (clipErr) {
        showAlert(clipErr.message);
      }
    }
  }
}

function showShareToast(message) {
  let toast = document.querySelector(".share-toast");
  if (!toast) {
    toast = document.createElement("div");
    toast.className = "share-toast";
    document.body.appendChild(toast);
  }
  toast.textContent = message;
  toast.classList.add("show");
  setTimeout(() => toast.classList.remove("show"), 3000);
}

/* ── Feature 3: Podium ── */

function renderPodium(summary) {
  const isMultiplayer = summary.players.length > 1;

  const titleText = summary.winners.length > 1
    ? t("summary.tie", summary.winners.join(" & "))
    : t("summary.winner", summary.winners[0]);

  el.summaryWinner.replaceChildren();
  const title = document.createElement("div");
  title.textContent = titleText;
  el.summaryWinner.appendChild(title);

  // Do not render podium steps in single-player mode
  if (!isMultiplayer) {
    return;
  }

  const medals = ["\uD83E\uDD47", "\uD83E\uDD48", "\uD83E\uDD49"];
  const top3 = summary.players.slice(0, 3);
  if (top3.length === 0) return;

  const podium = document.createElement("div");
  podium.className = "podium";

  top3.forEach((player, index) => {
    const step = document.createElement("div");
    step.className = "podium-step";

    const medal = document.createElement("div");
    medal.className = "podium-medal";
    medal.textContent = medals[index] || "";

    const name = document.createElement("div");
    name.className = "podium-name";
    name.textContent = player.player_name;

    const score = document.createElement("div");
    score.className = "podium-score";
    score.textContent = t("summary.podium_score", player.total_score);

    const accuracy = document.createElement("div");
    accuracy.className = "podium-accuracy";
    accuracy.textContent = `${player.accuracy_pct}%`;

    step.append(medal, name, score, accuracy);
    podium.appendChild(step);
  });

  el.summaryWinner.appendChild(podium);
}

/* ── Feature 4: Awards ── */

function renderAwards(summary) {
  // Remove any existing awards row
  const existingAwards = el.summaryCard.querySelector(".awards-row");
  if (existingAwards) existingAwards.remove();

  const awards = [];
  const summaryByName = new Map((summary.players || []).map((player) => [player.player_name, player]));

  const pickAwardWinner = (metricKey, tieBreakValueFn, { tieBreakPreferHigher = true, filterFn = null } = {}) => {
    let bestName = null;
    let bestMetricValue = -Infinity;
    let bestTieValue = null;
    let hasTie = false;

    for (const [name, stats] of Object.entries(state.playerStats)) {
      if (filterFn && !filterFn(name, stats)) {
        continue;
      }

      const metricValue = stats[metricKey] ?? 0;
      if (metricValue < 1) {
        continue;
      }

      if (metricValue > bestMetricValue) {
        bestName = name;
        bestMetricValue = metricValue;
        bestTieValue = tieBreakValueFn ? tieBreakValueFn(name) : null;
        hasTie = false;
      } else if (metricValue === bestMetricValue) {
        if (tieBreakValueFn) {
          const tieValue = tieBreakValueFn(name);
          const isBetter = tieBreakPreferHigher ? tieValue > bestTieValue : tieValue < bestTieValue;
          const isWorse = tieBreakPreferHigher ? tieValue < bestTieValue : tieValue > bestTieValue;

          if (isBetter) {
            bestName = name;
            bestMetricValue = metricValue;
            bestTieValue = tieValue;
            hasTie = false;
          } else if (isWorse) {
            // Current leader remains ahead; no tie
          } else {
            hasTie = true;
          }
        } else {
          hasTie = true;
        }
      }
    }

    return hasTie ? null : bestName;
  };

  const isAlbumShuffle = summary.game_mode === "album_shuffle";

  // 1. Sniper — most perfect location guesses (0 km / max points)
  if (summary.location_mode && !isAlbumShuffle) {
    const bestSniper = pickAwardWinner("perfectLocationCount", (name) => summaryByName.get(name)?.location_score ?? -1);
    if (bestSniper) {
      awards.push({
        titleKey: "award.sniper",
        descKey: "award.sniper_desc",
        descArgs: [state.playerStats[bestSniper]?.perfectLocationCount || 0],
        player: bestSniper,
      });
    }
  }

  // 2. Time Traveler — most perfect date guesses (0 days / exact month / max points)
  if (summary.date_mode && !isAlbumShuffle) {
    const bestTimeTraveler = pickAwardWinner("perfectDateCount", (name) => summaryByName.get(name)?.date_score ?? -1);
    if (bestTimeTraveler) {
      awards.push({
        titleKey: "award.time_traveler",
        descKey: "award.time_traveler_desc",
        descArgs: [state.playerStats[bestTimeTraveler]?.perfectDateCount || 0],
        player: bestTimeTraveler,
      });
    }
  }

  // 3. Speed Demon — max fast rounds (<=50% max time) and 0 timeouts
  const speedDemonPlayer = pickAwardWinner("fastRoundCount", (name) => state.playerStats[name]?.totalDurationSec ?? Infinity, {
    tieBreakPreferHigher: false,
    filterFn: (name, stats) => stats.timedOutCount === 0,
  });

  if (speedDemonPlayer) {
    awards.push({
      titleKey: "award.speed_demon",
      descKey: "award.speed_demon_desc",
      descArgs: [state.playerStats[speedDemonPlayer]?.fastRoundCount || 0],
      player: speedDemonPlayer,
    });
  }

  if (awards.length === 0) return;

  const row = document.createElement("div");
  row.className = "awards-row";

  awards.forEach((award) => {
    const card = document.createElement("div");
    card.className = "award-card";

    const titleEl = document.createElement("div");
    titleEl.className = "award-title";
    titleEl.textContent = t(award.titleKey);

    const playerEl = document.createElement("div");
    playerEl.className = "award-player";
    playerEl.textContent = award.player;

    const descEl = document.createElement("div");
    descEl.className = "award-desc";
    descEl.textContent = award.descArgs ? t(award.descKey, ...award.descArgs) : t(award.descKey);

    card.append(titleEl, playerEl, descEl);
    row.appendChild(card);
  });

  // Insert awards between summaryWinner and the table
  el.summaryWinner.after(row);
}

/* ── Feature 7: Fullscreen timer sync ── */

function syncFullscreenTimers(seconds, ratio, isWarning, isCritical) {
  document.querySelectorAll(".fullscreen-timer").forEach((ft) => {
    const fill = ft.querySelector(".fs-timer-fill");
    const label = ft.querySelector(".fs-timer-label");
    const remaining = ft.querySelector(".fs-timer-remaining");
    if (fill) {
      fill.style.width = `${ratio * 100}%`;
      fill.classList.toggle("is-warning", isWarning);
      fill.classList.toggle("is-critical", isCritical);
    }
    if (label) label.textContent = el.timerLabel.textContent;
    if (remaining) remaining.textContent = `${seconds}s`;
  });
}

function returnToSetup() {
  state.matchId = null;
  state.currentQuestion = null;
  state.matchFinished = false;
  state.playedAssetIds = [];
  state.perfectCounts = {};
  state.playerStats = {};
  resetTimerBar();
  showCard(el.setupCard);
  el.leaderboardCard.classList.remove("hidden");
}

function handleAbandonGame(action) {
  const label = action === "restart" ? t("game.abandon_restart") : t("game.abandon_exit");
  if (!confirm(t("game.abandon_confirm", label))) {
    return;
  }
  clearTimer();
  if (action === "restart") {
    restartSameGame().catch((err) => showAlert(err.message));
  } else {
    returnToSetup();
  }
}

async function restartSameGame() {
  const config = state.lastMatchConfig;
  if (!config) {
    returnToSetup();
    return;
  }

  state.matchId = null;
  state.currentQuestion = null;
  state.matchFinished = false;
  state.playedAssetIds = [];
  state.perfectCounts = {};
  state.playerStats = {};
  resetTimerBar();

  const response = await api("/api/game/setup", {
    method: "POST",
    body: JSON.stringify(config),
  });

  state.matchId = response.match_id;
  state.players = response.players;
  el.leaderboardCard.classList.add("hidden");
  showCard(el.gameCard);
  await loadQuestion();
}

/* ----------------------------------------------------------------- events */

el.setupForm.addEventListener("submit", (event) => {
  startMatch(event).catch((err) => showAlert(err.message));
});

el.library.addEventListener("change", () => {
  initAlbums(el.library.value)
    .then(() => loadLeaderboard())
    .catch((err) => showAlert(err.message));
});

el.album.addEventListener("change", () => {
  loadLeaderboard().catch((err) => console.warn("Leaderboard refresh failed:", err));
});

el.dateGuessYear.addEventListener("change", () => renderMonthOptions(true));

if (el.mediaSkipBtn) {
  el.mediaSkipBtn.addEventListener("click", () => {
    submitAnswer(true).catch((err) => showAlert(err.message));
  });
}

el.readyBtn.addEventListener("click", () => {
  if (!state.currentQuestion) {
    return;
  }
  el.passOverlay.classList.add("hidden");
  if (state.currentQuestion.game_mode === "pinpoint") {
    el.quizImage.src = state.currentQuestion.media_url;
    el.quizImage.classList.remove("hidden");
    el.mediaPlaceholder.classList.add("hidden");
    if (state.currentQuestion.location_mode) {
      ensureGuessMap();
    }
  }
  startTimer(state.currentQuestion.round_length);
});

el.submitAnswer.addEventListener("click", () => {
  submitAnswer(state.timedOut).catch((err) => showAlert(err.message));
});

window.handleNextRoundClick = () => handleNextRound().catch((err) => showAlert(err.message));

el.nextRound.addEventListener("click", window.handleNextRoundClick);

el.newMatch.addEventListener("click", returnToSetup);

if (el.shareSummaryBtn) {
  el.shareSummaryBtn.addEventListener("click", () => {
    shareMatchSummary().catch((err) => showAlert(err.message));
  });
}

el.gameRestartBtn.addEventListener("click", () => handleAbandonGame("restart"));
el.gameExitBtn.addEventListener("click", () => handleAbandonGame("exit"));
el.revealRestartBtn.addEventListener("click", () => handleAbandonGame("restart"));
el.revealExitBtn.addEventListener("click", () => handleAbandonGame("exit"));

el.quizImageFullscreen.addEventListener("click", () => toggleMapFullscreen(el.mediaFrame));
el.guessMapFullscreen.addEventListener("click", () => toggleMapFullscreen(el.guessMapShell));
el.revealMapFullscreen.addEventListener("click", () => toggleMapFullscreen(el.revealMapShell));
if (el.journeyMapFullscreen) {
  el.journeyMapFullscreen.addEventListener("click", () => toggleMapFullscreen(el.journeyMapShell));
}

document.addEventListener("fullscreenchange", () => {
  syncFullscreenButtons();

  // Leaflet needs to re-measure after the container resizes.
  [state.guessMap, state.revealMap, state.journeyMap].forEach((map) => {
    if (map) {
      setTimeout(() => map.invalidateSize(), 120);
    }
  });
});

// Setup form controls — reload leaderboard whenever any setting changes.
[el.roundCount, el.roundLength].forEach((control) => {
  if (control) {
    control.addEventListener("change", () => {
      loadLeaderboard().catch((err) => console.warn("Leaderboard refresh failed:", err));
    });
  }
});

const settingsContainer = document.getElementById("game-settings-container");
if (settingsContainer) {
  settingsContainer.addEventListener("change", () => {
    loadLeaderboard().catch((err) => console.warn("Leaderboard refresh failed:", err));
  });
}

el.refreshLeaderboard.addEventListener("click", () => {
  loadLeaderboard().catch((err) => showAlert(err.message));
});

el.leaderboardHead.addEventListener("click", handleSortClick);

if (el.audioToggleBtn) {
  el.audioToggleBtn.addEventListener("click", (e) => {
    e.preventDefault();
    toggleAudio();
  });
}
updateAudioUi();

/* Enter or Space key triggers the primary action of whatever screen is showing. */

function activeActionButton() {
  if (!el.passOverlay.classList.contains("hidden")) {
    return el.readyBtn;
  }
  if (!el.gameCard.classList.contains("hidden")) {
    if (!el.guessingUi.classList.contains("hidden")) {
      return el.submitAnswer;
    }
    if (!el.revealUi.classList.contains("hidden")) {
      return el.nextRound;
    }
  }
  return null;
}

document.addEventListener("keydown", (event) => {
  if ((event.key !== "Enter" && event.key !== " ") || event.isComposing) {
    return;
  }
  if (event.ctrlKey || event.altKey || event.metaKey || event.shiftKey) {
    return;
  }

  const target = event.target;
  if (
    target instanceof HTMLButtonElement ||
    target instanceof HTMLInputElement ||
    target instanceof HTMLSelectElement ||
    target instanceof HTMLTextAreaElement
  ) {
    return;
  }
  if (target instanceof HTMLElement && target.closest("#setup-card")) {
    return;
  }

  const button = activeActionButton();
  if (!button || button.disabled) {
    return;
  }
  event.preventDefault();
  button.click();
});

function initModeButtons() {
  const selector = document.getElementById("game-mode-selector");
  const settingsContainer = document.getElementById("game-settings-container");
  if (!selector) return;
  const buttons = selector.querySelectorAll(".mode-btn");

  function updateModeUI(modeName) {
    state.gameMode = modeName || "pinpoint";
    buttons.forEach((b) => b.classList.toggle("active", b.dataset.mode === state.gameMode));
    if (settingsContainer) {
      const mode = getActiveMode();
      mode.renderSettings(settingsContainer);
      applyLanguage();
    }
    loadLeaderboard().catch((err) => console.warn("Leaderboard refresh failed:", err));
  }

  buttons.forEach((btn) => {
    btn.addEventListener("click", () => {
      updateModeUI(btn.dataset.mode || "pinpoint");
    });
  });

  updateModeUI("pinpoint");
}


(async function bootstrap() {
  initDateDropdowns();
  initModeButtons();
  syncFullscreenButtons();
  updateAudioUi();

  const startupErrors = [];
  const rememberStartupError = (scope, err) => {
    const message = err instanceof Error ? err.message : String(err);
    startupErrors.push(`${scope}: ${message}`);
    console.error(`Startup error (${scope})`, err);
  };

  // UI config and libraries must complete before the leaderboard so that the
  // setup form values (library, album) are populated when we build filter params.
  await Promise.all([
    initUiConfig().catch((err) => rememberStartupError("UI config", err)),
    initLibraries().catch((err) => rememberStartupError("Library setup", err)),
  ]);

  await loadLeaderboard().catch((err) => rememberStartupError("Leaderboard", err));

  if (startupErrors.length > 0) {
    const details = startupErrors.map((err) => translateError(err)).join("\n");
    showAlert(t("setup.startup_error", details));
  }
})();

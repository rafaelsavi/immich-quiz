import { state, el } from "./modules/state.js";
import {
  t,
  translateError,
  showAlert,
  applyLanguage,
  getInitialLanguagePreference,
  updateLanguageUi,
  toggleLanguage,
} from "./modules/i18n.js";
import {
  playSubmitTone,
  playTick,
  playBuzzer,
  playChime,
  playVictoryFanfare,
  playScoreRollupTick,
  toggleAudio,
  updateAudioUi,
} from "./modules/audio.js";
import { api } from "./modules/api.js";
import { formatPlace, formatMonth, buildCell, playerNameCell } from "./modules/formatters.js";
import {
  updateSubmitState,
  renderJourneyMap,
  toggleMapFullscreen,
  syncFullscreenButtons,
  updateMapLayerControls,
  refitMap,
} from "./modules/maps.js";
import { loadLeaderboard, handleSortClick } from "./modules/leaderboard.js";
import { pinpointMode } from "./modules/modes/pinpoint.js";
import { albumShuffleMode, openPhotoLightbox, getShuffleMaps } from "./modules/modes/album_shuffle.js";

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

/* ------------------------------------------------- select wheel scroll */

function initWheelScrolls() {
  bindSelectWheelScroll(el.roundCount, false);
  bindSelectWheelScroll(el.roundLength, false);
  bindSelectWheelScroll(el.library, false);
  bindSelectWheelScroll(el.album, false);
}

async function initUiConfig() {
  const data = await api("/api/ui-config");
  applyUiConfig(data);
}

function applyUiConfig(config) {
  const savedLang = getInitialLanguagePreference();
  if (savedLang) {
    state.language = savedLang;
  } else if (config.language && (config.language === "PT" || config.language === "EN")) {
    state.language = config.language;
  }
  if (config.score_max_points) {
    state.scoreMaxPoints = Number(config.score_max_points);
  }
  updateLanguageUi();
  updateAudioUi();
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
  getActiveMode()?.setDisabled?.(true);

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

  getActiveMode().unmount();

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

  activeMode.mount(el.guessingUi, payload);
  applyLanguage();

  await loadQuestion();
}

function updateRoundMeta() {
  const roundMeta = el.roundMeta;
  if (!roundMeta || !state.currentQuestion) return;
  const data = state.currentQuestion;
  roundMeta.replaceChildren();
  const roundMetaText = document.createElement("span");
  roundMetaText.className = "round-meta-text";
  roundMetaText.textContent = t(
    "game.round_meta",
    data.player_round_number,
    data.total_rounds_per_player,
    data.player_number,
    data.total_players,
    data.player_name
  );
  roundMeta.appendChild(roundMetaText);

  if (state.gameMode === "album_shuffle") {
    const helpBtn = document.createElement("button");
    helpBtn.type = "button";
    helpBtn.className = "shuffle-help-btn";
    helpBtn.textContent = t("game.help_btn");
    helpBtn.addEventListener("click", () => {
      const activeMode = getActiveMode();
      activeMode.openHelp?.(state.currentQuestion);
    });
    roundMeta.appendChild(helpBtn);
  }
}

function checkMediaLoadable(url) {
  return new Promise((resolve) => {
    if (!url) return resolve(true);
    const img = new Image();
    img.onload = () => resolve(true);
    img.onerror = () => resolve(false);
    img.src = url;
  });
}

async function fetchAndVerifyQuestion() {
  while (true) {
    let data;
    try {
      data = await api("/api/question", {
        method: "POST",
        body: JSON.stringify({
          match_id: state.matchId,
          played_asset_ids: state.playedAssetIds,
        }),
      });
    } catch (err) {
      if (
        err.message &&
        (err.message.includes("No eligible assets") || err.message.includes("404"))
      ) {
        return null;
      }
      throw err;
    }

    const photosToTest = [];
    if (data.batch_photos && data.batch_photos.length > 0) {
      for (const p of data.batch_photos) {
        photosToTest.push({ id: p.photo_id, url: p.media_url });
      }
    } else if (data.media_url) {
      photosToTest.push({ id: data.asset_id, url: data.media_url });
    }

    const results = await Promise.all(
      photosToTest.map(async (photo) => ({
        id: photo.id,
        ok: await checkMediaLoadable(photo.url),
      }))
    );

    const failed = results.filter((r) => !r.ok);
    if (failed.length === 0) {
      return data;
    }

    console.warn(
      `[Media Verification] Failed to load ${failed.length} photo(s) [${failed.map((f) => f.id).join(", ")}]. Requesting replacement photo from server...`
    );

    for (const f of failed) {
      if (f.id && !state.playedAssetIds.includes(f.id)) {
        state.playedAssetIds.push(f.id);
      }
    }
  }
}

async function loadQuestion() {
  resetTimerBar();
  state.guessedLatLng = null;
  state.timedOut = false;
  state.currentQuestion = null;
  el.submitAnswer.textContent = t("game.submit_btn");
  getActiveMode()?.setDisabled?.(false);
  updateSubmitState();

  const data = await fetchAndVerifyQuestion();

  if (!data) {
    state.timedOut = true;
    showAlert("No eligible photos available. Round accepted.");
    await submitAnswer(true);
    return;
  }

  state.currentQuestion = data;
  state.gameMode = data.game_mode || "pinpoint";
  if (data.asset_id && !state.playedAssetIds.includes(data.asset_id)) {
    state.playedAssetIds.push(data.asset_id);
  }
  if (data.batch_photos) {
    for (const p of data.batch_photos) {
      if (p.photo_id && !state.playedAssetIds.includes(p.photo_id)) {
        state.playedAssetIds.push(p.photo_id);
      }
    }
  }

  updateRoundMeta();

  const activeMode = getActiveMode();
  activeMode.renderQuestion(data);
  el.guessingUi.classList.remove("hidden");
  el.revealUi.classList.add("hidden");
  window.scrollTo({ top: 0, behavior: "smooth" });
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
    activeMode.onReady(data);
    startTimer(data.round_length);
  }
}

async function submitAnswer(fromTimeout = false) {
  if (!state.currentQuestion || state.submitting) {
    return;
  }
  state.submitting = true;
  updateSubmitState();
  playSubmitTone();

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
    batch_reveal: reveal.batch_reveal || null,
    location_mode: reveal.location_mode,
    library_name: reveal.library_name || (state.currentQuestion ? state.currentQuestion.library_name : ""),
  };
  if (existingIdx >= 0) {
    state.roundHistory[existingIdx] = entry;
  } else {
    state.roundHistory.push(entry);
  }

  state.lastReveal = reveal;
  showCard(el.gameCard);
  el.guessingUi.classList.add("hidden");
  el.revealUi.classList.remove("hidden");

  const activeMode = getActiveMode();
  activeMode.renderReveal(el.revealUi, reveal);

  el.nextRound.textContent = reveal.match_finished ? t("reveal.see_results_btn") : t("reveal.next_round_btn");

  const targetScrollEl = reveal.location_mode ? el.revealMapShell : el.nextRound;
  if (targetScrollEl) {
    targetScrollEl.scrollIntoView({ behavior: "smooth", block: "center" });
  }
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
  if (state.submitting) {
    return;
  }
  state.submitting = true;
  updateSubmitState();

  try {
    if (state.matchFinished) {
      await showMatchSummary();
      return;
    }
    showCard(el.gameCard);
    await loadQuestion();
  } finally {
    state.submitting = false;
    updateSubmitState();
  }
}

/* ------------------------------------------------------- match conclusion */

function renderSummaryContent(summary) {
  if (!summary) return;
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
  columns.forEach((label) => {
    const cell = buildCell(label, true);
    if (label === t("summary.col_accuracy")) {
      cell.className = "col-accuracy hide-on-mobile";
    }
    headRow.appendChild(cell);
  });
  el.summaryTableHead.replaceChildren(headRow);

  el.summaryTableBody.replaceChildren();
  summary.players.forEach((player) => {
    const row = document.createElement("tr");
    row.classList.toggle("is-winner", player.is_winner);

    row.appendChild(buildCell(String(player.rank)));

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
    
    const accCell = buildCell(`${player.accuracy_pct}%`);
    accCell.className = "col-accuracy hide-on-mobile";
    row.appendChild(accCell);

    el.summaryTableBody.appendChild(row);
  });
}

async function showMatchSummary() {
  const summary = await api(`/api/match/${encodeURIComponent(state.matchId)}/summary`);
  state.lastSummary = summary;
  showCard(el.summaryCard);
  playVictoryFanfare();

  renderSummaryContent(summary);

  // Render World Journey Map
  renderJourneyMap(state.roundHistory, summary.location_mode);

  // Render Polaroid Memory Cards
  renderPolaroidGallery(state.roundHistory);

  el.leaderboardCard.classList.remove("hidden");
  await loadLeaderboard();
}

function renderPolaroidGallery(roundHistory) {
  if (!el.polaroidGallery) return;
  el.polaroidGallery.replaceChildren();

  const defaultLibrary = state.lastSummary
    ? state.lastSummary.library_name
    : state.currentQuestion
    ? state.currentQuestion.library_name
    : "";

  (roundHistory || []).forEach((round) => {
    if (round.batch_reveal && Array.isArray(round.batch_reveal) && round.batch_reveal.length > 0) {
      round.batch_reveal.forEach((item) => {
        const card = document.createElement("div");
        card.className = "polaroid-card";

        const imgWrap = document.createElement("div");
        imgWrap.className = "polaroid-img-wrap";

        const lib = round.library_name || defaultLibrary;
        const imgUrl = `/api/media/${item.photo_id}?library_name=${encodeURIComponent(lib)}`;
        const img = document.createElement("img");
        img.className = "polaroid-img";
        img.src = imgUrl;
        img.alt = `Round ${round.round_number} - Pin ${item.true_pin_id}`;
        img.style.cursor = "pointer";
        img.addEventListener("click", () => openPhotoLightbox(imgUrl));
        imgWrap.appendChild(img);

        const caption = document.createElement("div");
        caption.className = "polaroid-caption";

        const badge = document.createElement("span");
        badge.className = "polaroid-round-badge";
        badge.textContent = item.true_pin_id
          ? `${t("summary.journey_round", round.round_number)} - ${item.true_pin_id}`
          : t("summary.journey_round", round.round_number);

        const loc = document.createElement("span");
        loc.className = "polaroid-location";
        loc.textContent = formatPlace(item) || t("fmt.unknown_place");

        const date = document.createElement("span");
        date.className = "polaroid-date";
        date.textContent = formatMonth(item.actual_year, item.actual_month);

        caption.append(badge, loc, date);
        card.append(imgWrap, caption);
        el.polaroidGallery.appendChild(card);
      });
    } else {
      const card = document.createElement("div");
      card.className = "polaroid-card";

      const imgWrap = document.createElement("div");
      imgWrap.className = "polaroid-img-wrap";

      if (round.media_url) {
        const img = document.createElement("img");
        img.className = "polaroid-img";
        img.src = round.media_url;
        img.alt = `Round ${round.round_number}`;
        img.style.cursor = "pointer";
        img.addEventListener("click", () => openPhotoLightbox(round.media_url));
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
    }
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
  getActiveMode().unmount();
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
  getActiveMode().unmount();
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

  const activeMode = getActiveMode();
  activeMode.unmount();

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

  activeMode.mount(el.guessingUi, config);
  applyLanguage();

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

el.readyBtn.addEventListener("click", () => {
  if (!state.currentQuestion) {
    return;
  }
  el.passOverlay.classList.add("hidden");
  const activeMode = getActiveMode();
  activeMode.onReady(state.currentQuestion);
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


el.revealMapFullscreen.addEventListener("click", () => toggleMapFullscreen(el.revealMapShell));
if (el.journeyMapFullscreen) {
  el.journeyMapFullscreen.addEventListener("click", () => toggleMapFullscreen(el.journeyMapShell));
}

document.addEventListener("fullscreenchange", () => {
  syncFullscreenButtons();

  // Leaflet needs to re-measure and refit after the container resizes.
  [state.guessMap, state.revealMap, state.journeyMap, ...getShuffleMaps()].forEach((map) => {
    if (map) {
      refitMap(map);
      setTimeout(() => refitMap(map), 120);
    }
  });
});

window.addEventListener("resize", () => {
  [state.guessMap, state.revealMap, state.journeyMap, ...getShuffleMaps()].forEach((map) => {
    if (map) {
      refitMap(map);
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

function refreshActiveScreenLanguage() {
  updateLanguageUi();
  updateAudioUi();
  applyLanguage();
  syncFullscreenButtons();
  updateMapLayerControls(getShuffleMaps());

  if (!el.setupCard.classList.contains("hidden")) {
    const settingsContainer = document.getElementById("game-settings-container");
    if (settingsContainer) {
      const mode = getActiveMode();
      mode.renderSettings(settingsContainer);
      applyLanguage();
    }
  }

  // Only update the round-meta banner when guessing (on the reveal screen it shows
  // reveal.title which refreshRevealText will handle).
  if (state.currentQuestion && el.guessingUi && !el.guessingUi.classList.contains("hidden")) {
    updateRoundMeta();
  }

  // Refresh the Album Shuffle help modal body if it is currently open.
  if (state.currentQuestion) {
    const activeMode = getActiveMode();
    activeMode.refreshHelpModal?.(state.currentQuestion);
  }

  if (!el.passOverlay.classList.contains("hidden") && state.currentQuestion) {
    const data = state.currentQuestion;
    if (el.overlayTitle) {
      el.overlayTitle.textContent = t(
        "game.pass_device_title",
        data.player_name,
        data.player_number,
        data.total_players
      );
    }
    if (el.overlaySubtitle) {
      el.overlaySubtitle.textContent = t(
        "game.pass_device_subtitle",
        data.player_round_number,
        data.total_rounds_per_player
      );
    }
    if (el.readyBtn) {
      el.readyBtn.textContent = t("game.ready_btn");
    }
  }

  if (!el.guessingUi.classList.contains("hidden") && state.currentQuestion) {
    // Update only dynamic text nodes — never touch image/map/date selects.
    if (state.timedOut) {
      el.timerLabel.textContent = t("game.timer_time_up_label");
      el.timeoutNotice.textContent = t("game.timer_time_up_notice");
      el.submitAnswer.textContent = t("game.continue_btn");
    } else {
      if (state.currentQuestion.round_length === "unlimited") {
        el.timerLabel.textContent = t("game.timer_unlimited");
      } else if (!el.timerTrack.classList.contains("is-idle")) {
        el.timerLabel.textContent = t("game.timer_time_left");
      }
      el.submitAnswer.textContent = t("game.submit_btn");
    }
  }

  if (!el.revealUi.classList.contains("hidden") && state.lastReveal) {
    // Refresh all text in the reveal (table headers, actual date/location, buttons)
    // without re-initializing the map or triggering animations.
    const activeMode = getActiveMode();
    activeMode.refreshRevealText(el.revealUi, state.lastReveal);
    el.nextRound.textContent = state.lastReveal.match_finished
      ? t("reveal.see_results_btn")
      : t("reveal.next_round_btn");
  }

  if (!el.summaryCard.classList.contains("hidden") && state.lastSummary) {
    renderSummaryContent(state.lastSummary);
  }

  loadLeaderboard().catch((err) => console.warn("Leaderboard refresh failed:", err));
}

document.addEventListener("click", (e) => {
  const langBtn = e.target.closest("#lang-toggle-btn");
  if (langBtn) {
    e.preventDefault();
    toggleLanguage(() => {
      refreshActiveScreenLanguage();
    });
  }
});

if (el.audioToggleBtn) {
  el.audioToggleBtn.addEventListener("click", (e) => {
    e.preventDefault();
    toggleAudio();
  });
}
updateLanguageUi();
updateAudioUi();

/* Enter or Space key triggers the primary action of whatever screen is showing. */

function activeActionButton() {
  if (state.submitting) {
    return null;
  }
  if (!el.passOverlay.classList.contains("hidden")) {
    return el.readyBtn;
  }
  if (!el.gameCard.classList.contains("hidden")) {
    if (!el.guessingUi.classList.contains("hidden")) {
      return el.submitAnswer;
    }
    if (!el.revealUi.classList.contains("hidden")) {
      const activeNextBtn = document.querySelector(
        "#reveal-ui button#next-round:not(.hidden), #album-shuffle-reveal-ui button.next-round-btn:not(.hidden)"
      );
      return activeNextBtn || el.nextRound;
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
  refreshActiveScreenLanguage();
  initWheelScrolls();
  initModeButtons();
  syncFullscreenButtons();

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

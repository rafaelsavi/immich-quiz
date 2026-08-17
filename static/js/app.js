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
  playVictoryFanfare,
  toggleAudio,
  updateAudioUi,
} from "./modules/audio.js";
import { api } from "./modules/api.js";
import { formatPlace, renderRoundMeta } from "./modules/formatters.js";
import {
  updateSubmitState,
  renderJourneyMap,
  toggleMapFullscreen,
  syncFullscreenButtons,
  updateMapLayerControls,
  refitAllMaps,
  unregisterActiveMap,
} from "./modules/maps.js";
import { loadLeaderboard, handleSortClick } from "./modules/leaderboard.js";
import { pinpointMode } from "./modules/modes/pinpoint.js";
import { albumShuffleMode, getShuffleMaps } from "./modules/modes/album_shuffle.js";
import { renderSyncStatus, getLastSyncStatus } from "./modules/sync.js";
import { clearTimer, resetTimerBar, startTimer } from "./modules/timer.js";
import { bindGlobalShortcuts } from "./modules/shortcuts.js";
import { renderPodium } from "./modules/summary/podium.js";
import { renderAwards } from "./modules/summary/awards.js";
import { renderSummaryTable } from "./modules/summary/table.js";
import { renderPolaroidGallery } from "./modules/summary/polaroids.js";
import { shareMatchSummary } from "./modules/summary/share.js";
import {
  playerInput,
  albumMultiSelect,
  countryMultiSelect,
  cityMultiSelect,
  peopleMultiSelect,
  dateRangeSlider,
  getSelectedPeopleMode,
  restoreLibraryFilters,
  triggerPreflightDebounced,
  initPlayerInput,
  initLibraries,
  initWheelScrolls,
  refreshFilterComponentsLanguage,
  setGetActiveModeFn,
  getLastPreflightData,
  showPreflightWarning,
} from "./modules/setup_filters.js";

const GAME_MODES = {
  pinpoint: pinpointMode,
  album_shuffle: albumShuffleMode,
};

function getActiveMode() {
  return GAME_MODES[state.gameMode] || pinpointMode;
}

setGetActiveModeFn(getActiveMode);

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

function resetGameUi() {
  clearRevealAnimation();
  clearTimer();

  state.matchId = null;
  state.currentQuestion = null;
  state.lastReveal = null;
  state.lastSummary = null;
  state.guessedLatLng = null;
  state.mapBounds = null;
  state.playedAssetIds = [];
  state.roundHistory = [];
  state.perfectCounts = {};
  state.playerStats = {};
  state.matchFinished = false;
  state.timedOut = false;
  state.submitting = false;

  try {
    getActiveMode().unmount();
  } catch (_) {}

  if (el.roundMeta) el.roundMeta.replaceChildren();
  if (el.passOverlay) el.passOverlay.classList.add("hidden");
  if (el.guessingUi) el.guessingUi.classList.add("hidden");
  if (el.revealUi) el.revealUi.classList.add("hidden");
  if (el.timeoutNotice) {
    el.timeoutNotice.classList.add("hidden");
    el.timeoutNotice.textContent = "";
  }

  if (el.quizImage) {
    el.quizImage.classList.add("hidden");
    el.quizImage.removeAttribute("src");
    el.quizImage.onerror = null;
  }
  if (el.quizImageFullscreen) {
    el.quizImageFullscreen.classList.add("hidden");
  }
  if (el.mediaPlaceholder) el.mediaPlaceholder.classList.remove("hidden");
  if (el.mediaFrame) el.mediaFrame.classList.add("hidden");

  if (el.revealActual) el.revealActual.replaceChildren();
  if (el.revealLegend) el.revealLegend.replaceChildren();
  if (el.revealTableHead) el.revealTableHead.replaceChildren();
  if (el.revealTableBody) el.revealTableBody.replaceChildren();
  if (el.revealMapShell) el.revealMapShell.classList.add("hidden");
  if (el.revealMapHead) el.revealMapHead.classList.add("hidden");

  if (state.revealLayers && Array.isArray(state.revealLayers)) {
    state.revealLayers.forEach((l) => {
      try {
        if (state.revealMap) state.revealMap.removeLayer(l);
      } catch (_) {}
    });
    state.revealLayers = [];
  }
  if (state.revealMap) {
    try {
      unregisterActiveMap(state.revealMap);
      state.revealMap.remove();
    } catch (_) {}
    state.revealMap = null;
  }

  if (state.journeyLayers && Array.isArray(state.journeyLayers)) {
    state.journeyLayers.forEach((l) => {
      try {
        if (state.journeyMap) state.journeyMap.removeLayer(l);
      } catch (_) {}
    });
    state.journeyLayers = [];
  }
  if (state.journeyMap) {
    try {
      unregisterActiveMap(state.journeyMap);
      state.journeyMap.remove();
    } catch (_) {}
    state.journeyMap = null;
  }
  if (el.journeyMapShell) el.journeyMapShell.classList.add("hidden");
  if (el.journeyMapHead) el.journeyMapHead.classList.add("hidden");

  if (el.summaryWinner) el.summaryWinner.replaceChildren();
  if (el.summaryMeta) el.summaryMeta.textContent = "";
  if (el.summaryTableHead) el.summaryTableHead.replaceChildren();
  if (el.summaryTableBody) el.summaryTableBody.replaceChildren();
  if (el.polaroidGallery) el.polaroidGallery.replaceChildren();
  if (el.summaryCard) {
    const existingAwards = el.summaryCard.querySelector(".awards-row");
    if (existingAwards) existingAwards.remove();
  }
}

async function startMatch(event) {
  event.preventDefault();

  const submitBtn = el.setupSubmitBtn || document.querySelector("#setup-form button[type=submit]");
  if (submitBtn && submitBtn.disabled) {
    return;
  }

  const warningEl = document.getElementById("preflight-warning");
  if (warningEl && !warningEl.classList.contains("hidden")) {
    return;
  }

  const lastPreflight = getLastPreflightData();
  if (lastPreflight && !lastPreflight.ok) {
    return;
  }

  resetGameUi();

  const players = playerInput
    ? playerInput.getPlayers()
    : el.players.value
        .split(",")
        .map((name) => name.trim())
        .filter(Boolean);

  if (players.length === 0) {
    if (playerInput) {
      playerInput.showEmptyError();
    } else {
      showAlert(t("setup.players_empty_error"));
    }
    return;
  }

  const activeMode = getActiveMode();
  const modePayload = activeMode.getModePayload();

  const albumIds = albumMultiSelect ? albumMultiSelect.getSelectedIds() : [];
  const albumNames = albumMultiSelect ? albumMultiSelect.getSelectedItems().map((i) => i.name) : [];
  const albumName = albumNames.length > 0 ? albumNames.join(", ") : "-";
  const { minDate, maxDate } = dateRangeSlider ? dateRangeSlider.getSelectedRange() : { minDate: null, maxDate: null };

  const payload = {
    players,
    round_count: Number(el.roundCount.value),
    round_length: el.roundLength.value,
    library_name: el.library.value,
    album_ids: albumIds,
    album_name: albumName,
    person_ids: peopleMultiSelect ? peopleMultiSelect.getSelectedIds() : [],
    people_mode: getSelectedPeopleMode(),
    countries: countryMultiSelect ? countryMultiSelect.getSelectedIds() : [],
    cities: cityMultiSelect ? cityMultiSelect.getSelectedIds() : [],
    min_date: minDate,
    max_date: maxDate,
    include_shared: el.includeSharedCheckbox ? el.includeSharedCheckbox.checked : false,
    ...modePayload,
  };

  try {
    const preflight = await api("/api/game/preflight", {
      method: "POST",
      body: JSON.stringify(payload),
    });

    if (!preflight.ok) {
      showPreflightWarning(
        t("setup.not_enough_media", preflight.eligible_count, preflight.required)
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
  state.mapBounds = response.map_bounds || null;
  state.playedAssetIds = [];
  state.matchFinished = false;
  state.perfectCounts = {};
  state.playerStats = {};
  state.roundHistory = [];

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
  renderRoundMeta(roundMeta, {
    roundNum: data.player_round_number,
    totalRounds: data.total_rounds_per_player,
    playerNum: data.player_number,
    totalPlayers: data.total_players,
    playerName: data.player_name,
    isReveal: false,
    showHelp: state.gameMode === "album_shuffle",
    onHelpClick: () => {
      const activeMode = getActiveMode();
      activeMode.openHelp?.(state.currentQuestion);
    },
  });
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
      `[Media Verification] Failed to load ${failed.length} ${failed.length === 1 ? "photo" : "photos"} [${failed.map((f) => f.id).join(", ")}]. Requesting replacement photo from server...`
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

  if (el.revealUi) el.revealUi.classList.add("hidden");
  if (el.guessingUi) el.guessingUi.classList.remove("hidden");
  if (el.roundMeta) el.roundMeta.replaceChildren();

  if (el.quizImage) {
    el.quizImage.classList.add("hidden");
    el.quizImage.removeAttribute("src");
    el.quizImage.onerror = null;
  }
  if (el.quizImageFullscreen) {
    el.quizImageFullscreen.classList.add("hidden");
  }
  if (el.mediaPlaceholder) el.mediaPlaceholder.classList.remove("hidden");

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
    startTimer(data.round_length, getActiveMode);
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
          totalDistanceKm: 0,
          distanceCount: 0,
          totalDateDiffDays: 0,
          dateCount: 0,
          perfectLocationCount: 0,
          perfectDateCount: 0,
          perfectRounds: 0,
          timedOutCount: 0,
          fastRoundCount: 0,
          totalDurationSec: 0,
        };
      }
      state.playerStats[playerName].totalDurationSec = (state.playerStats[playerName].totalDurationSec || 0) + elapsedSec;
      if (!fromTimeout && elapsedSec <= totalSec / 2) {
        state.playerStats[playerName].fastRoundCount = (state.playerStats[playerName].fastRoundCount || 0) + 1;
      }
    }

    const activeMode = getActiveMode();
    const payload = activeMode.buildAnswerPayload(question, fromTimeout);
    payload.time_taken_seconds = elapsedSec;

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
    if (el.revealUi) el.revealUi.classList.add("hidden");
    if (el.guessingUi) el.guessingUi.classList.remove("hidden");
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
  renderAwards(summary, state.playerStats);
  renderSummaryTable(summary, state.perfectCounts);
}

async function showMatchSummary() {
  const summary = await api(`/api/match/${encodeURIComponent(state.matchId)}/summary`);
  state.lastSummary = summary;
  showCard(el.summaryCard);
  playVictoryFanfare();

  renderSummaryContent(summary);
  renderJourneyMap(state.roundHistory, summary.location_mode);
  renderPolaroidGallery(state.roundHistory, summary.library_name);

  el.leaderboardCard.classList.remove("hidden");
  await loadLeaderboard();
}

function returnToSetup() {
  resetGameUi();
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

  resetGameUi();

  const activeMode = getActiveMode();

  const response = await api("/api/game/setup", {
    method: "POST",
    body: JSON.stringify(config),
  });

  state.matchId = response.match_id;
  state.players = response.players;
  state.mapBounds = response.map_bounds || null;
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

el.readyBtn.addEventListener("click", () => {
  if (!state.currentQuestion) {
    return;
  }
  el.passOverlay.classList.add("hidden");
  const activeMode = getActiveMode();
  activeMode.onReady(state.currentQuestion);
  startTimer(state.currentQuestion.round_length, getActiveMode);
});

el.submitAnswer.addEventListener("click", () => {
  submitAnswer(state.timedOut).catch((err) => showAlert(err.message));
});

window.handleNextRoundClick = () => handleNextRound().catch((err) => showAlert(err.message));

el.nextRound.addEventListener("click", window.handleNextRoundClick);

el.newMatch.addEventListener("click", returnToSetup);

if (el.shareSummaryBtn) {
  el.shareSummaryBtn.addEventListener("click", () => {
    shareMatchSummary(state.lastSummary).catch((err) => showAlert(err.message));
  });
}

el.gameRestartBtn.addEventListener("click", () => handleAbandonGame("restart"));
el.gameExitBtn.addEventListener("click", () => handleAbandonGame("exit"));
el.revealRestartBtn.addEventListener("click", () => handleAbandonGame("restart"));
el.revealExitBtn.addEventListener("click", () => handleAbandonGame("exit"));

if (el.revealMapFullscreen) {
  if (window.L && L.DomEvent) {
    L.DomEvent.disableClickPropagation(el.revealMapFullscreen);
    L.DomEvent.disableScrollPropagation(el.revealMapFullscreen);
  }
  el.revealMapFullscreen.addEventListener("click", (e) => {
    e.stopPropagation();
    toggleMapFullscreen(el.revealMapShell);
  });
}
if (el.journeyMapFullscreen) {
  if (window.L && L.DomEvent) {
    L.DomEvent.disableClickPropagation(el.journeyMapFullscreen);
    L.DomEvent.disableScrollPropagation(el.journeyMapFullscreen);
  }
  el.journeyMapFullscreen.addEventListener("click", (e) => {
    e.stopPropagation();
    toggleMapFullscreen(el.journeyMapShell);
  });
}

document.addEventListener("fullscreenchange", () => {
  syncFullscreenButtons();
  refitAllMaps();
  setTimeout(() => refitAllMaps(), 120);
});

window.addEventListener("resize", () => {
  refitAllMaps();
});

[el.roundCount, el.roundLength].forEach((control) => {
  if (control) {
    control.addEventListener("change", () => {
      loadLeaderboard().catch((err) => console.warn("Leaderboard refresh failed:", err));
      if (control === el.roundCount) {
        triggerPreflightDebounced();
      }
    });
  }
});

const settingsContainer = document.getElementById("game-settings-container");
if (settingsContainer) {
  settingsContainer.addEventListener("change", () => {
    loadLeaderboard().catch((err) => console.warn("Leaderboard refresh failed:", err));
    triggerPreflightDebounced();
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
  refreshFilterComponentsLanguage();

  const syncStatus = getLastSyncStatus();
  if (syncStatus) {
    renderSyncStatus(syncStatus);
  }

  if (!el.setupCard.classList.contains("hidden")) {
    const settingsCont = document.getElementById("game-settings-container");
    if (settingsCont) {
      const mode = getActiveMode();
      mode.renderSettings(settingsCont);
      applyLanguage();
    }
  }

  if (state.currentQuestion && el.guessingUi && !el.guessingUi.classList.contains("hidden")) {
    updateRoundMeta();
  }

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

bindGlobalShortcuts();

function initModeButtons() {
  const selector = document.getElementById("game-mode-selector");
  const settingsCont = document.getElementById("game-settings-container");
  if (!selector) return;
  const buttons = selector.querySelectorAll(".mode-btn");

  function updateModeUI(modeName) {
    state.gameMode = modeName || "pinpoint";
    buttons.forEach((b) => b.classList.toggle("active", b.dataset.mode === state.gameMode));
    if (settingsCont) {
      const mode = getActiveMode();
      mode.renderSettings(settingsCont);
      applyLanguage();
    }
    loadLeaderboard().catch((err) => console.warn("Leaderboard refresh failed:", err));
    triggerPreflightDebounced();
  }

  buttons.forEach((btn) => {
    btn.addEventListener("click", () => {
      updateModeUI(btn.dataset.mode || "pinpoint");
    });
  });

  updateModeUI("pinpoint");
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
  if (el.library && el.library.value) {
    restoreLibraryFilters(el.library.value);
  }
  updateLanguageUi();
  updateAudioUi();
  applyLanguage();
}

(async function bootstrap() {
  initPlayerInput();
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

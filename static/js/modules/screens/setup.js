import { state, el, saveActiveMatchSession, clearActiveMatchSession } from "../state.js";
import { api } from "../api.js";
import { t, showAlert, applyLanguage } from "../i18n.js";
import { navigate } from "../router.js";
import { getActiveMode } from "../modes/index.js";
import { showCard, resetGameUi, confirmAbandonMatch } from "./common.js";
import { loadQuestion } from "./game.js";
import {
  playerInput,
  libraryMultiSelect,
  albumMultiSelect,
  countryMultiSelect,
  cityMultiSelect,
  peopleMultiSelect,
  dateRangeSlider,
  getSelectedPeopleMode,
  getLastPreflightData,
  showPreflightWarning,
} from "../setup_filters.js";

let _ensureLobbyInitializedFn = null;

export function setEnsureLobbyInitializedFn(fn) {
  _ensureLobbyInitializedFn = fn;
}

export async function startMatch(event) {
  if (event) event.preventDefault();

  if (state.startingMatch) {
    return;
  }

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

  state.startingMatch = true;
  if (submitBtn) {
    submitBtn.disabled = true;
  }

  try {
    resetGameUi();

    const activeMode = getActiveMode();
    const modePayload = activeMode.getModePayload();

    const albumIds = albumMultiSelect ? albumMultiSelect.getSelectedIds() : [];
    const albumNames = albumMultiSelect ? albumMultiSelect.getSelectedItems().map((i) => i.name) : [];
    const selectedLibs = libraryMultiSelect ? libraryMultiSelect.getSelectedIds() : [];
    const { minDate, maxDate } = dateRangeSlider ? dateRangeSlider.getSelectedRange() : { minDate: null, maxDate: null };

    const payload = {
      players,
      round_count: Number(el.roundCount?.value || 5),
      round_length: el.roundLength?.value || "standard",
      libraries: selectedLibs,
      albums: albumIds,
      album_names: albumNames,
      people: peopleMultiSelect ? peopleMultiSelect.getSelectedIds() : [],
      person_names: peopleMultiSelect
        ? peopleMultiSelect.getSelectedItems().map((p) => p.name)
        : [],
      people_mode: getSelectedPeopleMode(),
      countries: countryMultiSelect ? countryMultiSelect.getSelectedIds() : [],
      cities: cityMultiSelect ? cityMultiSelect.getSelectedIds() : [],
      min_date: minDate,
      max_date: maxDate,
      include_shared: el.includeSharedCheckbox ? el.includeSharedCheckbox.checked : false,
      ...modePayload,
    };

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

    saveActiveMatchSession();
    navigate(`/game/${encodeURIComponent(state.matchId)}`, { force: true });

    el.leaderboardCard.classList.add("hidden");
    showCard(el.gameCard);

    activeMode.mount(el.guessingUi, payload);
    applyLanguage();

    await loadQuestion();
  } catch (err) {
    showAlert(err.message || err);
  } finally {
    state.startingMatch = false;
    if (submitBtn) {
      const warning = document.getElementById("preflight-warning");
      const hasWarning = warning && !warning.classList.contains("hidden");
      submitBtn.disabled = Boolean(hasWarning);
    }
  }
}

export function returnToSetup({ updateUrl = true } = {}) {
  document.documentElement.classList.remove("route-non-lobby");
  state.startingMatch = false;
  clearActiveMatchSession();
  resetGameUi();
  showCard(el.setupCard);
  el.leaderboardCard.classList.remove("hidden");
  const submitBtn = el.setupSubmitBtn || document.querySelector("#setup-form button[type=submit]");
  if (submitBtn) {
    const warning = document.getElementById("preflight-warning");
    const hasWarning = warning && !warning.classList.contains("hidden");
    submitBtn.disabled = Boolean(hasWarning);
  }
  if (updateUrl) {
    navigate("/", { force: true });
  }
  if (_ensureLobbyInitializedFn) {
    _ensureLobbyInitializedFn().catch((err) => console.warn("Lobby setup error:", err));
  }
  window.scrollTo({ top: 0, behavior: "smooth" });
}

export async function restartSameGame() {
  if (state.startingMatch) {
    return;
  }

  const config = state.lastMatchConfig;
  if (!config) {
    returnToSetup();
    return;
  }

  state.startingMatch = true;

  try {
    resetGameUi();

    const activeMode = getActiveMode();

    const response = await api("/api/game/setup", {
      method: "POST",
      body: JSON.stringify(config),
    });

    state.matchId = response.match_id;
    state.players = response.players;
    state.mapBounds = response.map_bounds || null;
    state.playedAssetIds = [];
    state.matchFinished = false;
    state.perfectCounts = {};
    state.playerStats = {};
    state.roundHistory = [];

    saveActiveMatchSession();
    navigate(`/game/${encodeURIComponent(state.matchId)}`, { force: true });
    el.leaderboardCard.classList.add("hidden");
    showCard(el.gameCard);

    activeMode.mount(el.guessingUi, config);
    applyLanguage();

    await loadQuestion();
  } catch (err) {
    showAlert(err.message || err);
  } finally {
    state.startingMatch = false;
  }
}

export function handleAbandonGame(action) {
  if (!confirmAbandonMatch(action)) return;
  if (action === "restart") {
    restartSameGame().catch((err) => showAlert(err.message));
  } else {
    returnToSetup();
  }
}

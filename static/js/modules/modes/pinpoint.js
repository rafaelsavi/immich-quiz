import { t } from "../i18n.js";
import { el, state } from "../state.js";
import { ensureGuessMap } from "../maps.js";
import { renderGuessingModeSettings } from "./common.js";

export const pinpointMode = {
  name: "pinpoint",

  renderSettings(containerEl) {
    renderGuessingModeSettings(containerEl);
  },

  getModePayload() {
    const locCheckbox = document.getElementById("goal-location");
    const dateCheckbox = document.getElementById("goal-date");
    return {
      game_mode: "pinpoint",
      location_mode: locCheckbox ? locCheckbox.checked : true,
      date_mode: dateCheckbox ? dateCheckbox.checked : true,
    };
  },

  renderQuestion(guessingUi, questionData) {
    // Hide Album Shuffle UI container
    const shuffleUi = document.getElementById("album-shuffle-ui");
    if (shuffleUi) {
      shuffleUi.classList.add("hidden");
    }

    // Un-hide Pinpoint UI container
    const pinpointUi = document.getElementById("pinpoint-ui");
    if (pinpointUi) {
      pinpointUi.classList.remove("hidden");
    }

    // Show single photo frame and pinpoint controls
    if (el.mediaFrame) el.mediaFrame.classList.remove("hidden");
    if (el.mapGuessWrap) el.mapGuessWrap.classList.toggle("hidden", !questionData.location_mode);
    if (el.dateGuessWrap) el.dateGuessWrap.classList.toggle("hidden", !questionData.date_mode);

    const hasMapOnly = Boolean(questionData.location_mode) && !Boolean(questionData.date_mode);
    if (hasMapOnly) {
      document.documentElement.style.setProperty("--round-guess-layout-columns", "minmax(0, 1fr)");
    } else {
      document.documentElement.style.setProperty("--round-guess-layout-columns", "minmax(0, 67fr) minmax(0, 33fr)");
    }

    if (questionData.location_mode) {
      ensureGuessMap();
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
};

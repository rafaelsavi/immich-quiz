import { t } from "../i18n.js";
import { el, state } from "../state.js";
import { ensureGuessMap, toggleMapFullscreen } from "../maps.js";
import { renderGuessingModeSettings, mountModeTemplate } from "./common.js";

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
    // 1. Mount pinpoint UI template into host container (cleanly unmounts any previous mode)
    const pinpointUi = mountModeTemplate("pinpoint", guessingUi);

    // 2. Toggle location / date visibility controls
    const mediaFrame = document.getElementById("media-frame") || el.mediaFrame;
    const mapWrap = document.getElementById("map-guess-wrap") || el.mapGuessWrap;
    const dateWrap = document.getElementById("date-guess-wrap") || el.dateGuessWrap;

    if (mediaFrame) mediaFrame.classList.remove("hidden");
    if (mapWrap) mapWrap.classList.toggle("hidden", !questionData.location_mode);
    if (dateWrap) dateWrap.classList.toggle("hidden", !questionData.date_mode);

    const hasMapOnly = Boolean(questionData.location_mode) && !Boolean(questionData.date_mode);
    if (hasMapOnly) {
      document.documentElement.style.setProperty("--round-guess-layout-columns", "minmax(0, 1fr)");
    } else {
      document.documentElement.style.setProperty("--round-guess-layout-columns", "minmax(0, 67fr) minmax(0, 33fr)");
    }

    // 3. Bind template fullscreen buttons
    const imgFsBtn = document.getElementById("quiz-image-fullscreen");
    if (imgFsBtn && !imgFsBtn.dataset.bound) {
      imgFsBtn.dataset.bound = "true";
      imgFsBtn.addEventListener("click", () => toggleMapFullscreen(mediaFrame));
    }

    const mapFsBtn = document.getElementById("guess-map-fullscreen");
    if (mapFsBtn && !mapFsBtn.dataset.bound) {
      mapFsBtn.dataset.bound = "true";
      mapFsBtn.addEventListener("click", () => toggleMapFullscreen(document.getElementById("guess-map-shell")));
    }

    if (questionData.date_mode) {
      if (window.initDateDropdowns) window.initDateDropdowns();
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

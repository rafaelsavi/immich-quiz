import { t } from "../../i18n.js";
import { state, el } from "../../state.js";
import { toggleMapFullscreen } from "../../maps.js";
import { renderGuessingModeSettings, mountModeTemplate } from "../common.js";
import { renderPhotoCardsList } from "./board.js";
import { renderShuffleMap, highlightMapMarker, updateShuffleMapMarkers } from "./map.js";
import { renderShuffleReveal } from "./reveal.js";
import { openShuffleHelpModal } from "./help.js";

export const albumShuffleMode = {
  name: "album_shuffle",

  openHelp(questionData) {
    openShuffleHelpModal(questionData);
  },

  renderSettings(containerEl) {
    renderGuessingModeSettings(containerEl);
  },

  getModePayload() {
    const locCheckbox = document.getElementById("goal-location");
    const dateCheckbox = document.getElementById("goal-date");
    return {
      game_mode: "album_shuffle",
      location_mode: locCheckbox ? locCheckbox.checked : true,
      date_mode: dateCheckbox ? dateCheckbox.checked : true,
    };
  },

  renderQuestion(guessingUi, questionData) {
    // Standardized UI Strategy: mount template into host container (cleanly unmounts any previous mode)
    const uiContainer = mountModeTemplate("album_shuffle", guessingUi);
    uiContainer.classList.remove("hidden");
    uiContainer.replaceChildren();

    // Initialize photo order & pin assignments
    const photos = questionData.batch_photos || [];
    state.albumShuffleState = {
      orderedPhotoIds: photos.map((p) => p.photo_id),
      selectedPhotoId: photos[0]?.photo_id || null,
      pinAssignments: {}, // photoId -> pinId
    };

    photos.forEach((p) => {
      state.albumShuffleState.pinAssignments[p.photo_id] = null;
    });

    const boardEl = document.createElement("div");
    boardEl.className = "shuffle-board";

    // Left Column: Map
    const mapCol = document.createElement("div");
    mapCol.className = "shuffle-map-column";
    const mapShell = document.createElement("div");
    mapShell.className = "map-shell";
    mapShell.id = "shuffle-map-shell";

    // Add Map Fullscreen Button
    const mapFsBtn = document.createElement("button");
    mapFsBtn.type = "button";
    mapFsBtn.className = "map-fullscreen-btn";
    mapFsBtn.setAttribute("aria-pressed", "false");
    mapFsBtn.title = "Toggle fullscreen map";
    mapFsBtn.textContent = t("game.fullscreen_btn");
    mapFsBtn.addEventListener("click", () => toggleMapFullscreen(mapShell));

    mapShell.appendChild(mapFsBtn);
    mapCol.appendChild(mapShell);

    // Right Column: Cards List with Sequence Info Banner, Rank Buttons
    const cardsCol = document.createElement("div");
    cardsCol.className = "shuffle-photo-column";
    cardsCol.id = "shuffle-cards-list";

    if (!questionData.location_mode) {
      mapCol.style.display = "none";
      boardEl.classList.add("no-map");
      cardsCol.classList.add("no-map");
    }

    boardEl.append(mapCol, cardsCol);
    uiContainer.appendChild(boardEl);

    if (questionData.location_mode) {
      renderShuffleMap(mapShell, questionData.batch_pins, questionData, (pin) => {
        const selectedId = state.albumShuffleState ? state.albumShuffleState.selectedPhotoId : null;
        if (selectedId) {
          const pinAssignments = state.albumShuffleState.pinAssignments || {};
          Object.keys(pinAssignments).forEach((pid) => {
            if (pinAssignments[pid] === pin.pin_id) {
              pinAssignments[pid] = null;
            }
          });
          pinAssignments[selectedId] = pin.pin_id;
          updateShuffleMapMarkers(questionData.batch_pins);
          const cardsList = document.getElementById("shuffle-cards-list");
          if (cardsList) {
            renderPhotoCardsList(cardsList, questionData);
          }
          highlightMapMarker(pin.pin_id);
        }
      });
    }
    renderPhotoCardsList(cardsCol, questionData);
  },

  buildAnswerPayload(questionData, timedOut) {
    const orderedIds = state.albumShuffleState ? state.albumShuffleState.orderedPhotoIds || [] : [];
    const pinAssignments = state.albumShuffleState ? state.albumShuffleState.pinAssignments || {} : {};

    const answers = orderedIds.map((photoId, timelineIndex) => {
      return {
        photo_id: photoId,
        assigned_pin_id: pinAssignments[photoId] || null,
        assigned_timeline_index: timelineIndex,
      };
    });

    return {
      match_id: state.matchId,
      question_id: questionData.question_id,
      album_shuffle_answers: answers,
      timed_out: timedOut,
    };
  },

  renderReveal(revealUi, revealData) {
    renderShuffleReveal(revealUi, revealData);
  },
};

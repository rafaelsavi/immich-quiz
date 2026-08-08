import { t } from "../i18n.js";
import { state, el } from "../state.js";
import { createBaseTileLayers, addLayerControl, updateSubmitState, toggleMapFullscreen, fitMapToBounds } from "../maps.js";
import { renderGuessingModeSettings } from "./common.js";
import { playerBadge, playerNameCell, buildCell } from "../formatters.js";
import { animateScoreRollup, spawnFloatingScorePop, createPerfectBadge, launchGoldConfetti, launchStarBurst } from "../effects.js";
import { playChime } from "../audio.js";

let shuffleMap = null;
let revealShuffleMap = null;
let shuffleMarkers = {}; // pinId -> Leaflet marker

function createShuffleHelpModal() {
  let modal = document.getElementById("album-shuffle-help-modal");
  if (modal) return modal;

  modal = document.createElement("div");
  modal.id = "album-shuffle-help-modal";
  modal.className = "shuffle-help-modal hidden";
  modal.innerHTML = `
    <div class="shuffle-help-dialog" role="dialog" aria-modal="true" aria-labelledby="shuffle-help-title">
      <div class="shuffle-help-header">
        <h3 id="shuffle-help-title" data-i18n="game.shuffle_help_title">Album Shuffle Help</h3>
        <button type="button" class="shuffle-help-close" aria-label="Close help">×</button>
      </div>
      <div class="shuffle-help-body"></div>
    </div>
  `;

  document.body.appendChild(modal);

  const closeBtn = modal.querySelector(".shuffle-help-close");
  closeBtn.addEventListener("click", () => modal.classList.add("hidden"));

  modal.addEventListener("click", (event) => {
    if (event.target === modal) {
      modal.classList.add("hidden");
    }
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      modal.classList.add("hidden");
    }
  });

  return modal;
}

function openShuffleHelpModal(questionData) {
  const modal = createShuffleHelpModal();

  // Always update the title to the current language (modal is created lazily and
  // applyLanguage() may not have run since it was first inserted into the DOM).
  const titleEl = modal.querySelector("#shuffle-help-title");
  if (titleEl) titleEl.textContent = t("game.shuffle_help_title");

  const body = modal.querySelector(".shuffle-help-body");
  const locationMode = questionData?.location_mode !== false;
  const dateMode = questionData?.date_mode !== false;

  const sections = [];
  if (locationMode) {
    sections.push(`
      <div class="shuffle-help-section">
        <h4>${t("game.shuffle_help_location_title")}</h4>
        <ul>
          <li>${t("game.shuffle_help_location_item1")}</li>
          <li>${t("game.shuffle_help_location_item2")}</li>
          <li>${t("game.shuffle_help_location_item3")}</li>
          <li>${t("game.shuffle_help_location_item4")}</li>
        </ul>
      </div>
    `);
  }

  if (dateMode) {
    sections.push(`
      <div class="shuffle-help-section">
        <h4>${t("game.shuffle_help_date_title")}</h4>
        <ul>
          <li>${t("game.shuffle_help_date_item1")}</li>
          <li>${t("game.shuffle_help_date_item2")}</li>
          <li>${t("game.shuffle_help_date_item3")}</li>
        </ul>
      </div>
    `);
  }

  if (sections.length === 0) {
    sections.push(`
      <div class="shuffle-help-section">
        <p>${t("game.shuffle_help_fallback")}</p>
      </div>
    `);
  }

  body.innerHTML = `
    <p class="shuffle-help-intro">${t("game.shuffle_help_intro")}</p>
    ${sections.join("")}
    <p class="shuffle-help-footnote">${t("game.shuffle_help_footer")}</p>
  `;

  modal.classList.remove("hidden");
}

export const albumShuffleMode = {
  name: "album_shuffle",

  openHelp(questionData) {
    openShuffleHelpModal(questionData);
  },

  refreshHelpModal(questionData) {
    // If the help modal is currently visible, re-populate its body in the new language.
    const modal = document.getElementById("album-shuffle-help-modal");
    if (modal && !modal.classList.contains("hidden")) {
      openShuffleHelpModal(questionData);
    }
  },

  setDisabled(disabled) {
    state.albumShuffleDisabled = Boolean(disabled);
    const uiContainer = document.getElementById("album-shuffle-ui");
    if (uiContainer) {
      if (disabled) {
        uiContainer.classList.add("shuffle-disabled");
      } else {
        uiContainer.classList.remove("shuffle-disabled");
      }
    }
    const cardsCol = document.getElementById("shuffle-cards-list");
    if (cardsCol && state.currentQuestion) {
      renderPhotoCardsList(cardsCol, state.currentQuestion);
    }
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

  mount(hostEl, matchConfig) {
    this.hostEl = hostEl;
    const host = document.getElementById("mode-active-host") || hostEl;
    if (host) {
      host.replaceChildren();
      const tmpl = document.getElementById("tmpl-mode-album-shuffle");
      if (tmpl) {
        host.appendChild(tmpl.content.cloneNode(true));
      }
    }
    const uiContainer = document.getElementById("album-shuffle-ui");
    if (uiContainer) {
      uiContainer.classList.remove("hidden");
    }
  },

  unmount() {
    state.albumShuffleDisabled = false;
    if (shuffleMap) {
      shuffleMap.remove();
      shuffleMap = null;
    }
    if (revealShuffleMap) {
      revealShuffleMap.remove();
      revealShuffleMap = null;
    }
    shuffleMarkers = {};
    state.albumShuffleState = null;
    const host = document.getElementById("mode-active-host");
    if (host) {
      host.replaceChildren();
    }
    const shuffleReveal = document.getElementById("album-shuffle-reveal-ui");
    if (shuffleReveal) {
      shuffleReveal.classList.add("hidden");
      shuffleReveal.replaceChildren();
    }
  },

  onReady(questionData) { },

  renderQuestion(questionData) {
    state.albumShuffleDisabled = false;
    if (el.mediaFrame) el.mediaFrame.classList.add("hidden");

    let uiContainer = document.getElementById("album-shuffle-ui");
    if (!uiContainer) {
      uiContainer = document.createElement("div");
      uiContainer.id = "album-shuffle-ui";
      const host = this.hostEl || el.guessingUi;
      if (host) host.appendChild(uiContainer);
    }
    uiContainer.classList.remove("hidden");
    uiContainer.classList.remove("shuffle-disabled");
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
    mapFsBtn.title = t("game.fullscreen_map_title");
    mapFsBtn.textContent = t("game.fullscreen_btn");
    mapFsBtn.setAttribute("data-i18n", "game.fullscreen_btn");
    mapFsBtn.setAttribute("data-i18n-title", "game.fullscreen_map_title");
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
      renderShuffleMap(mapShell, questionData.batch_pins, questionData);
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

  renderReveal(revealUi, revealData, skipEffects = false) {
    const pinpointReveal = document.getElementById("pinpoint-reveal-ui");
    if (pinpointReveal) pinpointReveal.classList.add("hidden");

    let targetContainer = document.getElementById("album-shuffle-reveal-ui");
    if (!targetContainer) {
      targetContainer = document.createElement("div");
      targetContainer.id = "album-shuffle-reveal-ui";
      revealUi.appendChild(targetContainer);
    }
    targetContainer.classList.remove("hidden");
    if (!skipEffects) {
      targetContainer.replaceChildren();
    } else {
      targetContainer.replaceChildren();
    }
    revealUi.classList.remove("hidden");

    // Standardize Round Meta header banner (matching Pinpoint mode)
    if (el.roundMeta) {
      el.roundMeta.textContent = t("reveal.title", revealData.round_number, revealData.total_rounds);
    }

    const batchReveal = revealData.batch_reveal || [];
    const playerResults = revealData.results || [];
    const libraryName = revealData.library_name || (state.currentQuestion ? state.currentQuestion.library_name : "");
    const totalPhotos = batchReveal.length;

    // Sort batch items in TRUE chronological order (newest #1 to oldest #N)
    const sortedTrueBatch = [...batchReveal].sort((a, b) => {
      const dateA = a.actual_date ? new Date(a.actual_date).getTime() : 0;
      const dateB = b.actual_date ? new Date(b.actual_date).getTime() : 0;
      return dateB - dateA;
    });

    // Map photo_id to true rank index (0-based)
    const trueRankMap = {};
    sortedTrueBatch.forEach((item, trueRankIdx) => {
      trueRankMap[item.photo_id] = trueRankIdx;
    });

    // Compute player accuracy metrics
    const playerAccuracy = {};
    playerResults.forEach((pRes) => {
      const pGuesses = pRes.album_shuffle_guesses || [];
      let correctPins = 0;
      let correctRanks = 0;

      batchReveal.forEach((item) => {
        const pGuess = pGuesses.find((g) => g.photo_id === item.photo_id);
        if (pGuess) {
          if (pGuess.assigned_pin_id && String(pGuess.assigned_pin_id) === String(item.true_pin_id)) {
            correctPins++;
          }
          const trueRank = trueRankMap[item.photo_id];
          if (pGuess.assigned_timeline_index !== null && pGuess.assigned_timeline_index === trueRank) {
            correctRanks++;
          }
        }
      });

      playerAccuracy[pRes.player_name] = { correctPins, correctRanks };
    });

    // --- SECTION 1: POINT SCORING RESULTS TABLE (PINPOINT STYLE) ---
    const tableScroll = document.createElement("div");
    tableScroll.className = "table-scroll";
    const scoreTable = document.createElement("table");
    scoreTable.id = "reveal-table";
    const thead = document.createElement("thead");
    const tbody = document.createElement("tbody");
    scoreTable.append(thead, tbody);
    tableScroll.appendChild(scoreTable);

    // Build Table Headers
    const groups = [];
    if (revealData.location_mode) {
      groups.push({ label: t("reveal.col_location"), columns: [t("reveal.col_points"), t("reveal.col_pins_correct")] });
    }
    if (revealData.date_mode) {
      groups.push({ label: t("reveal.col_date"), columns: [t("reveal.col_points"), t("reveal.col_order_correct")] });
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
        if (index === 0) cell.className = "group-start";
        columnRow.appendChild(cell);
      });
    });
    thead.replaceChildren(groupRow, columnRow);

    // Build Table Body
    const maxPoints = revealData.score_max_points || state.scoreMaxPoints || 100;
    const maxRoundPoints = (revealData.location_mode ? maxPoints : 0) + (revealData.date_mode ? maxPoints : 0);
    const orderedResults = [...playerResults].sort((a, b) => (b.round_score ?? 0) - (a.round_score ?? 0));
    let hasAnyPerfectInRound = false;

    orderedResults.forEach((pRes, rIdx) => {
      const acc = playerAccuracy[pRes.player_name] || { correctPins: 0, correctRanks: 0 };
      const isPerfectLocation = revealData.location_mode && acc.correctPins === totalPhotos && totalPhotos > 0;
      const isPerfectDate = revealData.date_mode && acc.correctRanks === totalPhotos && totalPhotos > 0;
      const isPerfectRound = maxRoundPoints > 0 && pRes.round_score === maxRoundPoints;

      if (isPerfectLocation || isPerfectDate || isPerfectRound) {
        hasAnyPerfectInRound = true;
      }

      const row = document.createElement("tr");
      const pCell = buildCell();
      pCell.appendChild(playerNameCell(pRes.player_name, pRes.timed_out));
      row.appendChild(pCell);

      const valueGroups = [];
      if (revealData.location_mode) {
        valueGroups.push({
          isPerfect: isPerfectLocation,
          items: [
            pRes.location_score === null || pRes.location_score === undefined ? "-" : String(pRes.location_score),
            `${acc.correctPins} / ${totalPhotos}`,
          ],
        });
      }
      if (revealData.date_mode) {
        valueGroups.push({
          isPerfect: isPerfectDate,
          items: [
            pRes.date_score === null || pRes.date_score === undefined ? "-" : String(pRes.date_score),
            `${acc.correctRanks} / ${totalPhotos}`,
          ],
        });
      }
      valueGroups.push({
        isPerfect: isPerfectRound,
        isScoreGroup: true,
        roundScoreNum: pRes.round_score ?? 0,
        items: [String(pRes.round_score ?? 0), String(pRes.total_score ?? 0)],
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
            animateScoreRollup(cell, group.roundScoreNum, maxRoundPoints);
          }
          row.appendChild(cell);
        });
      });

      tbody.appendChild(row);

      if (!skipEffects) {
        setTimeout(() => {
          if (isPerfectLocation && isPerfectDate) {
            spawnFloatingScorePop(row, `🎯 PERFECT ROUND! +${pRes.round_score}`, "bullseye");
          } else if (isPerfectLocation) {
            spawnFloatingScorePop(row, `🎯 ALL PINS CORRECT! +${pRes.location_score}`, "bullseye");
          } else if (isPerfectDate) {
            spawnFloatingScorePop(row, `⏳ PERFECT ORDER! +${pRes.date_score}`, "perfect");
          } else if ((pRes.round_score ?? 0) > 0) {
            spawnFloatingScorePop(row, `+${pRes.round_score} pts`, "good");
          }
        }, rIdx * 250);
      }
    });

    // --- SECTION 2: MAP LAYOUT (ONLY IF LOCATION MODE IS ACTIVE) ---
    let mapHead = null;
    let mapShell = null;
    if (revealData.location_mode) {
      mapHead = document.createElement("div");
      mapHead.className = "field-head";
      mapHead.style.marginTop = "0.25rem";
      mapHead.innerHTML = `<label>${t("reveal.map_label")}</label>`;

      mapShell = document.createElement("div");
      mapShell.className = "map-shell";
      mapShell.id = "reveal-shuffle-map-shell";
      mapShell.style.height = "450px";

      const mapFsBtn = document.createElement("button");
      mapFsBtn.type = "button";
      mapFsBtn.className = "map-fullscreen-btn";
      mapFsBtn.setAttribute("aria-pressed", "false");
      mapFsBtn.title = t("game.fullscreen_map_title");
      mapFsBtn.textContent = t("game.fullscreen_btn");
      mapFsBtn.setAttribute("data-i18n", "game.fullscreen_btn");
      mapFsBtn.setAttribute("data-i18n-title", "game.fullscreen_map_title");
      mapFsBtn.addEventListener("click", () => toggleMapFullscreen(mapShell));
      mapShell.appendChild(mapFsBtn);
    }

    // --- SECTION 3: PHOTO BREAKDOWN VIEW ---
    const breakdownHead = document.createElement("div");
    breakdownHead.className = "field-head";
    breakdownHead.style.marginTop = "1.5rem";
    breakdownHead.innerHTML = `<label>${t("reveal.photo_breakdown_title")}</label>`;

    const breakdownContainer = document.createElement("div");
    breakdownContainer.className = "shuffle-breakdown-container";

    renderPhotoCardsView(breakdownContainer, sortedTrueBatch, playerResults, revealData, libraryName);

    // --- SECTION 4: NEXT ROUND BUTTON & ACTIONS ---
    const nextBtn = document.createElement("button");
    nextBtn.className = "next-round-btn btn-primary";
    nextBtn.style.marginTop = "1.5rem";
    nextBtn.textContent = revealData.match_finished ? t("reveal.see_results_btn") : t("reveal.next_round_btn");

    nextBtn.addEventListener("click", () => {
      if (window.handleNextRoundClick) {
        window.handleNextRoundClick(revealData.match_finished);
      } else if (el.nextRound) {
        el.nextRound.click();
      }
    });

    const actionsDiv = document.createElement("div");
    actionsDiv.className = "game-actions";
    actionsDiv.style.marginTop = "1rem";
    const restartBtn = document.createElement("button");
    restartBtn.type = "button";
    restartBtn.className = "btn-danger";
    restartBtn.textContent = t("game.restart_btn");
    restartBtn.addEventListener("click", () => {
      if (el.revealRestartBtn) el.revealRestartBtn.click();
    });
    const exitBtn = document.createElement("button");
    exitBtn.type = "button";
    exitBtn.className = "btn-danger";
    exitBtn.textContent = t("game.exit_btn");
    exitBtn.addEventListener("click", () => {
      if (el.revealExitBtn) el.revealExitBtn.click();
    });
    actionsDiv.append(restartBtn, exitBtn);

    tableScroll.style.marginTop = "1.5rem";

    // Append everything to targetContainer: Map (if active) -> Photo Breakdown -> Scoring Results Table -> Next Round Button -> Actions
    if (revealData.location_mode && mapHead && mapShell && !skipEffects) {
      targetContainer.append(mapHead, mapShell, breakdownHead, breakdownContainer, tableScroll, nextBtn, actionsDiv);
      renderBatchRevealMap(mapShell, batchReveal);
    } else if (revealData.location_mode && mapHead && mapShell && skipEffects) {
      targetContainer.append(mapHead, mapShell, breakdownHead, breakdownContainer, tableScroll, nextBtn, actionsDiv);
      // Do not re-initialize the map on a text-only refresh
    } else {
      targetContainer.append(breakdownHead, breakdownContainer, tableScroll, nextBtn, actionsDiv);
    }
  },

  refreshRevealText(revealUi, revealData) {
    // Re-render all reveal text without re-initializing the map or running animations.
    this.renderReveal(revealUi, revealData, true);
  },
};

let activeBreakdownViewMode = "photo";

const PIN_COLORS = {
  A: "#059669", 1: "#059669",
  B: "#d97706", 2: "#d97706",
  C: "#883aed", 3: "#883aed",
  D: "#db2777", 4: "#db2777",
  E: "#2563eb", 5: "#2563eb",
};

export function getPinColor(pinId) {
  if (!pinId) return "#0f7c7f";
  const rawColor = PIN_COLORS[pinId] || PIN_COLORS[String(pinId).toUpperCase()] || "#0f7c7f";
  if (typeof rawColor === "string" && rawColor.startsWith("#") && rawColor.length === 9) {
    return rawColor.slice(0, 7);
  }
  return rawColor;
}

function renderPhotoCardsView(container, sortedTrueBatch, playerResults, revealData, libraryName) {
  container.replaceChildren();
  const grid = document.createElement("div");
  grid.className = "shuffle-breakdown-grid";

  sortedTrueBatch.forEach((item, trueRankIdx) => {
    const imgUrl = `/api/media/${item.photo_id}?library_name=${encodeURIComponent(libraryName)}`;
    const dateStr = item.actual_date
      ? new Date(item.actual_date).toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" })
      : "Unknown date";

    const card = document.createElement("div");
    card.className = "shuffle-photo-card";

    const top = document.createElement("div");
    top.className = "shuffle-card-top";

    const thumbWrap = document.createElement("div");
    thumbWrap.className = "shuffle-card-thumb-wrap";
    const img = document.createElement("img");
    img.className = "shuffle-card-thumb-lg";
    img.src = imgUrl;
    img.alt = `Photo ${trueRankIdx + 1}`;
    img.addEventListener("click", () => openPhotoLightbox(imgUrl));
    thumbWrap.appendChild(img);

    const meta = document.createElement("div");
    meta.className = "shuffle-card-meta";

    const rankTag = document.createElement("div");
    rankTag.className = "shuffle-card-rank-tag";
    rankTag.textContent = `#${trueRankIdx + 1}`;

    const banner = document.createElement("div");
    banner.className = "true-val-banner";

    if (revealData.date_mode) {
      const datePill = document.createElement("span");
      datePill.className = "true-val-pill";
      datePill.textContent = `📅 ${dateStr}`;
      banner.appendChild(datePill);
    }
    if (revealData.location_mode) {
      const pinPill = document.createElement("span");
      pinPill.className = "true-val-pill";
      pinPill.innerHTML = `📍 Pin: <strong>${item.true_pin_id}</strong>`;
      banner.appendChild(pinPill);
    }

    meta.append(rankTag, banner);
    top.append(meta, thumbWrap);
    card.appendChild(top);

    const guessesList = document.createElement("div");
    guessesList.className = "shuffle-card-guesses";

    playerResults.forEach((pRes) => {
      const pRow = document.createElement("div");
      pRow.className = "player-guess-row";

      const pName = playerNameCell(pRes.player_name, pRes.timed_out);
      pRow.appendChild(pName);

      const chipsWrap = document.createElement("div");
      chipsWrap.className = "player-guess-chips";

      const pGuesses = pRes.album_shuffle_guesses || [];
      const pGuess = pGuesses.find((g) => g.photo_id === item.photo_id);

      if (revealData.location_mode) {
        const isPinCorrect = pGuess && String(pGuess.assigned_pin_id) === String(item.true_pin_id);
        const pinChip = document.createElement("span");
        pinChip.className = `guess-chip ${isPinCorrect ? "correct" : "incorrect"}`;

        const assignedPin = pGuess && pGuess.assigned_pin_id ? pGuess.assigned_pin_id : "None";

        if (isPinCorrect) {
          pinChip.innerHTML = `📍 Pin ${assignedPin} ✓`;
        } else {
          pinChip.innerHTML = `📍 ${assignedPin === "None" ? "None" : "Pin " + assignedPin} ✗`;
        }
        chipsWrap.appendChild(pinChip);
      }

      if (revealData.date_mode) {
        const pSubmittedRank = pGuess ? pGuess.assigned_timeline_index : null;
        const isRankCorrect = pSubmittedRank === trueRankIdx;
        const rankChip = document.createElement("span");
        rankChip.className = `guess-chip ${isRankCorrect ? "correct" : "incorrect"}`;

        const rankText = pSubmittedRank !== null && pSubmittedRank !== undefined ? `#${pSubmittedRank + 1}` : "None";

        if (isRankCorrect) {
          rankChip.textContent = `${rankText} ✓`;
        } else {
          rankChip.textContent = `${rankText} ✗`;
        }
        chipsWrap.appendChild(rankChip);
      }

      pRow.appendChild(chipsWrap);
      guessesList.appendChild(pRow);
    });

    card.appendChild(guessesList);
    grid.appendChild(card);
  });

  container.appendChild(grid);
}

function renderPhotoCardsList(containerEl, questionData, focusOptions = null) {
  containerEl.replaceChildren();

  const isDisabled = Boolean(state.timedOut || state.albumShuffleDisabled);
  const orderedIds = state.albumShuffleState ? state.albumShuffleState.orderedPhotoIds || [] : [];
  const selectedPhotoId = state.albumShuffleState ? state.albumShuffleState.selectedPhotoId : null;
  const pinAssignments = state.albumShuffleState ? state.albumShuffleState.pinAssignments || {} : {};
  const photosMap = {};
  (questionData.batch_photos || []).forEach((p) => {
    photosMap[p.photo_id] = p;
  });

  let elementToFocus = null;

  if (questionData.date_mode && orderedIds.length > 0) {
    const topHeader = document.createElement("div");
    topHeader.className = "shuffle-timeline-header newest";
    topHeader.innerHTML = `<span>⬆️ <span data-i18n="game.shuffle_newest">${t("game.shuffle_newest")}</span></span>`;
    containerEl.appendChild(topHeader);
  }

  orderedIds.forEach((photoId, index) => {
    const photo = photosMap[photoId];
    if (!photo) return;

    const assignedPin = questionData.location_mode ? pinAssignments[photoId] : null;
    const pinColor = assignedPin ? getPinColor(assignedPin) : null;
    const isSelected = selectedPhotoId === photoId;

    const card = document.createElement("div");
    card.className = `shuffle-card-row ${isSelected ? "selected" : ""} ${isDisabled ? "disabled" : ""} ${assignedPin ? "assigned" : ""}`;

    if (assignedPin && pinColor) {
      card.style.borderColor = pinColor;
      if (isSelected) {
        card.style.backgroundColor = `${pinColor}38`;
        card.style.boxShadow = `0 0 0 3.5px rgba(100, 116, 139, 0.35), 0 8px 20px rgba(0, 0, 0, 0.14)`;
        card.style.transform = "translateY(-2px) scale(1.015)";
      } else {
        card.style.backgroundColor = `${pinColor}24`;
        card.style.boxShadow = `0 2px 6px ${pinColor}33`;
        card.style.transform = "";
      }
    } else {
      card.style.borderColor = "";
      card.style.backgroundColor = "";
      card.style.boxShadow = "";
      card.style.transform = "";
    }

    card.addEventListener("click", () => {
      if (state.timedOut || state.submitting || state.albumShuffleDisabled) return;
      if (state.albumShuffleState) {
        state.albumShuffleState.selectedPhotoId = photoId;
        renderPhotoCardsList(containerEl, questionData);

        const assignedPin = state.albumShuffleState.pinAssignments
          ? state.albumShuffleState.pinAssignments[photoId]
          : null;
        highlightMapMarker(assignedPin || null);
      }
    });

    // Thumbnail
    const thumbWrap = document.createElement("div");
    thumbWrap.className = "shuffle-card-thumb-wrap";

    const img = document.createElement("img");
    img.className = "shuffle-card-thumb-lg";
    img.src = photo.media_url;
    img.alt = `Photo ${index + 1}`;

    const fsBtn = document.createElement("button");
    fsBtn.type = "button";
    fsBtn.className = "shuffle-card-fullscreen-btn";
    fsBtn.textContent = "🔍";
    fsBtn.title = t("game.view_fullscreen_photo");
    fsBtn.setAttribute("data-i18n-title", "game.view_fullscreen_photo");
    fsBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      openPhotoLightbox(photo.media_url);
    });

    thumbWrap.append(img, fsBtn);

    // Right Action Panel: Pin Badge + Rank Controls stacked vertically
    const rightActions = document.createElement("div");
    rightActions.className = "shuffle-card-actions";

    const pinBadgeWrap = document.createElement("div");
    pinBadgeWrap.className = "shuffle-card-details";

    if (questionData.location_mode) {
      const pinBadge = document.createElement("div");
      if (assignedPin && pinColor) {
        pinBadge.className = "shuffle-assigned-pin-badge assigned";
        pinBadge.textContent = `📍 ${assignedPin}`;
        pinBadge.style.backgroundColor = pinColor;
        pinBadge.style.color = "#ffffff";
        pinBadge.style.borderColor = pinColor;
      } else {
        pinBadge.className = "shuffle-assigned-pin-badge unassigned";
        pinBadge.textContent = "📍 -";
        pinBadge.style.backgroundColor = "";
        pinBadge.style.color = "";
        pinBadge.style.borderColor = "";
      }
      pinBadgeWrap.appendChild(pinBadge);
    } else {
      pinBadgeWrap.style.display = "none";
    }

    const rankControls = document.createElement("div");
    rankControls.className = "shuffle-rank-controls";

    if (!questionData.date_mode) {
      rankControls.style.display = "none";
    }

    const upBtn = document.createElement("button");
    upBtn.type = "button";
    upBtn.className = "shuffle-rank-btn";
    upBtn.textContent = "▲";
    upBtn.title = "Move Up (Newer)";
    upBtn.disabled = index === 0 || isDisabled;
    upBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      if (state.timedOut || state.submitting || state.albumShuffleDisabled) return;
      if (index > 0) {
        const temp = orderedIds[index - 1];
        orderedIds[index - 1] = orderedIds[index];
        orderedIds[index] = temp;
        renderPhotoCardsList(containerEl, questionData, { focusPhotoId: photoId, focusDirection: "up" });
      }
    });

    const downBtn = document.createElement("button");
    downBtn.type = "button";
    downBtn.className = "shuffle-rank-btn";
    downBtn.textContent = "▼";
    downBtn.title = "Move Down (Older)";
    downBtn.disabled = index === orderedIds.length - 1 || isDisabled;
    downBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      if (state.timedOut || state.submitting || state.albumShuffleDisabled) return;
      if (index < orderedIds.length - 1) {
        const temp = orderedIds[index + 1];
        orderedIds[index + 1] = orderedIds[index];
        orderedIds[index] = temp;
        renderPhotoCardsList(containerEl, questionData, { focusPhotoId: photoId, focusDirection: "down" });
      }
    });

    if (focusOptions && focusOptions.focusPhotoId === photoId) {
      if (focusOptions.focusDirection === "up") {
        elementToFocus = !upBtn.disabled ? upBtn : downBtn;
      } else if (focusOptions.focusDirection === "down") {
        elementToFocus = !downBtn.disabled ? downBtn : upBtn;
      } else {
        elementToFocus = card;
      }
    }

    rankControls.append(upBtn, downBtn);
    rightActions.append(pinBadgeWrap, rankControls);
    card.append(thumbWrap, rightActions);
    containerEl.appendChild(card);
  });

  if (questionData.date_mode && orderedIds.length > 0) {
    const bottomFooter = document.createElement("div");
    bottomFooter.className = "shuffle-timeline-header oldest";
    bottomFooter.innerHTML = `<span>⬇️ <span data-i18n="game.shuffle_oldest">${t("game.shuffle_oldest")}</span></span>`;
    containerEl.appendChild(bottomFooter);
  }

  if (questionData.location_mode && questionData.batch_pins) {
    updateShuffleMapMarkers(questionData.batch_pins);
  }

  updateSubmitState();

  if (elementToFocus) {
    elementToFocus.focus();
  }
}

function getPinMarkerDetails(pinId) {
  const pinAssignments = state.albumShuffleState ? state.albumShuffleState.pinAssignments || {} : {};
  const orderedIds = state.albumShuffleState ? state.albumShuffleState.orderedPhotoIds || [] : [];
  const assignedPhotoId = Object.keys(pinAssignments).find(
    (photoId) => pinAssignments[photoId] === pinId
  );

  return {
    isTaken: Boolean(assignedPhotoId && orderedIds.includes(assignedPhotoId)),
    badgeText: pinId,
    bgColor: getPinColor(pinId),
  };
}

function updateShuffleMapMarkers(pins) {
  if (!pins) return;
  pins.forEach((pin) => {
    const { badgeText, bgColor } = getPinMarkerDetails(pin.pin_id);
    const el = document.getElementById(`pin-marker-${pin.pin_id}`);
    if (el) {
      el.style.background = bgColor;
      el.textContent = badgeText;
    }
  });
}

function renderShuffleMap(containerEl, pins, questionData) {
  if (!window.L) return;
  if (shuffleMap) {
    shuffleMap.remove();
    shuffleMap = null;
  }
  shuffleMarkers = {};

  const mapShell = containerEl.id ? containerEl : document.getElementById("shuffle-map-shell");
  const base = createBaseTileLayers();
  const map = L.map(mapShell, { layers: [base.streets] }).setView([20, 0], 2);
  addLayerControl(map, base);

  shuffleMap = map;
  const bounds = L.latLngBounds();
  const pinAssignments = state.albumShuffleState ? state.albumShuffleState.pinAssignments || {} : {};

  // Group near-duplicate coordinates to apply a small visual offset if pins share exact locations
  const coordCounts = {};
  const processedPins = pins.map((pin) => {
    const key = `${pin.latitude.toFixed(4)},${pin.longitude.toFixed(4)}`;
    coordCounts[key] = (coordCounts[key] || 0) + 1;
    const occurrence = coordCounts[key];
    let displayLat = pin.latitude;
    let displayLon = pin.longitude;
    if (occurrence > 1) {
      const angle = (occurrence - 1) * ((2 * Math.PI) / 5);
      const radius = 0.00025 * Math.sqrt(occurrence);
      displayLat = pin.latitude + radius * Math.cos(angle);
      displayLon = pin.longitude + radius * Math.sin(angle);
    }
    return { ...pin, displayLat, displayLon };
  });

  processedPins.forEach((pin) => {
    const lat = pin.displayLat;
    const lon = pin.displayLon;
    bounds.extend([pin.latitude, pin.longitude]);

    const { badgeText, bgColor } = getPinMarkerDetails(pin.pin_id);

    const icon = L.divIcon({
      className: "custom-pin-icon",
      html: `<div id="pin-marker-${pin.pin_id}" style="background:${bgColor};color:#fff;width:36px;height:36px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-weight:bold;font-size:0.85rem;border:2px solid #fff;box-shadow:0 3px 8px rgba(0,0,0,0.35);transition:all 0.25s ease;">${badgeText}</div>`,
      iconSize: [36, 36],
      iconAnchor: [18, 18],
    });

    const marker = L.marker([lat, lon], { icon }).addTo(map);
    shuffleMarkers[pin.pin_id] = marker;

    marker.on("click", () => {
      if (state.timedOut || state.submitting || state.albumShuffleDisabled) return;
      const selectedId = state.albumShuffleState ? state.albumShuffleState.selectedPhotoId : null;
      if (selectedId) {
        Object.keys(pinAssignments).forEach((pid) => {
          if (pinAssignments[pid] === pin.pin_id) {
            pinAssignments[pid] = null;
          }
        });
        pinAssignments[selectedId] = pin.pin_id;
        updateShuffleMapMarkers(pins);
        const cardsList = document.getElementById("shuffle-cards-list");
        if (cardsList) {
          renderPhotoCardsList(cardsList, questionData);
        }
        highlightMapMarker(pin.pin_id);
      }
    });
  });

  if (pins.length > 0 && bounds.isValid()) {
    fitMapToBounds(map, bounds, { padding: [50, 50], maxZoom: 15 });
  }
}

function highlightMapMarker(pinId) {
  Object.keys(shuffleMarkers).forEach((pid) => {
    const el = document.getElementById(`pin-marker-${pid}`);
    if (el) {
      if (pinId && pid === pinId) {
        const pinColor = getPinColor(pid);
        el.style.transform = "scale(1.3)";
        el.style.boxShadow = `0 0 0 4px ${pinColor}80, 0 4px 12px rgba(0,0,0,0.4)`;
        el.style.borderColor = pinColor;
      } else {
        el.style.transform = "scale(1)";
        el.style.boxShadow = "0 3px 8px rgba(0,0,0,0.35)";
        el.style.borderColor = "#fff";
      }
    }
  });
}

function renderBatchRevealMap(containerEl, batchItems) {
  if (!window.L) return;
  if (revealShuffleMap) {
    revealShuffleMap.remove();
    revealShuffleMap = null;
  }

  const validItems = (batchItems || []).filter(
    (item) =>
      item.actual_latitude !== null &&
      item.actual_latitude !== undefined &&
      item.actual_longitude !== null &&
      item.actual_longitude !== undefined &&
      !(Math.abs(item.actual_latitude) < 1e-6 && Math.abs(item.actual_longitude) < 1e-6)
  );

  if (validItems.length === 0) {
    if (containerEl) containerEl.style.display = "none";
    const prev = containerEl ? containerEl.previousElementSibling : null;
    if (prev && prev.classList.contains("field-head")) {
      prev.style.display = "none";
    }
    return;
  }

  containerEl.style.display = "block";

  const base = createBaseTileLayers();
  const map = L.map(containerEl, { layers: [base.streets] }).setView([20, 0], 2);
  addLayerControl(map, base);

  revealShuffleMap = map;
  const bounds = L.latLngBounds();

  validItems.forEach((item) => {
    const lat = item.actual_latitude;
    const lon = item.actual_longitude;
    bounds.extend([lat, lon]);

    const pinColor = getPinColor(item.true_pin_id);
    const icon = L.divIcon({
      className: "custom-pin-icon",
      html: `<div style="background:${pinColor};color:#fff;width:36px;height:36px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-weight:bold;border:2px solid #fff;box-shadow:0 3px 8px rgba(0,0,0,0.35);">${item.true_pin_id}</div>`,
      iconSize: [36, 36],
      iconAnchor: [18, 18],
    });

    const dateStr = item.actual_date ? new Date(item.actual_date).toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" }) : "";
    L.marker([lat, lon], { icon })
      .bindPopup(`<b>${item.true_pin_id}</b><br>${dateStr}`)
      .addTo(map);
  });

  if (validItems.length > 0 && bounds.isValid()) {
    fitMapToBounds(map, bounds, { padding: [50, 50], maxZoom: 15 });
  }
}

export function getShuffleMaps() {
  return [shuffleMap, revealShuffleMap].filter(Boolean);
}

export function openPhotoLightbox(src) {
  let lightbox = document.getElementById("photo-lightbox");
  if (!lightbox) {
    lightbox = document.createElement("div");
    lightbox.id = "photo-lightbox";
    lightbox.className = "photo-lightbox-overlay";
    lightbox.innerHTML = `
      <div class="photo-lightbox-content">
        <button type="button" class="photo-lightbox-close" title="${t("game.close_btn")}" data-i18n-title="game.close_btn">&times;</button>
        <img id="photo-lightbox-img" src="" alt="${t("game.fullscreen_photo_alt")}" data-i18n-alt="game.fullscreen_photo_alt" />
      </div>
    `;
    document.body.appendChild(lightbox);

    const closeBtn = lightbox.querySelector(".photo-lightbox-close");
    closeBtn.addEventListener("click", () => lightbox.classList.remove("active"));
    lightbox.addEventListener("click", (e) => {
      if (e.target === lightbox) lightbox.classList.remove("active");
    });
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && lightbox.classList.contains("active")) {
        lightbox.classList.remove("active");
      }
    });
  }

  const imgEl = document.getElementById("photo-lightbox-img");
  if (imgEl) imgEl.src = src;
  lightbox.classList.add("active");
}

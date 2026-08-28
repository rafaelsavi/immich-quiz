import { t, formatDate } from "../i18n.js";
import { state, el } from "../state.js";
import { createStandardMap, createBadgePinIcon, updateSubmitState, toggleMapFullscreen, fitMapToBounds, createMapFullscreenButton, ensureMapFullscreenButton, applySpiderfy, unregisterActiveMap } from "../maps.js";
import { renderGuessingModeSettings } from "./common.js";
import { playerBadge, playerNameCell, buildCell, renderRoundMeta } from "../formatters.js";
import { animateScoreRollup, createPerfectBadge, launchGoldConfetti, launchStarBurst } from "../effects.js";
import { playChime } from "../audio.js";

let shuffleMap = null;
let revealShuffleMap = null;
let shuffleMarkers = {}; // pinId -> Leaflet marker
let spiderLines = {};    // pinId -> L.polyline connector line
let truePinCoords = {};  // pinId -> { lat, lng } original coordinates

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
        </ul>
      </div>
    `);
  }

  body.innerHTML = sections.join("");

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
    renderGuessingModeSettings(containerEl, "album_shuffle");
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
      game_mode: "album_shuffle",
      location_mode: locationMode,
      date_mode: dateMode,
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
      try { unregisterActiveMap(shuffleMap); shuffleMap.remove(); } catch (_) { }
      shuffleMap = null;
    }
    if (revealShuffleMap) {
      try { unregisterActiveMap(revealShuffleMap); revealShuffleMap.remove(); } catch (_) { }
      revealShuffleMap = null;
    }
    shuffleMarkers = {};
    spiderLines = {};
    truePinCoords = {};
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
      selectedPhotoId: questionData.location_mode ? (photos[0]?.photo_id || null) : null,
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
    const mapFsBtn = createMapFullscreenButton(mapShell);
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
      renderRoundMeta(el.roundMeta, {
        roundNum: revealData.round_number,
        totalRounds: revealData.total_rounds,
        isReveal: true,
      });
    }

    const batchReveal = revealData.batch_reveal || [];
    const playerResults = revealData.results || [];
    const totalPhotos = batchReveal.length;

    // Sort batch items in TRUE chronological order (earliest #1 to latest #N)
    const sortedTrueBatch = [...batchReveal].sort((a, b) => {
      const dateA = a.actual_date ? new Date(a.actual_date).getTime() : 0;
      const dateB = b.actual_date ? new Date(b.actual_date).getTime() : 0;
      return dateA - dateB;
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
      groups.push({
        label: t("reveal.col_location"),
        columns: [
          { label: t("reveal.col_points"), mobileLabel: t("reveal.col_location"), class: "" },
          { label: t("reveal.col_pins_correct"), class: "hide-on-mobile" },
        ],
      });
    }
    if (revealData.date_mode) {
      groups.push({
        label: t("reveal.col_date"),
        columns: [
          { label: t("reveal.col_points"), mobileLabel: t("reveal.col_date"), class: "" },
          { label: t("reveal.col_order_correct"), class: "hide-on-mobile" },
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
            {
              value: pRes.location_score === null || pRes.location_score === undefined ? "-" : String(pRes.location_score),
              scoreNum: pRes.location_score,
              isScore: pRes.location_score !== null && pRes.location_score !== undefined,
              maxScore: maxPoints,
              class: "",
            },
            {
              value: `${acc.correctPins} / ${totalPhotos}`,
              class: "hide-on-mobile",
            },
          ],
        });
      }
      if (revealData.date_mode) {
        valueGroups.push({
          isPerfect: isPerfectDate,
          items: [
            {
              value: pRes.date_score === null || pRes.date_score === undefined ? "-" : String(pRes.date_score),
              scoreNum: pRes.date_score,
              isScore: pRes.date_score !== null && pRes.date_score !== undefined,
              maxScore: maxPoints,
              class: "",
            },
            {
              value: `${acc.correctRanks} / ${totalPhotos}`,
              class: "hide-on-mobile",
            },
          ],
        });
      }
      valueGroups.push({
        isPerfect: isPerfectRound,
        items: [
          {
            value: String(pRes.round_score ?? 0),
            scoreNum: pRes.round_score ?? 0,
            isScore: true,
            maxScore: maxRoundPoints,
            class: "hide-on-mobile",
          },
          {
            value: String(pRes.total_score ?? 0),
            scoreNum: pRes.total_score ?? 0,
            startScore: Math.max(0, (pRes.total_score ?? 0) - (pRes.round_score ?? 0)),
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

      tbody.appendChild(row);
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
    }

    // --- SECTION 3: PHOTO BREAKDOWN VIEW ---
    const breakdownHead = document.createElement("div");
    breakdownHead.className = "field-head";
    breakdownHead.style.marginTop = "1.5rem";
    breakdownHead.innerHTML = `<label>${t("reveal.photo_breakdown_title")}</label>`;

    const breakdownContainer = document.createElement("div");
    breakdownContainer.className = "shuffle-breakdown-container";

    renderPhotoCardsView(breakdownContainer, sortedTrueBatch, playerResults, revealData);

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
    if (revealData.location_mode && mapHead && mapShell) {
      targetContainer.append(mapHead, mapShell, breakdownHead, breakdownContainer, tableScroll, nextBtn, actionsDiv);
      renderBatchRevealMap(mapShell, batchReveal);
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

function renderPhotoCardsView(container, sortedTrueBatch, playerResults, revealData) {
  container.replaceChildren();
  const grid = document.createElement("div");
  grid.className = "shuffle-breakdown-grid";

  sortedTrueBatch.forEach((item, trueRankIdx) => {
    const imgUrl = `/api/media/${item.photo_id}`;
    const dateStr = item.actual_date
      ? formatDate(item.actual_date, { year: "numeric", month: "short", day: "numeric" })
      : t("fmt.unknown_place");

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

    const dateTag = document.createElement("div");
    dateTag.className = "shuffle-card-date-tag";
    dateTag.textContent = `📅 ${dateStr}`;
    meta.appendChild(dateTag);

    top.append(meta, thumbWrap);
    card.appendChild(top);

    const guessesList = document.createElement("div");
    guessesList.className = "shuffle-card-guesses";

    // Integrated Correct Answer Row at the top of guesses breakdown
    const actualRow = document.createElement("div");
    actualRow.className = "player-guess-row true-val-row";

    const actualLabel = document.createElement("span");
    actualLabel.className = "player-cell actual-label-cell";

    const checkBadge = document.createElement("span");
    checkBadge.className = "legend-badge actual-badge";
    checkBadge.textContent = "✓";

    const labelText = document.createElement("strong");
    labelText.setAttribute("data-i18n", "reveal.correct_answer");
    labelText.textContent = t("reveal.correct_answer");

    actualLabel.append(checkBadge, labelText);
    actualRow.appendChild(actualLabel);

    const actualChipsWrap = document.createElement("div");
    actualChipsWrap.className = "player-guess-chips";

    if (revealData.date_mode) {
      const dateChip = document.createElement("span");
      dateChip.className = "guess-chip true-val-chip";
      dateChip.textContent = `📅 #${trueRankIdx + 1}`;
      actualChipsWrap.appendChild(dateChip);
    }

    if (revealData.location_mode) {
      const pinChip = document.createElement("span");
      pinChip.className = "guess-chip true-val-chip";
      pinChip.innerHTML = `📍 Pin <strong>${item.true_pin_id}</strong>`;
      actualChipsWrap.appendChild(pinChip);
    }

    actualRow.appendChild(actualChipsWrap);
    guessesList.appendChild(actualRow);

    playerResults.forEach((pRes) => {
      const pRow = document.createElement("div");
      pRow.className = "player-guess-row";

      const pName = playerNameCell(pRes.player_name, pRes.timed_out);
      pRow.appendChild(pName);

      const chipsWrap = document.createElement("div");
      chipsWrap.className = "player-guess-chips";

      const pGuesses = pRes.album_shuffle_guesses || [];
      const pGuess = pGuesses.find((g) => g.photo_id === item.photo_id);

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
    topHeader.className = "shuffle-timeline-header oldest";
    topHeader.innerHTML = `<span>⬆️ <span data-i18n="game.shuffle_oldest">${t("game.shuffle_oldest")}</span></span>`;
    containerEl.appendChild(topHeader);
  }

  orderedIds.forEach((photoId, index) => {
    const photo = photosMap[photoId];
    if (!photo) return;

    const assignedPin = questionData.location_mode ? pinAssignments[photoId] : null;
    const pinColor = assignedPin ? getPinColor(assignedPin) : null;
    const isSelectable = Boolean(questionData.location_mode);
    const isSelected = isSelectable && selectedPhotoId === photoId;

    const card = document.createElement("div");
    card.className = `shuffle-card-row ${isSelected ? "selected" : ""} ${isDisabled ? "disabled" : ""} ${assignedPin ? "assigned" : ""} ${isSelectable ? "selectable" : "not-selectable"}`;

    if (assignedPin && pinColor) {
      card.style.borderColor = pinColor;
      if (isSelected) {
        card.style.backgroundColor = `${pinColor}70`;
        card.style.boxShadow = `0 0 18px 4px ${pinColor}88, 0 6px 20px rgba(0, 0, 0, 0.14)`;
        card.style.transform = "translateY(-2px)";
        card.style.borderWidth = "4px";
      } else {
        card.style.backgroundColor = `${pinColor}30`;
        card.style.boxShadow = "none";
        card.style.transform = "";
        card.style.borderWidth = "2px";
      }
    } else {
      card.style.borderColor = "";
      card.style.backgroundColor = "";
      card.style.boxShadow = "";
      card.style.transform = "";
      card.style.borderWidth = "";
    }

    card.addEventListener("click", () => {
      if (state.timedOut || state.submitting || state.albumShuffleDisabled) return;
      if (!isSelectable) return;
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
    fsBtn.innerHTML = `<svg class="fs-icon" viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round">
      <polyline points="15 3 21 3 21 9"></polyline>
      <polyline points="9 21 3 21 3 15"></polyline>
      <line x1="21" y1="3" x2="14" y2="10"></line>
      <line x1="3" y1="21" x2="10" y2="14"></line>
    </svg>`;
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
    upBtn.title = "Move Up (Earlier)";
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
    downBtn.title = "Move Down (Later)";
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
    bottomFooter.className = "shuffle-timeline-header newest";
    bottomFooter.innerHTML = `<span>⬇️ <span data-i18n="game.shuffle_newest">${t("game.shuffle_newest")}</span></span>`;
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
    const { isTaken, badgeText, bgColor } = getPinMarkerDetails(pin.pin_id);
    const el = document.getElementById(`pin-marker-${pin.pin_id}`);
    if (el) {
      el.textContent = badgeText;

      if (isTaken) {
        el.classList.add("assigned");
        el.classList.remove("unassigned");
        el.style.background = bgColor;
        el.style.color = "#ffffff";
        el.style.borderColor = "#ffffff";
        el.style.opacity = "1";
        el.style.boxShadow = "0 3px 8px rgba(0,0,0,0.35)";
      } else {
        el.classList.add("unassigned");
        el.classList.remove("assigned");
        el.style.background = "#ffffff";
        el.style.color = bgColor;
        el.style.borderColor = bgColor;
        el.style.opacity = "1";
        el.style.boxShadow = "0 2px 6px rgba(0,0,0,0.2)";
      }
    }
  });
}

function renderShuffleMap(containerEl, pins, questionData) {
  if (!window.L) return;
  shuffleMarkers = {};

  const mapShell = containerEl.id ? containerEl : document.getElementById("shuffle-map-shell");
  const map = createStandardMap(mapShell, { existingMap: shuffleMap, titleKey: "game.fullscreen_map_title" });
  shuffleMap = map;

  if (!map) return;

  const bounds = L.latLngBounds();
  const pinAssignments = state.albumShuffleState ? state.albumShuffleState.pinAssignments || {} : {};

  // Store true coordinates and place markers at their true positions.
  // Visual separation of overlapping pins is handled dynamically by applySpiderfy().
  truePinCoords = {};
  pins.forEach((pin) => {
    const lat = pin.latitude;
    const lon = pin.longitude;
    truePinCoords[pin.pin_id] = { lat, lng: lon };
    bounds.extend([lat, lon]);

    const { isTaken, badgeText, bgColor } = getPinMarkerDetails(pin.pin_id);
    const icon = createBadgePinIcon(badgeText, bgColor, {
      id: `pin-marker-${pin.pin_id}`,
      isTaken,
      size: 36,
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

  // Register zoom-aware spiderfy: runs once after initial fit and on every zoom change.
  map.on("zoomend", () => applySpiderfy(map, truePinCoords, shuffleMarkers, spiderLines, getPinColor));
  if (pins.length > 0 && bounds.isValid()) {
    fitMapToBounds(map, bounds, { padding: [50, 50], maxZoom: 15 });
    map.once("moveend", () => applySpiderfy(map, truePinCoords, shuffleMarkers, spiderLines, getPinColor));
  }
}


function highlightMapMarker(pinId) {
  Object.keys(shuffleMarkers).forEach((pid) => {
    const el = document.getElementById(`pin-marker-${pid}`);
    if (el) {
      const pinColor = getPinColor(pid);
      const isSelected = Boolean(pinId && pid === pinId);
      const { isTaken } = getPinMarkerDetails(pid);

      el.style.transform = "scale(1)";

      if (isSelected) {
        el.classList.add("selected");
        el.style.opacity = "1";
        el.style.boxShadow = `0 0 0 3px #ffffff, 0 0 0 6px ${pinColor}, 0 4px 14px rgba(0,0,0,0.5)`;
        if (isTaken) {
          el.style.background = pinColor;
          el.style.color = "#ffffff";
          el.style.borderColor = "#ffffff";
        } else {
          el.style.background = "#ffffff";
          el.style.color = pinColor;
          el.style.borderColor = pinColor;
        }
        if (el.parentElement) {
          el.parentElement.style.zIndex = "1000";
        }
      } else {
        el.classList.remove("selected");
        if (el.parentElement) {
          el.parentElement.style.zIndex = "";
        }
        if (isTaken) {
          el.style.background = pinColor;
          el.style.color = "#ffffff";
          el.style.borderColor = "#ffffff";
          el.style.boxShadow = "0 3px 8px rgba(0,0,0,0.35)";
          el.style.opacity = "1";
        } else {
          el.style.background = "#ffffff";
          el.style.color = pinColor;
          el.style.borderColor = pinColor;
          el.style.boxShadow = "0 2px 6px rgba(0,0,0,0.2)";
          el.style.opacity = "1";
        }
      }
    }
  });
}

function renderBatchRevealMap(containerEl, batchItems) {
  if (!window.L) return;

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

  const map = createStandardMap(containerEl, { existingMap: revealShuffleMap, titleKey: "game.fullscreen_map_title" });
  revealShuffleMap = map;

  if (!map) return;

  const bounds = L.latLngBounds();

  // Local spiderfy state — scoped to this reveal instance.
  const revealTrueCoords = {};
  const revealMarkerByKey = {};
  const revealSpiderLines = {};

  validItems.forEach((item) => {
    const key = String(item.true_pin_id);
    const lat = item.actual_latitude;
    const lon = item.actual_longitude;
    bounds.extend([lat, lon]);
    revealTrueCoords[key] = { lat, lng: lon };

    const pinColor = getPinColor(item.true_pin_id);
    const icon = createBadgePinIcon(item.true_pin_id, pinColor, { isTaken: true, size: 36 });

    const dateStr = item.actual_date ? formatDate(item.actual_date, { year: "numeric", month: "short", day: "numeric" }) : "";
    const marker = L.marker([lat, lon], { icon })
      .bindPopup(`<b>${item.true_pin_id}</b><br>${dateStr}`)
      .addTo(map);
    revealMarkerByKey[key] = marker;
  });

  // Register zoom-aware spiderfy.
  map.on("zoomend", () =>
    applySpiderfy(map, revealTrueCoords, revealMarkerByKey, revealSpiderLines, getPinColor)
  );
  if (validItems.length > 0 && bounds.isValid()) {
    fitMapToBounds(map, bounds, { padding: [50, 50], maxZoom: 15 });
    map.once("moveend", () =>
      applySpiderfy(map, revealTrueCoords, revealMarkerByKey, revealSpiderLines, getPinColor)
    );
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

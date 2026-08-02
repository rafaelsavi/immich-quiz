import { t } from "../i18n.js";
import { state, el } from "../state.js";
import { createBaseTileLayers, addLayerControl, updateSubmitState, toggleMapFullscreen } from "../maps.js";
import { renderGuessingModeSettings } from "./common.js";
import { playerBadge, playerNameCell, buildCell } from "../formatters.js";
import { animateScoreRollup, spawnFloatingScorePop, createPerfectBadge, launchGoldConfetti, launchStarBurst } from "../effects.js";
import { playChime } from "../audio.js";

let shuffleMap = null;
let revealShuffleMap = null;
let shuffleMarkers = {}; // pinId -> Leaflet marker

export const albumShuffleMode = {
  name: "album_shuffle",

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
    const pinpointUi = document.getElementById("pinpoint-ui");
    if (pinpointUi) pinpointUi.classList.add("hidden");

    if (el.mediaFrame) el.mediaFrame.classList.add("hidden");

    let uiContainer = document.getElementById("album-shuffle-ui");
    if (!uiContainer) {
      uiContainer = document.createElement("div");
      uiContainer.id = "album-shuffle-ui";
      guessingUi.appendChild(uiContainer);
    }
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
    mapShell.style.height = "560px";

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

    boardEl.append(mapCol, cardsCol);
    uiContainer.appendChild(boardEl);

    renderShuffleMap(mapShell, questionData.batch_pins, questionData);
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
    revealUi.replaceChildren();
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
    });

    if (hasAnyPerfectInRound) {
      playChime();
      launchStarBurst();
      launchGoldConfetti();
    }

    // --- SECTION 2: MAP LAYOUT (WITH FULLSCREEN & MAP IMAGERY LAYER CONTROLS) ---
    const mapHead = document.createElement("div");
    mapHead.className = "field-head";
    mapHead.style.marginTop = "0.25rem";
    mapHead.innerHTML = `<label>${t("reveal.map_label")}</label>`;

    const mapShell = document.createElement("div");
    mapShell.className = "map-shell";
    mapShell.id = "reveal-shuffle-map-shell";
    mapShell.style.height = "450px";

    const mapFsBtn = document.createElement("button");
    mapFsBtn.type = "button";
    mapFsBtn.className = "map-fullscreen-btn";
    mapFsBtn.setAttribute("aria-pressed", "false");
    mapFsBtn.title = "Toggle fullscreen map";
    mapFsBtn.textContent = t("game.fullscreen_btn");
    mapFsBtn.addEventListener("click", () => toggleMapFullscreen(mapShell));
    mapShell.appendChild(mapFsBtn);

    // --- SECTION 3: PHOTO BREAKDOWN TABLE ---
    const breakdownHead = document.createElement("div");
    breakdownHead.className = "field-head";
    breakdownHead.style.marginTop = "1.5rem";
    breakdownHead.innerHTML = `<label>${t("reveal.photo_breakdown_title")}</label>`;

    const breakdownScroll = document.createElement("div");
    breakdownScroll.className = "table-scroll";
    const bdTable = document.createElement("table");
    bdTable.className = "shuffle-breakdown-table";

    const bdThead = document.createElement("thead");
    const bdTr = document.createElement("tr");
    const bdCols = [t("reveal.col_photo"), t("reveal.col_true_values"), t("reveal.col_player")];
    if (revealData.location_mode) bdCols.push(t("reveal.col_pin_guess"));
    if (revealData.date_mode) bdCols.push(t("reveal.col_rank_guess"));

    bdCols.forEach((colText) => {
      const th = document.createElement("th");
      th.textContent = colText;
      bdTr.appendChild(th);
    });
    bdThead.appendChild(bdTr);

    const bdTbody = document.createElement("tbody");

    sortedTrueBatch.forEach((item, trueRankIdx) => {
      const imgUrl = `/api/media/${item.photo_id}?library_name=${encodeURIComponent(libraryName)}`;
      const dateStr = item.actual_date
        ? new Date(item.actual_date).toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" })
        : "Unknown date";

      playerResults.forEach((pRes, pIdx) => {
        const tr = document.createElement("tr");

        // Photo Column (only on first player row for this photo, with rowSpan)
        if (pIdx === 0) {
          const photoTd = document.createElement("td");
          photoTd.rowSpan = playerResults.length;
          photoTd.style.verticalAlign = "middle";

          const photoWrap = document.createElement("div");
          photoWrap.className = "shuffle-photo-cell";

          const rankBadge = document.createElement("div");
          rankBadge.className = "shuffle-rank-badge";
          rankBadge.textContent = `#${trueRankIdx + 1}`;

          const thumbWrap = document.createElement("div");
          thumbWrap.className = "shuffle-card-thumb-wrap";
          const img = document.createElement("img");
          img.className = "shuffle-card-thumb-lg";
          img.src = imgUrl;
          img.alt = `Photo ${trueRankIdx + 1}`;
          img.addEventListener("click", () => openPhotoLightbox(imgUrl));
          thumbWrap.appendChild(img);

          photoWrap.append(rankBadge, thumbWrap);
          photoTd.appendChild(photoWrap);
          tr.appendChild(photoTd);

          // True Values Column (rowSpan)
          const trueTd = document.createElement("td");
          trueTd.rowSpan = playerResults.length;
          trueTd.style.verticalAlign = "middle";
          trueTd.innerHTML = `
            <div style="font-size:0.85rem; font-weight:600; color:var(--text-main);">
              ${revealData.date_mode ? `<div>📅 Date: ${dateStr}</div>` : ""}
              ${revealData.location_mode ? `<div>📍 Pin: <strong>${item.true_pin_id}</strong></div>` : ""}
            </div>
          `;
          tr.appendChild(trueTd);
        }

        // Player Column
        const pTd = document.createElement("td");
        pTd.style.verticalAlign = "middle";
        pTd.appendChild(playerNameCell(pRes.player_name, pRes.timed_out));
        tr.appendChild(pTd);

        const pGuesses = pRes.album_shuffle_guesses || [];
        const pGuess = pGuesses.find((g) => g.photo_id === item.photo_id);
        const isPinCorrect = pGuess && String(pGuess.assigned_pin_id) === String(item.true_pin_id);
        const pSubmittedRank = pGuess ? pGuess.assigned_timeline_index : null;
        const isRankCorrect = pSubmittedRank === trueRankIdx;

        // Pin Guess Column
        if (revealData.location_mode) {
          const pinTd = document.createElement("td");
          pinTd.style.verticalAlign = "middle";
          const pinBadgeText = pGuess && pGuess.assigned_pin_id ? `Pin ${pGuess.assigned_pin_id}` : "None";
          pinTd.innerHTML = `<span class="shuffle-badge-reveal ${isPinCorrect ? "correct" : "incorrect"}">${pinBadgeText} ${isPinCorrect ? "✓" : "✗"}</span>`;
          tr.appendChild(pinTd);
        }

        // Rank Guess Column
        if (revealData.date_mode) {
          const rankTd = document.createElement("td");
          rankTd.style.verticalAlign = "middle";
          const rankBadgeText = pSubmittedRank !== null && pSubmittedRank !== undefined ? `Rank #${pSubmittedRank + 1}` : "None";
          rankTd.innerHTML = `<span class="shuffle-badge-reveal ${isRankCorrect ? "correct" : "incorrect"}">${rankBadgeText} ${isRankCorrect ? "✓" : "✗"}</span>`;
          tr.appendChild(rankTd);
        }

        bdTbody.appendChild(tr);
      });
    });

    bdTable.append(bdThead, bdTbody);
    breakdownScroll.appendChild(bdTable);

    // --- SECTION 4: NEXT ROUND BUTTON & ACTIONS ---
    const nextBtn = document.createElement("button");
    nextBtn.id = "next-round";
    nextBtn.className = "btn-primary";
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

    // Append everything to revealUi: Map -> Photo Breakdown -> Scoring Results Table -> Next Round Button -> Actions
    revealUi.append(mapHead, mapShell, breakdownHead, breakdownScroll, tableScroll, nextBtn, actionsDiv);

    // Render Leaflet Map with tile imagery layers & controls
    renderBatchRevealMap(mapShell, batchReveal);
  },
};

function renderPhotoCardsList(containerEl, questionData) {
  containerEl.replaceChildren();

  // Informational Banner informing user of chronological sequence
  if (questionData.date_mode) {
    const totalCount = (questionData.batch_photos || []).length || 5;
    const infoBanner = document.createElement("div");
    infoBanner.className = "shuffle-info-banner";
    infoBanner.innerHTML = `<span>${t("game.shuffle_info_banner", totalCount)}</span>`;
    containerEl.appendChild(infoBanner);
  }

  const orderedIds = state.albumShuffleState ? state.albumShuffleState.orderedPhotoIds || [] : [];
  const selectedPhotoId = state.albumShuffleState ? state.albumShuffleState.selectedPhotoId : null;
  const pinAssignments = state.albumShuffleState ? state.albumShuffleState.pinAssignments || {} : {};
  const photosMap = {};
  (questionData.batch_photos || []).forEach((p) => {
    photosMap[p.photo_id] = p;
  });

  orderedIds.forEach((photoId, index) => {
    const photo = photosMap[photoId];
    if (!photo) return;

    const card = document.createElement("div");
    card.className = `shuffle-card-row ${selectedPhotoId === photoId ? "selected" : ""}`;

    card.addEventListener("click", () => {
      if (state.albumShuffleState) {
        state.albumShuffleState.selectedPhotoId = photoId;
        renderPhotoCardsList(containerEl, questionData);

        const assignedPin = state.albumShuffleState.pinAssignments
          ? state.albumShuffleState.pinAssignments[photoId]
          : null;
        highlightMapMarker(assignedPin || null);
      }
    });

    // Rank Badge
    const rankBadge = document.createElement("div");
    rankBadge.className = "shuffle-rank-badge";
    rankBadge.textContent = `#${index + 1}`;

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
    fsBtn.title = "View fullscreen photo";
    fsBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      openPhotoLightbox(photo.media_url);
    });

    thumbWrap.append(img, fsBtn);

    // Assigned Pin Badge Indicator
    const pinBadgeWrap = document.createElement("div");
    pinBadgeWrap.className = "shuffle-card-details";

    const assignedPin = pinAssignments[photoId];
    const pinBadge = document.createElement("div");
    pinBadge.className = `shuffle-assigned-pin-badge ${assignedPin ? "assigned" : "unassigned"}`;
    pinBadge.textContent = assignedPin ? `📍 Pin ${assignedPin}` : "📍";

    pinBadgeWrap.appendChild(pinBadge);

    // Compact Arrow Buttons
    const rankControls = document.createElement("div");
    rankControls.className = "shuffle-rank-controls";

    if (!questionData.date_mode) {
      rankControls.style.display = "none";
      rankBadge.style.display = "none";
    }

    const upBtn = document.createElement("button");
    upBtn.type = "button";
    upBtn.className = "shuffle-rank-btn";
    upBtn.textContent = "▲";
    upBtn.title = "Move Up (Newer)";
    upBtn.disabled = index === 0;
    upBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      if (index > 0) {
        const temp = orderedIds[index - 1];
        orderedIds[index - 1] = orderedIds[index];
        orderedIds[index] = temp;
        renderPhotoCardsList(containerEl, questionData);
      }
    });

    const downBtn = document.createElement("button");
    downBtn.type = "button";
    downBtn.className = "shuffle-rank-btn";
    downBtn.textContent = "▼";
    downBtn.title = "Move Down (Older)";
    downBtn.disabled = index === orderedIds.length - 1;
    downBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      if (index < orderedIds.length - 1) {
        const temp = orderedIds[index + 1];
        orderedIds[index + 1] = orderedIds[index];
        orderedIds[index] = temp;
        renderPhotoCardsList(containerEl, questionData);
      }
    });

    rankControls.append(upBtn, downBtn);

    card.append(rankBadge, thumbWrap, pinBadgeWrap, rankControls);
    containerEl.appendChild(card);
  });

  updateSubmitState();
}

function updateShuffleMapMarkers(pins) {
  const pinAssignments = state.albumShuffleState ? state.albumShuffleState.pinAssignments || {} : {};
  pins.forEach((pin) => {
    const isTaken = Object.values(pinAssignments).includes(pin.pin_id);
    const bgColor = isTaken ? "#f59f00" : "#0f7c7f";
    const badgeText = isTaken ? `${pin.pin_id} ✓` : pin.pin_id;
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

  pins.forEach((pin) => {
    const lat = pin.latitude;
    const lon = pin.longitude;
    bounds.extend([lat, lon]);

    const isTaken = Object.values(pinAssignments).includes(pin.pin_id);
    const bgColor = isTaken ? "#f59f00" : "#0f7c7f";
    const badgeText = isTaken ? `${pin.pin_id} ✓` : pin.pin_id;

    const icon = L.divIcon({
      className: "custom-pin-icon",
      html: `<div id="pin-marker-${pin.pin_id}" style="background:${bgColor};color:#fff;width:36px;height:36px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-weight:bold;font-size:0.9rem;border:2px solid #fff;box-shadow:0 3px 8px rgba(0,0,0,0.35);transition:all 0.25s ease;">${badgeText}</div>`,
      iconSize: [36, 36],
      iconAnchor: [18, 18],
    });

    const marker = L.marker([lat, lon], { icon }).addTo(map);
    shuffleMarkers[pin.pin_id] = marker;

    marker.on("click", () => {
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

  if (pins.length > 0) {
    map.fitBounds(bounds, { padding: [50, 50] });
  }

  setTimeout(() => map.invalidateSize(), 150);
}

function highlightMapMarker(pinId) {
  Object.keys(shuffleMarkers).forEach((pid) => {
    const el = document.getElementById(`pin-marker-${pid}`);
    if (el) {
      if (pinId && pid === pinId) {
        el.style.transform = "scale(1.3)";
        el.style.boxShadow = "0 0 0 4px rgba(245, 159, 0, 0.6), 0 4px 12px rgba(0,0,0,0.4)";
        el.style.borderColor = "#f59f00";
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

  const base = createBaseTileLayers();
  const map = L.map(containerEl, { layers: [base.streets] }).setView([20, 0], 2);
  addLayerControl(map, base);

  revealShuffleMap = map;
  const bounds = L.latLngBounds();

  batchItems.forEach((item) => {
    const lat = item.actual_latitude || 0.0;
    const lon = item.actual_longitude || 0.0;
    bounds.extend([lat, lon]);

    const icon = L.divIcon({
      className: "custom-pin-icon",
      html: `<div style="background:#0f7c7f;color:#fff;width:36px;height:36px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-weight:bold;border:2px solid #fff;box-shadow:0 3px 8px rgba(0,0,0,0.35);">📍 ${item.true_pin_id}</div>`,
      iconSize: [36, 36],
      iconAnchor: [18, 18],
    });

    const dateStr = item.actual_date ? new Date(item.actual_date).toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" }) : "";
    L.marker([lat, lon], { icon })
      .bindPopup(`<b>Pin ${item.true_pin_id}</b><br>${dateStr}`)
      .addTo(map);
  });

  if (batchItems.length > 0) {
    map.fitBounds(bounds, { padding: [50, 50] });
  }

  setTimeout(() => map.invalidateSize(), 150);
}

function openPhotoLightbox(src) {
  let lightbox = document.getElementById("photo-lightbox");
  if (!lightbox) {
    lightbox = document.createElement("div");
    lightbox.id = "photo-lightbox";
    lightbox.className = "photo-lightbox-overlay";
    lightbox.innerHTML = `
      <div class="photo-lightbox-content">
        <button type="button" class="photo-lightbox-close">&times;</button>
        <img id="photo-lightbox-img" src="" alt="Fullscreen photo" />
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

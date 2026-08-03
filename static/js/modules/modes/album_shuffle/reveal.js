import { t } from "../../i18n.js";
import { state, el } from "../../state.js";
import { toggleMapFullscreen } from "../../maps.js";
import { playerNameCell, buildCell } from "../../formatters.js";
import { animateScoreRollup, spawnFloatingScorePop, createPerfectBadge, launchGoldConfetti, launchStarBurst } from "../../effects.js";
import { playChime } from "../../audio.js";
import { openPhotoLightbox } from "../../components/lightbox.js";
import { renderBatchRevealMap } from "./map.js";

export function renderShuffleReveal(revealUi, revealData) {
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
    mapFsBtn.title = "Toggle fullscreen map";
    mapFsBtn.textContent = t("game.fullscreen_btn");
    mapFsBtn.addEventListener("click", () => toggleMapFullscreen(mapShell));
    mapShell.appendChild(mapFsBtn);
  }

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
        const pinBadgeText = pGuess && pGuess.assigned_pin_id ? `${pGuess.assigned_pin_id}` : "None";
        pinTd.innerHTML = `<span class="shuffle-badge-reveal ${isPinCorrect ? "correct" : "incorrect"}">${pinBadgeText} ${isPinCorrect ? "✓" : "✗"}</span>`;
        tr.appendChild(pinTd);
      }

      // Rank Guess Column
      if (revealData.date_mode) {
        const rankTd = document.createElement("td");
        rankTd.style.verticalAlign = "middle";
        const rankBadgeText = pSubmittedRank !== null && pSubmittedRank !== undefined ? `#${pSubmittedRank + 1}` : "None";
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

  // Append everything to revealUi: Map (if active) -> Photo Breakdown -> Scoring Results Table -> Next Round Button -> Actions
  if (revealData.location_mode && mapHead && mapShell) {
    revealUi.append(mapHead, mapShell, breakdownHead, breakdownScroll, tableScroll, nextBtn, actionsDiv);
    renderBatchRevealMap(mapShell, batchReveal);
  } else {
    revealUi.append(breakdownHead, breakdownScroll, tableScroll, nextBtn, actionsDiv);
  }
}

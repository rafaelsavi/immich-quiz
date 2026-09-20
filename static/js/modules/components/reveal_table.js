/**
 * Reveal Table Reusable Component.
 *
 * Renders the standardized 2-tier grouped header reveal table for round breakdowns
 * across Pinpoint Reveal, Album Shuffle Reveal, and Match Replay.
 */

import { t } from "../i18n.js";
import { buildCell, playerNameCell, formatDistance, formatMonth, formatMonthError, formatRankBadge } from "../formatters.js";
import { animateScoreRollup, createPerfectBadge } from "../effects.js";

/**
 * Builds and mounts the 2-tier grouped headers into tableEl's <thead>.
 *
 * @param {HTMLTableElement} tableEl
 * @param {object} options
 * @param {boolean} options.locationMode
 * @param {boolean} options.dateMode
 * @param {string} [options.gameMode] - "pinpoint" or "unshuffle"
 * @param {boolean} [options.showRank=false] - If true, adds a Rank column (for multiplayer replay)
 */
export function renderRevealTableHeaders(tableEl, { locationMode = true, dateMode = true, gameMode = "pinpoint", showRank = false } = {}) {
  if (!tableEl) return;
  const thead = tableEl.querySelector("thead");
  if (!thead) return;

  const isShuffle = gameMode === "unshuffle";
  const groups = [];

  if (locationMode) {
    if (isShuffle) {
      groups.push({
        key: "reveal.col_location",
        label: t("reveal.col_location"),
        columns: [
          { key: "reveal.col_points", mobileKey: "reveal.col_location", label: t("reveal.col_points"), mobileLabel: t("reveal.col_location"), class: "" },
          { key: "reveal.col_pins_correct", label: t("reveal.col_pins_correct"), class: "hide-on-mobile" },
        ],
      });
    } else {
      groups.push({
        key: "reveal.col_location",
        label: t("reveal.col_location"),
        columns: [
          { key: "reveal.col_points", mobileKey: "reveal.col_location", label: t("reveal.col_points"), mobileLabel: t("reveal.col_location"), class: "" },
          { key: "reveal.col_distance_error", label: t("reveal.col_distance_error"), class: "hide-on-mobile" },
        ],
      });
    }
  }

  if (dateMode) {
    if (isShuffle) {
      groups.push({
        key: "reveal.col_date",
        label: t("reveal.col_date"),
        columns: [
          { key: "reveal.col_points", mobileKey: "reveal.col_date", label: t("reveal.col_points"), mobileLabel: t("reveal.col_date"), class: "" },
          { key: "reveal.col_order_correct", label: t("reveal.col_order_correct"), class: "hide-on-mobile" },
        ],
      });
    } else {
      groups.push({
        key: "reveal.col_date",
        label: t("reveal.col_date"),
        columns: [
          { key: "reveal.col_points", mobileKey: "reveal.col_date", label: t("reveal.col_points"), mobileLabel: t("reveal.col_date"), class: "" },
          { key: "reveal.col_guessed", label: t("reveal.col_guessed"), class: "hide-on-mobile" },
          { key: "reveal.col_date_error", label: t("reveal.col_date_error"), class: "hide-on-mobile" },
        ],
      });
    }
  }

  groups.push({
    key: "reveal.col_score",
    label: t("reveal.col_score"),
    columns: [
      { key: "reveal.col_round", label: t("reveal.col_round"), class: "hide-on-mobile" },
      { key: "reveal.col_total", mobileKey: "reveal.col_score", label: t("reveal.col_total"), mobileLabel: t("reveal.col_score"), class: "group-start-mobile" },
    ],
  });

  const groupRow = document.createElement("tr");
  groupRow.className = "group-head-row";

  if (showRank) {
    const rankHead = buildCell("#", true);
    rankHead.className = "col-rank-cell";
    rankHead.rowSpan = 2;
    groupRow.appendChild(rankHead);
  }

  const playerHead = buildCell(t("reveal.col_player"), true);
  playerHead.setAttribute("data-i18n", "reveal.col_player");
  playerHead.rowSpan = 2;
  groupRow.appendChild(playerHead);

  groups.forEach((group) => {
    const cell = buildCell(group.label, true);
    if (group.key) cell.setAttribute("data-i18n", group.key);
    cell.colSpan = group.columns.length;
    cell.className = "group-head group-start";
    groupRow.appendChild(cell);
  });

  const columnRow = document.createElement("tr");
  columnRow.className = "column-head-row";

  if (showRank) {
    const rankSubHead = buildCell("#", true);
    rankSubHead.className = "col-rank-cell hide-on-desktop";
    columnRow.appendChild(rankSubHead);
  }

  const playerSubHead = buildCell(t("reveal.col_player"), true);
  playerSubHead.setAttribute("data-i18n", "reveal.col_player");
  playerSubHead.className = "player-subhead hide-on-desktop";
  columnRow.appendChild(playerSubHead);

  groups.forEach((group) => {
    group.columns.forEach((col, index) => {
      const cell = buildCell("", true);
      const labelSpan = document.createElement("span");
      labelSpan.className = "desktop-head-label";
      if (col.key) labelSpan.setAttribute("data-i18n", col.key);
      labelSpan.textContent = col.label;
      cell.appendChild(labelSpan);

      if (col.mobileLabel) {
        cell.setAttribute("data-mobile-label", col.mobileLabel);
        if (col.mobileKey) cell.setAttribute("data-mobile-key", col.mobileKey);
      }

      const classes = [];
      if (index === 0) classes.push("group-start");
      if (col.class) classes.push(col.class);
      if (classes.length > 0) cell.className = classes.join(" ");
      columnRow.appendChild(cell);
    });
  });

  thead.replaceChildren(groupRow, columnRow);
}

/**
 * Builds and mounts rows into tableEl's <tbody>.
 *
 * @param {HTMLTableElement} tableEl
 * @param {Array<object>} results - Array of player result objects
 * @param {object} options
 * @param {boolean} options.locationMode
 * @param {boolean} options.dateMode
 * @param {string} [options.gameMode="pinpoint"]
 * @param {number} [options.maxPoints=100]
 * @param {boolean} [options.skipEffects=false]
 * @param {boolean} [options.showRank=false]
 * @param {number} [options.totalPhotos=1]
 * @param {object} [options.playerAccuracy=null] - Accuracy map for shuffle mode
 * @returns {boolean} Whether any player achieved a perfect round
 */
export function renderRevealTableRows(tableEl, results, {
  locationMode = true,
  dateMode = true,
  gameMode = "pinpoint",
  maxPoints = 100,
  skipEffects = false,
  showRank = false,
  totalPhotos = 1,
  playerAccuracy = null,
} = {}) {
  if (!tableEl) return false;
  const tbody = tableEl.querySelector("tbody");
  if (!tbody) return false;

  tbody.replaceChildren();

  const isShuffle = gameMode === "unshuffle";
  const maxRoundPoints = (locationMode ? maxPoints : 0) + (dateMode ? maxPoints : 0);
  let hasAnyPerfectInRound = false;

  const sortedResults = [...(results || [])].sort((a, b) => {
    // Sort primarily by cumulative score descending if available, else round score
    const scoreA = a.cumulative_score ?? a.total_score ?? a.round_score ?? 0;
    const scoreB = b.cumulative_score ?? b.total_score ?? b.round_score ?? 0;
    if (scoreB !== scoreA) return scoreB - scoreA;
    return (b.round_score ?? 0) - (a.round_score ?? 0);
  });

  const isMultiplayer = sortedResults.length > 1;

  sortedResults.forEach((result, idx) => {
    const rank = idx + 1;
    const p = result.pinpoint || result;
    const acc = (playerAccuracy && playerAccuracy[result.player_name]) || { correctPins: 0, correctRanks: 0 };

    let isPerfectLocation = false;
    let isPerfectDate = false;

    if (isShuffle) {
      isPerfectLocation = locationMode && acc.correctPins === totalPhotos && totalPhotos > 0;
      isPerfectDate = dateMode && acc.correctRanks === totalPhotos && totalPhotos > 0;
    } else {
      isPerfectLocation = locationMode && (result.location_score === maxPoints || p.distance_km === 0);
      isPerfectDate = dateMode && (result.date_score === maxPoints || p.date_diff_days === 0);
    }

    const isPerfectRound = maxRoundPoints > 0 && result.round_score === maxRoundPoints;
    const isPerfectPlayer = isPerfectLocation || isPerfectDate || isPerfectRound;

    if (isPerfectPlayer) {
      hasAnyPerfectInRound = true;
    }

    const row = document.createElement("tr");
    if (isPerfectPlayer) {
      row.className = "is-perfect-row";
    }

    if (showRank) {
      const rankCell = buildCell();
      rankCell.className = "col-rank-cell";
      if (isMultiplayer) {
        rankCell.innerHTML = formatRankBadge(rank, { showNumber: true });
      }
      row.appendChild(rankCell);
    }

    const nameCell = playerNameCell(result.player_name, result.timed_out);
    row.appendChild(buildCell(nameCell));

    const valueGroups = [];

    if (locationMode) {
      if (isShuffle) {
        valueGroups.push({
          isPerfect: isPerfectLocation,
          items: [
            {
              value: result.location_score === null || result.location_score === undefined ? "-" : String(result.location_score),
              scoreNum: result.location_score,
              isScore: result.location_score !== null && result.location_score !== undefined,
              maxScore: maxPoints,
              class: "",
            },
            {
              value: `${acc.correctPins} / ${totalPhotos}`,
              class: "hide-on-mobile",
            },
          ],
        });
      } else {
        const distStr = p.guessed_latitude === null || p.guessed_latitude === undefined
          ? (p.distance_km != null ? formatDistance(p.distance_km) : t("fmt.no_guess"))
          : formatDistance(p.distance_km);

        valueGroups.push({
          isPerfect: isPerfectLocation,
          items: [
            {
              value: result.location_score === null || result.location_score === undefined ? (result.round_score != null && !dateMode ? String(result.round_score) : "-") : String(result.location_score),
              scoreNum: result.location_score ?? (dateMode ? 0 : result.round_score),
              isScore: (result.location_score != null) || (!dateMode && result.round_score != null),
              maxScore: maxPoints,
              subtext: distStr !== t("fmt.no_guess") ? distStr : null,
              class: "",
            },
            {
              value: distStr,
              class: "hide-on-mobile",
            },
          ],
        });
      }
    }

    if (dateMode) {
      if (isShuffle) {
        valueGroups.push({
          isPerfect: isPerfectDate,
          items: [
            {
              value: result.date_score === null || result.date_score === undefined ? "-" : String(result.date_score),
              scoreNum: result.date_score,
              isScore: result.date_score !== null && result.date_score !== undefined,
              maxScore: maxPoints,
              class: "",
            },
            {
              value: `${acc.correctRanks} / ${totalPhotos}`,
              class: "hide-on-mobile",
            },
          ],
        });
      } else {
        const dateErrStr = formatMonthError(result);
        const guessedDateStr = p.guessed_year && p.guessed_month ? formatMonth(p.guessed_year, p.guessed_month) : "-";

        valueGroups.push({
          isPerfect: isPerfectDate,
          items: [
            {
              value: result.date_score === null || result.date_score === undefined ? (result.round_score != null && !locationMode ? String(result.round_score) : "-") : String(result.date_score),
              scoreNum: result.date_score ?? (locationMode ? 0 : result.round_score),
              isScore: (result.date_score != null) || (!locationMode && result.round_score != null),
              maxScore: maxPoints,
              subtext: dateErrStr !== "-" ? dateErrStr : null,
              class: "",
            },
            {
              value: guessedDateStr,
              class: "hide-on-mobile",
            },
            {
              value: dateErrStr,
              class: "hide-on-mobile",
            },
          ],
        });
      }
    }

    const totalScoreVal = result.total_score ?? result.cumulative_score ?? result.round_score ?? 0;
    const roundScoreVal = result.round_score ?? 0;

    valueGroups.push({
      isPerfect: isPerfectRound,
      items: [
        {
          value: String(roundScoreVal),
          scoreNum: roundScoreVal,
          isScore: true,
          maxScore: maxRoundPoints,
          class: "hide-on-mobile",
        },
        {
          value: String(totalScoreVal),
          scoreNum: totalScoreVal,
          startScore: Math.max(0, totalScoreVal - roundScoreVal),
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
        if (itemObj.isScore && !skipEffects) {
          animateScoreRollup(cell, itemObj.scoreNum, itemObj.maxScore, "", skipEffects, itemObj.startScore || 0);
        }
        row.appendChild(cell);
      });
    });

    tbody.appendChild(row);
  });

  return hasAnyPerfectInRound;
}

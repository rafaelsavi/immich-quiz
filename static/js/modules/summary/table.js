import { el } from "../state.js";
import { t } from "../i18n.js";
import {
  createRankBadge,
  formatRankBadge,
  formatPlayerCellHtml,
  formatRoundsBadge,
  escapeHtml,
  playerColor,
} from "../formatters.js";
import { animateScoreRollup } from "../effects.js";
import { renderMatchMeta } from "../components/match_meta.js";

export function renderSummaryMeta(summary) {
  if (!el.summaryMeta || !summary) return;
  const container = el.summaryMetaItems || el.summaryMeta;
  renderMatchMeta(container, summary);
}

export function renderSummaryTable(summary, perfectCounts = {}, { currentSessionPlayerName = null } = {}) {
  if (!summary) return;

  renderSummaryMeta(summary);

  const isChallenge = Boolean(
    summary.is_challenge ||
    summary.play_mode === "challenge" ||
    summary.challenge_id
  );

  const columns = [
    { key: "rank", label: t("summary.col_rank"), className: "col-rank" },
    { key: "player", label: t("summary.col_player"), className: "col-player" },
  ];

  if (isChallenge) {
    columns.push({ key: "rounds", label: t("summary.col_rounds"), className: "col-rounds text-center" });
  }
  if (summary.location_mode !== false) {
    columns.push({ key: "location", label: t("summary.col_location"), className: "col-score text-right" });
  }
  if (summary.date_mode !== false) {
    columns.push({ key: "date", label: t("summary.col_date"), className: "col-score text-right" });
  }
  columns.push(
    { key: "total", label: t("summary.col_total"), className: "col-score text-right" },
    { key: "accuracy", label: t("summary.col_accuracy"), className: "col-acc text-right hide-on-mobile" }
  );

  if (el.summaryTableHead) {
    const headRow = document.createElement("tr");
    columns.forEach((col) => {
      const th = document.createElement("th");
      th.className = col.className;
      th.textContent = col.label;
      headRow.appendChild(th);
    });
    el.summaryTableHead.replaceChildren(headRow);
  }

  if (el.summaryTableBody) {
    el.summaryTableBody.replaceChildren();

    const activeGoalCount = (summary.location_mode !== false ? 1 : 0) + (summary.date_mode !== false ? 1 : 0);
    const totalRoundsCount = summary.total_rounds || summary.rounds_played || 1;
    const maxGoalScore = activeGoalCount > 0
      ? Math.round((summary.max_possible_score || (totalRoundsCount * 100 * activeGoalCount)) / activeGoalCount)
      : (summary.max_possible_score || 100);

    const isMultiplayer = (summary.players || []).length > 1;

    (summary.players || []).forEach((player) => {
      const row = document.createElement("tr");
      const isWinner = isMultiplayer && (player.rank === 1 || player.is_winner);
      const isCurrent = Boolean(
        currentSessionPlayerName && player.player_name === currentSessionPlayerName
      );

      row.setAttribute("data-player-name", player.player_name);
      row.setAttribute("data-total-score", String(player.total_score ?? 0));

      if (isWinner) row.classList.add("winner-row");
      if (isCurrent) row.classList.add("highlight-player-row");

      // 1. Rank Cell
      const rankTd = document.createElement("td");
      rankTd.className = "col-rank";
      rankTd.innerHTML = formatRankBadge(player.rank, { showNumber: true });
      row.appendChild(rankTd);

      // 2. Player Cell
      const playerTd = document.createElement("td");
      playerTd.className = "col-player";
      let cellHtml = formatPlayerCellHtml(player.player_name, { isWinner, isCurrent });
      const count = perfectCounts[player.player_name] ?? 0;
      if (count > 0) {
        cellHtml += ` <span class="perfect-count-badge">${escapeHtml(t("fmt.perfect_count", count))}</span>`;
      }
      playerTd.innerHTML = cellHtml;
      row.appendChild(playerTd);

      // 3. Challenge Rounds Badge (if challenge mode)
      if (isChallenge) {
        const roundsTd = document.createElement("td");
        roundsTd.className = "col-rounds text-center";
        const completedRounds = player.completed_rounds != null ? player.completed_rounds : totalRoundsCount;
        const isFin = Boolean(player.is_finished || completedRounds >= totalRoundsCount);
        roundsTd.innerHTML = formatRoundsBadge(completedRounds, totalRoundsCount, isFin);
        row.appendChild(roundsTd);
      }

      // 4. Location Score
      if (summary.location_mode !== false) {
        const locCell = document.createElement("td");
        locCell.className = "col-score text-right";
        if (player.location_score != null) {
          animateScoreRollup(locCell, player.location_score ?? 0, maxGoalScore);
        } else {
          locCell.textContent = "—";
        }
        row.appendChild(locCell);
      }

      // 5. Date Score
      if (summary.date_mode !== false) {
        const dateCell = document.createElement("td");
        dateCell.className = "col-score text-right";
        if (player.date_score != null) {
          animateScoreRollup(dateCell, player.date_score ?? 0, maxGoalScore);
        } else {
          dateCell.textContent = "—";
        }
        row.appendChild(dateCell);
      }

      // 6. Total Score
      const totalTd = document.createElement("td");
      totalTd.className = "col-score col-total-score text-right font-bold";
      const totalVal = player.total_score ?? 0;
      if (isChallenge) {
        totalTd.textContent = String(totalVal);
        animateScoreRollup(totalTd, totalVal, totalVal * 1.5, "", false, 0);
      } else {
        totalTd.textContent = `${totalVal}/${player.max_possible_score ?? 100}`;
        animateScoreRollup(totalTd, totalVal, player.max_possible_score ?? 100, `/${player.max_possible_score ?? 100}`);
      }
      row.appendChild(totalTd);

      // 7. Accuracy
      const accTd = document.createElement("td");
      accTd.className = "col-acc text-right hide-on-mobile";
      const accVal = player.accuracy_pct != null
        ? player.accuracy_pct
        : (player.accuracy_percentage != null ? Math.round(player.accuracy_percentage) : 0);
      accTd.textContent = `${accVal}%`;
      row.appendChild(accTd);

      el.summaryTableBody.appendChild(row);
    });
  }
}

/**
 * Flash table rows and rollup scores when live updates arrive from polling.
 * @param {Array<object>} updatedPlayers
 */
export function flashUpdatedSummaryRows(updatedPlayers) {
  if (!el.summaryTableBody || !updatedPlayers || updatedPlayers.length === 0) return;
  const updatedNames = new Set(updatedPlayers.map((p) => p.player_name));

  Array.from(el.summaryTableBody.querySelectorAll("tr[data-player-name]")).forEach((tr) => {
    const name = tr.getAttribute("data-player-name");
    if (updatedNames.has(name)) {
      const color = playerColor(name);
      tr.classList.remove("row-arrival-flash");
      tr.style.setProperty("--player-accent", color);
      tr.style.setProperty("--player-accent-alpha", `${color}33`);
      void tr.offsetWidth;
      tr.classList.add("row-arrival-flash");

      const totalScoreCell = tr.querySelector(".col-total-score");
      const targetScore = Number(tr.getAttribute("data-total-score") || 0);
      if (totalScoreCell && !isNaN(targetScore)) {
        animateScoreRollup(totalScoreCell, targetScore, targetScore * 1.5, "", false, 0);
      }
    }
  });
}

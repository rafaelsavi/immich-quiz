import { el } from "../state.js";
import { t } from "../i18n.js";
import { buildCell, playerNameCell, createRankBadge } from "../formatters.js";
import { animateScoreRollup } from "../effects.js";

import { renderMatchMeta } from "../components/match_meta.js";

export function renderSummaryMeta(summary) {
  if (!el.summaryMeta || !summary) return;
  renderMatchMeta(el.summaryMeta, summary);
}

export function renderSummaryTable(summary, perfectCounts = {}) {
  if (!summary) return;

  renderSummaryMeta(summary);

  const columns = [t("summary.col_rank"), t("summary.col_player")];
  if (summary.location_mode) {
    columns.push(t("summary.col_location"));
  }
  if (summary.date_mode) {
    columns.push(t("summary.col_date"));
  }
  columns.push(t("summary.col_total"), t("summary.col_accuracy"));

  if (el.summaryTableHead) {
    const headRow = document.createElement("tr");
    columns.forEach((label) => {
      const cell = buildCell(label, true);
      if (label === t("summary.col_rank")) {
        cell.className = "col-rank";
      } else if (label === t("summary.col_player")) {
        cell.className = "col-player";
      } else if (label === t("summary.col_accuracy")) {
        cell.className = "col-accuracy hide-on-mobile";
      } else if (label === t("summary.col_total")) {
        cell.className = "col-score";
      }
      headRow.appendChild(cell);
    });
    el.summaryTableHead.replaceChildren(headRow);
  }

  if (el.summaryTableBody) {
    el.summaryTableBody.replaceChildren();
    const activeGoalCount = (summary.location_mode ? 1 : 0) + (summary.date_mode ? 1 : 0);
    const maxGoalScore = activeGoalCount > 0
      ? Math.round((summary.max_possible_score || ((summary.rounds_played || 1) * 100 * activeGoalCount)) / activeGoalCount)
      : (summary.max_possible_score || 100);

    const isMultiplayer = (summary.players || []).length > 1;

    (summary.players || []).forEach((player) => {
      const row = document.createElement("tr");
      if (isMultiplayer && player.rank === 1) {
        row.classList.add("winner-row");
      }

      const rankCell = buildCell(createRankBadge(player.rank, { dot: true }));
      rankCell.className = "col-rank";
      row.appendChild(rankCell);

      const nameCell = playerNameCell(player.player_name);
      const count = perfectCounts[player.player_name] ?? 0;
      if (count > 0) {
        const countBadge = document.createElement("span");
        countBadge.className = "perfect-count-badge";
        countBadge.textContent = t("fmt.perfect_count", count);
        nameCell.appendChild(countBadge);
      }
      const playerCell = buildCell(nameCell);
      playerCell.className = "col-player";
      row.appendChild(playerCell);

      if (summary.location_mode) {
        const locCell = buildCell(String(player.location_score ?? 0));
        animateScoreRollup(locCell, player.location_score ?? 0, maxGoalScore);
        row.appendChild(locCell);
      }
      if (summary.date_mode) {
        const dateCell = buildCell(String(player.date_score ?? 0));
        animateScoreRollup(dateCell, player.date_score ?? 0, maxGoalScore);
        row.appendChild(dateCell);
      }
      const totalCell = buildCell(`${player.total_score}/${player.max_possible_score}`);
      animateScoreRollup(totalCell, player.total_score ?? 0, player.max_possible_score ?? 100, `/${player.max_possible_score}`);
      row.appendChild(totalCell);

      const accCell = buildCell(`${player.accuracy_pct}%`);
      accCell.className = "col-accuracy hide-on-mobile";
      row.appendChild(accCell);

      el.summaryTableBody.appendChild(row);
    });
  }
}

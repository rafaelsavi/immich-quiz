import { state, el } from "../state.js";
import { t, showAlert } from "../i18n.js";
import { buildCell } from "../formatters.js";
import { renderJourneyMap } from "../maps.js";
import { renderPolaroidGallery } from "../summary.js";
import { api } from "../api.js";

/**
 * Controller for the Match Summary View.
 */
export const summaryView = {
  init({ onPlayAgain }) {
    this.onPlayAgain = onPlayAgain;
    this.bindEvents();
  },

  bindEvents() {
    if (el.playAgainBtn) {
      el.playAgainBtn.addEventListener("click", () => {
        if (this.onPlayAgain) this.onPlayAgain();
      });
    }
  },

  renderSummary(summary) {
    if (!el.summaryTableBody) return;
    el.summaryTableBody.replaceChildren();

    if (el.summaryWinner) {
      const winnerText =
        summary.winners.length > 1
          ? t("summary.tie", summary.winners.join(" & "))
          : t("summary.winner", summary.winners[0]);
      el.summaryWinner.textContent = winnerText;
    }

    summary.players.forEach((player) => {
      const row = document.createElement("tr");
      if (player.is_winner) row.className = "winner-row";

      row.appendChild(buildCell(String(player.rank)));
      row.appendChild(buildCell(player.player_name));

      if (summary.location_mode) {
        row.appendChild(buildCell(String(player.location_score ?? 0)));
      }
      if (summary.date_mode) {
        row.appendChild(buildCell(String(player.date_score ?? 0)));
      }
      row.appendChild(buildCell(`${player.total_score}/${player.max_possible_score}`));
      row.appendChild(buildCell(`${player.accuracy_pct}%`));

      el.summaryTableBody.appendChild(row);
    });

    state.lastSummary = summary;

    renderJourneyMap(state.roundHistory, summary.location_mode);
    renderPolaroidGallery(el.polaroidGallery, state.roundHistory);
  },
};

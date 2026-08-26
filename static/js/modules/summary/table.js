import { el } from "../state.js";
import { t } from "../i18n.js";
import { buildCell, playerNameCell } from "../formatters.js";
import { animateScoreRollup } from "../effects.js";

const ICONS = {
  mode: `<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><line x1="6" y1="12" x2="10" y2="12"></line><line x1="8" y1="10" x2="8" y2="14"></line><line x1="15" y1="13" x2="15.01" y2="13"></line><line x1="18" y1="11" x2="18.01" y2="11"></line><rect x="2" y="6" width="20" height="12" rx="6"></rect></svg>`,
  rounds: `<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><circle cx="12" cy="12" r="6"></circle><circle cx="12" cy="12" r="2"></circle></svg>`,
  targets: `<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><polygon points="16.24 7.76 14.12 14.12 7.76 16.24 9.88 9.88 16.24 7.76"></polygon></svg>`,
  library: `<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"></path></svg>`,
  filter: `<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3"></polygon></svg>`,
  globe: `<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="2" y1="12" x2="22" y2="12"></line><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1 4-10z"></path></svg>`,
};

function createMetaChip(iconSvg, text, className = "", tooltip = "") {
  const chip = document.createElement("span");
  chip.className = `summary-meta-chip ${className}`.trim();
  if (tooltip) {
    chip.setAttribute("title", tooltip);
  }

  const iconSpan = document.createElement("span");
  iconSpan.className = "meta-chip-icon";
  iconSpan.innerHTML = iconSvg;

  const textSpan = document.createElement("span");
  textSpan.className = "meta-chip-text";
  textSpan.textContent = text;

  chip.append(iconSpan, textSpan);
  return chip;
}

export function renderSummaryMeta(summary) {
  if (!el.summaryMeta || !summary) return;

  const chips = [];

  // 1. Game Mode Chip
  const modeText =
    summary.game_mode === "album_shuffle"
      ? t("mode.album_shuffle")
      : t("mode.pinpoint");
  const modeTooltip =
    summary.game_mode === "album_shuffle"
      ? t("mode.album_shuffle_desc")
      : t("mode.pinpoint_desc");
  chips.push(createMetaChip(ICONS.mode, modeText, "meta-mode", modeTooltip));

  // 2. Rounds Count Chip
  const roundsText = t("summary.meta_rounds", summary.rounds_played);
  chips.push(
    createMetaChip(
      ICONS.rounds,
      roundsText,
      "meta-rounds",
      `${summary.rounds_played} ${t("setup.rounds_label")}`
    )
  );

  // 3. Targets / Challenges Chip
  const targets = [];
  if (summary.location_mode) {
    targets.push(t("summary.mode_location"));
  }
  if (summary.date_mode) {
    targets.push(t("summary.mode_date"));
  }
  if (targets.length > 0) {
    chips.push(
      createMetaChip(
        ICONS.targets,
        targets.join(" + "),
        "meta-targets",
        `${t("setup.game_settings_label")}: ${targets.join(" + ")}`
      )
    );
  }

  // 4. Library Chip (only shown when specific libraries are selected)
  if (summary.libraries && summary.libraries.length > 0) {
    const libraryLabel = summary.libraries.join(", ");
    chips.push(
      createMetaChip(
        ICONS.library,
        t("summary.meta_library", libraryLabel),
        "meta-library",
        `${t("setup.library_label")}: ${libraryLabel}`
      )
    );
  }

  // 5. Filters / Scope Chip
  const hasCustomFilters = Boolean(
    summary.is_custom_filtered ||
      (summary.album_names && summary.album_names.length > 0)
  );

  const filterText =
    summary.filter_summary ||
    (summary.album_names && summary.album_names.length > 0
      ? summary.album_names.join(", ")
      : null);

  const tooltipText =
    summary.filter_tooltip ||
    (hasCustomFilters && filterText ? filterText : t("leaderboard.scope_all"));

  if (hasCustomFilters && filterText) {
    chips.push(
      createMetaChip(
        ICONS.filter,
        t("summary.meta_filters", filterText),
        "meta-filters has-active-filters",
        tooltipText
      )
    );
  } else {
    chips.push(
      createMetaChip(
        ICONS.globe,
        t("leaderboard.scope_all"),
        "meta-filters",
        tooltipText
      )
    );
  }

  el.summaryMeta.replaceChildren(...chips);
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
      if (label === t("summary.col_accuracy")) {
        cell.className = "col-accuracy hide-on-mobile";
      }
      headRow.appendChild(cell);
    });
    el.summaryTableHead.replaceChildren(headRow);
  }

  if (el.summaryTableBody) {
    el.summaryTableBody.replaceChildren();
    (summary.players || []).forEach((player) => {
      const row = document.createElement("tr");

      row.appendChild(buildCell(String(player.rank)));

      const nameCell = playerNameCell(player.player_name);
      const count = perfectCounts[player.player_name] || 0;
      if (count > 0) {
        const countBadge = document.createElement("span");
        countBadge.className = "perfect-count-badge";
        countBadge.textContent = t("fmt.perfect_count", count);
        nameCell.appendChild(countBadge);
      }
      row.appendChild(buildCell(nameCell));

      if (summary.location_mode) {
        const locCell = buildCell(String(player.location_score ?? 0));
        animateScoreRollup(locCell, player.location_score ?? 0, summary.max_possible_score || 100);
        row.appendChild(locCell);
      }
      if (summary.date_mode) {
        const dateCell = buildCell(String(player.date_score ?? 0));
        animateScoreRollup(dateCell, player.date_score ?? 0, summary.max_possible_score || 100);
        row.appendChild(dateCell);
      }
      const totalCell = buildCell(`${player.total_score}/${player.max_possible_score}`);
      animateScoreRollup(totalCell, player.total_score ?? 0, player.max_possible_score || 100, `/${player.max_possible_score}`);
      row.appendChild(totalCell);

      const accCell = buildCell(`${player.accuracy_pct}%`);
      accCell.className = "col-accuracy hide-on-mobile";
      row.appendChild(accCell);

      el.summaryTableBody.appendChild(row);
    });
  }
}

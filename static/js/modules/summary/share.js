import { t, showAlert, formatList } from "../i18n.js";

export function showShareToast(message) {
  let toast = document.querySelector(".share-toast");
  if (!toast) {
    toast = document.createElement("div");
    toast.className = "share-toast";
    document.body.appendChild(toast);
  }
  toast.textContent = message;
  toast.classList.add("show");
  setTimeout(() => toast.classList.remove("show"), 3000);
}

export async function shareMatchSummary(summary) {
  if (!summary) return;

  const winnerText =
    summary.winners && summary.winners.length > 1
      ? t("summary.tie", formatList(summary.winners))
      : summary.winners && summary.winners.length > 0
        ? t("summary.winner", summary.winners[0])
        : "";

  let text = `🏆 Immich Quiz - ${winnerText}\n`;
  const filterInfo =
    summary.filter_summary && summary.filter_summary !== "Full Library"
      ? ` • ${summary.filter_summary}`
      : summary.album_names && summary.album_names.length > 0
        ? ` • ${formatList(summary.album_names)}`
        : "";
  const libLabel =
    summary.libraries && summary.libraries.length > 0
      ? formatList(summary.libraries)
      : t("leaderboard.scope_all");
  text += `📍 ${libLabel}${filterInfo} | ${t("summary.meta_rounds", summary.rounds_played)}\n\n`;
  text += `${t("summary.scores_header")}\n`;
  (summary.players || []).forEach((p) => {
    text += `${p.rank}. ${p.player_name}: ${p.total_score}/${p.max_possible_score} (${p.accuracy_pct}%)\n`;
  });

  try {
    if (navigator.share && navigator.canShare && navigator.canShare({ text })) {
      await navigator.share({ title: t("summary.share_title"), text });
    } else {
      await navigator.clipboard.writeText(text);
      showShareToast(t("summary.share_copied"));
    }
  } catch (err) {
    if (err && err.name !== "AbortError") {
      try {
        await navigator.clipboard.writeText(text);
        showShareToast(t("summary.share_copied"));
      } catch (clipErr) {
        showAlert(clipErr.message || String(clipErr));
      }
    }
  }
}

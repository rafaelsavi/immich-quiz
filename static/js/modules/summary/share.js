import { t, showAlert } from "../i18n.js";

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
      ? t("summary.tie", summary.winners.join(" & "))
      : summary.winners && summary.winners.length > 0
        ? t("summary.winner", summary.winners[0])
        : "";

  let text = `🏆 Immich Quiz - ${winnerText}\n`;
  text += `📍 ${summary.library_name} | ${summary.rounds_played} rounds\n\n`;
  text += `Scores:\n`;
  (summary.players || []).forEach((p) => {
    text += `${p.rank}. ${p.player_name}: ${p.total_score}/${p.max_possible_score} (${p.accuracy_pct}%)\n`;
  });

  try {
    if (navigator.share && navigator.canShare && navigator.canShare({ text })) {
      await navigator.share({ title: "Immich Quiz Results", text });
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

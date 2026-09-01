import { t, tOr, showAlert, formatList } from "../i18n.js";

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

/**
 * Safely copy text to clipboard with fallback and optional button/toast feedback.
 * @param {string} text - Text to copy.
 * @param {Object} [options]
 * @param {HTMLElement} [options.button] - Button element to animate feedback on.
 * @param {string} [options.copiedText] - Text to show on button when copied.
 * @param {string} [options.copiedHtml] - HTML string to show on button when copied.
 * @param {string} [options.successMessage] - Toast message to show on copy.
 * @param {number} [options.resetTimeoutMs=2500] - Duration before reverting button state.
 * @returns {Promise<boolean>}
 */
export async function copyToClipboard(text, options = {}) {
  const { button, copiedText, copiedHtml, successMessage, resetTimeoutMs = 2500 } = options;
  let success = false;

  try {
    if (navigator.clipboard && window.isSecureContext) {
      await navigator.clipboard.writeText(text);
      success = true;
    } else {
      throw new Error("Clipboard API unavailable");
    }
  } catch (_) {
    try {
      const textarea = document.createElement("textarea");
      textarea.value = text;
      textarea.style.position = "fixed";
      textarea.style.left = "-9999px";
      textarea.style.top = "0";
      textarea.setAttribute("readonly", "");
      document.body.appendChild(textarea);
      textarea.focus();
      textarea.select();
      success = document.execCommand("copy");
      document.body.removeChild(textarea);
    } catch (fallbackErr) {
      console.warn("Clipboard copy failed:", fallbackErr);
      success = false;
    }
  }

  if (success) {
    if (button) {
      button.classList.add("copied");
      const originalHtml = button.innerHTML;
      if (copiedHtml) {
        button.innerHTML = copiedHtml;
      } else if (copiedText) {
        button.textContent = copiedText;
      }
      setTimeout(() => {
        button.classList.remove("copied");
        if (copiedHtml || copiedText) {
          button.innerHTML = originalHtml;
        }
      }, resetTimeoutMs);
    }
    if (successMessage) {
      showShareToast(successMessage);
    }
  } else {
    showShareToast(tOr("summary.share_failed", "Failed to copy to clipboard"));
  }

  return success;
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
  const albumNames = summary.config?.album_names || summary.album_names || [];
  const filterInfo =
    summary.is_custom_filtered && summary.filter_summary
      ? summary.filter_summary
      : albumNames.length > 0
        ? formatList(albumNames)
        : t("leaderboard.scope_all");

  const libraries = summary.config?.libraries || summary.libraries || [];
  const libPrefix =
    libraries.length > 0
      ? `${formatList(libraries)} • `
      : "";

  text += `📍 ${libPrefix}${filterInfo} | ${t("summary.meta_rounds", summary.rounds_played)}\n\n`;
  text += `${t("summary.scores_header")}\n`;
  (summary.players || []).forEach((p) => {
    text += `${p.rank}. ${p.player_name}: ${p.total_score}/${p.max_possible_score} (${p.accuracy_pct}%)\n`;
  });

  const shareUrl = summary.match_id
    ? `${window.location.origin}/game/${encodeURIComponent(summary.match_id)}/summary`
    : window.location.href;

  text += `\n🔗 ${shareUrl}`;

  try {
    if (navigator.share && navigator.canShare && navigator.canShare({ text, url: shareUrl })) {
      await navigator.share({ title: t("summary.share_title"), text, url: shareUrl });
    } else {
      await copyToClipboard(text, { successMessage: t("summary.share_copied") });
    }
  } catch (err) {
    if (err && err.name !== "AbortError") {
      await copyToClipboard(text, { successMessage: t("summary.share_copied") });
    }
  }
}

import { el } from "../state.js";
import { t } from "../i18n.js";

export function renderPodium(summary, targetEl = null) {
  const winnerEl = targetEl || el.summaryWinner;
  if (!winnerEl) return;

  const isMultiplayer = summary.players && summary.players.length > 1;

  const titleText =
    summary.winners && summary.winners.length > 1
      ? t("summary.tie", summary.winners.join(" & "))
      : summary.winners && summary.winners.length > 0
        ? t("summary.winner", summary.winners[0])
        : "";

  winnerEl.replaceChildren();
  const title = document.createElement("div");
  title.textContent = titleText;
  winnerEl.appendChild(title);


  // Do not render podium steps in single-player mode
  if (!isMultiplayer) {
    return;
  }

  const medals = ["\uD83E\uDD47", "\uD83E\uDD48", "\uD83E\uDD49"];
  const top3 = (summary.players || []).slice(0, 3);
  if (top3.length === 0) return;

  const podium = document.createElement("div");
  podium.className = "podium";

  top3.forEach((player, index) => {
    const step = document.createElement("div");
    step.className = "podium-step";

    const medal = document.createElement("div");
    medal.className = "podium-medal";
    medal.textContent = medals[index] || "";

    const name = document.createElement("div");
    name.className = "podium-name";
    name.textContent = player.player_name;

    const score = document.createElement("div");
    score.className = "podium-score";
    score.textContent = t("summary.podium_score", player.total_score);

    const accuracy = document.createElement("div");
    accuracy.className = "podium-accuracy";
    accuracy.textContent = `${player.accuracy_pct}%`;

    step.append(medal, name, score, accuracy);
    podium.appendChild(step);
  });

  winnerEl.appendChild(podium);
}


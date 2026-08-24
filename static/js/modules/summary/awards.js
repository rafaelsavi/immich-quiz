import { el } from "../state.js";
import { t } from "../i18n.js";

export function renderAwards(summary, playerStats = {}) {
  if (!el.summaryCard || !el.summaryWinner) return;

  // Remove any existing awards row
  const existingAwards = el.summaryCard.querySelector(".awards-row");
  if (existingAwards) existingAwards.remove();

  const awards = [];
  const summaryByName = new Map((summary.players || []).map((player) => [player.player_name, player]));

  const pickAwardWinner = (metricKey, tieBreakValueFn, { tieBreakPreferHigher = true, filterFn = null } = {}) => {
    let bestName = null;
    let bestMetricValue = -Infinity;
    let bestTieValue = null;
    let hasTie = false;

    for (const [name, stats] of Object.entries(playerStats)) {
      if (filterFn && !filterFn(name, stats)) {
        continue;
      }

      const metricValue = stats[metricKey] ?? 0;
      if (metricValue < 1) {
        continue;
      }

      if (metricValue > bestMetricValue) {
        bestName = name;
        bestMetricValue = metricValue;
        bestTieValue = tieBreakValueFn ? tieBreakValueFn(name) : null;
        hasTie = false;
      } else if (metricValue === bestMetricValue) {
        if (tieBreakValueFn) {
          const tieValue = tieBreakValueFn(name);
          const isBetter = tieBreakPreferHigher ? tieValue > bestTieValue : tieValue < bestTieValue;
          const isWorse = tieBreakPreferHigher ? tieValue < bestTieValue : tieValue > bestTieValue;

          if (isBetter) {
            bestName = name;
            bestMetricValue = metricValue;
            bestTieValue = tieValue;
            hasTie = false;
          } else if (isWorse) {
            // Current leader remains ahead; no tie
          } else {
            hasTie = true;
          }
        } else {
          hasTie = true;
        }
      }
    }

    return hasTie ? null : bestName;
  };

  const isAlbumShuffle = summary.game_mode === "album_shuffle";

  // 1. Sniper — most perfect location guesses (0 km / max points)
  if (summary.location_mode && !isAlbumShuffle) {
    const bestSniper = pickAwardWinner("perfectLocationCount", (name) => summaryByName.get(name)?.location_score ?? -1);
    if (bestSniper) {
      awards.push({
        titleKey: "award.sniper",
        descKey: "award.sniper_desc",
        descArgs: [playerStats[bestSniper]?.perfectLocationCount || 0],
        player: bestSniper,
      });
    }
  }

  // 2. Time Traveler — most perfect date guesses (0 days / exact month / max points)
  if (summary.date_mode && !isAlbumShuffle) {
    const bestTimeTraveler = pickAwardWinner("perfectDateCount", (name) => summaryByName.get(name)?.date_score ?? -1);
    if (bestTimeTraveler) {
      awards.push({
        titleKey: "award.time_traveler",
        descKey: "award.time_traveler_desc",
        descArgs: [playerStats[bestTimeTraveler]?.perfectDateCount || 0],
        player: bestTimeTraveler,
      });
    }
  }

  // 3. Speed Demon — max fast rounds (<=50% max time) and 0 timeouts
  const speedDemonPlayer = pickAwardWinner("fastRoundCount", (name) => playerStats[name]?.totalDurationSec ?? Infinity, {
    tieBreakPreferHigher: false,
    filterFn: (name, stats) => stats.timedOutCount === 0,
  });

  if (speedDemonPlayer) {
    awards.push({
      titleKey: "award.speed_demon",
      descKey: "award.speed_demon_desc",
      descArgs: [playerStats[speedDemonPlayer]?.fastRoundCount || 0],
      player: speedDemonPlayer,
    });
  }

  if (awards.length === 0) return;

  const row = document.createElement("div");
  row.className = "awards-row";

  awards.forEach((award) => {
    const card = document.createElement("div");
    card.className = "award-card";

    const titleEl = document.createElement("div");
    titleEl.className = "award-title";
    titleEl.textContent = t(award.titleKey);

    const playerEl = document.createElement("div");
    playerEl.className = "award-player";
    playerEl.textContent = award.player;

    const descEl = document.createElement("div");
    descEl.className = "award-desc";
    descEl.textContent = award.descArgs ? t(award.descKey, ...award.descArgs) : t(award.descKey);

    card.append(titleEl, playerEl, descEl);
    row.appendChild(card);
  });

  // Insert awards between summaryWinner and the table
  el.summaryWinner.after(row);
}

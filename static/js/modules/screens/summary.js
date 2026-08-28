import { state, el, clearActiveMatchSession } from "../state.js";
import { api } from "../api.js";
import { t, getLocale } from "../i18n.js";
import { navigate } from "../router.js";
import { playVictoryFanfare } from "../audio.js";
import { renderJourneyMap } from "../maps.js";
import { loadLeaderboard } from "../leaderboard.js";
import { clearTimer } from "../timer.js";
import { renderPodium } from "../summary/podium.js";
import { renderAwards } from "../summary/awards.js";
import { renderSummaryTable } from "../summary/table.js";
import { renderPolaroidGallery } from "../summary/polaroids.js";
import { showCard, clearRevealAnimation } from "./common.js";

export function renderSummaryContent(summary) {
  if (!summary) return;
  renderPodium(summary);
  renderAwards(summary, state.playerStats);
  renderSummaryTable(summary, state.perfectCounts);
}

export async function showMatchSummary() {
  if (!state.matchId) return;
  await showMatchSummaryByMatchId(state.matchId);
}

export async function showMatchSummaryByMatchId(matchId) {
  try {
    const lang = getLocale();
    const summary = await api(
      `/api/match/${encodeURIComponent(matchId)}/summary?lang=${encodeURIComponent(lang)}`
    );
    state.matchId = matchId;
    state.lastSummary = summary;
    if (summary.round_history && (!state.roundHistory || state.roundHistory.length === 0)) {
      state.roundHistory = summary.round_history;
    }

    showCard(el.summaryCard);
    window.scrollTo({ top: 0, behavior: "smooth" });
    playVictoryFanfare();

    renderSummaryContent(summary);
    renderJourneyMap(state.roundHistory, summary.location_mode);
    renderPolaroidGallery(state.roundHistory);

    el.leaderboardCard.classList.remove("hidden");
    await loadLeaderboard();
  } catch (err) {
    console.warn("Failed to load match summary:", err);
    showGameEndedCard(
      null,
      t("game_ended.match_not_found_msg", matchId),
      t("game_ended.match_not_found_title"),
      "🔍"
    );
  }
}

export function showGameEndedCard(matchId = null, customMsg = null, customTitle = null, customIcon = null) {
  clearRevealAnimation();
  clearTimer();
  clearActiveMatchSession();

  showCard(el.gameEndedCard);
  el.leaderboardCard.classList.add("hidden");

  const iconEl = document.getElementById("game-ended-icon");
  if (iconEl) {
    iconEl.textContent = customIcon ?? "🏁";
  }

  const titleEl = document.getElementById("game-ended-title");
  if (titleEl) {
    titleEl.textContent = customTitle ?? t("game_ended.heading");
  }

  const msgEl = document.getElementById("game-ended-msg");
  if (msgEl) {
    msgEl.textContent = customMsg ?? t("game_ended.message");
  }

  if (el.gameEndedSummaryBtn) {
    if (matchId) {
      el.gameEndedSummaryBtn.classList.remove("hidden");
      el.gameEndedSummaryBtn.onclick = () => {
        navigate(`/game/${encodeURIComponent(matchId)}/summary`);
      };
    } else {
      el.gameEndedSummaryBtn.classList.add("hidden");
    }
  }

  if (el.gameEndedLobbyBtn) {
    el.gameEndedLobbyBtn.onclick = () => {
      navigate("/");
    };
  }
}

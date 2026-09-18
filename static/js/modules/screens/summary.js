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
import { MatchReplayViewer } from "../components/match_replay.js";

let _summaryReplayViewer = null;

export function renderSummaryContent(summary) {
  if (!summary) return;
  renderPodium(summary);
  renderAwards(summary, state.playerStats);
  renderSummaryTable(summary, state.perfectCounts);
}

export async function showMatchSummary() {
  if (!state.matchId) return;
  await showMatchSummaryByMatchId(state.matchId, { playFanfare: true });
}

export async function showMatchSummaryByMatchId(matchId, { playFanfare = false } = {}) {
  try {
    const lang = getLocale();
    const summary = await api(
      `/api/match/${encodeURIComponent(matchId)}/summary?lang=${encodeURIComponent(lang)}`
    );
    if (summary && !summary.finished) {
      showGameEndedCard(
        null,
        t("game_ended.match_in_progress_msg"),
        t("game_ended.match_in_progress_title"),
        "🎮"
      );
      return;
    }
    state.matchId = matchId;
    state.lastSummary = summary;
    if (summary.round_history && (!state.roundHistory || state.roundHistory.length === 0)) {
      state.roundHistory = summary.round_history;
    }

    showCard(el.summaryCard);
    window.scrollTo({ top: 0, behavior: "smooth" });
    if (playFanfare) {
      playVictoryFanfare();
    }

    renderSummaryContent(summary);
    renderJourneyMap(state.roundHistory, summary.location_mode);
    renderPolaroidGallery(state.roundHistory);

    // Load and render Match Replay in the summary card
    const replaySection = document.getElementById("summary-replay-section");
    const replayGrid = document.getElementById("summary-replay-grid");
    const replayBtn = document.getElementById("summary-watch-replay-btn");

    if (replaySection && replayGrid) {
      try {
        const replayRes = await fetch(`/api/match/${encodeURIComponent(matchId)}/replay`);
        if (replayRes.ok) {
          const replayData = await replayRes.json();
          if (!_summaryReplayViewer) {
            _summaryReplayViewer = new MatchReplayViewer(replayGrid, {
              idPrefix: "summary-replay-",
              showReportButton: true,
            });
          }
          _summaryReplayViewer.setMatchData(replayData, 0);
          replaySection.classList.remove("hidden");
          if (replayBtn) {
            replayBtn.classList.remove("hidden");
            replayBtn.onclick = () => {
              replaySection.scrollIntoView({ behavior: "smooth", block: "start" });
            };
          }
        }
      } catch (e) {
        console.warn("Could not load replay in summary:", e);
      }
    }

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

export function refreshSummaryLanguage() {
  if (el.summaryCard && !el.summaryCard.classList.contains("hidden") && state.lastSummary) {
    renderSummaryContent(state.lastSummary);
    renderPolaroidGallery(state.roundHistory);
    if (_summaryReplayViewer) {
      _summaryReplayViewer.renderCurrentRound();
    }
  }
}

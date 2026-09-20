/**
 * Unified Match Review Screen Controller
 *
 * Serves both:
 * 1. Mode "summary": Fresh post-game results screen (/game/:id/summary)
 *    - Outcome Hero (Podium, Standings Table, Performance Awards)
 *    - Universal 3-Tab Review Deck (Replay, Journey Map, Photo Memories)
 *    - Victory Fanfare audio & confetti
 *    - All-Time Leaderboard Card
 *    - "Start New Game" and "Share Game" actions
 *
 * 2. Mode "replay": Historical match archive review screen (/game/:id/replay)
 *    - Standard Hub Back Button ("← Exit Replay")
 *    - Match Meta specifications panel (Setup & Filter chips)
 *    - Outcome Hero (Podium & Standings Table)
 *    - Universal 3-Tab Review Deck (Replay, Journey Map, Photo Memories)
 *    - "Exit Replay" and "Share Game" bottom actions
 */

import { state, el, clearActiveMatchSession } from "../state.js";
import { api } from "../api.js";
import { t, getLocale, formatDateTime } from "../i18n.js";
import { navigate } from "../router.js";
import { playVictoryFanfare } from "../audio.js";
import { loadLeaderboard } from "../leaderboard.js";
import { clearTimer } from "../timer.js";
import { renderPodium } from "../summary/podium.js";
import { renderAwards } from "../summary/awards.js";
import { renderSummaryTable } from "../summary/table.js";
import { renderPolaroidGallery } from "../summary/polaroids.js";
import { showCard, clearRevealAnimation } from "./common.js";
import { ReviewDeck } from "../components/review_deck.js";
import { renderMatchMeta } from "../components/match_meta.js";
import { escapeHtml } from "../formatters.js";
import { renderReplayTitleHeader } from "./replay.js";

let _reviewDeck = null;
let _currentMode = "summary";
let _currentMatchData = null;

export function renderSummaryContent(summary) {
  if (!summary) return;
  renderPodium(summary);
  renderAwards(summary, state.playerStats);
  renderSummaryTable(summary, state.perfectCounts);
}

export function replayToSummary(replayData) {
  const lastRound = replayData.rounds_data && replayData.rounds_data.length > 0
    ? replayData.rounds_data[replayData.rounds_data.length - 1]
    : null;
  const guesses = lastRound ? (lastRound.player_guesses || []) : [];

  let playersList = [];
  if (Array.isArray(replayData.players) && replayData.players.length > 0) {
    playersList = replayData.players.map((p, idx) => ({
      player_name: typeof p === "string" ? p : p.player_name,
      total_score: (typeof p === "object" && p.total_score != null) ? p.total_score : 0,
      location_score: typeof p === "object" ? p.location_score : null,
      date_score: typeof p === "object" ? p.date_score : null,
      rank: (typeof p === "object" && p.rank) ? p.rank : (idx + 1),
      max_possible_score: (replayData.rounds || 1) * 10000,
      accuracy_percentage: typeof p === "object" ? p.accuracy_percentage : null,
      avatar_color: typeof p === "object" ? (p.avatar_color || p.player_color) : null,
    }));
  } else if (guesses.length > 0) {
    const sortedGuesses = [...guesses].sort((a, b) => (b.cumulative_score || 0) - (a.cumulative_score || 0));
    playersList = sortedGuesses.map((g, idx) => ({
      player_name: g.player_name,
      total_score: g.cumulative_score || 0,
      location_score: g.location_score,
      date_score: g.date_score,
      rank: idx + 1,
      max_possible_score: (replayData.rounds || (replayData.rounds_data ? replayData.rounds_data.length : 1)) * 10000,
      avatar_color: g.player_color,
    }));
  }

  const winners = Array.isArray(replayData.winners) && replayData.winners.length > 0
    ? replayData.winners
    : (playersList.length > 0 ? [playersList[0].player_name] : []);

  return {
    match_id: replayData.match_id,
    game_mode: replayData.game_mode,
    play_mode: replayData.play_mode,
    location_mode: replayData.location_mode ?? replayData.config?.location_mode ?? true,
    date_mode: replayData.date_mode ?? replayData.config?.date_mode ?? true,
    rounds_played: replayData.rounds || (replayData.rounds_data ? replayData.rounds_data.length : 1),
    max_possible_score: (replayData.rounds || (replayData.rounds_data ? replayData.rounds_data.length : 1)) * 10000,
    players: playersList,
    winners,
    is_concluded: true,
    round_history: replayData.rounds_data || [],
    config: replayData.config,
    challenge_title: replayData.challenge_title,
    challenge_creator: replayData.challenge_creator,
  };
}

export async function showMatchSummary() {
  if (!state.matchId) return;
  await showMatchSummaryByMatchId(state.matchId, { mode: "summary", playFanfare: true });
}

export async function showMatchSummaryByMatchId(matchId, { mode = "summary", playFanfare = false } = {}) {
  _currentMode = mode;
  state.matchId = matchId;

  const headerSummary = document.getElementById("review-header-summary");
  const headerReplay = document.getElementById("review-header-replay");
  const actionsSummary = document.getElementById("summary-actions");
  const actionsReplay = document.getElementById("replay-actions");
  const loadingEl = document.getElementById("replay-loading-state");
  const errorEl = document.getElementById("replay-error-state");
  const reviewContent = document.getElementById("review-content");

  if (loadingEl) loadingEl.classList.add("hidden");
  if (errorEl) errorEl.classList.add("hidden");
  if (reviewContent) reviewContent.classList.remove("hidden");

  if (mode === "replay") {
    if (headerSummary) headerSummary.classList.add("hidden");
    if (headerReplay) headerReplay.classList.remove("hidden");
    if (actionsSummary) actionsSummary.classList.add("hidden");
    if (actionsReplay) actionsReplay.classList.remove("hidden");
    if (el.leaderboardCard) el.leaderboardCard.classList.add("hidden");
  } else {
    if (headerSummary) headerSummary.classList.remove("hidden");
    if (headerReplay) headerReplay.classList.add("hidden");
    if (actionsSummary) actionsSummary.classList.remove("hidden");
    if (actionsReplay) actionsReplay.classList.add("hidden");
  }

  showCard(el.summaryCard);
  window.scrollTo({ top: 0, behavior: "smooth" });

  const lang = getLocale();
  let summary = null;
  let replayData = null;

  if (mode === "replay") {
    if (loadingEl) loadingEl.classList.remove("hidden");
    if (reviewContent) reviewContent.classList.add("hidden");

    try {
      const res = await fetch(`/api/match/${encodeURIComponent(matchId)}/replay`);
      if (!res.ok) throw new Error("Failed to load match replay");
      replayData = await res.json();
      _currentMatchData = replayData;

      try {
        summary = await api(`/api/match/${encodeURIComponent(matchId)}/summary?lang=${encodeURIComponent(lang)}`);
      } catch (_) {}
      if (!summary || !summary.players || summary.players.length === 0) {
        summary = replayToSummary(replayData);
      }

      state.lastSummary = summary;
      if (replayData.rounds_data) {
        state.roundHistory = replayData.rounds_data;
      }

      if (loadingEl) loadingEl.classList.add("hidden");
      if (reviewContent) reviewContent.classList.remove("hidden");

      renderReplayTitleHeader(replayData);
      const metaContainer = document.getElementById("replay-match-meta-container");
      if (metaContainer) {
        renderMatchMeta(metaContainer, replayData);
      }
    } catch (err) {
      console.error("Error loading match replay:", err);
      if (loadingEl) loadingEl.classList.add("hidden");
      if (reviewContent) reviewContent.classList.add("hidden");
      if (errorEl) {
        errorEl.classList.remove("hidden");
        const errText = document.getElementById("replay-error-text");
        if (errText) errText.textContent = t("replay.not_found");
      }
      return;
    }
  } else {
    // Mode: Summary
    try {
      summary = await api(
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
      state.lastSummary = summary;
      if (summary.round_history && (!state.roundHistory || state.roundHistory.length === 0)) {
        state.roundHistory = summary.round_history;
      }

      // Also attempt to load replay data for the review deck
      try {
        const replayRes = await fetch(`/api/match/${encodeURIComponent(matchId)}/replay`);
        if (replayRes.ok) {
          replayData = await replayRes.json();
          _currentMatchData = replayData;
        }
      } catch (_) {}

      if (playFanfare) {
        playVictoryFanfare();
      }

      if (el.leaderboardCard) {
        el.leaderboardCard.classList.remove("hidden");
        await loadLeaderboard();
      }
    } catch (err) {
      console.warn("Failed to load match summary:", err);
      showGameEndedCard(
        null,
        t("game_ended.match_not_found_msg", matchId),
        t("game_ended.match_not_found_title"),
        "🔍"
      );
      return;
    }
  }

  // Render Outcome Hero (Podium, Standings Table, Awards)
  if (summary) {
    renderSummaryContent(summary);
  }

  // Mount & Hydrate Universal Review Deck
  const deckMount = document.getElementById("summary-review-deck");
  if (deckMount) {
    if (!_reviewDeck) {
      _reviewDeck = new ReviewDeck(deckMount, {
        showReportButton: true,
        defaultTab: "replay",
      });
    }
    const deckPayload = replayData || summary;
    _reviewDeck.setMatchData(deckPayload, 0);
  }
}

export function showGameEndedCard(matchId = null, customMsg = null, customTitle = null, customIcon = null) {
  clearRevealAnimation();
  clearTimer();
  clearActiveMatchSession();

  showCard(el.gameEndedCard);
  if (el.leaderboardCard) el.leaderboardCard.classList.add("hidden");

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
  if (el.summaryCard && !el.summaryCard.classList.contains("hidden")) {
    if (state.lastSummary) {
      renderSummaryContent(state.lastSummary);
    }
    if (_reviewDeck) {
      _reviewDeck.refreshLanguage();
    }
    if (_currentMode === "replay" && _currentMatchData) {
      renderReplayTitleHeader(_currentMatchData);
      const metaContainer = document.getElementById("replay-match-meta-container");
      if (metaContainer) {
        renderMatchMeta(metaContainer, _currentMatchData);
      }
      const backBtn = document.getElementById("replay-back-btn");
      if (backBtn) {
        const span = backBtn.querySelector("[data-i18n]");
        if (span) span.textContent = t("replay.exit");
      }
      const exitBottom = document.getElementById("replay-exit-bottom-btn");
      if (exitBottom) {
        exitBottom.textContent = t("replay.exit");
      }
    }
  }
}

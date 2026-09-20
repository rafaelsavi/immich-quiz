/**
 * Unified Match Review Screen Controller
 *
 * Serves:
 * 1. Mode "summary" (Local Match): Fresh post-game results screen (/game/:id/summary)
 * 2. Mode "summary" (Challenge): Challenge Grand Reveal review (/play/:token/summary)
 * 3. Mode "replay": Historical match archive review screen (/game/:id/replay)
 *
 * Unified architecture:
 * - Outcome Hero (3D Podium, Provisional Status Card, Performance Awards)
 * - Standardized Standings Table with row arrivals and score rollup
 * - Universal 3-Tab Review Deck (Replay, Journey Map, Photo Memories)
 * - Standardized Bottom Actions with Challenge Invite Drawer
 * - All-Time Leaderboard Card
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
import { showCard, clearRevealAnimation } from "./common.js";
import { ReviewDeck } from "../components/review_deck.js";
import { renderMatchMeta } from "../components/match_meta.js";
import { escapeHtml } from "../formatters.js";
import { renderShareUrlContainerHtml, setupShareBox } from "../components/share_box.js";
import { challengeSession } from "../challenge/session.js";

let _reviewDeck = null;
let _currentMode = "summary";
let _currentMatchData = null;

export function renderReplayTitleHeader(data = null) {
  const headingTitleEl = document.getElementById("replay-heading-title");
  const titleEl = document.getElementById("replay-match-title");
  if (!titleEl || !data) return;

  const isChallenge =
    data.play_mode === "challenge" ||
    Boolean(data.challenge_id || data.challenge_title || data.challenge_creator);

  if (isChallenge) {
    const challengeTitle =
      data.challenge_title ||
      (data.challenge_creator ? `${data.challenge_creator}'s Challenge` : t("challenge.badge"));
    const hostText = data.challenge_creator
      ? t("challenges_page.host_label", data.challenge_creator)
      : "";
    const dateText = formatDateTime(data.played_at);

    if (headingTitleEl) {
      headingTitleEl.removeAttribute("data-i18n");
      headingTitleEl.textContent = challengeTitle;
    }

    const parts = [
      `<span class="badge-tag badge-type badge-type-challenge">⚔️ ${t("replay.play_mode_challenge")}</span>`,
      `<span class="replay-challenge-title">${escapeHtml(challengeTitle)}</span>`,
    ];
    if (hostText) {
      parts.push(`<span class="replay-challenge-host">${escapeHtml(hostText)}</span>`);
    }
    if (dateText) {
      parts.push(`<span class="replay-match-date">${escapeHtml(dateText)}</span>`);
    }
    titleEl.innerHTML = parts.join(` <span class="meta-separator" aria-hidden="true">•</span> `);
  } else if (data.play_mode === "room" && data.room_name) {
    if (headingTitleEl) {
      headingTitleEl.removeAttribute("data-i18n");
      headingTitleEl.textContent = data.room_name;
    }
    const dateText = formatDateTime(data.played_at);
    titleEl.innerHTML = `
      <span class="badge-tag badge-type badge-type-room">🏠 ${t("replay.play_mode_room")}</span>
      <span class="meta-separator" aria-hidden="true">•</span>
      <span class="replay-match-date">${escapeHtml(dateText)}</span>
    `;
  } else {
    if (headingTitleEl) {
      headingTitleEl.setAttribute("data-i18n", "replay.title");
      headingTitleEl.textContent = t("replay.title");
    }
    const dateText = formatDateTime(data.played_at);
    titleEl.innerHTML = `
      <span class="badge-tag badge-type badge-type-local">👥 ${t("replay.play_mode_local")}</span>
      <span class="meta-separator" aria-hidden="true">•</span>
      <span class="replay-match-date">${escapeHtml(dateText)}</span>
    `;
  }
}

export function renderSummaryTitleHeader(data = null) {
  const badgeEl = el.summaryGameModeBadge || document.getElementById("summary-game-mode-badge");
  const livePill = el.grandRevealLivePill || document.getElementById("grand-reveal-live-pill");
  const liveStatus = el.grandRevealLiveStatus || document.getElementById("grand-reveal-live-status");
  const headingEl = el.summaryHeading || document.getElementById("summary-heading");

  if (!data) return;

  const isChallenge = Boolean(
    data.is_challenge ||
    data.play_mode === "challenge" ||
    data.challenge_id ||
    data.challenge_title ||
    data.challenge_creator
  );

  if (isChallenge) {
    if (badgeEl) {
      badgeEl.className = "badge-tag badge-type badge-type-challenge";
      badgeEl.innerHTML = `⚔️ ${t("replay.play_mode_challenge")}`;
    }
    if (headingEl) {
      headingEl.removeAttribute("data-i18n");
      headingEl.textContent =
        data.challenge_title ||
        data.title ||
        (data.challenge_creator || data.creator_name
          ? `${data.challenge_creator || data.creator_name}'s Challenge`
          : t("challenge.badge"));
    }
    const totalRounds = data.rounds_played || data.total_rounds || 1;
    const participants = (data.players || data.leaderboard || []);
    if (livePill && liveStatus) {
      livePill.classList.remove("hidden");
      const finishedCount = participants.filter(
        (p) => p.is_finished || (p.completed_rounds >= totalRounds)
      ).length;
      liveStatus.textContent = t("challenge.live_finished_tally", finishedCount, participants.length);
    }
  } else if (data.play_mode === "room" && data.room_name) {
    if (badgeEl) {
      badgeEl.className = "badge-tag badge-type badge-type-room";
      badgeEl.innerHTML = `🏠 ${t("replay.play_mode_room")}`;
    }
    if (headingEl) {
      headingEl.removeAttribute("data-i18n");
      headingEl.textContent = data.room_name;
    }
    if (livePill) livePill.classList.add("hidden");
  } else {
    if (badgeEl) {
      badgeEl.className = "badge-tag badge-type badge-type-local";
      badgeEl.innerHTML = `👥 ${t("replay.play_mode_local")}`;
    }
    if (headingEl) {
      headingEl.setAttribute("data-i18n", "summary.heading");
      headingEl.textContent = t("summary.heading");
    }
    if (livePill) livePill.classList.add("hidden");
  }
}

export function renderSummaryContent(summary) {
  if (!summary) return;

  // 1. Header (Badge, Title, Meta tally)
  renderSummaryTitleHeader(summary);

  const isChallenge = Boolean(
    summary.is_challenge ||
    summary.play_mode === "challenge" ||
    summary.challenge_id
  );
  const isSettled = summary.is_settled !== false;

  // 2. Outcome Hero (Podium or Provisional Card)
  const winnerEl = document.getElementById("summary-winner");
  if (winnerEl) {
    if (isChallenge && !isSettled) {
      winnerEl.innerHTML = `
        <div class="challenge-provisional-card" id="grand-reveal-provisional">
          <div class="provisional-header">
            <span class="pulse-dot"></span>
            <h3 class="provisional-title">${escapeHtml(t("challenge.provisional_title"))}</h3>
          </div>
          <p class="provisional-desc">${escapeHtml(t("challenge.provisional_desc"))}</p>
          <div class="provisional-hint">
            <span aria-hidden="true">🏆</span>
            <span>${escapeHtml(t("challenge.single_player_podium_hint"))}</span>
          </div>
        </div>
      `;
    } else {
      winnerEl.innerHTML = `
        <div class="grand-reveal-podium-wrap" id="grand-reveal-podium-section">
          <div id="grand-reveal-podium" class="summary-winner"></div>
        </div>
      `;
      const podiumEl = document.getElementById("grand-reveal-podium") || winnerEl;
      renderPodium(summary, podiumEl);
      renderAwards(summary, state.playerStats, winnerEl, podiumEl);
    }
  }

  // 3. Standings Table
  renderSummaryTable(summary, state.perfectCounts, {
    currentSessionPlayerName: summary.current_player_name || challengeSession?.sessionPlayerName,
  });

  // 4. Challenge Invite Friends Action & Drawer
  const inviteBtn = document.getElementById("challenge-invite-btn");
  const inviteDrawer = document.getElementById("summary-invite-drawer");
  const inviteBox = document.getElementById("summary-invite-share-box");

  if (isChallenge) {
    if (inviteBtn) {
      inviteBtn.classList.remove("hidden");
      inviteBtn.onclick = () => {
        if (inviteDrawer) {
          inviteDrawer.classList.toggle("hidden");
        }
      };
    }
    const capToken =
      summary.capability_token ||
      challengeSession?.challengeData?.capability_token;
    const playUrl = capToken ? `${window.location.origin}/play/${capToken}` : window.location.href;
    if (inviteBox && (!inviteBox.dataset.ready || inviteBox.dataset.token !== capToken)) {
      inviteBox.innerHTML = renderShareUrlContainerHtml(playUrl, { prefix: "summary-invite" });
      setupShareBox(inviteBox, playUrl, {
        prefix: "summary-invite",
        title: t("challenge.invite_message"),
        qrSize: 180,
      });
      inviteBox.dataset.ready = "true";
      inviteBox.dataset.token = capToken || "";
    }
  } else {
    if (inviteBtn) inviteBtn.classList.add("hidden");
    if (inviteDrawer) inviteDrawer.classList.add("hidden");
  }
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
      completed_rounds: typeof p === "object" ? p.completed_rounds : null,
      is_finished: typeof p === "object" ? p.is_finished : null,
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

  const totalRounds = replayData.rounds || (replayData.rounds_data ? replayData.rounds_data.length : 1);
  const finishedCount = playersList.filter((p) => p.is_finished || (p.completed_rounds != null && p.completed_rounds >= totalRounds)).length;
  const isSettled = replayData.play_mode === "challenge" ? finishedCount >= 2 : true;

  return {
    match_id: replayData.match_id,
    game_mode: replayData.game_mode,
    play_mode: replayData.play_mode,
    is_challenge: replayData.play_mode === "challenge",
    location_mode: replayData.location_mode ?? replayData.config?.location_mode ?? true,
    date_mode: replayData.date_mode ?? replayData.config?.date_mode ?? true,
    rounds_played: totalRounds,
    total_rounds: totalRounds,
    max_possible_score: totalRounds * 10000,
    players: playersList,
    winners,
    is_settled: isSettled,
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

export async function showMatchSummaryByMatchId(
  matchId,
  {
    mode = "summary",
    playFanfare = false,
    isChallenge = false,
    challengeData = null,
  } = {}
) {
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
    if (el.summaryCard) el.summaryCard.classList.remove("challenge-grand-reveal");
  } else {
    if (headerSummary) headerSummary.classList.remove("hidden");
    if (headerReplay) headerReplay.classList.add("hidden");
    if (actionsSummary) actionsSummary.classList.remove("hidden");
    if (actionsReplay) actionsReplay.classList.add("hidden");
    if (el.summaryCard) {
      el.summaryCard.classList.toggle("challenge-grand-reveal", Boolean(isChallenge || challengeData));
    }
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
  } else if (challengeData) {
    // Mode: Challenge Summary
    const totalRoundsCount = challengeData.total_rounds || challengeSession?.totalRounds || 1;
    const leaderboard = challengeData.leaderboard || [];
    const finishedPlayers = leaderboard.filter(
      (p) => p.is_finished || p.completed_rounds >= totalRoundsCount
    );
    const isSettled = finishedPlayers.length >= 2;
    const isConcluded = Boolean(
      challengeData.is_concluded ||
      challengeSession?.challengeData?.is_active === false ||
      (challengeSession?.challengeData?.expires_at && new Date() > new Date(challengeSession.challengeData.expires_at))
    );
    const winners = finishedPlayers.filter((p) => p.is_winner).map((p) => p.player_name);

    summary = {
      match_id: matchId,
      is_challenge: true,
      play_mode: "challenge",
      challenge_id: challengeData.challenge_id || challengeSession?.challengeData?.challenge_id,
      challenge_title:
        challengeData.title ||
        (challengeData.creator_name
          ? `${challengeData.creator_name}'s Challenge`
          : challengeSession?.challengeData?.title || null),
      challenge_creator: challengeData.creator_name || challengeSession?.challengeData?.creator_name,
      capability_token:
        challengeData.capability_token || challengeSession?.challengeData?.capability_token,
      game_mode: challengeData.game_mode || challengeSession?.challengeData?.game_mode || "pinpoint",
      location_mode:
        challengeSession?.challengeData?.location_mode !== false && challengeData.location_mode !== false,
      date_mode:
        challengeSession?.challengeData?.date_mode !== false && challengeData.date_mode !== false,
      rounds_played: totalRoundsCount,
      total_rounds: totalRoundsCount,
      max_possible_score: totalRoundsCount * 10000,
      players: leaderboard,
      winners: winners.length > 0 ? winners : (finishedPlayers[0] ? [finishedPlayers[0].player_name] : []),
      is_settled: isSettled,
      is_concluded: isConcluded,
      current_player_name: challengeSession?.sessionPlayerName,
      round_history: challengeData.round_history || [],
      round_guesses: challengeData.round_guesses || [],
      config: challengeData.config || challengeSession?.challengeData?.config,
    };

    state.lastSummary = summary;
    if (summary.round_history && (!state.roundHistory || state.roundHistory.length === 0)) {
      state.roundHistory = summary.round_history;
    }

    if (matchId) {
      try {
        const replayRes = await fetch(`/api/match/${encodeURIComponent(matchId)}/replay`);
        if (replayRes.ok) {
          replayData = await replayRes.json();
          _currentMatchData = replayData;
        }
      } catch (_) {}
    }

    if (playFanfare) {
      playVictoryFanfare();
    }

    // Always show All-Time Leaderboard Card in both game reviews
    if (el.leaderboardCard) {
      el.leaderboardCard.classList.remove("hidden");
      await loadLeaderboard();
    }
  } else {
    // Mode: Local Match Summary
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

      // Load replay data for the review deck
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

      // Always show All-Time Leaderboard Card in both game reviews
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

  // Render Outcome Hero (Podium / Provisional, Standings Table, Awards)
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

import { state, el, saveActiveMatchSession, clearActiveMatchSession } from "../state.js";
import { api } from "../api.js";
import { t } from "../i18n.js";
import { formatPlace, refreshRoundMeta } from "../formatters.js";
import { updateSubmitState } from "../maps.js";
import { markShortcutCooldown } from "../shortcuts.js";
import { navigate } from "../router.js";
import { getActiveMode } from "../modes/index.js";
import { showCard } from "./common.js";
import { loadQuestion } from "./game.js";
import { challenge } from "../challenge/index.js";

export async function showRoundReveal(roundNumber) {
  const reveal = await api("/api/round/result", {
    method: "POST",
    body: JSON.stringify({ match_id: state.matchId, round_number: roundNumber }),
  });

  const existingIdx = state.roundHistory.findIndex((r) => r.round_number === reveal.round_number);
  const pr = reveal.pinpoint_reveal;
  const entry = {
    round_number: reveal.round_number,
    asset_id: pr?.asset_id || (state.currentQuestion ? state.currentQuestion.asset_id : null),
    media_url: pr?.media_url || reveal.media_url || (state.currentQuestion ? state.currentQuestion.media_url : null),
    actual_latitude: pr?.actual_latitude ?? null,
    actual_longitude: pr?.actual_longitude ?? null,
    actual_date: pr?.actual_date ?? null,
    actual_year: pr?.actual_year ?? null,
    actual_month: pr?.actual_month ?? null,
    actual_city: pr?.actual_city ?? null,
    actual_country: pr?.actual_country ?? null,
    location_string: formatPlace(pr || reveal),
    results: reveal.results,
    pinpoint_reveal: pr || null,
    batch_reveal: reveal.batch_reveal || null,
    location_mode: reveal.location_mode,
  };
  if (existingIdx >= 0) {
    state.roundHistory[existingIdx] = entry;
  } else {
    state.roundHistory.push(entry);
  }

  if (state.currentQuestion) {
    if (state.currentQuestion.asset_id && !state.playedAssetIds.includes(state.currentQuestion.asset_id)) {
      state.playedAssetIds.push(state.currentQuestion.asset_id);
    }
    if (state.currentQuestion.batch_photos) {
      for (const p of state.currentQuestion.batch_photos) {
        if (p.photo_id && !state.playedAssetIds.includes(p.photo_id)) {
          state.playedAssetIds.push(p.photo_id);
        }
      }
    }
  }

  state.lastReveal = reveal;
  state.currentScreen = "reveal";
  showCard(el.gameCard);
  if (el.leaderboardCard) {
    el.leaderboardCard.classList.add("hidden");
  }
  if (!challenge || !challenge.isActive()) {
    if (el.revealRestartBtn) el.revealRestartBtn.classList.remove("hidden");
  }
  el.guessingUi.classList.add("hidden");
  el.revealUi.classList.remove("hidden");

  if (reveal.game_mode) {
    state.gameMode = reveal.game_mode;
  }
  const activeMode = getActiveMode();
  activeMode.renderReveal(el.revealUi, reveal);

  if (el.nextRound) {
    el.nextRound.textContent = reveal.match_finished ? t("reveal.see_results_btn") : t("reveal.next_round_btn");
  }

  const targetScrollEl =
    reveal.game_mode === "album_shuffle"
      ? (document.querySelector(".shuffle-breakdown-container") || el.nextRound)
      : (reveal.location_mode ? el.revealMapShell : el.nextRound);
  if (targetScrollEl && targetScrollEl.offsetParent !== null) {
    targetScrollEl.scrollIntoView({ behavior: "smooth", block: "center" });
  }
  saveActiveMatchSession();
  markShortcutCooldown(20);
}

export async function handleNextRound() {
  if (challenge && challenge.isActive()) {
    return challenge.handleNextRound();
  }
  if (state.submitting) {
    return;
  }
  state.submitting = true;
  updateSubmitState();

  try {
    state.currentScreen = null;
    state.lastReveal = null;
    state.passConfirmed = false;
    state.timerEndTimeMs = null;
    state.timerTotalSeconds = null;
    saveActiveMatchSession();

    if (state.matchFinished) {
      state.justFinishedMatch = true;
      clearActiveMatchSession();
      navigate(`/game/${encodeURIComponent(state.matchId)}/summary`, { force: true });
      return;
    }
    showCard(el.gameCard);
    if (el.revealUi) el.revealUi.classList.add("hidden");
    if (el.guessingUi) el.guessingUi.classList.remove("hidden");
    await loadQuestion();
  } finally {
    state.submitting = false;
    updateSubmitState();
  }
}

export function refreshRevealLanguage() {
  const isRevealVisible = el.revealUi && !el.revealUi.classList.contains("hidden");
  const revealData = state.lastReveal || (challenge && challenge.challengeSession?.currentRevealData);
  if ((state.currentScreen === "reveal" || isRevealVisible) && revealData) {
    const activeMode = getActiveMode();
    activeMode?.refreshRevealText?.(el.revealUi, revealData);
    refreshRoundMeta(el.roundMeta);
    if (el.nextRound) {
      el.nextRound.textContent = revealData.match_finished || revealData.is_game_over
        ? t("reveal.see_results_btn")
        : t("reveal.next_round_btn");
    }
  }
}

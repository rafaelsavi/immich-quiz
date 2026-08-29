import { state, el, saveActiveMatchSession, clearActiveMatchSession } from "../state.js";
import { api } from "../api.js";
import { t } from "../i18n.js";
import { formatPlace } from "../formatters.js";
import { updateSubmitState } from "../maps.js";
import { markShortcutCooldown } from "../shortcuts.js";
import { navigate } from "../router.js";
import { getActiveMode } from "../modes/index.js";
import { showCard } from "./common.js";
import { loadQuestion } from "./game.js";

export async function showRoundReveal(roundNumber) {
  const reveal = await api("/api/round/result", {
    method: "POST",
    body: JSON.stringify({ match_id: state.matchId, round_number: roundNumber }),
  });

  const existingIdx = state.roundHistory.findIndex((r) => r.round_number === reveal.round_number);
  const entry = {
    round_number: reveal.round_number,
    asset_id: reveal.asset_id || (state.currentQuestion ? state.currentQuestion.asset_id : null),
    media_url: reveal.media_url || (state.currentQuestion ? state.currentQuestion.media_url : null),
    actual_latitude: reveal.actual_latitude,
    actual_longitude: reveal.actual_longitude,
    actual_date: reveal.actual_date,
    actual_year: reveal.actual_year,
    actual_month: reveal.actual_month,
    actual_city: reveal.actual_city,
    actual_country: reveal.actual_country,
    location_string: formatPlace(reveal),
    results: reveal.results,
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
  el.guessingUi.classList.add("hidden");
  el.revealUi.classList.remove("hidden");

  const activeMode = getActiveMode();
  activeMode.renderReveal(el.revealUi, reveal);

  if (el.nextRound) {
    el.nextRound.textContent = reveal.match_finished ? t("reveal.see_results_btn") : t("reveal.next_round_btn");
  }

  const targetScrollEl = reveal.location_mode ? el.revealMapShell : el.nextRound;
  if (targetScrollEl) {
    targetScrollEl.scrollIntoView({ behavior: "smooth", block: "center" });
  }
  saveActiveMatchSession();
  markShortcutCooldown(20);
}

export async function handleNextRound() {
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

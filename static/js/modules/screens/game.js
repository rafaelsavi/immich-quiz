import { state, el, saveActiveMatchSession, loadActiveMatchSession } from "../state.js";
import { api } from "../api.js";
import { t, showAlert } from "../i18n.js";
import { playSubmitTone } from "../audio.js";
import { updateSubmitState } from "../maps.js";
import { renderRoundMeta } from "../formatters.js";
import { clearTimer, resetTimerBar, startTimer } from "../timer.js";
import { markShortcutCooldown } from "../shortcuts.js";
import { getActiveMode } from "../modes/index.js";
import { showRoundReveal } from "./reveal.js";
import { challenge } from "../challenge.js";

export function updateRoundMeta() {
  const roundMeta = el.roundMeta;
  if (!roundMeta || !state.currentQuestion) return;
  const data = state.currentQuestion;
  renderRoundMeta(roundMeta, {
    roundNum: data.player_round_number,
    totalRounds: data.total_rounds_per_player,
    playerNum: data.player_number,
    totalPlayers: data.total_players,
    playerName: data.player_name,
    isReveal: false,
    showHelp: state.gameMode === "album_shuffle",
    onHelpClick: () => {
      const activeMode = getActiveMode();
      activeMode.openHelp?.(state.currentQuestion);
    },
  });
}

export function checkMediaLoadable(url) {
  return new Promise((resolve) => {
    if (!url) return resolve(true);
    const img = new Image();
    let settled = false;
    const timer = setTimeout(() => {
      if (!settled) {
        settled = true;
        img.onload = null;
        img.onerror = null;
        resolve(false);
      }
    }, 10000);
    img.onload = () => {
      if (!settled) {
        settled = true;
        clearTimeout(timer);
        resolve(true);
      }
    };
    img.onerror = () => {
      if (!settled) {
        settled = true;
        clearTimeout(timer);
        resolve(false);
      }
    };
    img.src = url;
  });
}

export async function fetchAndVerifyQuestion() {
  const currentMatchId = state.matchId;
  while (true) {
    if (state.matchId !== currentMatchId) {
      return null;
    }
    let data;
    try {
      data = await api("/api/question", {
        method: "POST",
        body: JSON.stringify({
          match_id: state.matchId,
          played_asset_ids: state.playedAssetIds,
        }),
      });
    } catch (err) {
      if (
        err.message &&
        (err.message.includes("No eligible assets") || err.message.includes("404"))
      ) {
        return null;
      }
      throw err;
    }

    if (state.matchId !== currentMatchId) {
      return null;
    }

    const photosToTest = [];
    if (data.batch_photos && data.batch_photos.length > 0) {
      for (const p of data.batch_photos) {
        photosToTest.push({ id: p.photo_id, url: p.media_url });
      }
    } else if (data.media_url) {
      photosToTest.push({ id: data.asset_id, url: data.media_url });
    }

    const results = await Promise.all(
      photosToTest.map(async (photo) => ({
        id: photo.id,
        ok: await checkMediaLoadable(photo.url),
      }))
    );

    if (state.matchId !== currentMatchId) {
      return null;
    }

    const failed = results.filter((r) => !r.ok);
    if (failed.length === 0) {
      return data;
    }

    console.warn(
      `[Media Verification] Failed to load ${failed.length} ${failed.length === 1 ? "photo" : "photos"} [${failed.map((f) => f.id).join(", ")}]. Requesting replacement photo from server...`
    );

    for (const f of failed) {
      if (f.id && !state.playedAssetIds.includes(f.id)) {
        state.playedAssetIds.push(f.id);
      }
    }
  }
}

export function computeEffectiveRemainingSeconds(questionData, session) {
  if (!questionData) return null;
  if (
    session &&
    session.activeQuestionId === questionData.question_id &&
    session.passConfirmed &&
    session.timerEndTimeMs
  ) {
    return Math.max(0, (session.timerEndTimeMs - Date.now()) / 1000);
  }
  return null;
}

export async function loadQuestion() {
  const matchId = state.matchId;
  if (!matchId) return;

  resetTimerBar();
  state.guessedLatLng = null;
  state.timedOut = false;
  state.currentQuestion = null;

  if (el.revealUi) el.revealUi.classList.add("hidden");
  if (el.guessingUi) el.guessingUi.classList.remove("hidden");
  if (!challenge || !challenge.isActive()) {
    if (el.gameRestartBtn) el.gameRestartBtn.classList.remove("hidden");
  }
  if (el.roundMeta) el.roundMeta.replaceChildren();

  if (el.quizImage) {
    el.quizImage.classList.add("hidden");
    el.quizImage.removeAttribute("src");
    el.quizImage.onerror = null;
  }
  if (el.quizImageFullscreen) {
    el.quizImageFullscreen.classList.add("hidden");
  }
  if (el.mediaPlaceholder) el.mediaPlaceholder.classList.remove("hidden");

  el.submitAnswer.textContent = t("game.submit_btn");
  getActiveMode()?.setDisabled?.(false);
  updateSubmitState();

  const data = await fetchAndVerifyQuestion();

  if (state.matchId !== matchId) {
    return;
  }

  if (!data) {
    state.timedOut = true;
    showAlert("No eligible photos available. Round accepted.");
    await submitAnswer(true);
    return;
  }

  state.currentQuestion = data;
  state.gameMode = data.game_mode || "pinpoint";
  updateRoundMeta();

  const activeMode = getActiveMode();
  activeMode.renderQuestion(data);
  el.guessingUi.classList.remove("hidden");
  el.revealUi.classList.add("hidden");
  window.scrollTo({ top: 0, behavior: "smooth" });
  updateSubmitState();

  const session = loadActiveMatchSession();
  const remainingSeconds = computeEffectiveRemainingSeconds(data, session);

  const alreadyConfirmed = Boolean(
    session && session.activeQuestionId === data.question_id && session.passConfirmed
  );

  if (data.total_players > 1 && !alreadyConfirmed) {
    state.currentScreen = "pass_device";
    state.passConfirmed = false;
    state.timerEndTimeMs = null;
    state.timerTotalSeconds = null;
    el.overlayTitle.textContent = t(
      "game.pass_device_title",
      data.player_name,
      data.player_number,
      data.total_players
    );
    el.overlaySubtitle.textContent = t("game.pass_device_subtitle", data.player_round_number, data.total_rounds_per_player);
    el.passOverlay.classList.remove("hidden");
    saveActiveMatchSession();
  } else {
    state.currentScreen = "guessing";
    state.passConfirmed = true;
    el.passOverlay.classList.add("hidden");
    activeMode.onReady(data);
    startTimer(data.round_length, getActiveMode, remainingSeconds);
    saveActiveMatchSession();
  }
  markShortcutCooldown(20);
}

export async function submitAnswer(fromTimeout = false) {
  if (challenge && challenge.isActive()) {
    return challenge.submitAnswer(fromTimeout);
  }
  if (!state.currentQuestion || state.submitting) {
    return;
  }
  state.submitting = true;
  updateSubmitState();
  playSubmitTone();

  try {
    const question = state.currentQuestion;
    const playerName = question ? question.player_name : null;
    const totalSec = state.timerTotalSeconds || 0;
    const remainingSec = state.timerRemainingSeconds || 0;
    const elapsedSec = fromTimeout ? totalSec : Math.max(0, totalSec - remainingSec);

    if (playerName && totalSec > 0) {
      if (!state.playerStats[playerName]) {
        state.playerStats[playerName] = {
          totalDistanceKm: 0,
          distanceCount: 0,
          totalDateDiffDays: 0,
          dateCount: 0,
          perfectLocationCount: 0,
          perfectDateCount: 0,
          perfectRounds: 0,
          timedOutCount: 0,
          fastRoundCount: 0,
          totalDurationSec: 0,
        };
      }
      state.playerStats[playerName].totalDurationSec = (state.playerStats[playerName].totalDurationSec || 0) + elapsedSec;
      if (!fromTimeout && elapsedSec <= totalSec / 2) {
        state.playerStats[playerName].fastRoundCount = (state.playerStats[playerName].fastRoundCount || 0) + 1;
      }
    }

    const activeMode = getActiveMode();
    const payload = activeMode.buildAnswerPayload(question, fromTimeout);
    payload.time_taken_seconds = elapsedSec;

    const result = await api("/api/answer", {
      method: "POST",
      body: JSON.stringify(payload),
    });

    clearTimer();
    state.passConfirmed = false;
    state.timerEndTimeMs = null;
    state.timerTotalSeconds = null;
    state.matchFinished = result.match_finished;

    if (result.round_complete) {
      await showRoundReveal(result.round_number);
      return;
    }

    await loadQuestion();
  } finally {
    state.submitting = false;
    updateSubmitState();
  }
}

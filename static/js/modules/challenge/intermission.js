/**
 * Challenge Post-Game Intermission ("Invite Friends" Screen).
 *
 * Displays the invitation screen with QR code, link copying, and 3-second live
 * polling of the finished participant count before advancing to the Grand Reveal.
 */

import { api } from "../api.js";
import { state, el } from "../state.js";
import { t } from "../i18n.js";
import { showCard } from "../screens/common.js";
import { renderShareUrlContainerHtml, setupShareBox } from "../components/share_box.js";
import { challengeSession, POLL_INTERVAL_MS } from "./session.js";

export const challengeIntermission = {
  /**
   * "Invite Friends" intermission shown after the final round.
   * @param {Function} onSeeResults Callback to show Grand Reveal summary
   */
  renderInviteFriendsScreen(onSeeResults) {
    challengeSession.stopPolling();
    challengeSession.cleanupMaps();
    state.currentScreen = null;
    state.currentQuestion = null;
    challengeSession.lastRoundResult = null;

    if (!el.challengeCard) return;
    showCard(el.challengeCard);
    window.scrollTo({ top: 0, behavior: "smooth" });

    const playUrl = `${window.location.origin}/play/${challengeSession.challengeData.capability_token}`;

    el.challengeCard.innerHTML = `
      <div class="challenge-invite">
        <div class="challenge-invite-header">
          <h2>🎉 ${t("challenge.finished_title")}</h2>
          <p>${t("challenge.invite_message")}</p>
        </div>

        <div class="challenge-share-box">
          ${renderShareUrlContainerHtml(playUrl, { prefix: "challenge-invite" })}
        </div>

        <div class="challenge-invite-counter" id="challenge-finisher-count">
          <span class="live-poll-dot"></span>
          <span id="finisher-count-text">${t("challenge.loading_count")}</span>
        </div>

        <button type="button" class="btn btn-large btn-primary" id="challenge-see-results-btn">
          ${t("challenge.see_results")}
        </button>
      </div>
    `;

    // Initialize standardized share box component
    setupShareBox(el.challengeCard, playUrl, {
      prefix: "challenge-invite",
      title: t("challenge.invite_message"),
      qrSize: 180,
    });

    // See results handler
    document.getElementById("challenge-see-results-btn")?.addEventListener("click", () => {
      if (onSeeResults) {
        onSeeResults();
      }
    });

    this.startFinisherPolling();
  },

  /**
   * Poll for finished player count on invite screen.
   */
  startFinisherPolling() {
    challengeSession.stopPolling();

    const poll = async () => {
      if (!challengeSession.challengeData) return;
      try {
        const data = await api(
          `/play/api/${encodeURIComponent(challengeSession.challengeData.capability_token)}/leaderboard`,
          {
            headers: {
              "X-Player-Token": challengeSession.sessionToken,
            },
          }
        );
        challengeSession.cachedLeaderboardData = data;
        const totalRounds = data.total_rounds || challengeSession.totalRounds;
        const finishedCount = data.leaderboard.filter((e) => e.is_finished || e.completed_rounds >= totalRounds).length;
        const friendsCount = challengeSession.sessionPlayerName
          ? data.leaderboard.filter((e) => (e.is_finished || e.completed_rounds >= totalRounds) && e.player_name !== challengeSession.sessionPlayerName).length
          : Math.max(0, finishedCount - 1);
        const countTextEl = document.getElementById("finisher-count-text");
        const counterWrapEl = document.getElementById("challenge-finisher-count");
        if (countTextEl) {
          const newText = t("challenge.finisher_count", friendsCount);
          if (counterWrapEl && countTextEl.textContent && countTextEl.textContent !== newText && countTextEl.textContent !== t("challenge.loading_count")) {
            counterWrapEl.classList.remove("bump");
            void counterWrapEl.offsetWidth;
            counterWrapEl.classList.add("bump");
          }
          countTextEl.textContent = newText;
        }
      } catch (err) {
        console.warn("Finisher polling error:", err);
      }
    };

    poll();
    challengeSession.pollingInterval = setInterval(poll, POLL_INTERVAL_MS);
  },
};

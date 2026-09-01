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
import { renderQRCode } from "../components/qrcode.js";
import { copyToClipboard } from "../summary/share.js";
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

        <div class="challenge-share-box" style="flex-direction: column; gap: 0.65rem;">
          <div class="share-link-box" id="challenge-invite-link-box" title="Click to copy link">
            <span class="share-link-icon" aria-hidden="true">🔗</span>
            <input type="text" readonly value="${playUrl}" id="challenge-share-url" class="share-url-input" spellcheck="false" autocomplete="off" />
          </div>
          <div class="share-action-buttons" style="display: flex; gap: 0.65rem; width: 100%;">
            <button type="button" class="btn-primary btn-copy-link" id="challenge-copy-btn">
              📋 ${t("challenge.copy_link")}
            </button>
            <button type="button" class="btn-secondary btn-qr-code" id="challenge-invite-qr-btn" title="${t("challenge.qr_code_title")}" aria-expanded="false" aria-controls="challenge-invite-qr-container">
              📱 ${t("challenge.qr_code")}
            </button>
          </div>
        </div>

        <div id="challenge-invite-qr-container" class="challenge-qr-container hidden" aria-hidden="true" style="margin-bottom: 1.5rem;">
          <div class="challenge-qr-card">
            <div id="challenge-invite-qr-code" class="challenge-qr-display"></div>
            <p class="qr-scan-hint">${t("challenge.scan_qr_hint")}</p>
          </div>
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

    // QR code setup & handler
    const inviteQrBtn = document.getElementById("challenge-invite-qr-btn");
    const inviteQrContainer = document.getElementById("challenge-invite-qr-container");
    const inviteQrCode = document.getElementById("challenge-invite-qr-code");

    if (inviteQrCode) {
      renderQRCode(inviteQrCode, playUrl, { size: 180 });
    }

    if (inviteQrBtn && inviteQrContainer) {
      inviteQrBtn.addEventListener("click", () => {
        const isHidden = inviteQrContainer.classList.toggle("hidden");
        inviteQrBtn.classList.toggle("active", !isHidden);
        inviteQrBtn.setAttribute("aria-expanded", String(!isHidden));
        inviteQrContainer.setAttribute("aria-hidden", String(isHidden));
      });
    }

    // Copy link handler
    const copyAction = async () => {
      const btn = document.getElementById("challenge-copy-btn");
      const input = document.getElementById("challenge-share-url");
      if (input) input.select();
      await copyToClipboard(playUrl, {
        button: btn,
        copiedText: `✅ ${t("challenge.link_copied")}`,
      });
    };

    document.getElementById("challenge-copy-btn")?.addEventListener("click", copyAction);
    document.getElementById("challenge-invite-link-box")?.addEventListener("click", copyAction);

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
      if (document.hidden || !challengeSession.challengeData) return;
      try {
        const data = await api(
          `/api/challenge/${encodeURIComponent(challengeSession.challengeData.capability_token)}/leaderboard`,
          {
            headers: {
              "X-Player-Token": challengeSession.sessionToken,
            },
          }
        );
        challengeSession.cachedLeaderboardData = data;
        const finishedCount = data.leaderboard.filter((e) => e.is_finished).length;
        const friendsCount = challengeSession.sessionPlayerName
          ? data.leaderboard.filter((e) => e.is_finished && e.player_name !== challengeSession.sessionPlayerName).length
          : Math.max(0, finishedCount - 1);
        const countTextEl = document.getElementById("finisher-count-text");
        if (countTextEl) {
          countTextEl.textContent = t("challenge.finisher_count", friendsCount);
        }
      } catch (err) {
        console.warn("Finisher polling error:", err);
      }
    };

    poll();
    challengeSession.pollingInterval = setInterval(poll, POLL_INTERVAL_MS);
  },
};

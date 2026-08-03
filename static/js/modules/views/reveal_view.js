import { state, el } from "../state.js";
import { t } from "../i18n.js";
import { playChime, playVictoryFanfare } from "../audio.js";
import { launchGoldConfetti } from "../effects.js";

/**
 * Controller for the Round Reveal View.
 */
export const revealView = {
  init({ onNextRound }) {
    this.onNextRound = onNextRound;
    this.bindEvents();
  },

  bindEvents() {
    if (el.nextRoundBtn) {
      el.nextRoundBtn.addEventListener("click", () => {
        if (this.onNextRound) this.onNextRound();
      });
    }
  },

  renderRevealHeader(roundResult) {
    if (el.revealRoundTitle) {
      el.revealRoundTitle.textContent = t("reveal.round_title", roundResult.round_number);
    }
  },

  handleEffects(roundResult) {
    const isLastRound = roundResult.round_number >= roundResult.total_rounds;
    if (isLastRound) {
      playVictoryFanfare();
      launchGoldConfetti();
    } else {
      playChime();
    }
  },
};

import { state, el } from "../state.js";
import { t, showAlert } from "../i18n.js";
import { updateSubmitState } from "../maps.js";
import { playSubmitTone } from "../audio.js";

/**
 * Controller for the Active Question / Turn View.
 */
export const gameView = {
  init({ onSubmitAnswer }) {
    this.onSubmitAnswer = onSubmitAnswer;
    this.bindEvents();
  },

  bindEvents() {
    if (el.submitAnswer) {
      el.submitAnswer.addEventListener("click", () => this.handleSubmitClick());
    }
  },

  renderHeader(questionData) {
    if (el.hudLibraryName) {
      el.hudLibraryName.textContent = questionData.album_name
        ? `${questionData.library_name} — ${questionData.album_name}`
        : questionData.library_name;
    }
    if (el.hudPlayerTurn) {
      el.hudPlayerTurn.textContent = questionData.player_name;
    }
    if (el.hudRoundProgress) {
      el.hudRoundProgress.textContent = `${questionData.player_round_number}/${questionData.total_rounds_per_player}`;
    }
  },

  async handleSubmitClick() {
    if (state.submitting) return;

    if (!state.timedOut && el.submitAnswer.disabled) {
      return;
    }

    playSubmitTone();
    state.submitting = true;
    updateSubmitState();

    if (this.onSubmitAnswer) {
      await this.onSubmitAnswer();
    }
  },
};

import { state, el } from "./state.js";

export function activeActionButton() {
  if (state.submitting) {
    return null;
  }
  if (el.passOverlay && !el.passOverlay.classList.contains("hidden")) {
    return el.readyBtn;
  }
  if (el.gameCard && !el.gameCard.classList.contains("hidden")) {
    if (el.guessingUi && !el.guessingUi.classList.contains("hidden")) {
      return el.submitAnswer;
    }
    if (el.revealUi && !el.revealUi.classList.contains("hidden")) {
      const activeNextBtn = document.querySelector(
        "#reveal-ui button#next-round:not(.hidden), #album-shuffle-reveal-ui button.next-round-btn:not(.hidden)"
      );
      return activeNextBtn || el.nextRound;
    }
  }
  return null;
}

export function bindGlobalShortcuts() {
  document.addEventListener("keydown", (event) => {
    if ((event.key !== "Enter" && event.key !== " ") || event.isComposing) {
      return;
    }
    if (event.ctrlKey || event.altKey || event.metaKey || event.shiftKey) {
      return;
    }

    const target = event.target;
    if (
      target instanceof HTMLButtonElement ||
      target instanceof HTMLInputElement ||
      target instanceof HTMLSelectElement ||
      target instanceof HTMLTextAreaElement
    ) {
      return;
    }
    if (target instanceof HTMLElement && target.closest("#setup-card")) {
      return;
    }

    const button = activeActionButton();
    if (!button || button.disabled) {
      return;
    }
    event.preventDefault();
    button.click();
  });
}

import { state, el } from "./state.js";

let cooldownUntil = 0;
const DEFAULT_COOLDOWN_MS = 20;

export function markShortcutCooldown(durationMs = DEFAULT_COOLDOWN_MS) {
  cooldownUntil = Math.max(cooldownUntil, Date.now() + durationMs);
}

export function activeActionButton() {
  if (state.submitting || state.startingMatch || Date.now() < cooldownUntil) {
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
      return el.nextRound && !el.nextRound.classList.contains("hidden") ? el.nextRound : null;
    }
  }
  return null;
}

export function bindGlobalShortcuts(actions = {}) {
  document.addEventListener("keydown", (event) => {
    if (event.repeat || event.isComposing) {
      return;
    }
    if (event.ctrlKey || event.altKey || event.metaKey) {
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
    if (document.querySelector(".modal-overlay:not(.hidden)")) {
      return;
    }

    if (Date.now() < cooldownUntil) {
      return;
    }

    const key = event.key;

    if (key === "Enter" || key === " ") {
      if (event.shiftKey) return;
      const button = activeActionButton();
      if (!button || button.disabled) {
        return;
      }
      markShortcutCooldown(DEFAULT_COOLDOWN_MS);
      event.preventDefault();
      button.click();
      return;
    }

    if (event.shiftKey) {
      return;
    }

    // 'm' / 'M': Toggle map fullscreen
    if (key === "m" || key === "M") {
      event.preventDefault();
      actions.onToggleFullscreen?.();
      return;
    }

    // 'f' / 'F': Toggle photo fullscreen / lightbox
    if (key === "f" || key === "F") {
      event.preventDefault();
      actions.onTogglePhotoFullscreen?.();
      return;
    }

    // Number keys 1-9 for photo slot selection in Album Shuffle
    if (key >= "1" && key <= "9") {
      const slotIndex = parseInt(key, 10) - 1;
      actions.onSelectPhotoSlot?.(slotIndex);
      return;
    }

    // Letter keys A-E for pin assignment in Album Shuffle
    if (key.length === 1 && /^[a-eA-E]$/.test(key)) {
      actions.onAssignPin?.(key.toUpperCase());
      return;
    }
  });
}

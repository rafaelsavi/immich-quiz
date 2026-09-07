/**
 * Focus Trap Utility for Accessible Modal Dialogs.
 * Traps Tab / Shift+Tab keyboard navigation within the active modal dialog
 * and restores focus to the triggering element upon closure.
 */

const FOCUSABLE_SELECTOR = [
  'a[href]',
  'button:not([disabled])',
  'input:not([disabled])',
  'select:not([disabled])',
  'textarea:not([disabled])',
  '[tabindex]:not([tabindex="-1"])',
].join(', ');

let _activeTrap = null;

/**
 * Activate a focus trap on a container element.
 * @param {HTMLElement} containerEl - The modal or dialog container.
 * @param {HTMLElement|null} [initialFocusEl] - Optional specific element to receive initial focus.
 */
export function activateFocusTrap(containerEl, initialFocusEl = null) {
  if (!containerEl) return;

  // Deactivate any existing trap first
  deactivateFocusTrap();

  const previouslyFocused = document.activeElement;

  function getFocusableElements() {
    return Array.from(containerEl.querySelectorAll(FOCUSABLE_SELECTOR)).filter(
      (el) => el.offsetParent !== null || el.offsetWidth > 0 || el.offsetHeight > 0
    );
  }

  function handleKeyDown(event) {
    if (event.key !== 'Tab') return;

    const focusable = getFocusableElements();
    if (focusable.length === 0) {
      event.preventDefault();
      return;
    }

    const firstEl = focusable[0];
    const lastEl = focusable[focusable.length - 1];

    if (event.shiftKey) {
      if (document.activeElement === firstEl || !containerEl.contains(document.activeElement)) {
        event.preventDefault();
        lastEl.focus();
      }
    } else {
      if (document.activeElement === lastEl || !containerEl.contains(document.activeElement)) {
        event.preventDefault();
        firstEl.focus();
      }
    }
  }

  containerEl.addEventListener('keydown', handleKeyDown);

  // Set initial focus
  requestAnimationFrame(() => {
    if (initialFocusEl && containerEl.contains(initialFocusEl)) {
      initialFocusEl.focus();
    } else {
      const focusable = getFocusableElements();
      if (focusable.length > 0) {
        focusable[0].focus();
      }
    }
  });

  _activeTrap = {
    containerEl,
    handleKeyDown,
    previouslyFocused,
  };
}

/**
 * Deactivate the currently active focus trap and restore previous focus.
 */
export function deactivateFocusTrap() {
  if (!_activeTrap) return;

  const { containerEl, handleKeyDown, previouslyFocused } = _activeTrap;
  containerEl.removeEventListener('keydown', handleKeyDown);

  if (previouslyFocused && typeof previouslyFocused.focus === 'function') {
    if (document.body.contains(previouslyFocused)) {
      previouslyFocused.focus();
    }
  }

  _activeTrap = null;
}

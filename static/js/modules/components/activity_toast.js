/**
 * Activity Toast Component for Multiplayer Challenge Live Updates.
 * Displays floating glassmorphism notifications when opponents submit answers or finish rounds.
 */

import { playerInitial, playerColor } from "../formatters.js";

let _containerEl = null;

function getToastContainer() {
  if (!_containerEl || !document.body.contains(_containerEl)) {
    _containerEl = document.querySelector(".activity-toast-container");
    if (!_containerEl) {
      _containerEl = document.createElement("div");
      _containerEl.className = "activity-toast-container";
      _containerEl.setAttribute("aria-live", "polite");
      _containerEl.setAttribute("aria-atomic", "true");
      document.body.appendChild(_containerEl);
    }
  }
  return _containerEl;
}

/**
 * Show a floating activity toast for live challenge events.
 *
 * @param {object} options
 * @param {string} [options.icon] - Emoji icon prefix (e.g. "✨", "🎉")
 * @param {string} options.playerName - Name of the active player
 * @param {string} [options.playerColor] - Explicit color hex/hsl (defaults to registered player color)
 * @param {string} options.title - Main message text
 * @param {string} [options.subtitle] - Secondary details line
 * @param {number|string} [options.score] - Optional round or total score to highlight (+XXX)
 * @param {number} [options.durationMs=3800] - Duration in ms before auto-dismissal
 * @returns {HTMLElement} Toast element
 */
export function showActivityToast({
  icon = "✨",
  playerName,
  playerColor: customColor = null,
  title,
  subtitle = null,
  score = null,
  durationMs = 3800,
}) {
  const container = getToastContainer();

  // Cap visible toasts to prevent vertical overflow on rapid polling
  while (container.children.length >= 3) {
    container.firstElementChild?.remove();
  }

  const color = customColor || playerColor(playerName);
  const initial = playerInitial(playerName);

  const toast = document.createElement("div");
  toast.className = "activity-toast";
  toast.style.setProperty("--toast-accent", color);

  toast.innerHTML = `
    <div class="activity-toast-leading">
      <span class="activity-toast-icon" aria-hidden="true">${icon}</span>
      <span class="activity-toast-avatar" style="background: ${color};" aria-hidden="true">${initial}</span>
    </div>
    <div class="activity-toast-body">
      <div class="activity-toast-title">${title}</div>
      ${subtitle ? `<div class="activity-toast-subtitle">${subtitle}</div>` : ""}
    </div>
    ${score !== null && score !== undefined ? `<span class="activity-toast-score font-bold">+${score}</span>` : ""}
  `;

  container.appendChild(toast);

  // Trigger entrance transition
  requestAnimationFrame(() => {
    toast.classList.add("show");
  });

  const dismissTimer = setTimeout(() => {
    toast.classList.remove("show");
    toast.classList.add("hide");
    setTimeout(() => {
      if (toast.parentNode) {
        toast.remove();
      }
    }, 320);
  }, durationMs);

  // Allow clicking toast to dismiss immediately
  toast.addEventListener("click", () => {
    clearTimeout(dismissTimer);
    toast.classList.remove("show");
    toast.classList.add("hide");
    setTimeout(() => toast.remove(), 200);
  });

  return toast;
}

/**
 * Clear all currently visible activity toasts.
 */
export function clearActivityToasts() {
  if (_containerEl) {
    _containerEl.replaceChildren();
  }
}

import { t } from "../i18n.js";

/**
 * Standard GameMode Interface specification.
 * Both pinpointMode and albumShuffleMode must implement all of the following:
 * 
 * @typedef {Object} GameMode
 * @property {string} name - Unique mode identifier ("pinpoint", "album_shuffle")
 * @property {function(HTMLElement): void} renderSettings - Render mode settings cards into setup container
 * @property {function(): Object} getModePayload - Get mode setup payload properties
 * @property {function(HTMLElement, Object): void} mount - Lifecycle hook: called once when a match starts
 * @property {function(): void} unmount - Lifecycle hook: called once when match finishes, resets, or is abandoned
 * @property {function(Object): void} renderQuestion - Render round guessing UI (host captured via mount)
 * @property {function(Object, boolean): Object} buildAnswerPayload - Build payload for answer submission
 * @property {function(HTMLElement, Object): void} renderReveal - Render round reveal view
 * @property {function(Object): void} openHelp - Open mode help modal
 * @property {function(Object): void} onReady - Triggered on player ready / single-player round start
 */

/**
 * Renders multi-selection card buttons for Guessing mode (Location & Date).
 * Used across game modes (Pinpoint, Album Shuffle).
 * @param {HTMLElement} containerEl 
 */
export function renderGuessingModeSettings(containerEl) {
  containerEl.replaceChildren();

  const cardsWrap = document.createElement("div");
  cardsWrap.className = "mode-buttons guess-mode-buttons";

  // Location Card
  const locCard = document.createElement("button");
  locCard.type = "button";
  locCard.className = "mode-btn multi-select active";
  locCard.id = "card-goal-location";

  const locCheckbox = document.createElement("input");
  locCheckbox.type = "checkbox";
  locCheckbox.id = "goal-location";
  locCheckbox.checked = true;
  locCheckbox.className = "hidden";

  const locTitle = document.createElement("span");
  locTitle.className = "mode-title";
  locTitle.setAttribute("data-i18n", "setup.goal_location");
  locTitle.textContent = t("setup.goal_location");

  const locDesc = document.createElement("span");
  locDesc.className = "mode-desc";
  locDesc.setAttribute("data-i18n", "mode.goal_location_desc");
  locDesc.textContent = t("mode.goal_location_desc");

  locCard.append(locCheckbox, locTitle, locDesc);

  // Date Card
  const dateCard = document.createElement("button");
  dateCard.type = "button";
  dateCard.className = "mode-btn multi-select active";
  dateCard.id = "card-goal-date";

  const dateCheckbox = document.createElement("input");
  dateCheckbox.type = "checkbox";
  dateCheckbox.id = "goal-date";
  dateCheckbox.checked = true;
  dateCheckbox.className = "hidden";

  const dateTitle = document.createElement("span");
  dateTitle.className = "mode-title";
  dateTitle.setAttribute("data-i18n", "setup.goal_date");
  dateTitle.textContent = t("setup.goal_date");

  const dateDesc = document.createElement("span");
  dateDesc.className = "mode-desc";
  dateDesc.setAttribute("data-i18n", "mode.goal_date_desc");
  dateDesc.textContent = t("mode.goal_date_desc");

  dateCard.append(dateCheckbox, dateTitle, dateDesc);

  // Toggle handler enforcing at least 1 selected mode
  const toggleCard = (card, checkbox, otherCheckbox) => {
    if (checkbox.checked && !otherCheckbox.checked) {
      card.classList.add("shake-warning");
      setTimeout(() => card.classList.remove("shake-warning"), 400);
      return;
    }
    checkbox.checked = !checkbox.checked;
    card.classList.toggle("active", checkbox.checked);
    checkbox.dispatchEvent(new Event("change", { bubbles: true }));
  };

  locCard.addEventListener("click", () => toggleCard(locCard, locCheckbox, dateCheckbox));
  dateCard.addEventListener("click", () => toggleCard(dateCard, dateCheckbox, locCheckbox));

  cardsWrap.append(locCard, dateCard);
  containerEl.append(cardsWrap);
}

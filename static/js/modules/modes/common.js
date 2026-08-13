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
  const existingLocCheckbox = document.getElementById("goal-location");
  const existingDateCheckbox = document.getElementById("goal-date");
  const existingLocCard = document.getElementById("card-goal-location");
  const existingDateCard = document.getElementById("card-goal-date");

  let locActive = existingLocCheckbox ? existingLocCheckbox.checked : (existingLocCard ? existingLocCard.classList.contains("active") : true);
  let dateActive = existingDateCheckbox ? existingDateCheckbox.checked : (existingDateCard ? existingDateCard.classList.contains("active") : true);

  // Safeguard: Ensure at least one mode is active
  if (!locActive && !dateActive) {
    locActive = true;
  }

  containerEl.replaceChildren();

  const cardsWrap = document.createElement("div");
  cardsWrap.className = "mode-buttons guess-mode-buttons";

  // Location Card
  const locCard = document.createElement("button");
  locCard.type = "button";
  locCard.className = `mode-btn multi-select ${locActive ? "active" : ""}`;
  locCard.id = "card-goal-location";
  locCard.setAttribute("role", "checkbox");
  locCard.setAttribute("aria-checked", String(locActive));

  const locCheckbox = document.createElement("input");
  locCheckbox.type = "checkbox";
  locCheckbox.id = "goal-location";
  locCheckbox.checked = locActive;
  locCheckbox.className = "hidden";
  locCheckbox.tabIndex = -1;
  locCheckbox.setAttribute("aria-hidden", "true");
  locCheckbox.style.display = "none";

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
  dateCard.className = `mode-btn multi-select ${dateActive ? "active" : ""}`;
  dateCard.id = "card-goal-date";
  dateCard.setAttribute("role", "checkbox");
  dateCard.setAttribute("aria-checked", String(dateActive));

  const dateCheckbox = document.createElement("input");
  dateCheckbox.type = "checkbox";
  dateCheckbox.id = "goal-date";
  dateCheckbox.checked = dateActive;
  dateCheckbox.className = "hidden";
  dateCheckbox.tabIndex = -1;
  dateCheckbox.setAttribute("aria-hidden", "true");
  dateCheckbox.style.display = "none";

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
    const isCurrentlyChecked = checkbox.checked;
    if (isCurrentlyChecked && !otherCheckbox.checked) {
      card.classList.add("shake-warning");
      setTimeout(() => card.classList.remove("shake-warning"), 400);
      return;
    }
    const nextState = !isCurrentlyChecked;
    checkbox.checked = nextState;
    card.classList.toggle("active", nextState);
    card.setAttribute("aria-checked", String(nextState));
    checkbox.dispatchEvent(new Event("change", { bubbles: true }));
  };

  locCard.addEventListener("click", (e) => {
    e.preventDefault();
    toggleCard(locCard, locCheckbox, dateCheckbox);
  });
  dateCard.addEventListener("click", (e) => {
    e.preventDefault();
    toggleCard(dateCard, dateCheckbox, locCheckbox);
  });

  cardsWrap.append(locCard, dateCard);
  containerEl.append(cardsWrap);
}

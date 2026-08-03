import { t } from "../../i18n.js";

export function createShuffleHelpModal() {
  let modal = document.getElementById("album-shuffle-help-modal");
  if (modal) return modal;

  modal = document.createElement("div");
  modal.id = "album-shuffle-help-modal";
  modal.className = "shuffle-help-modal hidden";
  modal.innerHTML = `
    <div class="shuffle-help-dialog" role="dialog" aria-modal="true" aria-labelledby="shuffle-help-title">
      <div class="shuffle-help-header">
        <h3 id="shuffle-help-title">Album Shuffle Help</h3>
        <button type="button" class="shuffle-help-close" aria-label="Close help">×</button>
      </div>
      <div class="shuffle-help-body"></div>
    </div>
  `;

  document.body.appendChild(modal);

  const closeBtn = modal.querySelector(".shuffle-help-close");
  closeBtn.addEventListener("click", () => modal.classList.add("hidden"));

  modal.addEventListener("click", (event) => {
    if (event.target === modal) {
      modal.classList.add("hidden");
    }
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      modal.classList.add("hidden");
    }
  });

  return modal;
}

export function openShuffleHelpModal(questionData) {
  const modal = createShuffleHelpModal();
  const body = modal.querySelector(".shuffle-help-body");
  const locationMode = questionData?.location_mode !== false;
  const dateMode = questionData?.date_mode !== false;

  const sections = [];
  if (locationMode) {
    sections.push(`
      <div class="shuffle-help-section">
        <h4>${t("game.shuffle_help_location_title")}</h4>
        <ul>
          <li>${t("game.shuffle_help_location_item1")}</li>
          <li>${t("game.shuffle_help_location_item2")}</li>
          <li>${t("game.shuffle_help_location_item3")}</li>
          <li>${t("game.shuffle_help_location_item4")}</li>
        </ul>
      </div>
    `);
  }

  if (dateMode) {
    sections.push(`
      <div class="shuffle-help-section">
        <h4>${t("game.shuffle_help_date_title")}</h4>
        <ul>
          <li>${t("game.shuffle_help_date_item1")}</li>
          <li>${t("game.shuffle_help_date_item2")}</li>
          <li>${t("game.shuffle_help_date_item3")}</li>
        </ul>
      </div>
    `);
  }

  if (sections.length === 0) {
    sections.push(`
      <div class="shuffle-help-section">
        <p>${t("game.shuffle_help_fallback")}</p>
      </div>
    `);
  }

  body.innerHTML = `
    <p class="shuffle-help-intro">${t("game.shuffle_help_intro")}</p>
    ${sections.join("")}
    <p class="shuffle-help-footnote">${t("game.shuffle_help_footer")}</p>
  `;

  modal.classList.remove("hidden");
}

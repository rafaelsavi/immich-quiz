import { state, el } from "./state.js";
import { t } from "./i18n.js";
import { formatMonth, formatPlace } from "./formatters.js";
import { openPhotoLightbox } from "./components/lightbox.js";

/**
 * Renders the Polaroid memory card gallery on the match summary page.
 * @param {HTMLElement} galleryEl Container element
 * @param {Array} roundHistory List of completed round results
 */
export function renderPolaroidGallery(galleryEl, roundHistory) {
  if (!galleryEl) return;
  galleryEl.replaceChildren();

  const defaultLibrary = state.lastSummary
    ? state.lastSummary.library_name
    : state.currentQuestion
    ? state.currentQuestion.library_name
    : "";

  (roundHistory || []).forEach((round) => {
    if (round.batch_reveal && Array.isArray(round.batch_reveal) && round.batch_reveal.length > 0) {
      round.batch_reveal.forEach((item) => {
        const card = document.createElement("div");
        card.className = "polaroid-card";

        const imgWrap = document.createElement("div");
        imgWrap.className = "polaroid-img-wrap";

        const lib = round.library_name || defaultLibrary;
        const imgUrl = `/api/media/${item.photo_id}?library_name=${encodeURIComponent(lib)}`;
        const img = document.createElement("img");
        img.className = "polaroid-img";
        img.src = imgUrl;
        img.alt = `Round ${round.round_number} - Pin ${item.true_pin_id}`;
        img.style.cursor = "pointer";
        img.addEventListener("click", () => openPhotoLightbox(imgUrl));
        imgWrap.appendChild(img);

        const caption = document.createElement("div");
        caption.className = "polaroid-caption";

        const badge = document.createElement("span");
        badge.className = "polaroid-round-badge";
        badge.textContent = item.true_pin_id
          ? `${t("summary.journey_round", round.round_number)} - ${item.true_pin_id}`
          : t("summary.journey_round", round.round_number);

        const loc = document.createElement("span");
        loc.className = "polaroid-location";
        loc.textContent = formatPlace(item) || t("fmt.unknown_place");

        const date = document.createElement("span");
        date.className = "polaroid-date";
        date.textContent = formatMonth(item.actual_year, item.actual_month);

        caption.append(badge, loc, date);
        card.append(imgWrap, caption);
        galleryEl.appendChild(card);
      });
    } else {
      const card = document.createElement("div");
      card.className = "polaroid-card";

      const imgWrap = document.createElement("div");
      imgWrap.className = "polaroid-img-wrap";

      if (round.media_url) {
        const img = document.createElement("img");
        img.className = "polaroid-img";
        img.src = round.media_url;
        img.alt = `Round ${round.round_number}`;
        img.style.cursor = "pointer";
        img.addEventListener("click", () => openPhotoLightbox(round.media_url));
        imgWrap.appendChild(img);
      }

      const caption = document.createElement("div");
      caption.className = "polaroid-caption";

      const badge = document.createElement("span");
      badge.className = "polaroid-round-badge";
      badge.textContent = t("summary.journey_round", round.round_number);

      const loc = document.createElement("span");
      loc.className = "polaroid-location";
      loc.textContent = round.location_string || t("fmt.unknown_place");

      const date = document.createElement("span");
      date.className = "polaroid-date";
      date.textContent = formatMonth(round.actual_year, round.actual_month);

      caption.append(badge, loc, date);
      card.append(imgWrap, caption);
      galleryEl.appendChild(card);
    }
  });
}

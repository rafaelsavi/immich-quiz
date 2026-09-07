import { el } from "../state.js";
import { t } from "../i18n.js";
import { formatPlace, formatMonth } from "../formatters.js";
import { openPhotoLightbox } from "../components/lightbox.js";

export function renderPolaroidGallery(roundHistory, targetContainer = null) {
  const container = targetContainer || el.polaroidGallery;
  if (!container) return;
  container.replaceChildren();

  (roundHistory || []).forEach((round) => {
    if (round.batch_reveal && Array.isArray(round.batch_reveal) && round.batch_reveal.length > 0) {
      round.batch_reveal.forEach((item) => {
        const card = document.createElement("div");
        card.className = "polaroid-card";

        const imgWrap = document.createElement("div");
        imgWrap.className = "polaroid-img-wrap";

        const imgUrl = `/api/media/${item.photo_id}`;
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
        container.appendChild(card);
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
      loc.textContent = formatPlace(round) || t("fmt.unknown_place");

      const date = document.createElement("span");
      date.className = "polaroid-date";
      date.textContent = formatMonth(round.actual_year, round.actual_month);

      caption.append(badge, loc, date);
      card.append(imgWrap, caption);
      container.appendChild(card);
    }
  });
}

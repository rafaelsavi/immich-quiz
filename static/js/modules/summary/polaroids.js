import { el } from "../state.js";
import { t } from "../i18n.js";
import { formatPlace, formatMonth } from "../formatters.js";
import { openPhotoLightbox } from "../components/lightbox.js";

export function renderPolaroidGallery(roundHistory, targetContainer = null) {
  const container = targetContainer || el.polaroidGallery;
  if (!container) return;
  container.replaceChildren();

  (roundHistory || []).forEach((round) => {
    const batchList =
      round.batch_reveal && Array.isArray(round.batch_reveal) && round.batch_reveal.length > 0
        ? round.batch_reveal
        : round.batch_photos && Array.isArray(round.batch_photos) && round.batch_photos.length > 0
          ? round.batch_photos
          : null;

    if (batchList) {
      batchList.forEach((item) => {
        const card = document.createElement("div");
        card.className = "polaroid-card";

        const imgWrap = document.createElement("div");
        imgWrap.className = "polaroid-img-wrap";

        const imgUrl = item.media_url || `/api/media/${item.photo_id || item.asset_id}`;
        const img = document.createElement("img");
        img.className = "polaroid-img";
        img.src = imgUrl;
        img.alt = `Round ${round.round_number} - Pin ${item.true_pin_id || ""}`;
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

      const roundImgUrl = round.media_url || (round.asset_id ? `/api/media/${round.asset_id}` : "");
      if (roundImgUrl) {
        const img = document.createElement("img");
        img.className = "polaroid-img";
        img.src = roundImgUrl;
        img.alt = `Round ${round.round_number}`;
        img.style.cursor = "pointer";
        img.addEventListener("click", () => openPhotoLightbox(roundImgUrl));
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

/**
 * Photo Lightbox Component for Immich Quiz.
 *
 * Provides a modal fullscreen photo preview with escape key dismissal,
 * click-outside-to-dismiss, and accessibility attributes.
 */

import { t } from "../i18n.js";

/**
 * Open photo in fullscreen lightbox overlay.
 * @param {string} src Media image URL
 */
export function openPhotoLightbox(src) {
  let lightbox = document.getElementById("photo-lightbox");
  if (!lightbox) {
    lightbox = document.createElement("div");
    lightbox.id = "photo-lightbox";
    lightbox.className = "photo-lightbox-overlay";
    lightbox.innerHTML = `
      <div class="photo-lightbox-content">
        <button type="button" class="photo-lightbox-close" title="${t("game.close_btn")}" data-i18n-title="game.close_btn">&times;</button>
        <img id="photo-lightbox-img" src="" alt="${t("game.fullscreen_photo_alt")}" data-i18n-alt="game.fullscreen_photo_alt" />
      </div>
    `;
    document.body.appendChild(lightbox);

    const closeBtn = lightbox.querySelector(".photo-lightbox-close");
    closeBtn.addEventListener("click", () => lightbox.classList.remove("active"));
    lightbox.addEventListener("click", (e) => {
      if (e.target === lightbox) lightbox.classList.remove("active");
    });
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && lightbox.classList.contains("active")) {
        lightbox.classList.remove("active");
      }
    });
  }

  const imgEl = document.getElementById("photo-lightbox-img");
  if (imgEl) imgEl.src = src;
  lightbox.classList.add("active");
}

/**
 * Close fullscreen photo lightbox overlay if open.
 */
export function closePhotoLightbox() {
  const lightbox = document.getElementById("photo-lightbox");
  if (lightbox) {
    lightbox.classList.remove("active");
  }
}

/**
 * Check if fullscreen photo lightbox overlay is currently open.
 * @returns {boolean}
 */
export function isPhotoLightboxOpen() {
  const lightbox = document.getElementById("photo-lightbox");
  return Boolean(lightbox && lightbox.classList.contains("active"));
}

/**
 * Round Stage Reusable Component.
 *
 * Provides a standardized split layout containing:
 * - Photo Canvas card (single photo or batch photos with tabs, lightbox, fullscreen button, metadata caption)
 * - Map Shell card (reusable Leaflet map container with fullscreen button)
 */

import { t, formatDate, formatDateTime } from "../i18n.js";
import { escapeHtml } from "../formatters.js";
import { openPhotoLightbox } from "./lightbox.js";

export class RoundStage {
  /**
   * @param {HTMLElement} containerEl - Outer container hosting the round stage
   * @param {object} [options]
   * @param {Function} [options.onPhotoChange] - Callback (photoIndex, photoData) when tabs switch
   * @param {Function} [options.onReportPhoto] - Callback (photoId, mediaUrl) for reporting photo issue
   * @param {boolean} [options.showReportButton=false]
   */
  constructor(containerEl, { onPhotoChange = null, onReportPhoto = null, showReportButton = false } = {}) {
    this.containerEl = containerEl;
    this.onPhotoChange = onPhotoChange;
    this.onReportPhoto = onReportPhoto;
    this.showReportButton = showReportButton;

    this.photos = [];
    this.currentPhotoIndex = 0;

    this._initMarkup();
  }

  _initMarkup() {
    this.containerEl.classList.add("round-stage");
    this.containerEl.classList.add("replay-stage");
    const existingRow = this.containerEl.querySelector(".round-media-map-row, .replay-media-map-row");
    if (!existingRow) {
      this.containerEl.innerHTML = `
        <div class="replay-media-map-row round-media-map-row">
          <div class="replay-photo-card round-photo-card">
            <div class="replay-photo-tabs-container round-photo-tabs-container"></div>
            <div class="media-frame replay-media-frame round-media-frame">
              <img class="quiz-image replay-photo-img round-photo-img" src="" alt="Round photo" />
              <button type="button" class="map-fullscreen-btn round-photo-fullscreen replay-photo-fullscreen" aria-pressed="false"
                title="${escapeHtml(t("game.fullscreen_image_title"))}" data-i18n-title="game.fullscreen_image_title">
                <svg class="fs-icon" viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor"
                  stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round">
                  <polyline points="15 3 21 3 21 9"></polyline>
                  <polyline points="9 21 3 21 3 15"></polyline>
                  <line x1="21" y1="3" x2="14" y2="10"></line>
                  <line x1="3" y1="21" x2="10" y2="14"></line>
                </svg>
              </button>
            </div>
            <div class="round-photo-caption">
              <div style="display:flex;align-items:center;justify-content:space-between;gap:0.5rem;">
                <span class="round-photo-loc">-</span>
                ${this.showReportButton ? `
                  <button type="button" class="btn-report-discrete round-photo-report-btn" title="${escapeHtml(t("report.modal_title"))}" data-i18n-title="report.modal_title">
                    <span aria-hidden="true">🚩</span>
                    <span class="report-discrete-text" data-i18n="report.btn_label">${escapeHtml(t("report.btn_label"))}</span>
                  </button>
                ` : ""}
              </div>
              <span class="round-photo-date">-</span>
            </div>
          </div>

          <div class="map-shell round-map-shell">
            <div class="round-leaflet-map" style="width:100%;height:100%;min-height:420px;"></div>
          </div>
        </div>
      `;
    }

    this.mediaMapRow = this.containerEl.querySelector(".round-media-map-row, .replay-media-map-row");
    this.photoCard = this.containerEl.querySelector(".round-photo-card, .replay-photo-card");
    this.tabsContainer = this.containerEl.querySelector(".round-photo-tabs-container, .replay-photo-tabs-container, [id*='tabs-container']");
    this.mediaFrame = this.containerEl.querySelector(".round-media-frame, .replay-media-frame");
    this.photoImg = this.containerEl.querySelector(".round-photo-img, .replay-photo-img");
    this.fullscreenBtn = this.containerEl.querySelector(".round-photo-fullscreen, [id*='photo-fullscreen'], .map-fullscreen-btn");
    this.locEl = this.containerEl.querySelector(".round-photo-loc, .replay-photo-loc, [id*='photo-loc']");
    this.dateEl = this.containerEl.querySelector(".round-photo-date, .replay-photo-date, [id*='photo-date']");
    this.mapShell = this.containerEl.querySelector(".round-map-shell, .replay-map-shell, .map-shell");
    this.mapContainer = this.containerEl.querySelector(".round-leaflet-map, #replay-leaflet-map, [id*='map']");
    this.reportBtn = this.containerEl.querySelector(".round-photo-report-btn, .btn-report-discrete, [id*='report-btn']");

    if (this.reportBtn) {
      this.reportBtn.setAttribute("data-i18n-title", "report.btn_label");
      this.reportBtn.setAttribute("data-i18n-aria-label", "report.btn_label");
    }

    // Fullscreen and lightbox handlers
    if (this.photoImg) {
      this.photoImg.addEventListener("click", () => {
        if (this.photoImg.src) {
          openPhotoLightbox(this.photoImg.src);
        }
      });
    }

    if (this.fullscreenBtn && this.mediaFrame) {
      this.fullscreenBtn.addEventListener("click", () => {
        if (!document.fullscreenElement) {
          if (this.mediaFrame.requestFullscreen) {
            this.mediaFrame.requestFullscreen().catch(() => { });
          }
        } else if (document.exitFullscreen) {
          document.exitFullscreen().catch(() => { });
        }
      });
    }

    if (this.reportBtn && this.onReportPhoto) {
      this.reportBtn.addEventListener("click", () => {
        const cur = this.getCurrentPhoto();
        if (cur) {
          this.onReportPhoto(cur.photo_id || cur.asset_id, cur.media_url || (this.photoImg ? this.photoImg.src : ""));
        }
      });
    }
  }

  /**
   * Updates photos array and renders active photo & tabs.
   *
   * @param {Array<object>} photos
   * @param {number} [activeIndex=0]
   */
  setPhotos(photos = [], activeIndex = 0) {
    this.photos = Array.isArray(photos) ? photos : [];
    this.currentPhotoIndex = Math.max(0, Math.min(activeIndex, this.photos.length - 1));
    this.renderPhotoCanvas();
  }

  getCurrentPhoto() {
    return this.photos[this.currentPhotoIndex] || null;
  }

  renderPhotoCanvas() {
    if (!this.photos || this.photos.length === 0) return;

    if (this.tabsContainer) {
      if (this.photos.length > 1) {
        this.tabsContainer.innerHTML = `
          <div class="replay-photo-tabs round-photo-tabs">
            ${this.photos
            .map(
              (p, idx) => `
                <button type="button" class="replay-photo-tab-btn round-photo-tab-btn ${idx === this.currentPhotoIndex ? "active" : ""}" data-idx="${idx}">
                  ${t("replay.photo_label", idx + 1)}
                </button>
              `
            )
            .join("")}
          </div>
        `;
        this.tabsContainer.querySelectorAll(".round-photo-tab-btn, .replay-photo-tab-btn").forEach((btn) => {
          btn.addEventListener("click", () => {
            this.currentPhotoIndex = parseInt(btn.getAttribute("data-idx"), 10);
            this.renderPhotoCanvas();
            if (this.onPhotoChange) {
              this.onPhotoChange(this.currentPhotoIndex, this.getCurrentPhoto());
            }
          });
        });
      } else {
        this.tabsContainer.innerHTML = "";
      }
    }

    const curPhoto = this.getCurrentPhoto();
    if (!curPhoto) return;

    const mediaUrl = curPhoto.media_url || (curPhoto.photo_id ? `/api/media/${curPhoto.photo_id}` : (curPhoto.asset_id ? `/api/media/${encodeURIComponent(curPhoto.asset_id)}` : ""));
    if (this.photoImg && mediaUrl) {
      this.photoImg.src = mediaUrl;
    }

    const locParts = [curPhoto.actual_city, curPhoto.actual_country].filter(Boolean);
    const locStr = locParts.length > 0
      ? locParts.join(", ")
      : (curPhoto.actual_latitude != null
        ? `${Number(curPhoto.actual_latitude).toFixed(3)}, ${Number(curPhoto.actual_longitude).toFixed(3)}`
        : t("stats.location_unknown"));

    if (this.locEl) this.locEl.textContent = locStr;

    let dateText = "";
    if (curPhoto.actual_date) {
      dateText = formatDate(curPhoto.actual_date, { year: "numeric", month: "short", day: "numeric" });
    } else if (curPhoto.actual_year && curPhoto.actual_month) {
      dateText = `${formatDate(new Date(curPhoto.actual_year, curPhoto.actual_month - 1), { month: "short", year: "numeric" })}`;
    }
    if (this.dateEl) this.dateEl.textContent = dateText;
  }

  /**
   * Show or hide the map shell in the split view (e.g. date-only mode).
   * @param {boolean} visible
   */
  setMapVisible(visible) {
    if (this.mapShell) {
      this.mapShell.classList.toggle("hidden", !visible);
    }
    if (this.mediaMapRow) {
      this.mediaMapRow.classList.toggle("single-col", !visible);
    }
  }

  getMapElement() {
    return this.mapContainer;
  }
}

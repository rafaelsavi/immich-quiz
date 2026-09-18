/**
 * Round Stage Reusable Component.
 *
 * Provides a standardized split layout containing:
 * - Photo Canvas card (single photo or batch photos with tabs, lightbox, fullscreen button, metadata caption)
 * - Map Shell card (reusable Leaflet map container with fullscreen button)
 *
 * Used by in-game live reveal screens (Pinpoint, Unshuffle), the dedicated match replay screen,
 * and summary replay views, providing a single source of truth for stage DOM and photo tabs.
 */

import { t, formatDate } from "../i18n.js";
import { escapeHtml } from "../formatters.js";
import { openPhotoLightbox } from "./lightbox.js";
import { toggleMapFullscreen } from "../maps.js";

export class RoundStage {
  /**
   * @param {HTMLElement} containerEl - Outer container hosting the round stage
   * @param {object} [options]
   * @param {string} [options.idPrefix=""] - Optional ID prefix to assign to elements for locator/API compatibility
   * @param {Function} [options.onPhotoChange] - Callback (photoIndex, photoData) when tabs switch
   * @param {Function} [options.onReportPhoto] - Callback (photoId, mediaUrl) for reporting photo issue
   * @param {boolean} [options.showReportButton=false]
   */
  constructor(
    containerEl,
    { idPrefix = "", onPhotoChange = null, onReportPhoto = null, showReportButton = false } = {}
  ) {
    this.containerEl = containerEl;
    this.idPrefix = idPrefix;
    this.onPhotoChange = onPhotoChange;
    this.onReportPhoto = onReportPhoto;
    this.showReportButton = showReportButton;

    this.photos = [];
    this.currentPhotoIndex = 0;
    this.locationMode = true;
    this.dateMode = true;

    this._initMarkup();
  }

  _initMarkup() {
    this.containerEl.classList.add("round-stage", "replay-stage");

    const existingRow = this.containerEl.querySelector(".round-media-map-row, .replay-media-map-row");
    if (!existingRow) {
      this.containerEl.innerHTML = `
        <div class="round-media-map-row replay-media-map-row">
          <div class="round-photo-card replay-photo-card">
            <div class="round-photo-tabs-container replay-photo-tabs-container"></div>
            <div class="media-frame round-media-frame replay-media-frame">
              <img class="quiz-image round-photo-img replay-photo-img" src="" alt="Round photo" />
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
            <div class="round-photo-caption replay-photo-caption">
              <div class="reveal-actual-row">
                <div class="reveal-actual">
                  <span class="reveal-actual-chip reveal-chip-date">
                    <span class="reveal-chip-icon" aria-hidden="true">📅</span>
                    <strong class="reveal-chip-val round-photo-date replay-photo-date">-</strong>
                  </span>
                  <span class="reveal-actual-chip reveal-chip-location">
                    <span class="reveal-chip-icon" aria-hidden="true">🗺️</span>
                    <strong class="reveal-chip-val round-photo-loc replay-photo-loc">-</strong>
                  </span>
                </div>
                <button type="button" class="btn-report-discrete round-photo-report-btn" title="${escapeHtml(t("report.modal_title"))}"
                  data-i18n-title="report.modal_title" aria-label="${escapeHtml(t("report.modal_title"))}">
                  <span aria-hidden="true">🚩</span>
                  <span class="report-discrete-text" data-i18n="report.btn_label">${escapeHtml(t("report.btn_label"))}</span>
                </button>
              </div>
            </div>
          </div>

          <div class="map-shell round-map-shell replay-map-shell">
            <div class="round-leaflet-map" style="width:100%;height:100%;min-height:420px;"></div>
            <button type="button" class="map-fullscreen-btn round-map-fullscreen replay-map-fullscreen" aria-pressed="false"
              title="${escapeHtml(t("game.fullscreen_map_title"))}" data-i18n-title="game.fullscreen_map_title">
              <svg class="fs-icon" viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor"
                stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round">
                <polyline points="15 3 21 3 21 9"></polyline>
                <polyline points="9 21 3 21 3 15"></polyline>
                <line x1="21" y1="3" x2="14" y2="10"></line>
                <line x1="3" y1="21" x2="10" y2="14"></line>
              </svg>
            </button>
          </div>
        </div>
      `;
    }

    this.mediaMapRow = this.containerEl.querySelector(".round-media-map-row, .replay-media-map-row");
    this.photoCard = this.containerEl.querySelector(".round-photo-card, .replay-photo-card");
    this.tabsContainer = this.containerEl.querySelector(".round-photo-tabs-container, .replay-photo-tabs-container");
    this.mediaFrame = this.containerEl.querySelector(".round-media-frame, .replay-media-frame, .media-frame");
    this.photoImg = this.containerEl.querySelector(".round-photo-img, .replay-photo-img, .quiz-image");
    this.fullscreenBtn = this.containerEl.querySelector(".round-photo-fullscreen, .replay-photo-fullscreen, .media-frame .map-fullscreen-btn");
    this.revealActualRow = this.containerEl.querySelector(".reveal-actual-row");
    this.revealActual = this.containerEl.querySelector(".reveal-actual");
    this.locEl = this.containerEl.querySelector(".round-photo-loc, .replay-photo-loc");
    this.dateEl = this.containerEl.querySelector(".round-photo-date, .replay-photo-date");
    this.dateChip = this.containerEl.querySelector(".reveal-chip-date");
    this.locChip = this.containerEl.querySelector(".reveal-chip-location");
    this.mapShell = this.containerEl.querySelector(".round-map-shell, .replay-map-shell, .map-shell");
    this.mapContainer = this.mapShell
      ? this.mapShell.querySelector(".round-leaflet-map, div[id*='map']")
      : this.containerEl.querySelector(".round-leaflet-map, div[id*='map']");
    this.mapFullscreenBtn = this.mapShell
      ? this.mapShell.querySelector(".round-map-fullscreen, .replay-map-fullscreen, .map-fullscreen-btn")
      : null;
    this.reportBtn = this.containerEl.querySelector(".round-photo-report-btn, .btn-report-discrete");

    if (this.reportBtn) {
      this.reportBtn.style.display = this.showReportButton ? "inline-flex" : "none";
      this.reportBtn.setAttribute("data-i18n-title", "report.btn_label");
      this.reportBtn.setAttribute("data-i18n-aria-label", "report.btn_label");
    }

    // Apply specific element IDs for prefix compatibility
    this._applyPrefixIds(this.idPrefix);

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
        toggleMapFullscreen(this.mediaFrame);
      });
    }

    if (this.mapFullscreenBtn && this.mapShell) {
      this.mapFullscreenBtn.addEventListener("click", () => {
        toggleMapFullscreen(this.mapShell);
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

  _applyPrefixIds(prefix) {
    if (!prefix) return;
    if (prefix === "replay-") {
      if (this.mediaMapRow) this.mediaMapRow.id = "replay-media-map-row";
      if (this.photoCard) this.photoCard.id = "replay-photo-card";
      if (this.tabsContainer) this.tabsContainer.id = "replay-photo-tabs-container";
      if (this.mediaFrame) {
        this.mediaFrame.id = "replay-media-frame";
        this.mediaFrame.className = "media-frame replay-media-frame";
      }
      if (this.photoImg) {
        this.photoImg.id = "replay-photo-img";
        this.photoImg.className = "quiz-image replay-photo-img";
      }
      if (this.fullscreenBtn) {
        this.fullscreenBtn.id = "replay-photo-fullscreen";
        this.fullscreenBtn.className = "map-fullscreen-btn";
      }
      if (this.revealActual) this.revealActual.id = "replay-reveal-actual";
      if (this.dateEl) this.dateEl.id = "replay-photo-date";
      if (this.locEl) this.locEl.id = "replay-photo-loc";
      if (this.reportBtn) this.reportBtn.id = "replay-report-btn";
      if (this.mapShell) {
        this.mapShell.id = "replay-map-shell";
        this.mapShell.className = "map-shell replay-map-shell";
      }
      if (this.mapContainer) this.mapContainer.id = "replay-leaflet-map";
    } else if (prefix === "pinpoint-") {
      if (this.mediaMapRow) this.mediaMapRow.id = "pinpoint-media-map-row";
      if (this.photoCard) this.photoCard.id = "pinpoint-photo-card";
      if (this.tabsContainer) this.tabsContainer.id = "pinpoint-photo-tabs-container";
      if (this.mediaFrame) this.mediaFrame.id = "pinpoint-reveal-media-frame";
      if (this.photoImg) this.photoImg.id = "pinpoint-reveal-img";
      if (this.fullscreenBtn) this.fullscreenBtn.id = "pinpoint-photo-fullscreen";
      if (this.revealActual) this.revealActual.id = "reveal-actual";
      if (this.reportBtn) this.reportBtn.id = "reveal-report-btn";
      if (this.mapShell) this.mapShell.id = "reveal-map-shell";
      if (this.mapContainer) this.mapContainer.id = "reveal-map";
      if (this.mapFullscreenBtn) this.mapFullscreenBtn.id = "reveal-map-fullscreen";
    } else if (prefix === "shuffle-") {
      if (this.mediaMapRow) this.mediaMapRow.id = "shuffle-media-map-row";
      if (this.photoCard) this.photoCard.id = "shuffle-photo-card";
      if (this.tabsContainer) this.tabsContainer.id = "shuffle-photo-tabs-container";
      if (this.mediaFrame) this.mediaFrame.id = "shuffle-reveal-media-frame";
      if (this.photoImg) this.photoImg.id = "shuffle-reveal-img";
      if (this.fullscreenBtn) this.fullscreenBtn.id = "shuffle-photo-fullscreen";
      if (this.revealActual) this.revealActual.id = "shuffle-reveal-actual";
      if (this.dateEl) this.dateEl.id = "shuffle-photo-date";
      if (this.locEl) this.locEl.id = "shuffle-photo-loc";
      if (this.reportBtn) this.reportBtn.id = "shuffle-report-btn";
      if (this.mapShell) this.mapShell.id = "reveal-shuffle-map-shell";
      if (this.mapContainer) this.mapContainer.id = "reveal-shuffle-map";
      if (this.mapFullscreenBtn) this.mapFullscreenBtn.id = "reveal-shuffle-map-fullscreen";
    } else {
      if (this.mediaMapRow) this.mediaMapRow.id = `${prefix}media-map-row`;
      if (this.photoCard) this.photoCard.id = `${prefix}photo-card`;
      if (this.tabsContainer) this.tabsContainer.id = `${prefix}photo-tabs-container`;
      if (this.mediaFrame) {
        this.mediaFrame.id = `${prefix}media-frame`;
        this.mediaFrame.className = `media-frame ${prefix}media-frame round-media-frame`;
      }
      if (this.photoImg) {
        this.photoImg.id = `${prefix}photo-img`;
        this.photoImg.className = `quiz-image ${prefix}photo-img round-photo-img`;
      }
      if (this.fullscreenBtn) this.fullscreenBtn.id = `${prefix}photo-fullscreen`;
      if (this.revealActual) this.revealActual.id = `${prefix}reveal-actual`;
      if (this.dateEl) this.dateEl.id = `${prefix}photo-date`;
      if (this.locEl) this.locEl.id = `${prefix}photo-loc`;
      if (this.reportBtn) this.reportBtn.id = `${prefix}report-btn`;
      if (this.mapShell) {
        this.mapShell.id = `${prefix}map-shell`;
        this.mapShell.className = `map-shell ${prefix}map-shell round-map-shell`;
      }
      if (this.mapContainer) this.mapContainer.id = `${prefix}leaflet-map`;
      if (this.mapFullscreenBtn) this.mapFullscreenBtn.id = `${prefix}map-fullscreen`;
    }
  }

  /**
   * Set location and date mode visibility.
   * @param {object} options
   * @param {boolean} [options.locationMode=true]
   * @param {boolean} [options.dateMode=true]
   */
  setModes({ locationMode = true, dateMode = true } = {}) {
    this.locationMode = locationMode;
    this.dateMode = dateMode;
    this.setMapVisible(locationMode);
    if (this.locChip) {
      this.locChip.style.display = locationMode ? "inline-flex" : "none";
    }
    if (this.dateChip) {
      this.dateChip.style.display = dateMode ? "inline-flex" : "none";
    }
  }

  /**
   * Updates photos array and renders active photo & tabs.
   * Sorts batch photos by true_pin_id (A, B, C…) so tabs always match map pin order.
   *
   * @param {Array<object>} photos
   * @param {number} [activeIndex=0]
   */
  setPhotos(photos = [], activeIndex = 0) {
    const raw = Array.isArray(photos) ? photos : [];
    // Sort by true_pin_id alphabetically so "Photo A" always maps to pin A on the map.
    // Photos without a true_pin_id (pinpoint mode) are left in original order.
    const hasPinIds = raw.some((p) => p.true_pin_id);
    this.photos = hasPinIds
      ? [...raw].sort((a, b) => {
        const pa = a.true_pin_id || "";
        const pb = b.true_pin_id || "";
        return pa < pb ? -1 : pa > pb ? 1 : 0;
      })
      : raw;
    this.currentPhotoIndex = Math.max(0, Math.min(activeIndex, this.photos.length - 1));
    this.renderPhotoCanvas();
  }

  getCurrentPhoto() {
    return this.photos[this.currentPhotoIndex] || null;
  }

  /**
   * Programmatically switch the active photo (e.g. when clicking a map pin).
   * @param {number} index
   */
  setActivePhoto(index) {
    if (!this.photos || this.photos.length === 0) return;
    const targetIdx = Math.max(0, Math.min(index, this.photos.length - 1));
    if (this.currentPhotoIndex === targetIdx) return;
    this.currentPhotoIndex = targetIdx;
    this.renderPhotoCanvas();
    if (this.onPhotoChange) {
      this.onPhotoChange(this.currentPhotoIndex, this.getCurrentPhoto());
    }
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
                  ${t("replay.photo_label", p.true_pin_id || String(idx + 1))}
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
        : "");

    let dateText = "";
    if (curPhoto.actual_date) {
      dateText = formatDate(curPhoto.actual_date, { year: "numeric", month: "short", day: "numeric" });
    }
    if (!dateText && curPhoto.actual_year && curPhoto.actual_month) {
      dateText = `${String(curPhoto.actual_month).padStart(2, "0")}/${curPhoto.actual_year}`;
    }
    if (!dateText && curPhoto.actual_year) {
      dateText = String(curPhoto.actual_year);
    }

    const showLoc = (this.locationMode !== false) && Boolean(locStr || curPhoto.actual_latitude != null);
    const showDate = (this.dateMode !== false) && Boolean(dateText || curPhoto.actual_date || curPhoto.actual_year);

    if (this.revealActual) {
      this.revealActual.replaceChildren();
      if (showDate) {
        const dateChip = document.createElement("span");
        dateChip.className = "reveal-actual-chip reveal-chip-date";
        const dateIcon = document.createElement("span");
        dateIcon.className = "reveal-chip-icon";
        dateIcon.setAttribute("aria-hidden", "true");
        dateIcon.textContent = "📅";
        const valSpan = document.createElement("strong");
        valSpan.className = "reveal-chip-val round-photo-date replay-photo-date";
        if (this.idPrefix === "pinpoint-") {
          valSpan.id = "round-photo-date";
        } else if (this.idPrefix) {
          valSpan.id = `${this.idPrefix}photo-date`;
        } else {
          valSpan.id = "round-photo-date";
        }
        valSpan.textContent = dateText;
        dateChip.append(dateIcon, valSpan);
        this.revealActual.appendChild(dateChip);
      }
      if (showLoc) {
        const locChip = document.createElement("span");
        locChip.className = "reveal-actual-chip reveal-chip-location";
        const locIcon = document.createElement("span");
        locIcon.className = "reveal-chip-icon";
        locIcon.setAttribute("aria-hidden", "true");
        locIcon.textContent = "🗺️";
        const valSpan = document.createElement("strong");
        valSpan.className = "reveal-chip-val round-photo-loc replay-photo-loc";
        if (this.idPrefix === "pinpoint-") {
          valSpan.id = "round-photo-loc";
        } else if (this.idPrefix) {
          valSpan.id = `${this.idPrefix}photo-loc`;
        } else {
          valSpan.id = "round-photo-loc";
        }
        valSpan.textContent = locStr || t("stats.location_unknown");
        locChip.append(locIcon, valSpan);
        this.revealActual.appendChild(locChip);
      }
    }
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


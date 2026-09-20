/**
 * Universal Match Review Deck Component.
 *
 * Provides a standardized 3-tab review experience:
 * 1. 🎬 Match Replay: Round-by-round interactive stage, photo tabs, guess maps, and reveal table.
 * 2. 🗺️ Journey Map: World map showing chronological flight arcs and round actual pins.
 * 3. 📸 Photo Memories: Grid of polaroid cards with metadata and click-to-zoom Lightbox.
 *
 * Reusable across Game Results (/game/:id/summary), Match Replays (/game/:id/replay),
 * and Challenge Grand Reveal screens.
 */

import { t } from "../i18n.js";
import { escapeHtml } from "../formatters.js";
import { MatchReplayViewer } from "./match_replay.js";
import { renderJourneyMap, toggleMapFullscreen } from "../maps.js";
import { renderPolaroidGallery } from "../summary/polaroids.js";

export class ReviewDeck {
  /**
   * @param {HTMLElement} containerEl - Container mounting the review deck
   * @param {object} [options]
   * @param {string} [options.idPrefix=""] - Optional ID prefix for nested elements
   * @param {boolean} [options.showReportButton=true] - Enable discrete report button on photos
   * @param {string} [options.defaultTab="replay"] - "replay" | "journey" | "memories"
   */
  constructor(
    containerEl,
    { idPrefix = "", showReportButton = true, defaultTab = "replay" } = {}
  ) {
    this.containerEl = containerEl;
    this.idPrefix = idPrefix;
    this.showReportButton = showReportButton;
    this.defaultTab = defaultTab;
    this.activeTab = defaultTab;

    this.matchData = null;
    this.journeyMapInstance = null;

    this._initMarkup();
    this._bindEvents();
  }

  _initMarkup() {
    this.containerEl.classList.add("review-deck");

    // Check if inner markup already exists
    let tabsContainer = this.containerEl.querySelector(".review-deck-tabs-container");
    if (!tabsContainer) {
      const p = this.idPrefix;
      this.containerEl.innerHTML = `
        <div class="review-deck-tabs-container">
          <div class="segmented-control review-deck-tabs" role="tablist">
            <button type="button" class="segmented-btn active" data-deck-tab="replay" role="tab" aria-selected="true" data-i18n="summary.tab_replay">
              ${escapeHtml(t("summary.tab_replay"))}
            </button>
            <button type="button" class="segmented-btn" data-deck-tab="journey" role="tab" aria-selected="false" data-i18n="summary.tab_journey">
              ${escapeHtml(t("summary.tab_journey"))}
            </button>
            <button type="button" class="segmented-btn" data-deck-tab="memories" role="tab" aria-selected="false" data-i18n="summary.tab_memories">
              ${escapeHtml(t("summary.tab_memories"))}
            </button>
          </div>
        </div>

        <div id="${p}deck-panel-replay" class="review-deck-panel review-deck-replay-panel" role="tabpanel">
          <div id="${p}replay-content-grid" class="replay-content-grid"></div>
        </div>

        <div id="${p}deck-panel-journey" class="review-deck-panel review-deck-journey-panel hidden" role="tabpanel">
          <div id="${p}journey-map-shell" class="map-shell journey-map-shell">
            <div id="${p}journey-map" class="journey-map" style="width:100%;height:100%;min-height:480px;"></div>
            <button type="button" id="${p}journey-map-fullscreen" class="map-fullscreen-btn journey-map-fullscreen" aria-pressed="false"
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

        <div id="${p}deck-panel-memories" class="review-deck-panel review-deck-memories-panel polaroids-section hidden" role="tabpanel">
          <div id="${p}polaroid-gallery" class="polaroid-grid"></div>
        </div>
      `;
    }

    // Cache element references
    this.tabs = Array.from(this.containerEl.querySelectorAll("[data-deck-tab]"));
    this.tabReplay = this.containerEl.querySelector('[data-deck-tab="replay"]');
    this.tabJourney = this.containerEl.querySelector('[data-deck-tab="journey"]');
    this.tabMemories = this.containerEl.querySelector('[data-deck-tab="memories"]');

    this.panelReplay = this.containerEl.querySelector(".review-deck-replay-panel");
    this.panelJourney = this.containerEl.querySelector(".review-deck-journey-panel");
    this.panelMemories = this.containerEl.querySelector(".review-deck-memories-panel");

    this.replayGrid = this.containerEl.querySelector(".replay-content-grid");
    this.journeyMapShell = this.containerEl.querySelector(".journey-map-shell");
    this.journeyMapEl = this.containerEl.querySelector(".journey-map");
    this.journeyFullscreenBtn = this.containerEl.querySelector(".journey-map-fullscreen");
    this.polaroidGrid = this.containerEl.querySelector(".polaroid-grid");

    // Initialize nested MatchReplayViewer in panel 1
    if (this.replayGrid) {
      this.replayViewer = new MatchReplayViewer(this.replayGrid, {
        idPrefix: this.idPrefix ? `${this.idPrefix}replay-` : "replay-",
        showReportButton: this.showReportButton,
      });
    }
  }

  _bindEvents() {
    this.tabs.forEach((btn) => {
      btn.addEventListener("click", () => {
        const tabKey = btn.getAttribute("data-deck-tab");
        if (tabKey) {
          this.switchTab(tabKey);
        }
      });
    });

    if (this.journeyFullscreenBtn && this.journeyMapShell) {
      this.journeyFullscreenBtn.addEventListener("click", () => {
        toggleMapFullscreen(this.journeyMapShell);
      });
    }
  }

  /**
   * Switch the active deck tab and stabilize Leaflet map dimensions.
   * @param {string} tabKey - "replay" | "journey" | "memories"
   */
  switchTab(tabKey) {
    if (!tabKey) return;
    this.activeTab = tabKey;

    // Update tab button classes and aria attributes
    this.tabs.forEach((btn) => {
      const match = btn.getAttribute("data-deck-tab") === tabKey;
      btn.classList.toggle("active", match);
      btn.setAttribute("aria-selected", match ? "true" : "false");
    });

    // Toggle panel visibility
    if (this.panelReplay) this.panelReplay.classList.toggle("hidden", tabKey !== "replay");
    if (this.panelJourney) this.panelJourney.classList.toggle("hidden", tabKey !== "journey");
    if (this.panelMemories) this.panelMemories.classList.toggle("hidden", tabKey !== "memories");

    // Stabilize Leaflet maps when unhidden
    if (tabKey === "journey" && this.journeyMapInstance) {
      setTimeout(() => {
        try {
          this.journeyMapInstance.invalidateSize();
        } catch (_) {}
      }, 50);
    } else if (tabKey === "replay" && this.replayViewer?.map) {
      setTimeout(() => {
        try {
          this.replayViewer.map.invalidateSize();
        } catch (_) {}
      }, 50);
    }
  }

  /**
   * Hydrate all 3 review canvases with match data.
   * @param {object} matchData - Full match replay or summary payload
   * @param {number} [initialRoundIndex=0]
   */
  setMatchData(matchData, initialRoundIndex = 0) {
    if (!matchData) return;
    this.matchData = matchData;

    const locationMode = matchData.location_mode !== false;

    // Toggle Journey Map tab based on location mode
    if (this.tabJourney) {
      this.tabJourney.classList.toggle("hidden", !locationMode);
    }
    if (!locationMode && this.activeTab === "journey") {
      this.activeTab = "replay";
    }

    // Extract rounds list (works with both rounds_data and round_history)
    const rawRounds = matchData.rounds_data || matchData.round_history || [];

    // 1. Populate MatchReplayViewer
    if (this.replayViewer) {
      this.replayViewer.setMatchData(matchData, initialRoundIndex);
    }

    // 2. Populate Journey Map (if location enabled)
    if (locationMode && this.journeyMapShell && this.journeyMapEl) {
      this.journeyMapInstance = renderJourneyMap(rawRounds, true, {
        mapShell: this.journeyMapShell,
        mapEl: this.journeyMapEl,
      });
    }

    // 3. Populate Photo Memories Polaroid Gallery
    if (this.polaroidGrid) {
      renderPolaroidGallery(rawRounds, this.polaroidGrid);
    }

    // Activate default tab
    this.switchTab(this.activeTab || this.defaultTab || "replay");
  }

  /**
   * Re-render text/labels on language switch.
   */
  refreshLanguage() {
    this.tabs.forEach((btn) => {
      const key = btn.getAttribute("data-deck-tab");
      if (key === "replay") btn.textContent = t("summary.tab_replay");
      if (key === "journey") btn.textContent = t("summary.tab_journey");
      if (key === "memories") btn.textContent = t("summary.tab_memories");
    });

    if (this.replayViewer) {
      this.replayViewer.renderCurrentRound();
    }

    if (this.matchData && this.polaroidGrid) {
      const rawRounds = this.matchData.rounds_data || this.matchData.round_history || [];
      renderPolaroidGallery(rawRounds, this.polaroidGrid);
    }
  }

  destroy() {
    if (this.replayViewer) {
      this.replayViewer.destroy();
    }
  }
}

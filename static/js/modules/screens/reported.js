/**
 * Reported Asset Moderation Screen Controller for Immich Quiz.
 *
 * Provides review dashboard for flagged/reported assets:
 * - Direct deep links to Immich Web for quick metadata correction
 * - Detailed issue breakdown (GPS mismatch, incorrect date, custom notes)
 * - Interactive asset inspection view with photo preview
 * - Moderation resolution workflows to unflag assets for future games
 */

import { api } from "../api.js";
import { state, el } from "../state.js";
import { t, formatDateTime } from "../i18n.js";
import { showCard } from "./common.js";
import { showShareToast } from "../summary/share.js";
import { formatRelativeTime, escapeHtml } from "../formatters.js";

let _reportedAssets = [];
let _selectedAssetId = null;
let _searchQuery = "";
let _issueFilter = "all";
let _sortBy = "newest";
let _isLoading = false;
let _isInitialized = false;

// DOM references
let _pageCardEl = null;
let _itemsListEl = null;
let _inspectionPanelEl = null;
let _searchInputEl = null;
let _issueTabsEl = null;
let _sortSelectEl = null;
let _refreshBtnEl = null;
let _totalBadgeEl = null;

/**
 * Initialize DOM element references and event listeners.
 */
export function initReportedPage() {
  if (_isInitialized) return;

  _pageCardEl = document.getElementById("reported-page-card");
  _itemsListEl = document.getElementById("reported-items-list");
  _inspectionPanelEl = document.getElementById("reported-inspection-panel");
  _searchInputEl = document.getElementById("reported-search-input");
  _issueTabsEl = document.getElementById("reported-issue-tabs");
  _sortSelectEl = document.getElementById("reported-sort-select");
  _refreshBtnEl = document.getElementById("reported-page-refresh-btn");
  _totalBadgeEl = document.getElementById("reported-page-total-badge");

  if (_searchInputEl) {
    _searchInputEl.addEventListener("input", (e) => {
      _searchQuery = e.target.value.trim().toLowerCase();
      renderReported();
    });
  }

  if (_issueTabsEl) {
    _issueTabsEl.querySelectorAll(".filter-pill").forEach((pill) => {
      pill.addEventListener("click", () => {
        _issueTabsEl.querySelectorAll(".filter-pill").forEach((p) => p.classList.remove("active"));
        pill.classList.add("active");
        _issueFilter = pill.getAttribute("data-issue") || "all";
        renderReported();
      });
    });
  }

  if (_sortSelectEl) {
    _sortSelectEl.addEventListener("change", (e) => {
      _sortBy = e.target.value;
      renderReported();
    });
  }

  if (_refreshBtnEl) {
    _refreshBtnEl.addEventListener("click", () => {
      loadReportedAssets(true).catch((err) => showShareToast(err.message || "Failed to load"));
    });
  }

  _isInitialized = true;
}

/**
 * Open the reported asset moderation page.
 */
export async function openReportedPage() {
  initReportedPage();
  if (el.leaderboardCard) el.leaderboardCard.classList.add("hidden");
  showCard(el.reportedPageCard);

  await loadReportedAssets();
}

/**
 * Fetch reported assets from the server.
 * @param {boolean} [showToast=false]
 */
export async function loadReportedAssets(showToast = false) {
  if (_isLoading) return;
  _isLoading = true;

  if (_itemsListEl && _reportedAssets.length === 0) {
    _itemsListEl.innerHTML = `<div class="reported-loading">${escapeHtml(t("reported_page.loading"))}</div>`;
  }

  try {
    const assets = await api("/api/assets/flagged?limit=300");
    _reportedAssets = Array.isArray(assets) ? assets : [];

    if (!_selectedAssetId || !_reportedAssets.some((a) => a.asset_id === _selectedAssetId)) {
      _selectedAssetId = _reportedAssets[0]?.asset_id || null;
    }

    renderReported();

    if (showToast) {
      showShareToast(t("reported_page.refresh_btn") + " ✓");
    }
  } catch (err) {
    console.error("Failed to load reported assets:", err);
    if (_itemsListEl) {
      _itemsListEl.innerHTML = `
        <div class="reported-empty-state">
          <div class="reported-empty-icon">⚠️</div>
          <h3>${escapeHtml(err.message || "Error loading reports")}</h3>
        </div>
      `;
    }
  } finally {
    _isLoading = false;
  }
}

/**
 * Filter, sort, and render reported assets list and inspection panel.
 */
export function renderReported() {
  if (!_itemsListEl || !_inspectionPanelEl) return;

  // Filter assets
  let filtered = _reportedAssets.filter((item) => {
    // Search query filter
    if (_searchQuery) {
      const matchId = item.asset_id.toLowerCase().includes(_searchQuery);
      const matchReporter = item.reported_by && item.reported_by.toLowerCase().includes(_searchQuery);
      const matchNotes = item.other && item.other.toLowerCase().includes(_searchQuery);
      if (!matchId && !matchReporter && !matchNotes) {
        return false;
      }
    }

    // Issue type filter
    if (_issueFilter === "location" && !item.flag_coordinates) return false;
    if (_issueFilter === "date" && !item.flag_date) return false;
    if (_issueFilter === "custom" && (!item.other || !item.other.trim())) return false;

    return true;
  });

  // Sort assets
  filtered.sort((a, b) => {
    if (_sortBy === "newest") {
      return new Date(b.reported_at).getTime() - new Date(a.reported_at).getTime();
    }
    if (_sortBy === "oldest") {
      return new Date(a.reported_at).getTime() - new Date(b.reported_at).getTime();
    }
    if (_sortBy === "id") {
      return a.asset_id.localeCompare(b.asset_id);
    }
    return 0;
  });

  // Total counter pill
  if (_totalBadgeEl) {
    if (_reportedAssets.length > 0) {
      _totalBadgeEl.textContent = `${filtered.length} / ${_reportedAssets.length}`;
      _totalBadgeEl.classList.remove("hidden");
    } else {
      _totalBadgeEl.classList.add("hidden");
    }
  }

  // Handle completely empty state
  if (_reportedAssets.length === 0) {
    _itemsListEl.innerHTML = `
      <div class="reported-empty-state">
        <div class="reported-empty-icon">🎉</div>
        <h3>${escapeHtml(t("reported_page.empty_title"))}</h3>
        <p>${escapeHtml(t("reported_page.empty_desc"))}</p>
      </div>
    `;
    _inspectionPanelEl.classList.add("hidden");
    _inspectionPanelEl.innerHTML = "";
    return;
  }

  // Handle empty search results
  if (filtered.length === 0) {
    _itemsListEl.innerHTML = `
      <div class="reported-empty-state">
        <div class="reported-empty-icon">🔍</div>
        <h3>${escapeHtml(t("reported_page.no_match_title"))}</h3>
        <p>${escapeHtml(t("reported_page.no_match_desc"))}</p>
      </div>
    `;
    _inspectionPanelEl.classList.add("hidden");
    _inspectionPanelEl.innerHTML = "";
    return;
  }

  // Ensure an active selection
  if (!_selectedAssetId || !filtered.some((a) => a.asset_id === _selectedAssetId)) {
    _selectedAssetId = filtered[0].asset_id;
  }

  // Render list of items
  _itemsListEl.innerHTML = filtered
    .map((item) => {
      const isActive = item.asset_id === _selectedAssetId;
      const mediaUrl = `/api/media/${encodeURIComponent(item.asset_id)}`;
      const timeStr = formatRelativeTime(item.reported_at);
      const reporter = item.reported_by || t("reported_page.reported_by_unknown");

      const badges = [];
      if (item.flag_coordinates) {
        badges.push(`<span class="issue-badge issue-badge-coords">📍 GPS</span>`);
      }
      if (item.flag_date) {
        badges.push(`<span class="issue-badge issue-badge-date">📅 Date</span>`);
      }
      if (item.other && item.other.trim()) {
        badges.push(`<span class="issue-badge issue-badge-notes">📝 Notes</span>`);
      }

      return `
        <div class="reported-item-card ${isActive ? "active" : ""}" data-asset-id="${escapeHtml(item.asset_id)}" role="button" tabindex="0">
          <div class="reported-item-thumb-wrap">
            <img class="reported-item-thumb" src="${mediaUrl}" alt="Thumbnail" loading="lazy" onerror="this.style.opacity='0.3'" />
          </div>
          <div class="reported-item-info">
            <div class="reported-item-header">
              <span class="reported-item-id" title="${escapeHtml(item.asset_id)}">${escapeHtml(item.asset_id)}</span>
              <span class="reported-item-time">${escapeHtml(timeStr)}</span>
            </div>
            <div class="reported-item-badges">
              ${badges.join("")}
            </div>
            <div class="reported-item-footer">
              👤 ${escapeHtml(reporter)}
            </div>
          </div>
        </div>
      `;
    })
    .join("");

  // Attach card click handlers
  _itemsListEl.querySelectorAll(".reported-item-card").forEach((card) => {
    card.addEventListener("click", () => {
      const assetId = card.getAttribute("data-asset-id");
      if (assetId && assetId !== _selectedAssetId) {
        _selectedAssetId = assetId;
        renderReported();
      }
    });
  });

  // Render inspection panel for selected asset
  const selectedItem = _reportedAssets.find((a) => a.asset_id === _selectedAssetId);
  if (selectedItem) {
    renderInspectionPanel(selectedItem);
  } else {
    _inspectionPanelEl.classList.add("hidden");
  }
}

/**
 * Render the inspection panel for a selected flagged asset.
 * @param {object} item
 */
function renderInspectionPanel(item) {
  _inspectionPanelEl.classList.remove("hidden");

  const mediaUrl = `/api/media/${encodeURIComponent(item.asset_id)}`;
  const reporter = item.reported_by || t("reported_page.reported_by_unknown");
  const reportedDateFormatted = item.reported_at ? formatDateTime(item.reported_at) : "";
  const timeRelative = formatRelativeTime(item.reported_at);

  const issuesList = [];
  if (item.flag_coordinates) {
    issuesList.push(`
      <div class="inspection-issue-card">
        <span class="inspection-issue-icon" aria-hidden="true">📍</span>
        <div class="inspection-issue-content">
          <div class="inspection-issue-title">${escapeHtml(t("reported_page.issue_location"))}</div>
          <div class="inspection-issue-desc">${escapeHtml(t("report.flag_coordinates"))}</div>
        </div>
      </div>
    `);
  }
  if (item.flag_date) {
    issuesList.push(`
      <div class="inspection-issue-card">
        <span class="inspection-issue-icon" aria-hidden="true">📅</span>
        <div class="inspection-issue-content">
          <div class="inspection-issue-title">${escapeHtml(t("reported_page.issue_date"))}</div>
          <div class="inspection-issue-desc">${escapeHtml(t("report.flag_date"))}</div>
        </div>
      </div>
    `);
  }
  if (item.other && item.other.trim()) {
    issuesList.push(`
      <div class="inspection-issue-card">
        <span class="inspection-issue-icon" aria-hidden="true">📝</span>
        <div class="inspection-issue-content">
          <div class="inspection-issue-title">${escapeHtml(t("reported_page.issue_notes"))}</div>
          <div class="inspection-notes-text">${escapeHtml(item.other.trim())}</div>
        </div>
      </div>
    `);
  }

  _inspectionPanelEl.innerHTML = `
    <div class="inspection-main-grid">
      <div class="inspection-preview-col">
        <div class="inspection-image-container">
          <img class="inspection-image-preview" src="${mediaUrl}" alt="Photo preview" />
        </div>
      </div>
      <div class="inspection-details-col">
        <div class="inspection-header-box">
          <div class="inspection-asset-id-row">
            <span class="inspection-asset-id-label">${escapeHtml(t("reported_page.asset_id_label"))}</span>
            <span class="inspection-asset-id-val">${escapeHtml(item.asset_id)}</span>
          </div>
          <div class="inspection-meta-row">
            <span>👤 ${escapeHtml(t("reported_page.reported_by", reporter))}</span>
            <span>•</span>
            <span title="${escapeHtml(reportedDateFormatted)}">🕒 ${escapeHtml(timeRelative)}</span>
          </div>
        </div>

        <div class="inspection-issues-box">
          <h4 class="inspection-section-label">${escapeHtml(t("reported_page.issues_title"))}</h4>
          ${issuesList.join("")}
        </div>

        <div class="inspection-actions-footer">
          <a href="${escapeHtml(item.immich_url)}" target="_blank" rel="noopener noreferrer" class="btn-open-immich" title="Open photo in Immich Web to edit metadata">
            <span>${escapeHtml(t("reported_page.open_immich"))}</span>
            <span aria-hidden="true">↗</span>
          </a>
          <button type="button" class="btn-resolve-report" id="btn-resolve-current-report" data-asset-id="${escapeHtml(item.asset_id)}">
            <span aria-hidden="true">✓</span>
            <span>${escapeHtml(t("reported_page.mark_resolved"))}</span>
          </button>
        </div>
      </div>
    </div>
  `;

  // Attach resolve action
  const resolveBtn = _inspectionPanelEl.querySelector("#btn-resolve-current-report");
  if (resolveBtn) {
    resolveBtn.addEventListener("click", () => {
      handleResolveReport(item.asset_id);
    });
  }
}

/**
 * Resolve an issue report, removing the asset from flagged records.
 * @param {string} assetId
 */
export async function handleResolveReport(assetId) {
  if (!assetId) return;

  const confirmed = window.confirm(t("reported_page.resolve_confirm"));
  if (!confirmed) return;

  try {
    await api(`/api/assets/flagged/${encodeURIComponent(assetId)}`, {
      method: "DELETE",
    });

    showShareToast(t("reported_page.resolve_success"));

    // Remove from local list
    const currentIndex = _reportedAssets.findIndex((a) => a.asset_id === assetId);
    _reportedAssets = _reportedAssets.filter((a) => a.asset_id !== assetId);

    // Pick next item or reset
    if (_selectedAssetId === assetId) {
      if (_reportedAssets.length > 0) {
        const nextIndex = Math.min(currentIndex, _reportedAssets.length - 1);
        _selectedAssetId = _reportedAssets[nextIndex].asset_id;
      } else {
        _selectedAssetId = null;
      }
    }

    renderReported();
  } catch (err) {
    console.error("Failed to resolve flagged asset:", err);
    showShareToast(err.message || t("reported_page.resolve_error"));
  }
}

/**
 * Refresh dynamic text and labels on language switch.
 */
export function refreshReportedPageLanguage() {
  if (!_isInitialized || !_pageCardEl) return;
  renderReported();
}

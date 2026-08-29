/**
 * Report Issue Modal Component for Immich Quiz.
 * Allows players to report map/GPS or date inconsistencies and open direct source links in Immich Web.
 */

import { state, el } from "../state.js";
import { api } from "../api.js";
import { t } from "../i18n.js";
import { showShareToast } from "../summary/share.js";

let _currentAssetId = null;
let _currentPlayerName = null;
let _modalEl = null;
let _flagCoordsEl = null;
let _flagDateEl = null;
let _flagOtherEl = null;
let _immichLinkEl = null;
let _submitBtn = null;
let _cancelBtn = null;
let _closeBtn = null;
let _thumbEl = null;

export function initReportModal() {
  _modalEl = document.getElementById("report-issue-modal");
  if (!_modalEl) return;

  _flagCoordsEl = document.getElementById("report-flag-coordinates");
  _flagDateEl = document.getElementById("report-flag-date");
  _flagOtherEl = document.getElementById("report-flag-other");
  _immichLinkEl = document.getElementById("report-immich-link");
  _submitBtn = document.getElementById("report-submit-btn");
  _cancelBtn = document.getElementById("report-cancel-btn");
  _closeBtn = document.getElementById("report-modal-close-btn");
  _thumbEl = document.getElementById("report-modal-thumb");

  if (_flagCoordsEl) _flagCoordsEl.addEventListener("change", validateFormState);
  if (_flagDateEl) _flagDateEl.addEventListener("change", validateFormState);
  if (_flagOtherEl) _flagOtherEl.addEventListener("input", validateFormState);

  if (_submitBtn) _submitBtn.addEventListener("click", handleReportSubmit);
  if (_cancelBtn) _cancelBtn.addEventListener("click", closeReportModal);
  if (_closeBtn) _closeBtn.addEventListener("click", closeReportModal);

  // Close on backdrop click
  _modalEl.addEventListener("click", (e) => {
    if (e.target === _modalEl) {
      closeReportModal();
    }
  });

  // Close on Escape key
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && _modalEl && !_modalEl.classList.contains("hidden")) {
      closeReportModal();
    }
  });
}

function validateFormState() {
  if (!_submitBtn) return;
  const hasCoords = _flagCoordsEl?.checked ?? false;
  const hasDate = _flagDateEl?.checked ?? false;
  const hasOther = Boolean(_flagOtherEl?.value?.trim());

  const isValid = hasCoords || hasDate || hasOther;
  _submitBtn.disabled = !isValid;
}

export function openReportModal(assetId, previewUrl = null, playerName = null) {
  if (!assetId) {
    console.warn("openReportModal called without assetId");
    return;
  }
  _currentAssetId = assetId;
  _currentPlayerName =
    playerName ||
    state.currentQuestion?.player_name ||
    (state.players && state.players[0]) ||
    null;

  if (!_modalEl) {
    initReportModal();
  }
  if (!_modalEl) return;

  // Reset form inputs
  if (_flagCoordsEl) _flagCoordsEl.checked = false;
  if (_flagDateEl) _flagDateEl.checked = false;
  if (_flagOtherEl) _flagOtherEl.value = "";

  // Set thumbnail if provided, else fallback to /api/media/{assetId}
  if (_thumbEl) {
    const src = previewUrl || `/api/media/${assetId}`;
    _thumbEl.src = src;
  }

  // Update direct Immich Web link
  if (_immichLinkEl) {
    const baseUrl = state.immichWebUrl || window.location.origin;
    _immichLinkEl.href = `${baseUrl.replace(/\/+$/, "")}/photos/${assetId}`;
    _immichLinkEl.target = "_blank";
    _immichLinkEl.rel = "noopener noreferrer";
  }

  validateFormState();
  _modalEl.classList.remove("hidden");
  _modalEl.setAttribute("aria-hidden", "false");

  // Focus the first actionable checkbox
  _flagCoordsEl?.focus();
}

export function closeReportModal() {
  if (!_modalEl) return;
  _modalEl.classList.add("hidden");
  _modalEl.setAttribute("aria-hidden", "true");
  _currentAssetId = null;
  _currentPlayerName = null;
}

async function handleReportSubmit(e) {
  if (e) e.preventDefault();
  if (!_currentAssetId) return;

  const flagCoords = _flagCoordsEl?.checked ?? false;
  const flagDate = _flagDateEl?.checked ?? false;
  const otherText = _flagOtherEl?.value?.trim() || null;

  if (!flagCoords && !flagDate && !otherText) {
    return;
  }

  if (_submitBtn) {
    _submitBtn.disabled = true;
  }

  try {
    const payload = {
      asset_id: _currentAssetId,
      flag_coordinates: flagCoords,
      flag_date: flagDate,
      other: otherText,
      reported_by: _currentPlayerName,
    };

    await api("/api/assets/flag", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    closeReportModal();
    showShareToast(t("report.success_toast"));
  } catch (err) {
    console.error("Failed to flag asset:", err);
    showShareToast(err.message || "Failed to submit report");
  } finally {
    if (_submitBtn) {
      validateFormState();
    }
  }
}

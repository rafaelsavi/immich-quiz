import { el } from "./state.js";
import { t, formatDateTime, formatNumber, formatRelativeTime } from "./i18n.js";
import { escapeHtml } from "./formatters.js";
import { api } from "./api.js";

let _syncPollInterval = null;
let _lastSyncStatus = null;
let _activeSyncPopup = null;
let _syncPopupDismissTimer = null;
let _onSyncDocClick = null;
let _onSyncKeyDown = null;

export function getLastSyncStatus() {
  return _lastSyncStatus;
}

export function formatSyncDate(isoStr) {
  if (!isoStr) return "";
  const relative = formatRelativeTime(isoStr);
  const exact = formatDateTime(isoStr, {
    dateStyle: "medium",
    timeStyle: "short",
  });
  return relative ? `${relative} (${exact})` : exact;
}

export function renderSyncStatus(status) {
  if (!status) return;
  _lastSyncStatus = status;
  const isSyncing = status.sync_status === "syncing";
  const neverSynced = !status.last_sync_at && (status.synced_assets || 0) === 0 && !isSyncing;

  if (el.syncLibraryBtn) {
    el.syncLibraryBtn.classList.toggle("syncing", isSyncing);
    el.syncLibraryBtn.classList.toggle("needs-sync", neverSynced);
    el.syncLibraryBtn.disabled = isSyncing;

    if (isSyncing) {
      el.syncLibraryBtn.title = t("setup.syncing_label");
    } else if (neverSynced) {
      el.syncLibraryBtn.title = t("setup.sync_title_never_synced");
    } else if (status.last_sync_at) {
      const formattedDate = formatSyncDate(status.last_sync_at);
      el.syncLibraryBtn.title = formattedDate
        ? t("setup.sync_title_with_date", formattedDate)
        : t("setup.sync_title");
    } else {
      el.syncLibraryBtn.title = t("setup.sync_title");
    }
  }
  if (el.syncBtnLabel) {
    if (isSyncing) {
      const mode = status.sync_mode || "full";
      const stage = status.sync_stage || "initializing";
      const total = status.total_assets || 0;
      const synced = status.synced_assets || 0;

      if (mode === "delta") {
        if (stage === "updating_assets" && synced > 0) {
          el.syncBtnLabel.textContent = t("setup.sync_stage_updating_assets", synced);
        } else if (stage === "updating_albums") {
          el.syncBtnLabel.textContent = t("setup.sync_stage_fetching_albums");
        } else if (stage === "finalizing") {
          el.syncBtnLabel.textContent = t("setup.sync_stage_finalizing");
        } else {
          el.syncBtnLabel.textContent = t("setup.sync_stage_checking_updates");
        }
      } else {
        // Full sync mode
        if (stage === "fetching_albums") {
          if (total > 0 && synced > 0) {
            el.syncBtnLabel.textContent = t("setup.sync_stage_albums_progress", synced, total);
          } else {
            el.syncBtnLabel.textContent = t("setup.sync_stage_fetching_albums");
          }
        } else if (stage === "scanning_assets" || stage === "indexing_assets" || synced > 0) {
          if (total > 0 && total >= synced && synced > 0) {
            const pct = Math.min(100, Math.round((synced / total) * 100));
            el.syncBtnLabel.textContent = `${formatNumber(synced)} / ${formatNumber(total)} (${pct}%)`;
          } else if (synced > 0) {
            el.syncBtnLabel.textContent = t("setup.sync_scanned_count", synced);
          } else {
            el.syncBtnLabel.textContent = t("setup.sync_stage_scanning_assets");
          }
        } else if (stage === "pruning") {
          el.syncBtnLabel.textContent = t("setup.sync_stage_pruning");
        } else if (stage === "finalizing") {
          el.syncBtnLabel.textContent = t("setup.sync_stage_finalizing");
        } else {
          el.syncBtnLabel.textContent = t("setup.sync_stage_initializing");
        }
      }
    } else if (neverSynced) {
      el.syncBtnLabel.textContent = t("setup.sync_label_never_synced");
    } else {
      el.syncBtnLabel.textContent = t("setup.sync_label");
    }
  }
}

export async function checkSyncStatus(onSyncComplete = null) {
  try {
    const status = await api("/api/sync/status");
    if (status.warnings && Object.keys(status.warnings).length > 0) {
      Object.entries(status.warnings).forEach(([lib, msg]) => {
        console.warn(`[Immich Sync Warning (${lib})] ${msg}`);
      });
    }
    if (status.sync_error) {
      console.error(`[Immich Sync Error] ${status.sync_error}`);
    }
    renderSyncStatus(status);
    if (status.sync_status === "syncing" || status.is_syncing) {
      startSyncPolling(onSyncComplete);
    } else if (_syncPollInterval) {
      clearInterval(_syncPollInterval);
      _syncPollInterval = null;
    }
  } catch (e) {
    console.warn("Failed to fetch sync status:", e);
  }
}

export function startSyncPolling(onSyncComplete = null) {
  if (_syncPollInterval) clearInterval(_syncPollInterval);

  let consecutiveErrors = 0;
  const poll = async () => {
    try {
      const status = await api("/api/sync/status");
      consecutiveErrors = 0;
      if (status.warnings && Object.keys(status.warnings).length > 0) {
        Object.entries(status.warnings).forEach(([lib, msg]) => {
          console.warn(`[Immich Sync Warning (${lib})] ${msg}`);
        });
      }
      if (status.sync_error) {
        console.error(`[Immich Sync Error] ${status.sync_error}`);
      }
      renderSyncStatus(status);
      if (status.sync_status !== "syncing" && !status.is_syncing) {
        if (_syncPollInterval) {
          clearInterval(_syncPollInterval);
          _syncPollInterval = null;
        }
        showSyncCompletedPopup(status);
        if (onSyncComplete) {
          await onSyncComplete();
        }
      }
    } catch (e) {
      consecutiveErrors += 1;
      console.warn("Error polling sync status:", e);
      if (consecutiveErrors >= 10) {
        if (_syncPollInterval) {
          clearInterval(_syncPollInterval);
          _syncPollInterval = null;
        }
        if (_lastSyncStatus) {
          renderSyncStatus({ ..._lastSyncStatus, sync_status: _lastSyncStatus.sync_status === "syncing" ? "idle" : _lastSyncStatus.sync_status });
        }
      }
    }
  };

  setTimeout(poll, 150);
  _syncPollInterval = setInterval(poll, 400);
}

export async function triggerLibrarySync(onSyncComplete = null) {
  try {
    dismissSyncPopup();
    const isDelta = Boolean(_lastSyncStatus && _lastSyncStatus.last_sync_at);
    renderSyncStatus({
      sync_status: "syncing",
      is_syncing: true,
      sync_mode: isDelta ? "delta" : "full",
      sync_stage: isDelta ? "checking_updates" : "initializing",
      total_assets: _lastSyncStatus ? _lastSyncStatus.total_assets : 0,
      synced_assets: 0,
    });
    const res = await api("/api/sync", { method: "POST" });
    if (res) renderSyncStatus(res);
    startSyncPolling(onSyncComplete);
  } catch (err) {
    console.error("Failed to trigger sync:", err);
    await checkSyncStatus(onSyncComplete);
  }
}

export function dismissSyncPopup() {
  if (_syncPopupDismissTimer) {
    clearTimeout(_syncPopupDismissTimer);
    _syncPopupDismissTimer = null;
  }
  if (_onSyncDocClick) {
    document.removeEventListener("click", _onSyncDocClick);
    _onSyncDocClick = null;
  }
  if (_onSyncKeyDown) {
    document.removeEventListener("keydown", _onSyncKeyDown);
    _onSyncKeyDown = null;
  }
  if (_activeSyncPopup) {
    const popup = _activeSyncPopup;
    _activeSyncPopup = null;
    popup.classList.add("hide");
    setTimeout(() => {
      if (popup.parentNode) {
        popup.remove();
      }
    }, 250);
  }
}

export function showSyncCompletedPopup(status) {
  if (!status) return null;
  dismissSyncPopup();

  const isError = Boolean(status.sync_error);
  const summary = status.last_sync_summary;
  const modeKey = (summary?.sync_mode || status.sync_mode || "full").toLowerCase();
  const isDelta = modeKey === "delta";
  const modeLabel = isDelta ? t("setup.sync_mode_delta") : t("setup.sync_mode_full");

  const totalAssets = summary?.total_assets ?? status.total_assets ?? 0;
  const assetsSynced = summary?.assets_synced ?? (isDelta ? 0 : (status.synced_assets ?? 0));
  const durationSec = summary?.duration_seconds ?? status.last_sync_duration_seconds;
  const albumsCount = summary?.albums_synced ?? 0;
  const tagsCount = summary?.tags_synced ?? 0;
  const prunedCount = summary?.pruned_assets ?? 0;

  const title = isError ? t("setup.sync_failed_title") : t("setup.sync_completed_title");

  let message = "";
  if (isError) {
    message = escapeHtml(status.sync_error);
  } else if (isDelta) {
    if (assetsSynced > 0) {
      message = t("setup.sync_summary_updated", formatNumber(assetsSynced), formatNumber(totalAssets));
    } else {
      message = t("setup.sync_summary_up_to_date", formatNumber(totalAssets));
    }
  } else {
    message = t("setup.sync_summary_indexed", formatNumber(totalAssets));
  }

  // Build stat chips
  const chips = [];
  if (!isError) {
    if (totalAssets > 0) {
      chips.push(`
        <span class="sync-popup-stat-chip">
          <span class="stat-icon" aria-hidden="true">📷</span>
          <span class="stat-val">${formatNumber(totalAssets)}</span>
        </span>
      `);
    }
    if (albumsCount > 0) {
      chips.push(`
        <span class="sync-popup-stat-chip">
          <span class="stat-icon" aria-hidden="true">📁</span>
          <span>${escapeHtml(t("setup.sync_summary_albums", formatNumber(albumsCount)))}</span>
        </span>
      `);
    }
    if (tagsCount > 0) {
      chips.push(`
        <span class="sync-popup-stat-chip">
          <span class="stat-icon" aria-hidden="true">🏷️</span>
          <span>${escapeHtml(t("setup.sync_summary_tags", formatNumber(tagsCount)))}</span>
        </span>
      `);
    }
    if (prunedCount > 0) {
      chips.push(`
        <span class="sync-popup-stat-chip">
          <span class="stat-icon" aria-hidden="true">🗑️</span>
          <span>${escapeHtml(t("setup.sync_summary_pruned", formatNumber(prunedCount)))}</span>
        </span>
      `);
    }
    if (durationSec !== null && durationSec !== undefined) {
      chips.push(`
        <span class="sync-popup-stat-chip">
          <span class="stat-icon" aria-hidden="true">⏱️</span>
          <span>${escapeHtml(t("setup.sync_summary_duration", durationSec))}</span>
        </span>
      `);
    }
  }

  const iconSvg = isError
    ? `<svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="12"></line><line x1="12" y1="16" x2="12.01" y2="16"></line></svg>`
    : `<svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2.6"><polyline points="20 6 9 17 4 12"></polyline></svg>`;

  const popup = document.createElement("div");
  popup.className = `sync-popup ${isError ? "is-error" : ""}`;
  popup.id = "sync-popup";
  popup.setAttribute("role", "status");
  popup.setAttribute("aria-live", "polite");

  popup.innerHTML = `
    <div class="sync-popup-header">
      <div class="sync-popup-title-wrap">
        <span class="sync-popup-icon" aria-hidden="true">${iconSvg}</span>
        <span class="sync-popup-title">${escapeHtml(title)}</span>
        <span class="sync-popup-mode-badge">${escapeHtml(modeLabel)}</span>
      </div>
      <button type="button" class="sync-popup-close-btn" id="sync-popup-close-btn" aria-label="Close">×</button>
    </div>
    <div class="sync-popup-body">
      <div class="sync-popup-message">${message}</div>
      ${chips.length > 0 ? `<div class="sync-popup-stats">${chips.join("")}</div>` : ""}
    </div>
    <div class="sync-popup-progress" aria-hidden="true"></div>
  `;

  // Determine anchor: prefer .accordion-meta-wrap if syncLibraryBtn is visible
  const syncBtn = el.syncLibraryBtn || document.getElementById("sync-library-btn");
  const isBtnVisible = syncBtn && syncBtn.offsetParent !== null;

  if (isBtnVisible && syncBtn.parentElement) {
    syncBtn.parentElement.appendChild(popup);
    try {
      const btnRect = syncBtn.getBoundingClientRect();
      const wrapRect = syncBtn.parentElement.getBoundingClientRect();
      const centerOffsetFromRight = Math.max(12, Math.round(wrapRect.right - (btnRect.left + btnRect.width / 2)));
      popup.style.setProperty("--pointer-right", `${centerOffsetFromRight}px`);
    } catch (_) {
      popup.style.setProperty("--pointer-right", "48px");
    }
  } else {
    popup.classList.add("floating");
    document.body.appendChild(popup);
  }

  _activeSyncPopup = popup;

  const closeBtn = popup.querySelector("#sync-popup-close-btn");
  if (closeBtn) {
    closeBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      dismissSyncPopup();
    });
  }

  // Auto-dismiss countdown
  _syncPopupDismissTimer = setTimeout(() => {
    dismissSyncPopup();
  }, 6000);

  popup.addEventListener("mouseenter", () => {
    if (_syncPopupDismissTimer) {
      clearTimeout(_syncPopupDismissTimer);
      _syncPopupDismissTimer = null;
    }
  });

  popup.addEventListener("mouseleave", () => {
    if (!_syncPopupDismissTimer) {
      _syncPopupDismissTimer = setTimeout(() => {
        dismissSyncPopup();
      }, 3000);
    }
  });

  _onSyncDocClick = (e) => {
    if (popup && !popup.contains(e.target) && (!syncBtn || !syncBtn.contains(e.target))) {
      dismissSyncPopup();
    }
  };
  setTimeout(() => {
    if (_activeSyncPopup === popup) {
      document.addEventListener("click", _onSyncDocClick);
    }
  }, 100);

  _onSyncKeyDown = (e) => {
    if (e.key === "Escape") {
      dismissSyncPopup();
    }
  };
  document.addEventListener("keydown", _onSyncKeyDown);

  return popup;
}


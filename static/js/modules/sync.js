import { state, el } from "./state.js";
import { t } from "./i18n.js";
import { api } from "./api.js";

let _syncPollInterval = null;
let _lastSyncStatus = null;

export function getLastSyncStatus() {
  return _lastSyncStatus;
}

export function formatSyncDate(isoStr) {
  if (!isoStr) return "";
  try {
    const d = new Date(isoStr);
    if (isNaN(d.getTime())) return "";
    const locale = state && state.language === "PT" ? "pt-BR" : "en-US";
    return d.toLocaleString(locale, {
      dateStyle: "medium",
      timeStyle: "short",
    });
  } catch (_) {
    return "";
  }
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
            el.syncBtnLabel.textContent = `${synced.toLocaleString()} / ${total.toLocaleString()} (${pct}%)`;
          } else if (synced > 0) {
            el.syncBtnLabel.textContent = `${synced.toLocaleString()} scanned`;
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


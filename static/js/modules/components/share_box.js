/**
 * Standardized Share Box & URL Container Component for Immich Quiz.
 *
 * Provides a reusable, uniform interface for sharing capability URLs and challenge links:
 *  1. Clickable URL input box with copy-on-click
 *  2. Icon-only Action Button row (Copy Link, Native Share, Vector QR Code)
 *  3. Expandable client-side SVG QR code container
 *
 * Used in:
 *  - Prepare Game Modal (Challenge Creation Result View)
 *  - Challenge Intermission Screen (Post-match invite card)
 */

import { t } from "../i18n.js";
import { escapeHtml } from "../formatters.js";
import { copyToClipboard } from "../summary/share.js";
import { renderQRCode } from "./qrcode.js";

/**
 * Standard SVG vector icons for uniform share actions.
 */
export const SHARE_ICONS = {
  COPY: `<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>`,
  CHECKMARK: `<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="20 6 9 17 4 12"></polyline></svg>`,
  NATIVE_SHARE: `<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="18" cy="5" r="3"></circle><circle cx="6" cy="12" r="3"></circle><circle cx="18" cy="19" r="3"></circle><line x1="8.59" y1="13.51" x2="15.42" y2="17.49"></line><line x1="15.41" y1="6.51" x2="8.59" y2="10.49"></line></svg>`,
  QR: `<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect width="5" height="5" x="3" y="3" rx="1"></rect><rect width="5" height="5" x="16" y="3" rx="1"></rect><rect width="5" height="5" x="3" y="16" rx="1"></rect><path d="M21 16h-3a2 2 0 0 0-2 2v3"></path><path d="M21 21v.01"></path><path d="M12 7v3a2 2 0 0 1-2 2H7"></path><path d="M3 12h.01"></path><path d="M12 3h.01"></path><path d="M12 16v.01"></path><path d="M16 12h1"></path><path d="M21 12v.01"></path><path d="M12 21v-1"></path></svg>`,
};

/**
 * Render the standardized share URL container and QR card HTML.
 * @param {string} url - The URL to share.
 * @param {Object} [options] - Configuration IDs and labels.
 * @param {string} [options.prefix="challenge-invite"] - ID prefix for element hooks.
 * @param {string} [options.linkBoxId] - Override for share link box element ID.
 * @param {string} [options.urlInputId] - Override for share URL input element ID.
 * @param {string} [options.copyBtnId] - Override for copy button element ID.
 * @param {string} [options.nativeBtnId] - Override for native share button element ID.
 * @param {string} [options.qrBtnId] - Override for QR code toggle button element ID.
 * @param {string} [options.qrContainerId] - Override for QR container element ID.
 * @param {string} [options.qrDisplayId] - Override for QR display container element ID.
 * @returns {string} Standardized HTML string.
 */
export function renderShareUrlContainerHtml(url, options = {}) {
  const prefix = options.prefix || "challenge-invite";
  const linkBoxId = options.linkBoxId || `${prefix}-link-box`;
  const urlInputId = options.urlInputId || `${prefix}-url`;
  const copyBtnId = options.copyBtnId || `${prefix}-copy-btn`;
  const nativeBtnId = options.nativeBtnId || `${prefix}-native-btn`;
  const qrBtnId = options.qrBtnId || `${prefix}-qr-btn`;
  const qrContainerId = options.qrContainerId || `${prefix}-qr-container`;
  const qrDisplayId = options.qrDisplayId || `${prefix}-qr-code`;

  const copyTitle = t("challenge.copy_link");
  const nativeTitle = t("challenge.share_native");
  const qrTitle = t("challenge.qr_code_title");
  const qrHint = t("challenge.scan_qr_hint");

  return `
    <div class="share-url-container">
      <div class="share-link-box" id="${escapeHtml(linkBoxId)}" title="${escapeHtml(copyTitle)}">
        <span class="share-link-icon" aria-hidden="true">🔗</span>
        <input type="text" readonly value="${escapeHtml(url)}" id="${escapeHtml(urlInputId)}" class="share-url-input" spellcheck="false" autocomplete="off" />
      </div>
      <div class="share-action-buttons">
        <button type="button" class="btn-secondary btn-copy-link" id="${escapeHtml(copyBtnId)}" data-i18n-title="challenge.copy_link" data-i18n-aria-label="challenge.copy_link" title="${escapeHtml(copyTitle)}" aria-label="${escapeHtml(copyTitle)}">
          <span class="btn-icon" aria-hidden="true">${SHARE_ICONS.COPY}</span>
        </button>
        <button type="button" class="btn-secondary btn-native-share hidden" id="${escapeHtml(nativeBtnId)}" data-i18n-title="challenge.share_native" data-i18n-aria-label="challenge.share_native" title="${escapeHtml(nativeTitle)}" aria-label="${escapeHtml(nativeTitle)}">
          <span class="btn-icon" aria-hidden="true">${SHARE_ICONS.NATIVE_SHARE}</span>
        </button>
        <button type="button" class="btn-secondary btn-qr-code" id="${escapeHtml(qrBtnId)}" data-i18n-title="challenge.qr_code_title" data-i18n-aria-label="challenge.qr_code_title" title="${escapeHtml(qrTitle)}" aria-label="${escapeHtml(qrTitle)}" aria-expanded="false" aria-controls="${escapeHtml(qrContainerId)}">
          <span class="btn-icon" aria-hidden="true">${SHARE_ICONS.QR}</span>
        </button>
      </div>
    </div>

    <div id="${escapeHtml(qrContainerId)}" class="challenge-qr-container hidden" aria-hidden="true">
      <div class="challenge-qr-card">
        <div id="${escapeHtml(qrDisplayId)}" class="challenge-qr-display"></div>
        <p class="qr-scan-hint" data-i18n="challenge.scan_qr_hint">${escapeHtml(qrHint)}</p>
      </div>
    </div>
  `;
}

/**
 * Wire all interactive events and capabilities for a standardized share box.
 *
 * @param {HTMLElement|Object} containerOrElements - Root container or map of DOM elements.
 * @param {string} url - The URL to share.
 * @param {Object} [options] - Options and callbacks.
 * @param {string} [options.title] - Share title for native share.
 * @param {string} [options.prefix] - Prefix used when resolving elements by ID inside container.
 * @param {number} [options.qrSize=180] - QR code pixel dimension.
 * @returns {{ setUrl: (newUrl: string) => void, toggleQr: (show?: boolean) => void, copy: () => Promise<boolean> }}
 */
export function setupShareBox(containerOrElements, url, options = {}) {
  const prefix = options.prefix || "challenge-invite";
  const root = containerOrElements instanceof HTMLElement ? containerOrElements : document;

  const linkBox =
    containerOrElements?.linkBox ||
    root.querySelector?.(`#${options.linkBoxId || `${prefix}-link-box`}`) ||
    document.getElementById(options.linkBoxId || `${prefix}-link-box`);

  const urlInput =
    containerOrElements?.urlInput ||
    root.querySelector?.(`#${options.urlInputId || `${prefix}-url`}`) ||
    document.getElementById(options.urlInputId || `${prefix}-url`);

  const copyBtn =
    containerOrElements?.copyBtn ||
    root.querySelector?.(`#${options.copyBtnId || `${prefix}-copy-btn`}`) ||
    document.getElementById(options.copyBtnId || `${prefix}-copy-btn`);

  const nativeBtn =
    containerOrElements?.nativeBtn ||
    root.querySelector?.(`#${options.nativeBtnId || `${prefix}-native-btn`}`) ||
    document.getElementById(options.nativeBtnId || `${prefix}-native-btn`);

  const qrBtn =
    containerOrElements?.qrBtn ||
    root.querySelector?.(`#${options.qrBtnId || `${prefix}-qr-btn`}`) ||
    document.getElementById(options.qrBtnId || `${prefix}-qr-btn`);

  const qrContainer =
    containerOrElements?.qrContainer ||
    root.querySelector?.(`#${options.qrContainerId || `${prefix}-qr-container`}`) ||
    document.getElementById(options.qrContainerId || `${prefix}-qr-container`);

  const qrDisplay =
    containerOrElements?.qrDisplay ||
    root.querySelector?.(`#${options.qrDisplayId || `${prefix}-qr-code`}`) ||
    document.getElementById(options.qrDisplayId || `${prefix}-qr-code`);

  let currentUrl = url;

  // 1. URL Input initialization
  if (urlInput && currentUrl) {
    urlInput.value = currentUrl;
    urlInput.setAttribute("value", currentUrl);
  }

  // 2. QR Code setup
  if (qrDisplay && currentUrl) {
    renderQRCode(qrDisplay, currentUrl, { size: options.qrSize || 180 });
  }

  // 2. QR Toggle handler
  const toggleQr = (force) => {
    if (!qrContainer) return;
    const shouldHide = force !== undefined ? !force : !qrContainer.classList.contains("hidden");
    qrContainer.classList.toggle("hidden", shouldHide);
    qrContainer.setAttribute("aria-hidden", String(shouldHide));
    if (qrBtn) {
      qrBtn.classList.toggle("active", !shouldHide);
      qrBtn.setAttribute("aria-expanded", String(!shouldHide));
    }
  };

  if (qrBtn && !qrBtn.dataset.shareBound) {
    qrBtn.dataset.shareBound = "true";
    qrBtn.addEventListener("click", () => toggleQr());
  }

  // 3. Copy Handler with SVG checkmark feedback
  const copy = async () => {
    if (!currentUrl) return false;
    if (urlInput) {
      urlInput.select();
    }
    return await copyToClipboard(currentUrl, {
      button: copyBtn,
      copiedHtml: `<span class="btn-icon" aria-hidden="true">${SHARE_ICONS.CHECKMARK}</span>`,
      successMessage: t("challenge.link_copied"),
    });
  };

  if (copyBtn && !copyBtn.dataset.shareBound) {
    copyBtn.dataset.shareBound = "true";
    copyBtn.addEventListener("click", copy);
  }

  if (linkBox && !linkBox.dataset.shareBound) {
    linkBox.dataset.shareBound = "true";
    linkBox.addEventListener("click", copy);
  }

  // 4. Native Share integration with capability check
  if (nativeBtn) {
    if (typeof navigator !== "undefined" && typeof navigator.share === "function") {
      nativeBtn.classList.remove("hidden");
      if (!nativeBtn.dataset.shareBound) {
        nativeBtn.dataset.shareBound = "true";
        nativeBtn.addEventListener("click", async () => {
          if (!currentUrl) return;
          try {
            await navigator.share({
              title: options.title || t("challenge.invite_message") || "Immich Quiz Challenge",
              url: currentUrl,
            });
          } catch (_) {}
        });
      }
    } else {
      nativeBtn.classList.add("hidden");
    }
  }

  // Controller
  return {
    setUrl(newUrl) {
      currentUrl = newUrl;
      if (urlInput) {
        urlInput.value = newUrl;
        urlInput.setAttribute("value", newUrl);
      }
      if (qrDisplay && newUrl) {
        renderQRCode(qrDisplay, newUrl, { size: options.qrSize || 180 });
      }
      if (copyBtn) {
        copyBtn.classList.remove("copied");
        copyBtn.innerHTML = `<span class="btn-icon" aria-hidden="true">${SHARE_ICONS.COPY}</span>`;
      }
      toggleQr(false);
    },
    toggleQr,
    copy,
  };
}

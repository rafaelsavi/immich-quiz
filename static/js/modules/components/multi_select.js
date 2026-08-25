import { t } from "../i18n.js";

/**
 * @typedef {Object} MultiSelectItem
 * @property {string} id - Unique identifier (UUID, country name, or album ID)
 * @property {string} name - Display label
 */

export class MultiSelect {
  /**
   * @param {Object} config
   * @param {HTMLElement} config.container - Root .multi-select wrapper element
   * @param {string} [config.placeholderKey] - i18n key for empty placeholder (e.g. "setup.all_photos")
   * @param {string} [config.searchPlaceholderKey] - i18n key for search input placeholder
   * @param {string} [config.noResultsKey] - i18n key for empty search results
   * @param {function(number): string} [config.summaryFormatter] - Formatter for >3 selected items
   * @param {function(string[], MultiSelectItem[]): void} [config.onChange] - Change callback
   */
  constructor(config) {
    this.container = config.container;
    this.placeholderKey = config.placeholderKey || "setup.all_photos";
    this.searchPlaceholderKey = config.searchPlaceholderKey || "setup.search_placeholder";
    this.noResultsKey = config.noResultsKey || "setup.no_results_found";
    this.minSearchItems = config.minSearchItems !== undefined
      ? config.minSearchItems
      : (config.searchThreshold !== undefined ? config.searchThreshold : 6);
    this.summaryFormatter = config.summaryFormatter || ((count) => `${count} selected`);
    this.onChange = config.onChange || (() => { });

    this.items = [];
    this.selectedMap = new Map(); // id -> name
    this.countsMap = null; // id/name -> count
    this.isOpen = false;

    this._boundOnDocClick = this._onDocClick.bind(this);
    this._boundOnDocKeydown = this._onDocKeydown.bind(this);

    this._renderDom();
    this._cacheDom();
    this._bindEvents();
    this.updateTriggerUi();
  }

  _renderDom() {
    this.container.innerHTML = `
      <div class="multi-select-trigger" role="combobox" aria-haspopup="listbox" aria-expanded="false" tabindex="0">
        <div class="multi-select-value"></div>
        <div class="multi-select-controls">
          <button type="button" class="multi-select-clear hidden" title="${t("setup.multi_select_clear")}" aria-label="${t("setup.multi_select_clear")}">
            <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
              <line x1="18" y1="6" x2="6" y2="18"></line>
              <line x1="6" y1="6" x2="18" y2="18"></line>
            </svg>
          </button>
          <span class="select-arrow multi-select-arrow" aria-hidden="true">
            <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
              <polyline points="6 9 12 15 18 9"></polyline>
            </svg>
          </span>
        </div>
      </div>
      <div class="multi-select-dropdown hidden" role="listbox">
        <div class="multi-select-search-wrap">
          <svg class="search-icon" viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
            <circle cx="11" cy="11" r="8"></circle>
            <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
          </svg>
          <input type="text" class="multi-select-search" autocomplete="off" />
          <button type="button" class="search-clear-btn hidden" title="${t("setup.clear_search")}" aria-label="${t("setup.clear_search")}">
            <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
              <line x1="18" y1="6" x2="6" y2="18"></line>
              <line x1="6" y1="6" x2="18" y2="18"></line>
            </svg>
          </button>
        </div>
        <div class="multi-select-actions">
          <button type="button" class="btn-text-action select-all-btn" data-i18n="setup.select_all">All</button>
          <button type="button" class="btn-text-action deselect-all-btn" data-i18n="setup.deselect_all">None</button>
        </div>
        <div class="multi-select-options"></div>
      </div>
    `;
  }

  _cacheDom() {
    this.triggerEl = this.container.querySelector(".multi-select-trigger");
    this.valueEl = this.container.querySelector(".multi-select-value");
    this.clearBtnEl = this.container.querySelector(".multi-select-clear");
    this.dropdownEl = this.container.querySelector(".multi-select-dropdown");
    this.searchWrapEl = this.container.querySelector(".multi-select-search-wrap");
    this.searchInputEl = this.container.querySelector(".multi-select-search");
    this.searchClearBtnEl = this.container.querySelector(".search-clear-btn");
    this.selectAllBtnEl = this.container.querySelector(".select-all-btn");
    this.deselectAllBtnEl = this.container.querySelector(".deselect-all-btn");
    this.optionsListEl = this.container.querySelector(".multi-select-options");

    if (this.searchInputEl) {
      this.searchInputEl.placeholder = t(this.searchPlaceholderKey);
    }
    this._updateSearchVisibility();
  }

  _bindEvents() {
    this.triggerEl.addEventListener("click", (e) => {
      if (e.target.closest(".multi-select-clear")) return;
      this.toggle();
    });

    this.triggerEl.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        this.toggle();
      } else if (e.key === "Escape") {
        this.close();
      }
    });

    this.clearBtnEl.addEventListener("click", (e) => {
      e.stopPropagation();
      this.clear();
    });

    this.searchInputEl.addEventListener("input", () => {
      this._updateSearchClearVisibility();
      this.renderOptions();
    });

    this.searchClearBtnEl.addEventListener("click", () => {
      this.searchInputEl.value = "";
      this._updateSearchClearVisibility();
      this.renderOptions();
      this.searchInputEl.focus();
    });

    this.selectAllBtnEl.addEventListener("click", () => this.selectAll());
    this.deselectAllBtnEl.addEventListener("click", () => this.deselectAll());

    document.addEventListener("click", this._boundOnDocClick);
    document.addEventListener("keydown", this._boundOnDocKeydown);
  }

  _onDocClick(e) {
    if (!this.container.contains(e.target)) {
      this.close();
    }
  }

  _onDocKeydown(e) {
    if (e.key === "Escape" && this.isOpen) {
      this.close();
      this.triggerEl.focus();
    }
  }

  destroy() {
    document.removeEventListener("click", this._boundOnDocClick);
    document.removeEventListener("keydown", this._boundOnDocKeydown);
    if (this.container) {
      this.container.classList.remove("open");
      this.container.innerHTML = "";
    }
  }

  _updateSearchClearVisibility() {
    if (this.searchInputEl && this.searchInputEl.value.length > 0) {
      this.searchClearBtnEl.classList.remove("hidden");
    } else if (this.searchClearBtnEl) {
      this.searchClearBtnEl.classList.add("hidden");
    }
  }

  _updateSearchVisibility() {
    if (!this.searchWrapEl) return;
    const shouldShow = this.items.length >= this.minSearchItems;
    if (shouldShow) {
      this.searchWrapEl.classList.remove("hidden");
    } else {
      this.searchWrapEl.classList.add("hidden");
      if (this.searchInputEl && this.searchInputEl.value) {
        this.searchInputEl.value = "";
        this._updateSearchClearVisibility();
      }
    }
  }

  _isSearchHidden() {
    return !this.searchWrapEl || this.searchWrapEl.classList.contains("hidden");
  }

  // Public API
  setItems(items) {
    this.items = items || [];
    const validIds = new Set(this.items.map((i) => i.id));
    for (const id of Array.from(this.selectedMap.keys())) {
      if (!validIds.has(id)) {
        this.selectedMap.delete(id);
      }
    }
    this._updateSearchVisibility();
    this.renderOptions();
    this.updateTriggerUi();
  }

  getSelectedIds() {
    return Array.from(this.selectedMap.keys());
  }

  getSelectedItems() {
    return Array.from(this.selectedMap.entries()).map(([id, name]) => ({ id, name }));
  }

  setSelectedIds(ids) {
    this.selectedMap.clear();
    const idSet = new Set(ids);
    this.items.forEach((item) => {
      if (idSet.has(item.id)) {
        this.selectedMap.set(item.id, item.name);
      }
    });
    this.renderOptions();
    this.updateTriggerUi();
  }

  clear() {
    this.selectedMap.clear();
    if (this.searchInputEl) this.searchInputEl.value = "";
    this._updateSearchClearVisibility();
    this.renderOptions();
    this.updateTriggerUi();
    this._notifyChange();
  }

  toggleItem(id, name) {
    if (this.selectedMap.has(id)) {
      this.selectedMap.delete(id);
    } else {
      this.selectedMap.set(id, name);
    }
    this.renderOptions();
    this.updateTriggerUi();
    this._notifyChange();
  }

  _getItemCount(item) {
    if (!this.countsMap) return null;
    if (this.countsMap.has(item.id)) return this.countsMap.get(item.id);
    if (this.countsMap.has(item.name)) return this.countsMap.get(item.name);
    if (typeof item.id === "string" && this.countsMap.has(item.id.toLowerCase())) {
      return this.countsMap.get(item.id.toLowerCase());
    }
    if (typeof item.name === "string" && this.countsMap.has(item.name.toLowerCase())) {
      return this.countsMap.get(item.name.toLowerCase());
    }
    return 0;
  }

  updateCounts(counts) {
    if (!counts) {
      this.countsMap = null;
    } else if (counts instanceof Map) {
      this.countsMap = counts;
    } else if (typeof counts === "object") {
      this.countsMap = new Map(Object.entries(counts));
    }
    this.renderOptions();
  }

  selectAll() {
    const query = (this.searchInputEl && !this._isSearchHidden())
      ? this.searchInputEl.value.trim().toLowerCase()
      : "";
    const filtered = this.items.filter((item) => item.name.toLowerCase().includes(query));
    filtered.forEach((item) => {
      if (this.countsMap !== null && this._getItemCount(item) === 0) return;
      this.selectedMap.set(item.id, item.name);
    });
    this.renderOptions();
    this.updateTriggerUi();
    this._notifyChange();
  }

  deselectAll() {
    const query = (this.searchInputEl && !this._isSearchHidden())
      ? this.searchInputEl.value.trim().toLowerCase()
      : "";
    if (query) {
      const filtered = this.items.filter((item) => item.name.toLowerCase().includes(query));
      filtered.forEach((item) => this.selectedMap.delete(item.id));
    } else {
      this.selectedMap.clear();
    }
    this.renderOptions();
    this.updateTriggerUi();
    this._notifyChange();
  }

  open() {
    this.isOpen = true;
    if (this.container) this.container.classList.add("open");
    this.triggerEl.setAttribute("aria-expanded", "true");
    this.dropdownEl.classList.remove("hidden");
    this._updateSearchVisibility();
    if (this.searchInputEl) {
      this.searchInputEl.value = "";
      this._updateSearchClearVisibility();
      this.renderOptions();
      const isTouchDevice = window.matchMedia && window.matchMedia("(pointer: coarse)").matches;
      if (!isTouchDevice && !this._isSearchHidden()) {
        setTimeout(() => {
          if (this.isOpen && !this._isSearchHidden()) {
            this.searchInputEl.focus();
          }
        }, 50);
      }
    }
  }

  close() {
    this.isOpen = false;
    if (this.container) this.container.classList.remove("open");
    this.triggerEl.setAttribute("aria-expanded", "false");
    this.dropdownEl.classList.remove("hidden");
    this.dropdownEl.classList.add("hidden");
  }

  toggle() {
    this.isOpen ? this.close() : this.open();
  }

  updateTriggerUi() {
    if (!this.valueEl) return;
    this.valueEl.replaceChildren();

    const selectedNames = Array.from(this.selectedMap.values());
    const allNamesList = selectedNames.length > 0
      ? (selectedNames.length > 1
        ? `${t("setup.multi_select_selected_count", selectedNames.length)}\n• ` + selectedNames.join("\n• ")
        : selectedNames[0])
      : "";

    if (this.selectedMap.size === 0) {
      const placeholder = document.createElement("span");
      placeholder.className = "placeholder";
      placeholder.textContent = t(this.placeholderKey);
      this.valueEl.appendChild(placeholder);
      this.clearBtnEl.classList.add("hidden");
      this.triggerEl.removeAttribute("title");
    } else if (this.selectedMap.size <= 3) {
      this.triggerEl.title = allNamesList;
      this.selectedMap.forEach((name, id) => {
        const tag = document.createElement("span");
        tag.className = "multi-select-tag";
        tag.title = name;

        const label = document.createElement("span");
        label.className = "tag-label";
        label.textContent = name;

        const removeBtn = document.createElement("button");
        removeBtn.type = "button";
        removeBtn.className = "tag-remove";
        removeBtn.title = t("setup.multi_select_remove_item", name);
        removeBtn.setAttribute("aria-label", t("setup.multi_select_remove_item", name));
        removeBtn.innerHTML = `
          <svg viewBox="0 0 24 24" width="10" height="10" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round">
            <line x1="18" y1="6" x2="6" y2="18"></line>
            <line x1="6" y1="6" x2="18" y2="18"></line>
          </svg>
        `;
        removeBtn.addEventListener("click", (e) => {
          e.stopPropagation();
          this.toggleItem(id, name);
        });

        tag.appendChild(label);
        tag.appendChild(removeBtn);
        this.valueEl.appendChild(tag);
      });
      this.clearBtnEl.classList.remove("hidden");
    } else {
      this.triggerEl.title = allNamesList;
      const summary = document.createElement("span");
      summary.className = "multi-select-summary";
      summary.title = allNamesList;
      summary.textContent = this.summaryFormatter(this.selectedMap.size);
      this.valueEl.appendChild(summary);
      this.clearBtnEl.classList.remove("hidden");
    }
  }

  renderOptions() {
    if (!this.optionsListEl) return;
    this.optionsListEl.replaceChildren();

    const query = (this.searchInputEl && !this._isSearchHidden())
      ? this.searchInputEl.value.trim().toLowerCase()
      : "";
    const filtered = this.items.filter((item) => item.name.toLowerCase().includes(query));

    const visibleItems = filtered.filter((item) => {
      if (this.selectedMap.has(item.id)) return true;
      const count = this._getItemCount(item);
      if (count !== null && count === 0) return false;
      return true;
    });

    if (visibleItems.length === 0) {
      const empty = document.createElement("div");
      empty.className = "multi-select-empty";
      empty.textContent = t(this.noResultsKey);
      this.optionsListEl.appendChild(empty);
      return;
    }

    visibleItems.forEach((item) => {
      const isSelected = this.selectedMap.has(item.id);
      const count = this._getItemCount(item);
      const isZeroMatch = count !== null && count === 0;

      const optEl = document.createElement("div");
      optEl.className = `multi-select-option ${isSelected ? "selected" : ""} ${isZeroMatch ? "zero-match" : ""}`;

      const checkbox = document.createElement("input");
      checkbox.type = "checkbox";
      checkbox.checked = isSelected;

      const label = document.createElement("span");
      label.className = "multi-select-option-label";
      label.textContent = item.name;

      optEl.appendChild(checkbox);
      optEl.appendChild(label);

      if (item.subtitle) {
        const sub = document.createElement("span");
        sub.className = "multi-select-option-sub";
        sub.textContent = item.subtitle;
        optEl.appendChild(sub);
      }

      if (count !== null) {
        const badge = document.createElement("span");
        badge.className = `multi-select-count-badge ${isZeroMatch ? "zero" : ""}`;
        badge.textContent = `(${count})`;
        optEl.appendChild(badge);
      }

      optEl.addEventListener("click", (e) => {
        e.stopPropagation();
        this.toggleItem(item.id, item.name);
      });

      this.optionsListEl.appendChild(optEl);
    });
  }

  _notifyChange() {
    this.onChange(this.getSelectedIds(), this.getSelectedItems());
  }
}

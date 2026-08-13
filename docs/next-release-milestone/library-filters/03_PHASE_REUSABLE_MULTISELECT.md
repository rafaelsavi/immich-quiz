# Phase 3: Reusable MultiSelect JavaScript Component

## Objective
Refactor the custom album dropdown in `static/js/app.js` into a reusable, class-based `MultiSelect` component (`static/js/modules/components/multi_select.js`) that powers **Albums**, **Countries**, **Cities**, and **People** with identical UX, styling, keyboard accessibility, and search capabilities.

---

## 1. Component Specification

### File: `static/js/modules/components/multi_select.js`

```javascript
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
   * @param {HTMLSelectElement} [config.nativeSelect] - Hidden native select for form serialization
   * @param {string} [config.placeholderKey] - i18n key for empty placeholder (e.g. "setup.all_photos")
   * @param {string} [config.searchPlaceholderKey] - i18n key for search input placeholder
   * @param {string} [config.noResultsKey] - i18n key for empty search results
   * @param {function(number): string} [config.summaryFormatter] - Formatter for >3 selected items
   * @param {function(string[], MultiSelectItem[]): void} [config.onChange] - Change callback
   */
  constructor(config) {
    this.container = config.container;
    this.nativeSelect = config.nativeSelect || null;
    this.placeholderKey = config.placeholderKey || "setup.all_photos";
    this.searchPlaceholderKey = config.searchPlaceholderKey || "setup.search_placeholder";
    this.noResultsKey = config.noResultsKey || "setup.no_results_found";
    this.summaryFormatter = config.summaryFormatter || ((count) => `${count} selected`);
    this.onChange = config.onChange || (() => {});

    this.items = [];
    this.selectedMap = new Map(); // id -> name
    this.isOpen = false;

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
          <button type="button" class="multi-select-clear hidden" title="Clear selection" aria-label="Clear selection">
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
          <button type="button" class="search-clear-btn hidden" title="Clear search" aria-label="Clear search">
            <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
              <line x1="18" y1="6" x2="6" y2="18"></line>
              <line x1="6" y1="6" x2="18" y2="18"></line>
            </svg>
          </button>
        </div>
        <div class="multi-select-actions">
          <button type="button" class="btn-text-action select-all-btn" data-i18n="setup.select_all">Select All</button>
          <button type="button" class="btn-text-action deselect-all-btn" data-i18n="setup.deselect_all">Deselect All</button>
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
    this.searchInputEl = this.container.querySelector(".multi-select-search");
    this.searchClearBtnEl = this.container.querySelector(".search-clear-btn");
    this.selectAllBtnEl = this.container.querySelector(".select-all-btn");
    this.deselectAllBtnEl = this.container.querySelector(".deselect-all-btn");
    this.optionsListEl = this.container.querySelector(".multi-select-options");

    if (this.searchInputEl) {
      this.searchInputEl.placeholder = t(this.searchPlaceholderKey);
    }
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

    document.addEventListener("click", (e) => {
      if (!this.container.contains(e.target)) {
        this.close();
      }
    });

    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && this.isOpen) {
        this.close();
        this.triggerEl.focus();
      }
    });
  }

  _updateSearchClearVisibility() {
    if (this.searchInputEl.value.length > 0) {
      this.searchClearBtnEl.classList.remove("hidden");
    } else {
      this.searchClearBtnEl.classList.add("hidden");
    }
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
    this.renderOptions();
    this.updateTriggerUi();
    this._syncNativeSelect();
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
    this._syncNativeSelect();
  }

  clear() {
    this.selectedMap.clear();
    if (this.searchInputEl) this.searchInputEl.value = "";
    this._updateSearchClearVisibility();
    this.renderOptions();
    this.updateTriggerUi();
    this._syncNativeSelect();
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
    this._syncNativeSelect();
    this._notifyChange();
  }

  selectAll() {
    const query = this.searchInputEl ? this.searchInputEl.value.trim().toLowerCase() : "";
    const filtered = this.items.filter((item) => item.name.toLowerCase().includes(query));
    filtered.forEach((item) => this.selectedMap.set(item.id, item.name));
    this.renderOptions();
    this.updateTriggerUi();
    this._syncNativeSelect();
    this._notifyChange();
  }

  deselectAll() {
    this.clear();
  }

  open() {
    this.isOpen = true;
    this.triggerEl.setAttribute("aria-expanded", "true");
    this.dropdownEl.classList.remove("hidden");
    if (this.searchInputEl) {
      this.searchInputEl.value = "";
      this._updateSearchClearVisibility();
      this.renderOptions();
      setTimeout(() => this.searchInputEl.focus(), 50);
    }
  }

  close() {
    this.isOpen = false;
    this.triggerEl.setAttribute("aria-expanded", "false");
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
          ? `Selected (${selectedNames.length}):\n• ` + selectedNames.join("\n• ")
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
        removeBtn.setAttribute("aria-label", `Remove ${name}`);
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

    const query = this.searchInputEl ? this.searchInputEl.value.trim().toLowerCase() : "";
    const filtered = this.items.filter((item) => item.name.toLowerCase().includes(query));

    if (filtered.length === 0) {
      const empty = document.createElement("div");
      empty.className = "multi-select-empty";
      empty.textContent = t(this.noResultsKey);
      this.optionsListEl.appendChild(empty);
      return;
    }

    filtered.forEach((item) => {
      const isSelected = this.selectedMap.has(item.id);
      const optEl = document.createElement("div");
      optEl.className = `multi-select-option ${isSelected ? "selected" : ""}`;

      const checkbox = document.createElement("input");
      checkbox.type = "checkbox";
      checkbox.checked = isSelected;

      const label = document.createElement("span");
      label.className = "multi-select-option-label";
      label.textContent = item.name;

      optEl.appendChild(checkbox);
      optEl.appendChild(label);

      optEl.addEventListener("click", (e) => {
        e.stopPropagation();
        this.toggleItem(item.id, item.name);
      });

      this.optionsListEl.appendChild(optEl);
    });
  }

  _syncNativeSelect() {
    if (!this.nativeSelect) return;
    const selectedIds = new Set(this.selectedMap.keys());
    Array.from(this.nativeSelect.options).forEach((opt) => {
      if (opt.value === "") {
        opt.selected = selectedIds.size === 0;
      } else {
        opt.selected = selectedIds.has(opt.value);
      }
    });
    this.nativeSelect.dispatchEvent(new Event("change", { bubbles: true }));
  }

  _notifyChange() {
    this.onChange(this.getSelectedIds(), this.getSelectedItems());
  }
}
```

---

## 2. Instantiation Examples in `app.js`

```javascript
// 1. Album Selector
const albumMultiSelect = new MultiSelect({
  container: document.getElementById("album-multi-select"),
  nativeSelect: document.getElementById("album"),
  placeholderKey: "setup.all_photos",
  searchPlaceholderKey: "setup.album_search_placeholder",
  noResultsKey: "setup.no_albums_found",
  summaryFormatter: (count) => t("setup.albums_selected", count),
  onChange: () => {
    updateFiltersSummaryBadge();
    triggerPreflightDebounced();
  },
});

// 2. Country Selector
const countryMultiSelect = new MultiSelect({
  container: document.getElementById("country-multi-select"),
  placeholderKey: "setup.all_countries",
  searchPlaceholderKey: "setup.country_search_placeholder",
  noResultsKey: "setup.no_countries_found",
  summaryFormatter: (count) => t("setup.countries_selected", count),
  onChange: () => {
    updateFiltersSummaryBadge();
    triggerPreflightDebounced();
  },
});

// 3. City / Region Selector
const cityMultiSelect = new MultiSelect({
  container: document.getElementById("city-multi-select"),
  placeholderKey: "setup.all_cities",
  searchPlaceholderKey: "setup.city_search_placeholder",
  noResultsKey: "setup.no_cities_found",
  summaryFormatter: (count) => t("setup.cities_selected", count),
  onChange: () => {
    updateFiltersSummaryBadge();
    triggerPreflightDebounced();
  },
});

// 4. People Selector
const peopleMultiSelect = new MultiSelect({
  container: document.getElementById("people-multi-select"),
  placeholderKey: "setup.all_people",
  searchPlaceholderKey: "setup.people_search_placeholder",
  noResultsKey: "setup.no_people_found",
  summaryFormatter: (count) => t("setup.people_selected", count),
  onChange: () => {
    updateFiltersSummaryBadge();
    triggerPreflightDebounced();
  },
});
```

---

## 3. Acceptance Criteria
- [ ] Component renders its own DOM shell into any target container.
- [ ] Component handles dynamic item updates (`setItems`) without leaking event listeners.
- [ ] Tag removal button clicks stop propagation and do not trigger dropdown toggle.
- [ ] Outside clicks and pressing `Escape` close any open dropdowns.
- [ ] Keyboard navigation (Enter / Space on options) toggles selection cleanly.

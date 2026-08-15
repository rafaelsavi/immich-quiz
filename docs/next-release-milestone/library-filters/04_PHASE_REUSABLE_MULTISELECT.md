# Phase 4: Reusable MultiSelect JavaScript Component

## Objective
Refactor the custom album dropdown in `static/js/app.js` into a reusable, class-based `MultiSelect` component (`static/js/modules/components/multi_select.js`) that powers **Albums**, **Countries**, **Cities**, and **People** with identical UX, styling, keyboard accessibility, dynamic updates (`setItems`), and search capabilities.

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

## 2. CSS Stylesheet

### File: `static/css/components/multi_select.css`

Create this file from scratch. It must style all class names generated by the `MultiSelect` component:

```css
/* === Reusable Multi-Select Component === */

.multi-select {
  position: relative;
  width: 100%;
  font-family: inherit;
  font-size: 0.9rem;
}

/* Trigger button (closed state) */
.multi-select-trigger {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.4rem;
  padding: 0.45rem 0.6rem 0.45rem 0.75rem;
  border: 1px solid #d1d5e0;
  border-radius: 8px;
  background: #ffffff;
  cursor: pointer;
  min-height: 38px;
  transition: border-color 0.15s ease, box-shadow 0.15s ease;
  user-select: none;
}

.multi-select-trigger:hover {
  border-color: #a0aabf;
}

.multi-select-trigger:focus-visible {
  outline: none;
  border-color: var(--accent, #0f7c7f);
  box-shadow: 0 0 0 3px rgba(15, 124, 127, 0.15);
}

.multi-select-trigger[aria-expanded="true"] {
  border-color: var(--accent, #0f7c7f);
  box-shadow: 0 0 0 3px rgba(15, 124, 127, 0.12);
}

/* Value area (tags / placeholder / summary) */
.multi-select-value {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 4px;
  flex: 1;
  min-width: 0;
}

.multi-select-value .placeholder {
  color: #9aa3b5;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* Selected tag pills */
.multi-select-tag {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 2px 6px 2px 8px;
  background: rgba(15, 124, 127, 0.1);
  color: var(--accent, #0f7c7f);
  border-radius: 999px;
  font-size: 0.8rem;
  font-weight: 500;
  max-width: 140px;
  white-space: nowrap;
}

.tag-label {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.tag-remove {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: none;
  background: transparent;
  color: inherit;
  opacity: 0.7;
  cursor: pointer;
  padding: 0;
  border-radius: 50%;
  transition: opacity 0.15s ease;
  flex-shrink: 0;
}

.tag-remove:hover {
  opacity: 1;
}

/* Summary text when > 3 items selected */
.multi-select-summary {
  font-size: 0.85rem;
  font-weight: 500;
  color: var(--accent, #0f7c7f);
}

/* Controls row (clear + arrow) */
.multi-select-controls {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-shrink: 0;
}

.multi-select-clear {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: none;
  background: transparent;
  color: #9aa3b5;
  cursor: pointer;
  padding: 2px;
  border-radius: 4px;
  transition: color 0.15s ease;
}

.multi-select-clear:hover {
  color: var(--text-dark, #242938);
}

.multi-select-arrow {
  display: inline-flex;
  align-items: center;
  color: #9aa3b5;
  transition: transform 0.2s cubic-bezier(0.4, 0, 0.2, 1);
}

.multi-select-trigger[aria-expanded="true"] .multi-select-arrow {
  transform: rotate(180deg);
}

/* Dropdown panel */
.multi-select-dropdown {
  position: absolute;
  top: calc(100% + 4px);
  left: 0;
  right: 0;
  z-index: 100;
  background: #ffffff;
  border: 1px solid #d1d5e0;
  border-radius: 10px;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.1);
  overflow: hidden;
  display: flex;
  flex-direction: column;
  max-height: 280px;
}

.multi-select-dropdown.hidden {
  display: none;
}

/* Search row */
.multi-select-search-wrap {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 0.45rem 0.65rem;
  border-bottom: 1px solid #edf1f7;
  background: #fafbfc;
}

.search-icon {
  color: #9aa3b5;
  flex-shrink: 0;
}

.multi-select-search {
  flex: 1;
  border: none;
  outline: none;
  background: transparent;
  font-family: inherit;
  font-size: 0.875rem;
  color: var(--text-dark, #242938);
}

.multi-select-search::placeholder {
  color: #b0b8cc;
}

.search-clear-btn {
  display: inline-flex;
  align-items: center;
  border: none;
  background: transparent;
  color: #9aa3b5;
  cursor: pointer;
  padding: 2px;
  border-radius: 4px;
  transition: color 0.15s ease;
}

.search-clear-btn:hover {
  color: var(--text-dark, #242938);
}

.search-clear-btn.hidden {
  display: none;
}

/* Select All / Deselect All action row */
.multi-select-actions {
  display: flex;
  gap: 0.75rem;
  padding: 0.3rem 0.75rem;
  border-bottom: 1px solid #edf1f7;
}

.btn-text-action {
  background: none;
  border: none;
  font-family: inherit;
  font-size: 0.8rem;
  font-weight: 600;
  color: var(--accent, #0f7c7f);
  cursor: pointer;
  padding: 0;
  transition: opacity 0.15s ease;
}

.btn-text-action:hover {
  opacity: 0.75;
}

/* Options list */
.multi-select-options {
  overflow-y: auto;
  flex: 1;
}

.multi-select-option {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.45rem 0.75rem;
  cursor: pointer;
  font-size: 0.875rem;
  color: var(--text-dark, #242938);
  transition: background-color 0.1s ease;
}

.multi-select-option:hover {
  background: #f4f6fb;
}

.multi-select-option.selected {
  background: rgba(15, 124, 127, 0.07);
}

.multi-select-option input[type="checkbox"] {
  accent-color: var(--accent, #0f7c7f);
  width: 15px;
  height: 15px;
  flex-shrink: 0;
  cursor: pointer;
}

.multi-select-option-label {
  flex: 1;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* Empty state */
.multi-select-empty {
  padding: 0.75rem;
  text-align: center;
  font-size: 0.85rem;
  color: #9aa3b5;
}

/* hidden utility */
.hidden {
  display: none !important;
}
```

---

## 3. Instantiation Examples in `app.js`

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

## 4. Acceptance Criteria
- [ ] `static/css/components/multi_select.css` is created, covering all component class names (`.multi-select`, `.multi-select-trigger`, `.multi-select-tag`, `.multi-select-dropdown`, `.multi-select-option`, `.multi-select-search`, etc.).
- [ ] Component renders its own DOM shell into any target container.
- [ ] Component handles dynamic item updates (`setItems`) without leaking event listeners.
- [ ] Tag removal button clicks stop propagation and do not trigger dropdown toggle.
- [ ] Outside clicks and pressing `Escape` close any open dropdowns.
- [ ] Keyboard navigation (Enter / Space on trigger) toggles the dropdown cleanly.

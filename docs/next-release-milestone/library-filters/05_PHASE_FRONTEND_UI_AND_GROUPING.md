# Phase 5: Frontend UI, Range Slider & Settings Grouping

## Objective
Build the expandable "Library & Photo Filters" accordion section in `static/index.html`, implement the custom dual-handle Year-Month `DateRangeSlider` component, add CSS styling, and add complete bilingual i18n support in `static/js/modules/i18n.js`.

---

## 1. HTML Layout Structure

### File: `static/index.html` (inside `#setup-form`, placed *above* Game Mode)

```html
<!-- Expandable Media & Library Filters Section -->
<div class="filters-accordion" id="filters-accordion">
  <button type="button" class="filters-accordion-header" id="filters-toggle-btn" aria-expanded="false">
    <div class="accordion-title-wrap">
      <span class="accordion-icon">
        <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2.2">
          <polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3"></polygon>
        </svg>
      </span>
      <span class="accordion-title" data-i18n="setup.filters_heading">Library & Photo Filters</span>
    </div>
    <div class="accordion-meta-wrap">
      <span class="filters-summary-badge" id="filters-summary-badge" data-i18n="setup.filters_summary_default">All media</span>
      <span class="select-arrow accordion-arrow" aria-hidden="true">
        <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2.2">
          <polyline points="6 9 12 15 18 9"></polyline>
        </svg>
      </span>
    </div>
  </button>

  <div class="filters-accordion-content hidden" id="filters-accordion-content">
    <!-- Row 1: Library & Albums -->
    <div class="grid-2">
      <div>
        <label data-i18n="setup.library_label">Library</label>
        <select id="library" required></select>
      </div>
      <div class="album-select-group">
        <label data-i18n="setup.album_label">Album</label>
        <div id="album-multi-select" class="multi-select"></div>
      </div>
    </div>

    <!-- Row 2: Date Range Slider -->
    <div class="form-group date-slider-group">
      <div class="field-head-inline">
        <label data-i18n="setup.date_range_label">Date Range</label>
        <span class="slider-value-readout" id="date-slider-readout">All Time</span>
      </div>
      <div class="range-slider-wrap" id="date-range-slider">
        <div class="range-slider-track">
          <div class="range-slider-fill" id="date-slider-fill"></div>
        </div>
        <input type="range" class="range-thumb thumb-min" id="date-slider-min" min="0" max="100" value="0" />
        <input type="range" class="range-thumb thumb-max" id="date-slider-max" min="0" max="100" value="100" />
      </div>
      <div class="range-slider-ticks">
        <span id="date-slider-bound-min">-</span>
        <span id="date-slider-bound-max">-</span>
      </div>
    </div>

    <!-- Row 3: Geographic & People Filters -->
    <div class="grid-3 filters-sub-grid">
      <div>
        <label data-i18n="setup.countries_label">Countries</label>
        <div id="country-multi-select" class="multi-select"></div>
      </div>
      <div>
        <label data-i18n="setup.cities_label">Cities / Regions</label>
        <div id="city-multi-select" class="multi-select"></div>
      </div>
      <div>
        <div class="field-head-inline">
          <label data-i18n="setup.people_label">People</label>
          <div class="people-mode-toggle hidden" id="people-mode-toggle" title="Match mode for selected people">
            <button type="button" class="people-mode-btn active" data-people-mode="OR" data-i18n="setup.people_mode_or">Any</button>
            <button type="button" class="people-mode-btn" data-people-mode="AND" data-i18n="setup.people_mode_and">All</button>
          </div>
        </div>
        <div id="people-multi-select" class="multi-select"></div>
      </div>
    </div>

    <!-- Filter Actions -->
    <div class="filters-footer-actions">
      <button type="button" class="btn-text-action" id="reset-filters-btn" data-i18n="setup.reset_filters">
        Reset filters
      </button>
    </div>
  </div>
</div>
```

---

## 2. Date Range Slider Component

### File: `static/js/modules/components/range_slider.js`

```javascript
import { t } from "../i18n.js";

/**
 * Dual-handle Year-Month Range Slider
 */
export class DateRangeSlider {
  constructor(config) {
    this.minThumb = config.minThumb;
    this.maxThumb = config.maxThumb;
    this.fillEl = config.fillEl;
    this.readoutEl = config.readoutEl;
    this.boundMinEl = config.boundMinEl;
    this.boundMaxEl = config.boundMaxEl;
    this.onChange = config.onChange || (() => {});

    this.allMonths = []; // Array of "YYYY-MM" strings
    this._bindEvents();
  }

  _bindEvents() {
    this.minThumb.addEventListener("input", () => {
      let minVal = parseInt(this.minThumb.value, 10);
      let maxVal = parseInt(this.maxThumb.value, 10);
      if (minVal > maxVal) {
        this.minThumb.value = String(maxVal);
      }
      this.updateVisuals();
      this.onChange();
    });

    this.maxThumb.addEventListener("input", () => {
      let minVal = parseInt(this.minThumb.value, 10);
      let maxVal = parseInt(this.maxThumb.value, 10);
      if (maxVal < minVal) {
        this.maxThumb.value = String(minVal);
      }
      this.updateVisuals();
      this.onChange();
    });
  }

  _generateMonthSpan(minMonth, maxMonth) {
    const [startYear, startMonth] = minMonth.split("-").map(Number);
    const [endYear, endMonth] = maxMonth.split("-").map(Number);

    const months = [];
    let curYear = startYear;
    let curMonth = startMonth;

    while (curYear < endYear || (curYear === endYear && curMonth <= endMonth)) {
      const monthStr = String(curMonth).padStart(2, "0");
      months.push(`${curYear}-${monthStr}`);
      curMonth += 1;
      if (curMonth > 12) {
        curMonth = 1;
        curYear += 1;
      }
    }
    return months;
  }

  _formatMonth(yyyyMm) {
    if (!yyyyMm) return "";
    const [year, month] = yyyyMm.split("-").map(Number);
    const dateObj = new Date(Date.UTC(year, month - 1, 1));
    return dateObj.toLocaleDateString(undefined, {
      month: "short",
      year: "numeric",
      timeZone: "UTC",
    });
  }

  setBounds(minMonth, maxMonth) {
    if (!minMonth || !maxMonth) {
      this.allMonths = [];
      this.reset();
      return;
    }
    this.allMonths = this._generateMonthSpan(minMonth, maxMonth);
    const maxIdx = Math.max(0, this.allMonths.length - 1);
    
    this.minThumb.min = "0";
    this.minThumb.max = String(maxIdx);
    this.minThumb.value = "0";

    this.maxThumb.min = "0";
    this.maxThumb.max = String(maxIdx);
    this.maxThumb.value = String(maxIdx);

    if (this.boundMinEl) this.boundMinEl.textContent = this._formatMonth(minMonth);
    if (this.boundMaxEl) this.boundMaxEl.textContent = this._formatMonth(maxMonth);

    this.updateVisuals();
  }

  setSelectedRange(minMonth, maxMonth) {
    if (!this.allMonths.length) return;
    const minIdx = this.allMonths.indexOf(minMonth);
    const maxIdx = this.allMonths.indexOf(maxMonth);
    if (minIdx !== -1) this.minThumb.value = String(minIdx);
    if (maxIdx !== -1) this.maxThumb.value = String(maxIdx);
    this.updateVisuals();
  }

  getSelectedRange() {
    if (this.allMonths.length === 0) return { minDate: null, maxDate: null };
    const minIdx = parseInt(this.minThumb.value, 10);
    const maxIdx = parseInt(this.maxThumb.value, 10);

    const isFullSpan = (minIdx === 0 && maxIdx === this.allMonths.length - 1);
    if (isFullSpan) {
      return { minDate: null, maxDate: null };
    }

    const minMonth = this.allMonths[minIdx];
    const maxMonth = this.allMonths[maxIdx];

    const minDate = `${minMonth}-01`;
    const [year, month] = maxMonth.split("-").map(Number);
    const lastDay = new Date(Date.UTC(year, month, 0)).getUTCDate();
    const maxDate = `${maxMonth}-${String(lastDay).padStart(2, "0")}`;

    return { minDate, maxDate };
  }

  updateVisuals() {
    if (this.allMonths.length === 0) {
      if (this.readoutEl) this.readoutEl.textContent = t("setup.all_dates");
      if (this.fillEl) {
        this.fillEl.style.left = "0%";
        this.fillEl.style.width = "100%";
      }
      return;
    }

    const minVal = parseInt(this.minThumb.value, 10);
    const maxVal = parseInt(this.maxThumb.value, 10);
    const total = Math.max(1, this.allMonths.length - 1);

    const minPct = (minVal / total) * 100;
    const maxPct = (maxVal / total) * 100;

    if (this.fillEl) {
      this.fillEl.style.left = `${minPct}%`;
      this.fillEl.style.width = `${maxPct - minPct}%`;
    }

    if (this.readoutEl) {
      if (minVal === 0 && maxVal === this.allMonths.length - 1) {
        this.readoutEl.textContent = t("setup.all_dates");
      } else {
        const start = this._formatMonth(this.allMonths[minVal]);
        const end = this._formatMonth(this.allMonths[maxVal]);
        this.readoutEl.textContent = `${start} — ${end}`;
      }
    }
  }

  reset() {
    if (this.minThumb) this.minThumb.value = this.minThumb.min || "0";
    if (this.maxThumb) this.maxThumb.value = this.maxThumb.max || "100";
    this.updateVisuals();
  }
}
```

---

## 3. CSS Stylesheets

### File: `static/css/components/filters.css`

```css
/* Filters Accordion Component */
.filters-accordion {
  margin-top: 1rem;
  border-radius: 12px;
  border: 1px solid #dbe1ee;
  background: #fbfcfe;
  overflow: hidden;
  transition: border-color 0.2s ease, box-shadow 0.2s ease;
}

.filters-accordion:hover {
  border-color: #c7ccd8;
}

.filters-accordion-header {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.75rem 1rem;
  background: transparent;
  border: none;
  cursor: pointer;
  font-family: inherit;
  font-size: 0.95rem;
  font-weight: 600;
  color: var(--text-dark, #242938);
  user-select: none;
}

.accordion-title-wrap {
  display: flex;
  align-items: center;
  gap: 0.55rem;
}

.accordion-icon {
  display: inline-flex;
  color: var(--accent, #0f7c7f);
}

.accordion-meta-wrap {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.filters-summary-badge {
  font-size: 0.8rem;
  font-weight: 500;
  color: #6c7893;
  padding: 0.15rem 0.5rem;
  border-radius: 999px;
  background: rgba(108, 120, 147, 0.12);
  transition: all 0.2s ease;
}

.filters-summary-badge.has-active {
  color: var(--accent, #0f7c7f);
  background: rgba(15, 124, 127, 0.14);
  font-weight: 600;
}

.accordion-arrow {
  display: inline-flex;
  align-items: center;
  transition: transform 0.25s cubic-bezier(0.4, 0, 0.2, 1);
  color: #8c97ad;
}

.filters-accordion-header[aria-expanded="true"] .accordion-arrow {
  transform: rotate(180deg);
}

.filters-accordion-content {
  padding: 0.25rem 1rem 1rem 1rem;
  display: flex;
  flex-direction: column;
  gap: 1rem;
  border-top: 1px solid #edf1f7;
}

.filters-accordion-content.hidden {
  display: none;
}

.filters-sub-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 0.75rem;
}

.filters-footer-actions {
  display: flex;
  justify-content: flex-end;
  padding-top: 0.5rem;
}

/* People Match Mode Segmented Toggle (OR vs AND) */
.people-mode-toggle {
  display: inline-flex;
  align-items: center;
  background: #edf1f7;
  border-radius: 999px;
  padding: 2px;
  gap: 2px;
  transition: opacity 0.2s ease;
}

.people-mode-toggle.hidden {
  display: none !important;
}

.people-mode-btn {
  border: none;
  background: transparent;
  padding: 0.15rem 0.55rem;
  border-radius: 999px;
  font-size: 0.75rem;
  font-weight: 600;
  color: #6c7893;
  cursor: pointer;
  line-height: 1.2;
  transition: background-color 0.15s ease, color 0.15s ease, box-shadow 0.15s ease;
}

.people-mode-btn:hover {
  color: var(--text-dark, #242938);
}

.people-mode-btn.active {
  background: #ffffff;
  color: var(--accent, #0f7c7f);
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.12);
}
```

### File: `static/css/components/range_slider.css`

```css
/* Dual-handle Year-Month Range Slider */
.date-slider-group {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}

.field-head-inline {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.slider-value-readout {
  font-size: 0.85rem;
  font-weight: 600;
  color: var(--accent, #0f7c7f);
}

.range-slider-wrap {
  position: relative;
  height: 28px;
  display: flex;
  align-items: center;
  margin: 0.25rem 0;
}

.range-slider-track {
  position: absolute;
  left: 0;
  right: 0;
  height: 6px;
  border-radius: 3px;
  background: #e1e6f0;
  pointer-events: none;
}

.range-slider-fill {
  position: absolute;
  top: 0;
  bottom: 0;
  left: 0%;
  width: 100%;
  border-radius: 3px;
  background: var(--accent, #0f7c7f);
  pointer-events: none;
}

.range-thumb {
  position: absolute;
  left: 0;
  width: 100%;
  height: 6px;
  margin: 0;
  padding: 0;
  background: none;
  pointer-events: none;
  -webkit-appearance: none;
  appearance: none;
}

.range-thumb::-webkit-slider-thumb {
  -webkit-appearance: none;
  appearance: none;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: #ffffff;
  border: 2px solid var(--accent, #0f7c7f);
  box-shadow: 0 2px 5px rgba(0, 0, 0, 0.15);
  cursor: pointer;
  pointer-events: auto;
  transition: transform 0.1s ease, box-shadow 0.1s ease;
}

.range-thumb::-webkit-slider-thumb:hover {
  transform: scale(1.15);
  box-shadow: 0 2px 8px rgba(15, 124, 127, 0.35);
}

.range-thumb::-moz-range-thumb {
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: #ffffff;
  border: 2px solid var(--accent, #0f7c7f);
  box-shadow: 0 2px 5px rgba(0, 0, 0, 0.15);
  cursor: pointer;
  pointer-events: auto;
}

.range-slider-ticks {
  display: flex;
  justify-content: space-between;
  font-size: 0.75rem;
  color: #8c97ad;
}
```

---

## 4. Bilingual i18n Translation Dictionary

### File: `static/js/modules/i18n.js`

```javascript
// English (EN)
"setup.filters_heading": "Library & Photo Filters",
"setup.filters_summary_default": "All media",
"setup.filters_active_count": (count) => `${count} filter${count > 1 ? "s" : ""} active`,
"setup.reset_filters": "Reset all filters",
"setup.date_range_label": "Date Range",
"setup.all_dates": "All Time",
"setup.countries_label": "Countries",
"setup.all_countries": "-",
"setup.country_search_placeholder": "Search countries...",
"setup.no_countries_found": "No countries found",
"setup.countries_selected": (count) => `${count} countries selected`,
"setup.cities_label": "Cities / Regions",
"setup.all_cities": "-",
"setup.city_search_placeholder": "Search cities...",
"setup.no_cities_found": "No cities found",
"setup.cities_selected": (count) => `${count} cities selected`,
"setup.people_label": "People",
"setup.all_people": "-",
"setup.people_search_placeholder": "Search people...",
"setup.no_people_found": "No people found",
"setup.people_selected": (count) => `${count} people selected`,
"setup.people_mode_or": "Any",
"setup.people_mode_and": "All",
"setup.filter_people": "People (Any)",
"setup.filter_people_all": "People (All together)",
"setup.filter_countries": "Countries",
"setup.filter_cities": "Cities",
"setup.filter_date_range": "Date Range",

// Brazilian Portuguese (PT)
"setup.filters_heading": "Filtros de Biblioteca e Fotos",
"setup.filters_summary_default": "Todas as fotos",
"setup.filters_active_count": (count) => `${count} filtro${count > 1 ? "s" : ""} ativo${count > 1 ? "s" : ""}`,
"setup.reset_filters": "Redefinir filtros",
"setup.date_range_label": "Intervalo de Datas",
"setup.all_dates": "Todo o período",
"setup.countries_label": "Países",
"setup.all_countries": "-",
"setup.country_search_placeholder": "Buscar países...",
"setup.no_countries_found": "Nenhum país encontrado",
"setup.countries_selected": (count) => `${count} países selecionados`,
"setup.cities_label": "Cidades / Regiões",
"setup.all_cities": "-",
"setup.city_search_placeholder": "Buscar cidades...",
"setup.no_cities_found": "Nenhuma cidade encontrada",
"setup.cities_selected": (count) => `${count} cidades selecionadas`,
"setup.people_label": "Pessoas",
"setup.all_people": "-",
"setup.people_search_placeholder": "Buscar pessoas...",
"setup.no_people_found": "Nenhuma pessoa encontrada",
"setup.people_selected": (count) => `${count} pessoas selecionadas`,
"setup.people_mode_or": "Qualquer um",
"setup.people_mode_and": "Todos juntos",
"setup.filter_people": "Pessoas (Qualquer uma)",
"setup.filter_people_all": "Pessoas (Todas juntas)",
"setup.filter_countries": "Países",
"setup.filter_cities": "Cidades",
"setup.filter_date_range": "Intervalo de Datas",
```

---

## 5. Acceptance Criteria
- [ ] Clicking the accordion header smoothly expands/collapses the filter options.
- [ ] The summary badge dynamically updates (e.g. `"All media"` -> `"3 filters active"`).
- [ ] The dual-handle slider prevents thumb cross-overs and updates the live readout accurately.
- [ ] When $\ge 2$ people are selected, the Any / All match mode toggle appears and updates the filter criteria dynamically.
- [ ] Reset button restores all 4 filter menus (Albums, Date, Countries, Cities, People) and the people match mode to defaults.
- [ ] Switching between `EN` and `PT` translates all new labels immediately.

import { t, formatDate } from "../i18n.js";

/**
 * Dual-handle Year-Month Range Slider
 */
export class DateRangeSlider {
  constructor(config) {
    this.wrapEl = config.wrapEl || (config.minThumb ? config.minThumb.closest(".range-slider-wrap") : null);
    this.minThumb = config.minThumb || null;
    this.maxThumb = config.maxThumb || null;
    this.fillEl = config.fillEl || null;
    this.readoutEl = config.readoutEl || null;
    this.boundMinEl = config.boundMinEl || null;
    this.boundMaxEl = config.boundMaxEl || null;
    this.onChange = config.onChange || (() => {});

    this.allMonths = []; // Array of "YYYY-MM" strings
    this._bindEvents();
  }

  _bindEvents() {
    if (!this.minThumb || !this.maxThumb) return;

    this._onMinInput = () => {
      let minVal = parseInt(this.minThumb.value, 10);
      let maxVal = parseInt(this.maxThumb.value, 10);
      if (minVal > maxVal) {
        this.minThumb.value = String(maxVal);
      }
      this.minThumb.style.zIndex = "4";
      this.maxThumb.style.zIndex = "3";
      this.updateVisuals();
      this.onChange();
    };

    this._onMaxInput = () => {
      let minVal = parseInt(this.minThumb.value, 10);
      let maxVal = parseInt(this.maxThumb.value, 10);
      if (maxVal < minVal) {
        this.maxThumb.value = String(minVal);
      }
      this.maxThumb.style.zIndex = "4";
      this.minThumb.style.zIndex = "3";
      this.updateVisuals();
      this.onChange();
    };

    this._onMinPointerDown = () => {
      this.minThumb.style.zIndex = "4";
      this.maxThumb.style.zIndex = "3";
    };

    this._onMaxPointerDown = () => {
      this.maxThumb.style.zIndex = "4";
      this.minThumb.style.zIndex = "3";
    };

    this.minThumb.addEventListener("input", this._onMinInput);
    this.minThumb.addEventListener("pointerdown", this._onMinPointerDown);
    this.minThumb.addEventListener("focus", this._onMinPointerDown);

    this.maxThumb.addEventListener("input", this._onMaxInput);
    this.maxThumb.addEventListener("pointerdown", this._onMaxPointerDown);
    this.maxThumb.addEventListener("focus", this._onMaxPointerDown);

    this._onTrackClick = (e) => {
      if (!this.allMonths.length || !this.minThumb || !this.maxThumb) return;
      if (this.minThumb.disabled || this.maxThumb.disabled) return;
      if (!this.wrapEl) return;

      const rect = this.wrapEl.getBoundingClientRect();
      if (!rect.width) return;
      const clickX = e.clientX - rect.left;
      const pct = Math.max(0, Math.min(1, clickX / rect.width));
      const maxIdx = Math.max(1, this.allMonths.length - 1);
      const targetVal = Math.round(pct * maxIdx);

      const minVal = parseInt(this.minThumb.value, 10);
      const maxVal = parseInt(this.maxThumb.value, 10);

      const distToMin = Math.abs(targetVal - minVal);
      const distToMax = Math.abs(targetVal - maxVal);

      if (distToMin <= distToMax) {
        this.minThumb.value = String(Math.min(targetVal, maxVal));
        this.minThumb.style.zIndex = "4";
        this.maxThumb.style.zIndex = "3";
      } else {
        this.maxThumb.value = String(Math.max(targetVal, minVal));
        this.maxThumb.style.zIndex = "4";
        this.minThumb.style.zIndex = "3";
      }

      this.updateVisuals();
      this.onChange();
    };

    if (this.wrapEl) {
      this.wrapEl.addEventListener("click", this._onTrackClick);
    }
  }

  destroy() {
    if (this.minThumb) {
      if (this._onMinInput) this.minThumb.removeEventListener("input", this._onMinInput);
      if (this._onMinPointerDown) {
        this.minThumb.removeEventListener("pointerdown", this._onMinPointerDown);
        this.minThumb.removeEventListener("focus", this._onMinPointerDown);
      }
    }
    if (this.maxThumb) {
      if (this._onMaxInput) this.maxThumb.removeEventListener("input", this._onMaxInput);
      if (this._onMaxPointerDown) {
        this.maxThumb.removeEventListener("pointerdown", this._onMaxPointerDown);
        this.maxThumb.removeEventListener("focus", this._onMaxPointerDown);
      }
    }
    if (this.wrapEl && this._onTrackClick) {
      this.wrapEl.removeEventListener("click", this._onTrackClick);
    }
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
    return formatDate(dateObj, {
      month: "short",
      year: "numeric",
      timeZone: "UTC",
    });
  }

  setBounds(minMonth, maxMonth) {
    if (!minMonth || !maxMonth) {
      this.allMonths = [];
      if (this.minThumb) {
        this.minThumb.disabled = true;
        this.minThumb.value = "0";
      }
      if (this.maxThumb) {
        this.maxThumb.disabled = true;
        this.maxThumb.value = "0";
      }
      if (this.boundMinEl) this.boundMinEl.textContent = "-";
      if (this.boundMaxEl) this.boundMaxEl.textContent = "-";
      this.updateVisuals();
      return;
    }
    this.allMonths = this._generateMonthSpan(minMonth, maxMonth);
    const maxIdx = Math.max(0, this.allMonths.length - 1);

    if (this.minThumb) {
      this.minThumb.disabled = false;
      this.minThumb.min = "0";
      this.minThumb.max = String(maxIdx);
      this.minThumb.value = "0";
    }

    if (this.maxThumb) {
      this.maxThumb.disabled = false;
      this.maxThumb.min = "0";
      this.maxThumb.max = String(maxIdx);
      this.maxThumb.value = String(maxIdx);
    }

    if (this.boundMinEl) this.boundMinEl.textContent = this._formatMonth(minMonth);
    if (this.boundMaxEl) this.boundMaxEl.textContent = this._formatMonth(maxMonth);

    this.updateVisuals();
  }

  setSelectedRange(minMonth, maxMonth) {
    if (!this.allMonths.length) return;
    const minIdx = this.allMonths.indexOf(minMonth);
    const maxIdx = this.allMonths.indexOf(maxMonth);
    if (minIdx !== -1 && this.minThumb) this.minThumb.value = String(minIdx);
    if (maxIdx !== -1 && this.maxThumb) this.maxThumb.value = String(maxIdx);
    this.updateVisuals();
  }

  getSelectedRange() {
    if (this.allMonths.length === 0 || !this.minThumb || !this.maxThumb) {
      return { minDate: null, maxDate: null };
    }
    const minIdx = parseInt(this.minThumb.value, 10);
    const maxIdx = parseInt(this.maxThumb.value, 10);

    const isFullSpan = minIdx === 0 && maxIdx === this.allMonths.length - 1;
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
    if (this.wrapEl) {
      this.wrapEl.classList.toggle("disabled", this.allMonths.length === 0);
    }

    if (this.allMonths.length === 0) {
      if (this.readoutEl) this.readoutEl.textContent = t("setup.all_dates");
      if (this.fillEl) {
        this.fillEl.style.left = "0%";
        this.fillEl.style.width = "0%";
      }
      return;
    }

    if (!this.minThumb || !this.maxThumb) return;

    const minVal = parseInt(this.minThumb.value, 10);
    const maxVal = parseInt(this.maxThumb.value, 10);
    const total = Math.max(1, this.allMonths.length - 1);

    const minPct = (minVal / total) * 100;
    const maxPct = (maxVal / total) * 100;

    if (this.fillEl) {
      this.fillEl.style.left = `${minPct}%`;
      this.fillEl.style.width = `${maxPct - minPct}%`;
    }

    if (this.boundMinEl && this.allMonths.length > 0) {
      this.boundMinEl.textContent = this._formatMonth(this.allMonths[0]);
    }
    if (this.boundMaxEl && this.allMonths.length > 0) {
      this.boundMaxEl.textContent = this._formatMonth(this.allMonths[this.allMonths.length - 1]);
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
    if (this.allMonths.length === 0) {
      if (this.minThumb) {
        this.minThumb.disabled = true;
        this.minThumb.value = "0";
      }
      if (this.maxThumb) {
        this.maxThumb.disabled = true;
        this.maxThumb.value = "0";
      }
      if (this.boundMinEl) this.boundMinEl.textContent = "-";
      if (this.boundMaxEl) this.boundMaxEl.textContent = "-";
    } else {
      if (this.minThumb) {
        this.minThumb.disabled = false;
        this.minThumb.value = this.minThumb.min || "0";
      }
      if (this.maxThumb) {
        this.maxThumb.disabled = false;
        this.maxThumb.value = this.maxThumb.max || String(Math.max(0, this.allMonths.length - 1));
      }
    }
    this.updateVisuals();
  }
}

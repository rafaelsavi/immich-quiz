/**
 * Lightweight Player Name Autocomplete Dropdown
 * Fetches recent and frequent players from /api/players/names
 * Provides accessible keyboard navigation, colored avatar initials, and match count pill.
 */
export class PlayerAutocomplete {
  /**
   * @param {HTMLInputElement} inputEl - Target text input
   * @param {Object} [options]
   * @param {function(string): void} [options.onSelect] - Callback when player selected
   * @param {function(): string[]} [options.getExcludedNames] - Names to exclude (e.g. already selected)
   */
  constructor(inputEl, options = {}) {
    if (!inputEl) return;
    this.inputEl = inputEl;
    this.onSelect = options.onSelect || null;
    this.getExcludedNames = options.getExcludedNames || (() => []);
    this.dropdownEl = null;
    this.selectedIndex = -1;
    this.items = [];
    this._debounceTimer = null;
    this._cachedNames = null;

    this._init();
  }

  _init() {
    // Create dropdown element
    this.dropdownEl = document.createElement('div');
    this.dropdownEl.className = 'player-autocomplete-dropdown hidden';
    this.dropdownEl.setAttribute('role', 'listbox');
    this.dropdownEl.id = `autocomplete-${Math.random().toString(36).slice(2, 9)}`;

    // Position relative to player-input-container if available, else parentElement
    this.anchorEl = this.inputEl.closest('.player-input-container') || this.inputEl.parentElement;
    if (this.anchorEl) {
      if (getComputedStyle(this.anchorEl).position === 'static') {
        this.anchorEl.style.position = 'relative';
      }
      this.anchorEl.appendChild(this.dropdownEl);
    }

    // Prevent input blur when tapping or scrolling inside dropdown
    this.dropdownEl.addEventListener('pointerdown', (e) => {
      e.preventDefault();
    });

    // Bind event handlers
    this.inputEl.addEventListener('input', () => this._onInput());
    this.inputEl.addEventListener('focus', () => this._onFocus());
    this.inputEl.addEventListener('blur', () => {
      setTimeout(() => this.close(), 200);
    });
    this.inputEl.addEventListener('keydown', (e) => this._onKeyDown(e));

    if (this.inputEl.form) {
      this.inputEl.form.addEventListener('submit', () => this.close());
    }

    document.addEventListener('pointerdown', (e) => {
      if (
        !this.inputEl.contains(e.target) &&
        !this.dropdownEl.contains(e.target) &&
        !(this.anchorEl && this.anchorEl.contains(e.target))
      ) {
        this.close();
      }
    });

    window.addEventListener('resize', () => {
      if (this.dropdownEl && !this.dropdownEl.classList.contains('hidden')) {
        this._updatePosition();
      }
    });
  }

  _onFocus() {
    const val = this.inputEl.value.trim();
    this._fetchSuggestions(val);
  }

  _onInput() {
    clearTimeout(this._debounceTimer);
    this._debounceTimer = setTimeout(() => {
      const val = this.inputEl.value.trim();
      this._fetchSuggestions(val);
    }, 150);
  }

  async _fetchSuggestions(query) {
    try {
      const res = await fetch(`/api/players/names?q=${encodeURIComponent(query)}&limit=10`);
      if (!res.ok) return;
      const suggestions = await res.json();
      const excluded = new Set((this.getExcludedNames() || []).map((n) => n.toLowerCase()));

      this.items = suggestions.filter((item) => !excluded.has(item.player_name.toLowerCase()));

      // If user has already typed the exact full name and it's the only match, don't obstruct buttons
      if (
        this.items.length === 1 &&
        query.length > 0 &&
        this.items[0].player_name.toLowerCase() === query.toLowerCase()
      ) {
        this.close();
        return;
      }

      this._renderDropdown();
    } catch (err) {
      console.warn('Failed to fetch player autocomplete suggestions:', err);
    }
  }

  _renderDropdown() {
    if (!this.items || this.items.length === 0) {
      this.close();
      return;
    }

    this.selectedIndex = -1;
    this.dropdownEl.innerHTML = this.items
      .map((item, idx) => {
        const initial = (item.player_name || '?').charAt(0).toUpperCase();
        const color = item.color || '#3b82f6';
        const matchLabel = item.match_count === 1 ? '1 match' : `${item.match_count} matches`;

        return `
          <div class="player-autocomplete-item" role="option" data-index="${idx}">
            <div class="player-autocomplete-avatar" style="background-color: ${color}">
              ${initial}
            </div>
            <div class="player-autocomplete-info">
              <span class="player-autocomplete-name">${this._escapeHtml(item.player_name)}</span>
              <span class="player-autocomplete-count">${matchLabel}</span>
            </div>
          </div>
        `;
      })
      .join('');

    this.dropdownEl.querySelectorAll('.player-autocomplete-item').forEach((el) => {
      const handleSelect = (e) => {
        e.preventDefault();
        e.stopPropagation();
        const idx = parseInt(el.getAttribute('data-index'), 10);
        this._selectIndex(idx);
      };

      el.addEventListener('pointerdown', handleSelect);
      el.addEventListener('click', handleSelect);
    });

    this.dropdownEl.classList.remove('hidden');
    this._updatePosition();
  }

  _updatePosition() {
    if (!this.dropdownEl || !this.anchorEl) return;

    const anchorRect = this.anchorEl.getBoundingClientRect();
    const dropdownHeight = Math.min(this.dropdownEl.scrollHeight || 220, 240);
    const spaceBelow = window.innerHeight - anchorRect.bottom;
    const spaceAbove = anchorRect.top;

    // Flip upwards if space below is too small to fit the dropdown and space above has more clearance
    if (spaceBelow < dropdownHeight + 12 && spaceAbove > spaceBelow) {
      this.dropdownEl.classList.add('open-upwards');
    } else {
      this.dropdownEl.classList.remove('open-upwards');
    }
  }

  _onKeyDown(e) {
    if (this.dropdownEl.classList.contains('hidden') || this.items.length === 0) {
      return;
    }

    if (e.key === 'ArrowDown') {
      e.preventDefault();
      this.selectedIndex = (this.selectedIndex + 1) % this.items.length;
      this._updateActiveOption();
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      this.selectedIndex = (this.selectedIndex - 1 + this.items.length) % this.items.length;
      this._updateActiveOption();
    } else if (e.key === 'Enter') {
      if (this.selectedIndex >= 0 && this.selectedIndex < this.items.length) {
        e.preventDefault();
        e.stopPropagation();
        this._selectIndex(this.selectedIndex);
      } else {
        this.close();
      }
    } else if (e.key === 'Escape') {
      this.close();
    }
  }

  _updateActiveOption() {
    const opts = this.dropdownEl.querySelectorAll('.player-autocomplete-item');
    opts.forEach((opt, idx) => {
      if (idx === this.selectedIndex) {
        opt.classList.add('active');
        opt.scrollIntoView({ block: 'nearest' });
      } else {
        opt.classList.remove('active');
      }
    });
  }

  _selectIndex(idx) {
    const item = this.items[idx];
    if (!item) return;

    if (this.onSelect) {
      this.onSelect(item.player_name);
    } else {
      this.inputEl.value = item.player_name;
      this.inputEl.dispatchEvent(new Event('input', { bubbles: true }));
      this.inputEl.dispatchEvent(new Event('change', { bubbles: true }));
    }
    this.close();
  }

  close() {
    if (this.dropdownEl) {
      this.dropdownEl.classList.add('hidden');
      this.dropdownEl.innerHTML = '';
      this.selectedIndex = -1;
    }
  }

  _escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }
}

/**
 * Convenience helper to attach autocomplete to an input
 */
export function attachPlayerAutocomplete(inputEl, options = {}) {
  return new PlayerAutocomplete(inputEl, options);
}

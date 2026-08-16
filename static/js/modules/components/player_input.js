import { t } from "../i18n.js";
import { PLAYER_COLORS, playerColor, playerInitial } from "../formatters.js";

/**
 * Modern Player Input Component
 * Interactive chip management for players with avatar color badges,
 * duplicate detection, keyboard shortcuts, mobile virtual keyboard support,
 * and smooth animations.
 */
export class PlayerInput {
  /**
   * @param {Object} options
   * @param {HTMLElement} options.container - Root container element
   * @param {HTMLInputElement} [options.hiddenInput] - Underlying input element for form compatibility
   * @param {HTMLElement} [options.countBadge] - Badge element to display player count / mode
   * @param {string[]} [options.initialPlayers] - Initial player names
   * @param {number} [options.maxPlayers=16] - Maximum allowed players
   * @param {function(string[]): void} [options.onChange] - Callback when player list changes
   */
  constructor(options = {}) {
    this.container = options.container;
    this.hiddenInput = options.hiddenInput || document.getElementById("players");
    this.countBadge = options.countBadge || document.getElementById("player-count-badge");
    this.maxPlayers = options.maxPlayers || 16;
    this.onChange = options.onChange || (() => {});

    this.players = [];
    this._feedbackTimer = null;

    this._renderBaseDom();
    this._bindEvents();

    const initial = options.initialPlayers !== undefined
      ? options.initialPlayers
      : (this.hiddenInput && this.hiddenInput.value
        ? this.hiddenInput.value.split(",").map((s) => s.trim()).filter(Boolean)
        : []);

    this.setPlayers(initial, false);
  }

  _renderBaseDom() {
    this.container.innerHTML = `
      <div class="player-input-container" id="player-input-container">
        <div class="player-chips-wrap" id="player-chips-wrap"></div>
        <div class="player-input-entry-wrap">
          <input
            type="text"
            class="player-text-input"
            id="player-text-input"
            placeholder="${t("setup.players_placeholder")}"
            maxlength="30"
            autocapitalize="words"
            autocomplete="off"
            autocorrect="off"
            spellcheck="false"
            enterkeyhint="done"
          />
          <button type="button" class="player-add-btn" id="player-add-btn" title="${t("setup.players_add_btn")}" disabled>
            <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
              <line x1="12" y1="5" x2="12" y2="19"></line>
              <line x1="5" y1="12" x2="19" y2="12"></line>
            </svg>
            <span class="add-btn-label">${t("setup.players_add_btn")}</span>
          </button>
        </div>
      </div>
      <div class="player-input-feedback hidden" id="player-input-feedback" role="alert" aria-live="polite"></div>
    `;

    this.inputContainer = this.container.querySelector("#player-input-container");
    this.chipsWrap = this.container.querySelector("#player-chips-wrap");
    this.textInput = this.container.querySelector("#player-text-input");
    this.addBtn = this.container.querySelector("#player-add-btn");
    this.feedbackEl = this.container.querySelector("#player-input-feedback");
    this._updateAddBtnState();
  }

  _bindEvents() {
    // Focus text input when clicking anywhere in the container
    this.inputContainer.addEventListener("click", (e) => {
      if (e.target.closest(".player-chip-remove") || e.target.closest(".player-add-btn")) {
        return;
      }
      this.textInput.focus();
    });

    // Handle typing and keyboard shortcuts
    this.textInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        e.preventDefault();
        e.stopPropagation();
        const val = this.textInput.value.trim();
        if (val) {
          this.addPlayer(val);
        } else {
          // If input is empty and Enter is pressed, submit form if valid
          const form = this.container.closest("form");
          if (form && this.players.length > 0) {
            form.requestSubmit();
          }
        }
        return;
      }

      if (e.key === ",") {
        e.preventDefault();
        const val = this.textInput.value.trim();
        if (val) {
          this.addPlayer(val);
        }
        return;
      }

      if (e.key === "Backspace" && !this.textInput.value) {
        if (this.players.length > 0) {
          this.removePlayer(this.players.length - 1);
        }
        return;
      }

      this._clearFeedback();
    });

    // Handle add button click
    this.addBtn.addEventListener("click", (e) => {
      e.preventDefault();
      e.stopPropagation();
      const val = this.textInput.value.trim();
      if (val) {
        this.addPlayer(val);
        this.textInput.focus();
      } else {
        this.textInput.focus();
      }
    });

    // Handle paste of comma-separated or multi-line player names
    this.textInput.addEventListener("paste", (e) => {
      const text = (e.clipboardData || window.clipboardData)?.getData("text");
      if (text && (text.includes(",") || text.includes("\n"))) {
        e.preventDefault();
        const candidates = text
          .split(/[\n,]+/)
          .map((n) => n.trim())
          .filter(Boolean);

        let addedCount = 0;
        candidates.forEach((name) => {
          if (this.players.length < this.maxPlayers && !this._isDuplicate(name)) {
            this.players.push(name);
            addedCount++;
          }
        });

        if (addedCount > 0) {
          this.textInput.value = "";
          this._updateAddBtnState();
          this._sync();
        }
      }
    });

    // Clear error on input and update add button state
    this.textInput.addEventListener("input", () => {
      this._updateAddBtnState();
      this._clearFeedback();
    });
  }

  _updateAddBtnState() {
    if (this.addBtn && this.textInput) {
      this.addBtn.disabled = !this.textInput.value.trim();
    }
  }

  _isDuplicate(name) {
    const norm = name.trim().toLowerCase();
    return this.players.some((p) => p.trim().toLowerCase() === norm);
  }

  _showFeedback(message) {
    if (this._feedbackTimer) {
      clearTimeout(this._feedbackTimer);
    }
    this.feedbackEl.textContent = message;
    this.feedbackEl.classList.remove("hidden");
    this.inputContainer.classList.add("has-error");

    this._feedbackTimer = setTimeout(() => {
      this._clearFeedback();
    }, 4000);
  }

  _clearFeedback() {
    if (this._feedbackTimer) {
      clearTimeout(this._feedbackTimer);
      this._feedbackTimer = null;
    }
    this.feedbackEl.textContent = "";
    this.feedbackEl.classList.add("hidden");
    this.inputContainer.classList.remove("has-error");
  }

  /**
   * Add a new player name to the roster
   * @param {string} rawName
   * @returns {boolean} Whether player was successfully added
   */
  addPlayer(rawName) {
    const name = (rawName || "").trim();
    if (!name) {
      this._showFeedback(t("setup.players_empty_error"));
      return false;
    }

    if (this.players.length >= this.maxPlayers) {
      this._showFeedback(t("setup.players_max_limit", this.maxPlayers));
      return false;
    }

    if (this._isDuplicate(name)) {
      this._showFeedback(t("setup.players_duplicate_error"));
      return false;
    }

    this.players.push(name);
    this.textInput.value = "";
    this._updateAddBtnState();
    this._clearFeedback();
    this._sync();
    return true;
  }

  /**
   * Remove a player by index
   * @param {number} index
   */
  removePlayer(index) {
    if (index >= 0 && index < this.players.length) {
      this.players.splice(index, 1);
      this._clearFeedback();
      this._sync();
    }
  }

  /**
   * Set players list programmatically
   * @param {string[]} names
   * @param {boolean} [triggerChange=true]
   */
  setPlayers(names, triggerChange = true) {
    const sanitized = [];
    (names || []).forEach((n) => {
      const trimmed = (n || "").trim();
      if (trimmed && !sanitized.some((s) => s.toLowerCase() === trimmed.toLowerCase())) {
        sanitized.push(trimmed);
      }
    });

    this.players = sanitized.slice(0, this.maxPlayers);
    this._sync(triggerChange);
  }

  /**
   * Get array of player names
   * @returns {string[]}
   */
  getPlayers() {
    return [...this.players];
  }

  _sync(triggerChange = true) {
    this._renderChips();
    this._updateBadge();

    if (this.hiddenInput) {
      this.hiddenInput.value = this.players.join(", ");
    }

    if (triggerChange) {
      this.onChange(this.getPlayers());
    }
  }

  _getPlayerInitial(playerName) {
    const letters = String(playerName || "?").replace(/[^\p{L}\p{N}]/gu, "");
    const first = (letters[0] || "?").toUpperCase();
    const clashes = this.players.filter((name) => {
      const l = String(name || "?").replace(/[^\p{L}\p{N}]/gu, "");
      return (l[0] || "?").toUpperCase() === first;
    });
    if (clashes.length > 1 && letters.length > 1) {
      return first + letters[1].toLowerCase();
    }
    return first;
  }

  _renderChips() {
    this.chipsWrap.innerHTML = "";

    this.players.forEach((playerName, index) => {
      const chip = document.createElement("div");
      chip.className = "player-chip";

      const avatar = document.createElement("span");
      avatar.className = "player-chip-avatar";
      const color = PLAYER_COLORS[index % PLAYER_COLORS.length];
      avatar.style.background = color;
      avatar.textContent = this._getPlayerInitial(playerName);

      const nameSpan = document.createElement("span");
      nameSpan.className = "player-chip-name";
      nameSpan.textContent = playerName;

      const removeBtn = document.createElement("button");
      removeBtn.type = "button";
      removeBtn.className = "player-chip-remove";
      removeBtn.title = t("setup.players_remove_title", playerName);
      removeBtn.setAttribute("aria-label", t("setup.players_remove_title", playerName));
      removeBtn.innerHTML = `
        <svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
          <line x1="18" y1="6" x2="6" y2="18"></line>
          <line x1="6" y1="6" x2="18" y2="18"></line>
        </svg>
      `;

      removeBtn.addEventListener("click", (e) => {
        e.preventDefault();
        e.stopPropagation();
        this.removePlayer(index);
        this.textInput.focus();
      });

      chip.appendChild(avatar);
      chip.appendChild(nameSpan);
      chip.appendChild(removeBtn);

      this.chipsWrap.appendChild(chip);
    });
  }

  _updateBadge() {
    if (!this.countBadge) return;
    const count = this.players.length;

    if (count === 1) {
      this.countBadge.textContent = t("setup.players_count_solo");
      this.countBadge.classList.remove("multi", "empty");
    } else if (count > 1) {
      this.countBadge.textContent = t("setup.players_count_multi", count);
      this.countBadge.classList.add("multi");
      this.countBadge.classList.remove("empty");
    } else {
      this.countBadge.textContent = t("setup.players_count_none");
      this.countBadge.classList.remove("multi");
      this.countBadge.classList.add("empty");
    }
  }

  /**
   * Focus the text input
   */
  focus() {
    if (this.textInput) {
      this.textInput.focus();
    }
  }

  /**
   * Display empty player error feedback and focus input
   */
  showEmptyError() {
    this._showFeedback(t("setup.players_empty_error"));
    this.focus();
  }

  /**
   * Update component labels and placeholders after language change
   */
  updateLanguage() {
    if (this.textInput) {
      this.textInput.placeholder = t("setup.players_placeholder");
    }
    if (this.addBtn) {
      this.addBtn.title = t("setup.players_add_btn");
      const label = this.addBtn.querySelector(".add-btn-label");
      if (label) {
        label.textContent = t("setup.players_add_btn");
      }
    }
    this._updateBadge();
    this._renderChips();
  }
}

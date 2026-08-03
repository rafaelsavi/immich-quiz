import { state, el } from "../state.js";
import { t, showAlert } from "../i18n.js";
import { api } from "../api.js";

/**
 * Controller for the Game Setup View.
 */
export const setupView = {
  /**
   * Initializes setup form elements and event handlers.
   * @param {Object} options Options containing setup callbacks
   */
  init({ onSetupSuccess }) {
    this.onSetupSuccess = onSetupSuccess;
    this.bindEvents();
  },

  bindEvents() {
    if (el.setupForm) {
      el.setupForm.addEventListener("submit", (e) => this.handleSetupSubmit(e));
    }
    if (el.librarySelect) {
      el.librarySelect.addEventListener("change", () => this.handleLibraryChange());
    }
  },

  async loadLibraries() {
    if (!el.librarySelect) return;
    try {
      const data = await api.getLibraries();
      el.librarySelect.replaceChildren();

      const defaultOpt = document.createElement("option");
      defaultOpt.value = "";
      defaultOpt.textContent = `-- ${t("setup.select_library")} --`;
      el.librarySelect.appendChild(defaultOpt);

      (data.libraries || []).forEach((lib) => {
        const opt = document.createElement("option");
        opt.value = lib;
        opt.textContent = lib;
        el.librarySelect.appendChild(opt);
      });
    } catch (err) {
      showAlert(t("setup.load_libraries_error", err.message));
    }
  },

  async handleLibraryChange() {
    if (!el.albumSelect || !el.librarySelect) return;
    const libraryName = el.librarySelect.value;
    el.albumSelect.replaceChildren();
    const allOpt = document.createElement("option");
    allOpt.value = "";
    allOpt.textContent = t("setup.all_photos");
    el.albumSelect.appendChild(allOpt);

    if (!libraryName) return;

    try {
      const data = await api.getAlbums(libraryName);
      (data.albums || []).forEach((album) => {
        const opt = document.createElement("option");
        opt.value = album.id;
        opt.textContent = album.name;
        el.albumSelect.appendChild(opt);
      });
    } catch (err) {
      showAlert(t("setup.load_albums_error", err.message));
    }
  },

  async handleSetupSubmit(e) {
    e.preventDefault();
    if (!el.librarySelect || !el.librarySelect.value) {
      showAlert(t("setup.select_library_required"));
      return;
    }

    const playerInputs = document.querySelectorAll(".player-name-input");
    const players = Array.from(playerInputs)
      .map((input) => input.value.strip ? input.value.strip() : input.value.trim())
      .filter(Boolean);

    if (players.length === 0) {
      showAlert(t("setup.at_least_one_player"));
      return;
    }

    const selectedModeObj = window.GAME_MODES ? window.GAME_MODES[state.selectedGameMode] : null;
    const modePayload = selectedModeObj ? selectedModeObj.getModePayload() : { game_mode: "pinpoint", location_mode: true, date_mode: true };

    const payload = {
      library_name: el.librarySelect.value,
      album_id: el.albumSelect && el.albumSelect.value ? el.albumSelect.value : null,
      round_count: Number(el.roundCountSelect ? el.roundCountSelect.value : 5),
      round_length: el.roundLengthSelect ? el.roundLengthSelect.value : "unlimited",
      players: players,
      ...modePayload,
    };

    try {
      const preflight = await api.preflightGame({
        library_name: payload.library_name,
        album_id: payload.album_id,
        round_count: payload.round_count,
        location_mode: payload.location_mode,
        date_mode: payload.date_mode,
        game_mode: payload.game_mode,
      });

      if (!preflight.ok) {
        showAlert(t("setup.preflight_insufficient_photos", preflight.eligible_count, preflight.required));
        return;
      }

      const res = await api.setupGame(payload);
      state.matchId = res.match_id;
      state.totalTurns = res.total_turns;
      state.players = players;

      if (this.onSetupSuccess) {
        this.onSetupSuccess(res);
      }
    } catch (err) {
      showAlert(t("setup.create_game_error", err.message));
    }
  },
};

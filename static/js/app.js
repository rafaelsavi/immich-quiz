const PLAYER_COLORS = [
  "#f25f5c",
  "#0f7c7f",
  "#7048e8",
  "#f7b267",
  "#2f80ed",
  "#e0338d",
  "#3aa655",
  "#8d5524",
];

const ACTUAL_COLOR = "#1f2a44";
const EARLIEST_YEAR = 1950;
const DEFAULT_MAP_WIDTH_PCT = 67;

/* ---------------------------------------------------------------- i18n */

const TRANSLATIONS = {
  EN: {
    // Setup card
    "setup.heading": "Game Setup",
    "setup.players_label": "Players (comma separated)",
    "setup.rounds_label": "Rounds",
    "setup.round_length_label": "Round Length",
    "setup.round_30s": "30s",
    "setup.round_1m": "1 min",
    "setup.round_unlimited": "Unlimited",
    "setup.guess_mode": "Guess Mode",
    "setup.goal_location": "Location",
    "setup.goal_date": "Date",
    "setup.library_label": "Library",
    "setup.album_label": "Album",
    "setup.all_photos": "-",
    "setup.start_btn": "Start Match",
    "setup.not_enough_media": (found, required, filters) =>
      `Cannot start match: only ${found} photo(s) matching criteria found in selected album/library, but ${required} rounds are required.\n\nActive filters: ${filters}`,
    "setup.filter_location": "Location (GPS required)",
    "setup.filter_date": "Date (timestamp required)",
    "setup.filter_date_range": (minDate, maxDate) => {
      if (minDate && maxDate) {
        return `Date range limit (${minDate} to ${maxDate})`;
      }
      if (minDate) {
        return `Date range limit (from ${minDate})`;
      }
      if (maxDate) {
        return `Date range limit (until ${maxDate})`;
      }
      return "Date range limit";
    },
    // Game card
    "game.ready_btn": "I'm Ready",
    "game.media_placeholder": 'Photo hidden until you press "I\'m Ready".',
    "game.media_error_msg": "Photo failed to load from Immich server.",
    "game.media_skip_btn": "Skip Photo",
    "game.fullscreen_btn": "Fullscreen",
    "game.fullscreen_exit_btn": "Exit Fullscreen",
    "game.location_guess_label": "Location Guess",
    "game.date_guess_label": "Date Guess (year / month)",
    "game.submit_btn": "Submit Answer",
    "game.restart_btn": "Restart",
    "game.exit_btn": "Exit",
    "game.timer_unlimited": "Unlimited round time",
    "game.timer_time_left": "Time left",
    "game.timer_time_up_label": "Time is up",
    "game.timer_time_up_notice": "Time's up! Your answers are frozen. Press Continue when you are ready.",
    "game.continue_btn": "Continue",
    "game.pin_required": "Place a pin on the map first",
    "game.round_meta": (roundNum, totalRounds, playerNum, totalPlayers, playerName) =>
      `Round ${roundNum} of ${totalRounds}\nPlayer ${playerNum}: ${playerName}`,
    "game.pass_device_title": (playerName, playerNum, totalPlayers) =>
      `Pass device to player ${playerNum}: ${playerName}`,
    "game.pass_device_subtitle": (roundNum, totalRounds) =>
      `Round ${roundNum} of ${totalRounds}`,
    "game.abandon_restart": "restart the game with the same settings",
    "game.abandon_exit": "exit to the setup screen",
    "game.abandon_confirm": (label) =>
      `Are you sure you want to ${label}? Current game progress will be lost.`,
    // Reveal card
    "reveal.title": (roundNum, totalRounds) => `Round ${roundNum} of ${totalRounds} - Reveal`,
    "reveal.correct_answer": "Correct answer",
    "reveal.actual_date": "Actual date:",
    "reveal.actual_location": "Actual location:",
    "reveal.actual_location_legend": "Actual location",
    "reveal.map_label": "Round Map",
    "reveal.next_round_btn": "Next Round",
    "reveal.see_results_btn": "See Final Results",
    "reveal.col_player": "Player",
    "reveal.col_location": "Location",
    "reveal.col_date": "Date",
    "reveal.col_score": "Score",
    "reveal.col_points": "Points",
    "reveal.col_distance_error": "Distance Error",
    "reveal.col_guessed": "Guessed",
    "reveal.col_date_error": "Date Error",
    "reveal.col_round": "Round",
    "reveal.col_total": "Total",
    "reveal.no_guess": "no guess",
    "reveal.perfect_badge": "PERFECT!",
    "reveal.popup_actual": "Actual location",
    "reveal.popup_guess": (playerName, dist) => `${playerName}: ${dist} off`,
    // Summary card
    "summary.heading": "Match Results",
    "summary.new_match_btn": "Start New Match",
    "summary.tie": (names) => `It's a tie: ${names}!`,
    "summary.winner": (name) => `Winner: ${name}!`,
    "summary.mode_location": "location",
    "summary.mode_date": "date",
    "summary.meta": (rounds, modes, library, album) =>
      `${rounds} rounds\nGuess Mode: ${modes}\nLibrary: ${library} / ${album}`,
    "summary.col_rank": "#",
    "summary.col_player": "Player",
    "summary.col_location": "Location",
    "summary.col_date": "Date",
    "summary.col_total": "Total",
    "summary.col_accuracy": "Accuracy %",
    // Leaderboard
    "leaderboard.heading": "Leaderboard",
    "leaderboard.refresh_btn": "Refresh",
    "leaderboard.col_played_at": "Played At",
    "leaderboard.col_player": "Player",
    "leaderboard.col_accuracy": "Accuracy %",
    "leaderboard.col_score": "Score",
    // Formatting
    "fmt.no_guess": "no guess",
    "fmt.unknown_place": "unknown",
    "fmt.exact_month": "exact month (0 days)",
    "fmt.years_abbr": "y",
    "fmt.months_abbr": "m",
    "fmt.day": "day",
    "fmt.days": "days",
    "fmt.timed_out_tag": "TIMED OUT",
    // Errors & Popups
    "error.Player names must be unique": "Player names must be unique.",
    "error.Player list cannot be empty": "Player list cannot be empty.",
    "error.Player names must be non-empty": "Player names must be non-empty.",
    "error.At least one mode must be enabled": "At least one mode must be enabled.",
    "error.round_count must be one of: 5, 10, 20": "Round count must be 5, 10, or 20.",
    "error.guessed_year and guessed_month must be provided together": "Year and month must be provided together.",
    "error.unknown_album": "Unknown album ID for selected library.",
    "game.fullscreen_error": (msg) => `Fullscreen unavailable: ${msg}`,
    "setup.startup_error": (details) => `Some startup data could not be loaded:\n\n${details}`,
  },
  PT: {
    // Setup card
    "setup.heading": "Configuração do Jogo",
    "setup.players_label": "Jogadores (separados por vírgula)",
    "setup.rounds_label": "Rodadas",
    "setup.round_length_label": "Duração da Rodada",
    "setup.round_30s": "30s",
    "setup.round_1m": "1 min",
    "setup.round_unlimited": "Ilimitado",
    "setup.guess_mode": "Modo de adivinhação",
    "setup.goal_location": "Localização",
    "setup.goal_date": "Data",
    "setup.library_label": "Biblioteca",
    "setup.album_label": "Álbum",
    "setup.all_photos": "-",
    "setup.start_btn": "Iniciar Partida",
    "setup.not_enough_media": (found, required, filters) =>
      `Não é possível iniciar a partida: apenas ${found} foto(s) com os critérios foram encontradas no álbum/biblioteca selecionado, mas são necessárias ${required} rodadas.\n\nFiltros ativos: ${filters}`,
    "setup.filter_location": "Localização (GPS necessário)",
    "setup.filter_date": "Data (data/hora necessária)",
    "setup.filter_date_range": (minDate, maxDate) => {
      if (minDate && maxDate) {
        return `Limite de intervalo de datas (${minDate} a ${maxDate})`;
      }
      if (minDate) {
        return `Limite de intervalo de datas (a partir de ${minDate})`;
      }
      if (maxDate) {
        return `Limite de intervalo de datas (até ${maxDate})`;
      }
      return "Limite de intervalo de datas";
    },
    // Game card
    "game.ready_btn": "Estou Pronto",
    "game.media_placeholder": 'Foto oculta até você pressionar "Estou Pronto".',
    "game.media_error_msg": "Não foi possível carregar a foto do servidor Immich.",
    "game.media_skip_btn": "Pular Foto",
    "game.fullscreen_btn": "Tela cheia",
    "game.fullscreen_exit_btn": "Sair da tela cheia",
    "game.location_guess_label": "Palpite de Localização",
    "game.date_guess_label": "Palpite de Data (ano / mês)",
    "game.submit_btn": "Enviar Resposta",
    "game.restart_btn": "Reiniciar",
    "game.exit_btn": "Sair",
    "game.timer_unlimited": "Tempo ilimitado",
    "game.timer_time_left": "Tempo restante",
    "game.timer_time_up_label": "Tempo esgotado",
    "game.timer_time_up_notice": "Tempo esgotado! Suas respostas foram congeladas. Pressione Continuar quando estiver pronto.",
    "game.continue_btn": "Continuar",
    "game.pin_required": "Coloque um pino no mapa primeiro",
    "game.round_meta": (roundNum, totalRounds, playerNum, totalPlayers, playerName) =>
      `Rodada ${roundNum} de ${totalRounds}\nJogador ${playerNum}: ${playerName}`,
    "game.pass_device_title": (playerName, playerNum, totalPlayers) =>
      `Passe o dispositivo para o jogador ${playerNum}: ${playerName}`,
    "game.pass_device_subtitle": (roundNum, totalRounds) =>
      `Rodada ${roundNum} de ${totalRounds}`,
    "game.abandon_restart": "reiniciar o jogo com as mesmas configurações",
    "game.abandon_exit": "voltar para a tela inicial",
    "game.abandon_confirm": (label) =>
      `Tem certeza que deseja ${label}? O progresso atual será perdido.`,
    // Reveal card
    "reveal.title": (roundNum, totalRounds) => `Rodada ${roundNum} de ${totalRounds} - Revelação`,
    "reveal.correct_answer": "Resposta correta",
    "reveal.actual_date": "Data real:",
    "reveal.actual_location": "Local real:",
    "reveal.actual_location_legend": "Local real",
    "reveal.map_label": "Mapa da Rodada",
    "reveal.next_round_btn": "Próxima Rodada",
    "reveal.see_results_btn": "Ver Resultado Final",
    "reveal.col_player": "Jogador",
    "reveal.col_location": "Localização",
    "reveal.col_date": "Data",
    "reveal.col_score": "Pontuação",
    "reveal.col_points": "Pontos",
    "reveal.col_distance_error": "Erro de Distância",
    "reveal.col_guessed": "Palpite",
    "reveal.col_date_error": "Erro de Data",
    "reveal.col_round": "Rodada",
    "reveal.col_total": "Total",
    "reveal.no_guess": "sem palpite",
    "reveal.perfect_badge": "PERFEITO!",
    "reveal.popup_actual": "Local real",
    "reveal.popup_guess": (playerName, dist) => `${playerName}: ${dist} de distância`,
    // Summary card
    "summary.heading": "Resultado da Partida",
    "summary.new_match_btn": "Iniciar Nova Partida",
    "summary.tie": (names) => `Empate: ${names}!`,
    "summary.winner": (name) => `Vencedor: ${name}!`,
    "summary.mode_location": "localização",
    "summary.mode_date": "data",
    "summary.meta": (rounds, modes, library, album) =>
      `${rounds} rodadas\nAdivinhação: ${modes}\nBiblioteca: ${library} / ${album}`,
    "summary.col_rank": "#",
    "summary.col_player": "Jogador",
    "summary.col_location": "Localização",
    "summary.col_date": "Data",
    "summary.col_total": "Total",
    "summary.col_accuracy": "Precisão %",
    // Leaderboard
    "leaderboard.heading": "Classificação",
    "leaderboard.refresh_btn": "Atualizar",
    "leaderboard.col_played_at": "Jogado em",
    "leaderboard.col_player": "Jogador",
    "leaderboard.col_accuracy": "Precisão %",
    "leaderboard.col_score": "Pontuação",
    // Formatting
    "fmt.no_guess": "sem palpite",
    "fmt.unknown_place": "desconhecido",
    "fmt.exact_month": "mês exato (0 dias)",
    "fmt.years_abbr": "a",
    "fmt.months_abbr": "m",
    "fmt.day": "dia",
    "fmt.days": "dias",
    "fmt.timed_out_tag": "TEMPO ESGOTADO",
    // Errors & Popups
    "error.Player names must be unique": "Os nomes dos jogadores devem ser únicos.",
    "error.Player list cannot be empty": "A lista de jogadores não pode estar vazia.",
    "error.Player names must be non-empty": "Os nomes dos jogadores não podem estar vazios.",
    "error.At least one mode must be enabled": "Pelo menos um modo deve estar ativado.",
    "error.round_count must be one of: 5, 10, 20": "O número de rodadas deve ser 5, 10 ou 20.",
    "error.guessed_year and guessed_month must be provided together": "Ano e mês devem ser fornecidos juntos.",
    "error.unknown_album": "Álbum desconhecido para a biblioteca selecionada.",
    "game.fullscreen_error": (msg) => `Tela cheia indisponível: ${msg}`,
    "setup.startup_error": (details) => `Não foi possível carregar alguns dados iniciais:\n\n${details}`,
  },
};

/**
 * Translate a key using the current language stored in state.
 * For function-valued entries, extra args are forwarded.
 */
function t(key, ...args) {
  const lang = state ? state.language || "EN" : "EN";
  const dict = TRANSLATIONS[lang] || TRANSLATIONS.EN;
  const entry = key in dict ? dict[key] : TRANSLATIONS.EN[key];
  if (typeof entry === "function") {
    return entry(...args);
  }
  return entry !== undefined ? entry : key;
}

function translateError(msg) {
  if (!msg) return "";
  const raw = typeof msg === "string" ? msg : msg.message || String(msg);
  const str = raw.trim();

  const key = `error.${str}`;
  const translated = t(key);
  if (translated !== key) {
    return translated;
  }

  if (str.startsWith("Unknown album_id for library")) {
    return t("error.unknown_album");
  }

  return str;
}

function showAlert(msg) {
  if (!msg) return;
  alert(translateError(msg));
}

/**
 * Apply translations to all [data-i18n] elements in the DOM.
 * Elements with a sort arrow child keep the arrow intact.
 */
function applyLanguage() {
  document.querySelectorAll("[data-i18n]").forEach((el) => {
    const key = el.getAttribute("data-i18n");
    const translation = t(key);
    // Leaderboard headers contain a nested .sort-arrow span — preserve it.
    const arrow = el.querySelector(".sort-arrow");
    if (arrow) {
      const arrowClone = arrow.cloneNode(true);
      el.textContent = translation;
      el.appendChild(arrowClone);
    } else if (el.hasAttribute("placeholder")) {
      el.setAttribute("placeholder", translation);
    } else {
      el.textContent = translation;
    }
  });
}

/* ------------------------------------------------------------- audio sfx */

let audioCtx = null;

function unlockAudioContext() {
  if (!audioCtx) {
    const AudioContextClass = window.AudioContext || window.webkitAudioContext;
    if (AudioContextClass) {
      audioCtx = new AudioContextClass();
    }
  }
  if (audioCtx && audioCtx.state === "suspended") {
    audioCtx.resume().catch(() => {});
  }
}

document.addEventListener("pointerdown", unlockAudioContext, { capture: true });
document.addEventListener("keydown", unlockAudioContext, { capture: true });

function getAudioContext() {
  unlockAudioContext();
  return audioCtx;
}

function playTone(freq, type, duration, gainValue = 0.15) {
  if (!state || !state.audioEnabled) return;
  try {
    const ctx = getAudioContext();
    if (!ctx) return;
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();

    osc.type = type;
    osc.frequency.setValueAtTime(freq, ctx.currentTime);

    gain.gain.setValueAtTime(gainValue, ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + duration);

    osc.connect(gain);
    gain.connect(ctx.destination);

    osc.start();
    osc.stop(ctx.currentTime + duration);
  } catch (_) {
    // Ignore audio autoplay restrictions
  }
}

function playTick() {
  playTone(800, "sine", 0.05, 0.08);
}

function playBuzzer() {
  playTone(220, "sawtooth", 0.4, 0.12);
}

function playChime() {
  if (!state || !state.audioEnabled) return;
  try {
    const ctx = getAudioContext();
    if (!ctx) return;
    const notes = [523.25, 659.25, 783.99, 1046.5];
    notes.forEach((freq, idx) => {
      setTimeout(() => {
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.type = "triangle";
        osc.frequency.setValueAtTime(freq, ctx.currentTime);
        gain.gain.setValueAtTime(0.18, ctx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + 0.35);
        osc.connect(gain);
        gain.connect(ctx.destination);
        osc.start();
        osc.stop(ctx.currentTime + 0.35);
      }, idx * 100);
    });
  } catch (_) {}
}

function playVictoryFanfare() {
  if (!state || !state.audioEnabled) return;
  try {
    const ctx = getAudioContext();
    if (!ctx) return;

    const notes = [
      { freq: 349.23, delay: 0, duration: 0.18 },
      { freq: 440.0, delay: 0.12, duration: 0.18 },
      { freq: 523.25, delay: 0.24, duration: 0.18 },
      { freq: 698.46, delay: 0.36, duration: 0.65 },
    ];

    notes.forEach((n) => {
      setTimeout(() => {
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.type = "triangle";
        osc.frequency.setValueAtTime(n.freq, ctx.currentTime);

        gain.gain.setValueAtTime(0.22, ctx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + n.duration);

        osc.connect(gain);
        gain.connect(ctx.destination);

        osc.start();
        osc.stop(ctx.currentTime + n.duration);
      }, n.delay * 1000);
    });
  } catch (_) {}
}

function toggleAudio() {
  unlockAudioContext();
  state.audioEnabled = !state.audioEnabled;
  localStorage.setItem("immich_quiz_audio", state.audioEnabled ? "1" : "0");
  updateAudioUi();
  if (state.audioEnabled) {
    playTone(600, "sine", 0.08, 0.1);
  }
}

function updateAudioUi() {
  if (el.audioIcon) {
    el.audioIcon.textContent = state.audioEnabled ? "🔊" : "🔇";
  }
  if (el.audioToggleBtn) {
    el.audioToggleBtn.setAttribute(
      "title",
      state.audioEnabled ? "Sound Effects: Enabled" : "Sound Effects: Muted"
    );
  }
}

const state = {
  matchId: null,
  players: [],
  language: "EN",
  scoreMaxPoints: 100,
  lastMatchConfig: null,
  playedAssetIds: [],
  currentQuestion: null,
  guessedLatLng: null,
  guessMap: null,
  revealMap: null,
  guessMarker: null,
  revealLayers: [],
  timerRef: null,
  timedOut: false,
  submitting: false,
  matchFinished: false,
  leaderboardRows: [],
  leaderboardSort: { key: "total_score", asc: false },
  audioEnabled: localStorage.getItem("immich_quiz_audio") !== "0",
};

const el = {
  audioToggleBtn: document.getElementById("audio-toggle-btn"),
  audioIcon: document.getElementById("audio-icon"),
  setupCard: document.getElementById("setup-card"),
  gameCard: document.getElementById("game-card"),
  summaryCard: document.getElementById("summary-card"),
  leaderboardCard: document.getElementById("leaderboard-card"),
  guessingUi: document.getElementById("guessing-ui"),
  revealUi: document.getElementById("reveal-ui"),
  setupForm: document.getElementById("setup-form"),
  players: document.getElementById("players"),
  roundCount: document.getElementById("round-count"),
  roundLength: document.getElementById("round-length"),
  goalLocation: document.getElementById("goal-location"),
  goalDate: document.getElementById("goal-date"),
  library: document.getElementById("library"),
  album: document.getElementById("album"),
  roundMeta: document.getElementById("round-meta"),
  passOverlay: document.getElementById("pass-overlay"),
  overlayTitle: document.getElementById("overlay-title"),
  overlaySubtitle: document.getElementById("overlay-subtitle"),
  readyBtn: document.getElementById("ready-btn"),
  mediaFrame: document.getElementById("media-frame"),
  quizImage: document.getElementById("quiz-image"),
  quizImageFullscreen: document.getElementById("quiz-image-fullscreen"),
  mediaPlaceholder: document.getElementById("media-placeholder"),
  mediaErrorCard: document.getElementById("media-error-card"),
  mediaErrorMsg: document.getElementById("media-error-msg"),
  mediaSkipBtn: document.getElementById("media-skip-btn"),
  mapGuessWrap: document.getElementById("map-guess-wrap"),
  guessMapShell: document.getElementById("guess-map-shell"),
  guessMapFullscreen: document.getElementById("guess-map-fullscreen"),
  dateGuessWrap: document.getElementById("date-guess-wrap"),
  dateGuessYear: document.getElementById("date-guess-year"),
  dateGuessMonth: document.getElementById("date-guess-month"),
  submitAnswer: document.getElementById("submit-answer"),
  timerLabel: document.getElementById("timer-label"),
  timerRemaining: document.getElementById("timer-remaining"),
  timerTrack: document.getElementById("timer-track"),
  timerFill: document.getElementById("timer-fill"),
  timeoutNotice: document.getElementById("timeout-notice"),
  revealActual: document.getElementById("reveal-actual"),
  revealLegend: document.getElementById("reveal-legend"),
  revealTableHead: document.querySelector("#reveal-table thead"),
  revealTableBody: document.querySelector("#reveal-table tbody"),
  revealMapShell: document.getElementById("reveal-map-shell"),
  revealMapHead: document.getElementById("reveal-map-head"),
  revealMapFullscreen: document.getElementById("reveal-map-fullscreen"),
  nextRound: document.getElementById("next-round"),
  summaryWinner: document.getElementById("summary-winner"),
  summaryMeta: document.getElementById("summary-meta"),
  summaryTableHead: document.querySelector("#summary-table thead"),
  summaryTableBody: document.querySelector("#summary-table tbody"),
  newMatch: document.getElementById("new-match"),
  gameRestartBtn: document.getElementById("game-restart-btn"),
  gameExitBtn: document.getElementById("game-exit-btn"),
  revealRestartBtn: document.getElementById("reveal-restart-btn"),
  revealExitBtn: document.getElementById("reveal-exit-btn"),
  refreshLeaderboard: document.getElementById("refresh-leaderboard"),
  leaderboardBody: document.querySelector("#leaderboard-table tbody"),
  leaderboardHead: document.querySelector("#leaderboard-table thead"),
};

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });

  if (!response.ok) {
    const text = await response.text();
    let message = text;
    try {
      const data = JSON.parse(text);
      if (data && data.detail) {
        if (typeof data.detail === "string") {
          message = data.detail;
        } else if (Array.isArray(data.detail)) {
          message = data.detail
            .map((item) => {
              if (typeof item === "string") return item;
              if (item && item.msg) {
                return item.msg.replace(/^Value error,\s*/i, "");
              }
              return JSON.stringify(item);
            })
            .join("\n");
        } else {
          message = JSON.stringify(data.detail);
        }
      } else if (data && data.message) {
        message = data.message;
      }
    } catch (_) {
      // Keep plain text response if not JSON
    }
    throw new Error(message || `Request failed with ${response.status}`);
  }

  const contentType = response.headers.get("content-type") || "";
  if (!contentType.includes("application/json")) {
    return response;
  }
  return response.json();
}

/* --------------------------------------------------------------- helpers */

function normalizedName(playerName) {
  return String(playerName || "?").replace(/[^\p{L}\p{N}]/gu, "");
}

function playerColor(playerName) {
  const index = state.players.indexOf(playerName);
  return PLAYER_COLORS[(index < 0 ? 0 : index) % PLAYER_COLORS.length];
}

function playerInitial(playerName) {
  const letters = normalizedName(playerName);
  const first = (letters[0] || "?").toUpperCase();

  // Players sharing a first letter get a second character so map pins stay unambiguous.
  const clashes = state.players.filter((name) => (normalizedName(name)[0] || "?").toUpperCase() === first);
  if (clashes.length > 1 && letters.length > 1) {
    return first + letters[1].toLowerCase();
  }
  return first;
}

function formatMonth(year, month) {
  if (!year || !month) {
    return t("fmt.no_guess");
  }
  return `${String(month).padStart(2, "0")}/${year}`;
}

function formatPlace(reveal) {
  // Immich reverse-geocodes assets already, so reuse its labels.
  const parts = [reveal.actual_country, reveal.actual_city].filter(Boolean);
  if (parts.length > 0) {
    return parts.join(", ");
  }
  if (reveal.actual_latitude === null || reveal.actual_longitude === null) {
    return t("fmt.unknown_place");
  }
  return `${reveal.actual_latitude.toFixed(4)}, ${reveal.actual_longitude.toFixed(4)}`;
}

function formatDistance(km) {
  if (km === null || km === undefined) {
    return "-";
  }
  if (km < 1) {
    return `${Math.round(km * 1000)} m`;
  }
  if (km < 10) {
    return `${km.toFixed(1)} km`;
  }
  return `${Math.round(km).toLocaleString()} km`;
}

function formatMonthError(result) {
  if (result.date_diff_days === null || result.date_diff_days === undefined) {
    return "-";
  }
  if (result.date_diff_days === 0) {
    return t("fmt.exact_month");
  }

  const years = result.date_diff_years_part ?? 0;
  const months = result.date_diff_months_part ?? 0;
  const parts = [];
  if (years > 0) {
    parts.push(`${years}${t("fmt.years_abbr")}`);
  }
  if (months > 0) {
    parts.push(`${months}${t("fmt.months_abbr")}`);
  }

  const dayWord = result.date_diff_days === 1 ? t("fmt.day") : t("fmt.days");
  const days = `${result.date_diff_days} ${dayWord}`;
  return parts.length > 0 ? `${parts.join(" ")} (${days})` : days;
}

function buildCell(content, isHeader = false) {
  const cell = document.createElement(isHeader ? "th" : "td");
  if (content instanceof Node) {
    cell.appendChild(content);
  } else {
    cell.textContent = content;
  }
  return cell;
}

function playerBadge(playerName) {
  const badge = document.createElement("span");
  badge.className = "legend-badge";
  badge.style.background = playerColor(playerName);
  badge.textContent = playerInitial(playerName);
  return badge;
}

function playerNameCell(playerName, timedOut = false) {
  const wrap = document.createElement("span");
  wrap.className = "player-cell";
  wrap.append(playerBadge(playerName), document.createTextNode(playerName));
  if (timedOut) {
    const tag = document.createElement("span");
    tag.className = "timed-out-tag";
    tag.textContent = t("fmt.timed_out_tag");
    wrap.appendChild(tag);
  }
  return wrap;
}

/* -------------------------------------------------------- setup + lookups */

async function initLibraries() {
  const data = await api("/api/libraries");
  el.library.replaceChildren();
  data.libraries.forEach((name) => {
    const option = document.createElement("option");
    option.value = name;
    option.textContent = name;
    el.library.appendChild(option);
  });

  if (data.libraries.length > 0) {
    await initAlbums(data.libraries[0]);
  }
}

async function initAlbums(libraryName) {
  const data = await api(`/api/albums?library_name=${encodeURIComponent(libraryName)}`);
  const allPhotos = document.createElement("option");
  allPhotos.value = "";
  allPhotos.setAttribute("data-i18n", "setup.all_photos");
  allPhotos.textContent = t("setup.all_photos");
  el.album.replaceChildren(allPhotos);
  data.albums.forEach((album) => {
    const option = document.createElement("option");
    option.value = album.id;
    option.textContent = album.name;
    el.album.appendChild(option);
  });
}

/* ------------------------------------------------- year / month dropdowns */

function initDateDropdowns() {
  const currentYear = new Date().getFullYear();

  el.dateGuessYear.replaceChildren();
  for (let year = currentYear; year >= EARLIEST_YEAR; year -= 1) {
    const option = document.createElement("option");
    option.value = String(year);
    option.textContent = String(year);
    el.dateGuessYear.appendChild(option);
  }

  el.dateGuessYear.value = String(currentYear);
  renderMonthOptions();
}

function renderMonthOptions(keepSelection = true) {
  const now = new Date();
  const currentYear = now.getFullYear();
  const currentMonth = now.getMonth() + 1;
  const selectedYear = Number(el.dateGuessYear.value);
  const maxMonth = selectedYear >= currentYear ? currentMonth : 12;
  const previous = Number(el.dateGuessMonth.value);

  el.dateGuessMonth.replaceChildren();
  for (let month = 1; month <= maxMonth; month += 1) {
    const option = document.createElement("option");
    option.value = String(month);
    option.textContent = String(month).padStart(2, "0");
    el.dateGuessMonth.appendChild(option);
  }

  // Default to (and clamp at) the newest selectable month.
  const keep = keepSelection && previous >= 1 && previous <= maxMonth;
  el.dateGuessMonth.value = String(keep ? previous : maxMonth);
}

async function initUiConfig() {
  const data = await api("/api/ui-config");
  applyUiConfig(data);
}

function applyUiConfig(config) {
  const heightPxRaw = Number(config.quiz_image_max_height_px);
  const heightPx = Number.isFinite(heightPxRaw) ? Math.min(1600, Math.max(200, heightPxRaw)) : 420;
  document.documentElement.style.setProperty("--quiz-image-max-height", `${heightPx}px`);

  if (config.language && (config.language === "PT" || config.language === "EN")) {
    state.language = config.language;
  }
  if (config.score_max_points) {
    state.scoreMaxPoints = Number(config.score_max_points);
  }
  applyLanguage();
}

function applyGuessLayout(locationMode, dateMode) {
  const hasMapOnly = Boolean(locationMode) && !Boolean(dateMode);
  if (hasMapOnly) {
    document.documentElement.style.setProperty("--round-guess-layout-columns", "minmax(0, 1fr)");
    return;
  }

  const mapWidthPct = DEFAULT_MAP_WIDTH_PCT;
  const dateWidthPct = 100 - mapWidthPct;
  document.documentElement.style.setProperty(
    "--round-guess-layout-columns",
    `minmax(0, ${mapWidthPct}fr) minmax(0, ${dateWidthPct}fr)`
  );
}

function resetDateGuess() {
  const now = new Date();
  el.dateGuessYear.value = String(now.getFullYear());
  renderMonthOptions(false);
}

function stepSelectOption(selectEl, direction) {
  if (!selectEl || selectEl.disabled || selectEl.options.length === 0) {
    return;
  }

  const current = selectEl.selectedIndex;
  const next = Math.max(0, Math.min(selectEl.options.length - 1, current + direction));
  if (next === current) {
    return;
  }

  selectEl.selectedIndex = next;
  selectEl.dispatchEvent(new Event("change", { bubbles: true }));
}

function bindSelectWheelScroll(selectEl, invertScroll = false) {
  selectEl.addEventListener(
    "wheel",
    (event) => {
      event.preventDefault();
      let direction = event.deltaY > 0 ? 1 : -1;
      if (invertScroll) direction = -direction;
      stepSelectOption(selectEl, direction);
    },
    { passive: false }
  );
}

/* ------------------------------------------------------------------- maps */

function createPinIcon(label, color) {
  return L.divIcon({
    className: "player-pin",
    html: `<span style="background:${color}"><b>${label}</b></span>`,
    iconSize: [28, 28],
    iconAnchor: [14, 28],
    popupAnchor: [0, -26],
  });
}

function ensureGuessMap() {
  if (state.guessMap) {
    state.guessMap.invalidateSize();
    return;
  }

  state.guessMap = L.map("guess-map", { worldCopyJump: true }).setView([20, 0], 2);
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19,
    attribution: "&copy; OpenStreetMap",
  }).addTo(state.guessMap);

  state.guessMap.on("click", (event) => {
    if (state.timedOut || state.submitting) {
      return;
    }
    // Normalize longitude to [-180, 180] so clicks on repeated world copies
    // always resolve to canonical coordinates, avoiding mismatched pin placement.
    const lat = event.latlng.lat;
    const lng = ((event.latlng.lng + 180) % 360 + 360) % 360 - 180;
    state.guessedLatLng = L.latLng(lat, lng);
    const player = state.currentQuestion ? state.currentQuestion.player_name : "";
    const icon = createPinIcon(playerInitial(player), playerColor(player));
    if (state.guessMarker) {
      state.guessMarker.remove();
    }
    state.guessMarker = L.marker([lat, lng], { icon }).addTo(state.guessMap);
    updateSubmitState();
  });

  // The container was hidden while Leaflet measured it, so re-measure once
  // the browser has painted the visible layout.
  requestAnimationFrame(() => state.guessMap.invalidateSize());
}

function ensureRevealMap() {
  if (!state.revealMap) {
    state.revealMap = L.map("reveal-map").setView([20, 0], 2);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
      attribution: "&copy; OpenStreetMap",
    }).addTo(state.revealMap);
  }
  requestAnimationFrame(() => state.revealMap.invalidateSize());
}

function toggleMapFullscreen(shell) {
  const request =
    document.fullscreenElement === shell ? document.exitFullscreen() : shell.requestFullscreen();
  Promise.resolve(request).catch((err) => showAlert(t("game.fullscreen_error", err.message)));
}

function syncFullscreenButtons() {
  [
    [el.mediaFrame, el.quizImageFullscreen],
    [el.guessMapShell, el.guessMapFullscreen],
    [el.revealMapShell, el.revealMapFullscreen],
  ].forEach(([shell, button]) => {
    const isActive = document.fullscreenElement === shell;
    button.textContent = isActive ? t("game.fullscreen_exit_btn") : t("game.fullscreen_btn");
    button.setAttribute("aria-pressed", isActive ? "true" : "false");
  });
}

/* ------------------------------------------------------------ submit gate */

function updateSubmitState() {
  if (state.submitting) {
    el.submitAnswer.disabled = true;
    return;
  }

  // After a timeout the answers are frozen, but the player still has to
  // acknowledge the reveal before the screen moves on.
  if (state.timedOut) {
    el.submitAnswer.disabled = false;
    el.submitAnswer.removeAttribute("title");
    return;
  }

  const needsPin = Boolean(state.currentQuestion && state.currentQuestion.location_mode);
  const missingPin = needsPin && !state.guessedLatLng;
  el.submitAnswer.disabled = !state.currentQuestion || missingPin;
  if (missingPin) {
    el.submitAnswer.title = t("game.pin_required");
  } else {
    el.submitAnswer.removeAttribute("title");
  }
}

/* ------------------------------------------------------------------ timer */

function clearTimer() {
  if (state.timerRef) {
    clearInterval(state.timerRef);
    state.timerRef = null;
  }
}

function resetTimerBar() {
  clearTimer();
  el.timerFill.style.width = "100%";
  el.timerFill.classList.remove("is-warning", "is-critical");
  el.timerTrack.classList.add("is-idle");
  el.timerLabel.textContent = "";
  el.timerRemaining.textContent = "";
  el.timeoutNotice.classList.add("hidden");
  el.timeoutNotice.textContent = "";
}

function startTimer(roundLength) {
  resetTimerBar();
  state.timedOut = false;

  if (roundLength === "unlimited") {
    el.timerLabel.textContent = t("game.timer_unlimited");
    return;
  }

  const total = roundLength === "30s" ? 30 : 60;
  let remaining = total;
  el.timerTrack.classList.remove("is-idle");
  el.timerLabel.textContent = t("game.timer_time_left");
  el.timerRemaining.textContent = `${remaining}s`;

  state.timerRef = setInterval(() => {
    remaining -= 1;
    const clamped = Math.max(remaining, 0);
    const ratio = clamped / total;

    el.timerRemaining.textContent = `${clamped}s`;
    el.timerFill.style.width = `${ratio * 100}%`;
    el.timerFill.classList.toggle("is-warning", ratio <= 0.5 && ratio > 0.2);
    el.timerFill.classList.toggle("is-critical", ratio <= 0.2);

    if (clamped <= 5 && clamped > 0) {
      playTick();
    }

    if (clamped <= 0) {
      clearTimer();
      playBuzzer();
      handleTimeout();
    }
  }, 1000);
}

function handleTimeout() {
  if (state.timedOut || state.submitting || !state.currentQuestion) {
    return;
  }
  state.timedOut = true;
  el.timerLabel.textContent = t("game.timer_time_up_label");
  el.timerRemaining.textContent = "0s";
  el.dateGuessYear.disabled = true;
  el.dateGuessMonth.disabled = true;

  el.timeoutNotice.textContent = t("game.timer_time_up_notice");
  el.timeoutNotice.classList.remove("hidden");

  // Nothing is submitted until the player acknowledges the timeout.
  el.submitAnswer.textContent = t("game.continue_btn");
  updateSubmitState();
}

/* ------------------------------------------------------------- game cycle */

function showCard(cardEl) {
  [el.setupCard, el.gameCard, el.summaryCard].forEach((c) => {
    c.classList.add("hidden");
  });
  cardEl.classList.remove("hidden");
}

async function startMatch(event) {
  event.preventDefault();

  const players = el.players.value
    .split(",")
    .map((name) => name.trim())
    .filter(Boolean);

  const albumId = el.album.value || null;
  const payload = {
    players,
    round_count: Number(el.roundCount.value),
    round_length: el.roundLength.value,
    location_mode: el.goalLocation.checked,
    date_mode: el.goalDate.checked,
    library_name: el.library.value,
    album_id: albumId,
    album_name: albumId ? el.album.options[el.album.selectedIndex].text : "-",
  };

  try {
    const preflight = await api("/api/game/preflight", {
      method: "POST",
      body: JSON.stringify(payload),
    });

    if (!preflight.ok) {
      const filterNames = (preflight.active_filters || [])
        .map((f) => t(`setup.filter_${f}`, preflight.min_date, preflight.max_date))
        .join(", ");
      alert(
        t("setup.not_enough_media", preflight.eligible_count, preflight.required, filterNames)
      );
      return;
    }
  } catch (err) {
    showAlert(err.message || err);
    return;
  }

  state.lastMatchConfig = payload;

  const response = await api("/api/game/setup", {
    method: "POST",
    body: JSON.stringify(payload),
  });

  state.matchId = response.match_id;
  state.players = response.players;
  state.playedAssetIds = [];
  state.matchFinished = false;

  // Standings stay secret while a match is in progress.
  el.leaderboardCard.classList.add("hidden");
  showCard(el.gameCard);

  await loadQuestion();
}

async function loadQuestion() {
  resetTimerBar();
  state.guessedLatLng = null;
  state.timedOut = false;
  state.currentQuestion = null;
  el.guessingUi.classList.remove("hidden");
  el.revealUi.classList.add("hidden");
  el.submitAnswer.textContent = t("game.submit_btn");
  el.dateGuessYear.disabled = false;
  el.dateGuessMonth.disabled = false;
  updateSubmitState();

  if (state.guessMarker) {
    state.guessMarker.remove();
    state.guessMarker = null;
  }
  if (state.guessMap) {
    state.guessMap.setView([20, 0], 2);
  }
  resetDateGuess();

  // Clear the image immediately so the previous round's photo never shows
  // through the pass-device overlay while the API call is in flight.
  el.quizImage.classList.add("hidden");
  el.quizImage.removeAttribute("src");
  if (el.mediaErrorCard) {
    el.mediaErrorCard.classList.add("hidden");
  }
  el.mediaPlaceholder.classList.remove("hidden");

  el.quizImage.onerror = () => {
    el.quizImage.classList.add("hidden");
    el.mediaPlaceholder.classList.add("hidden");
    if (el.mediaErrorCard) {
      el.mediaErrorCard.classList.remove("hidden");
    }
  };

  const data = await api("/api/question", {
    method: "POST",
    body: JSON.stringify({
      match_id: state.matchId,
      played_asset_ids: state.playedAssetIds,
    }),
  });

  state.currentQuestion = data;
  if (!state.playedAssetIds.includes(data.asset_id)) {
    state.playedAssetIds.push(data.asset_id);
  }

  el.roundMeta.textContent = t(
    "game.round_meta",
    data.player_round_number,
    data.total_rounds_per_player,
    data.player_number,
    data.total_players,
    data.player_name
  );
  applyGuessLayout(data.location_mode, data.date_mode);
  el.mapGuessWrap.classList.toggle("hidden", !data.location_mode);
  el.dateGuessWrap.classList.toggle("hidden", !data.date_mode);
  updateSubmitState();

  if (data.total_players > 1) {
    el.overlayTitle.textContent = t(
      "game.pass_device_title",
      data.player_name,
      data.player_number,
      data.total_players
    );
    el.overlaySubtitle.textContent = t("game.pass_device_subtitle", data.player_round_number, data.total_rounds_per_player);
    el.passOverlay.classList.remove("hidden");
  } else {
    el.passOverlay.classList.add("hidden");
    el.quizImage.src = data.media_url;
    el.quizImage.classList.remove("hidden");
    el.mediaPlaceholder.classList.add("hidden");
    if (data.location_mode) {
      ensureGuessMap();
    }
    startTimer(data.round_length);
  }
}

async function submitAnswer(fromTimeout = false) {
  if (!state.currentQuestion || state.submitting) {
    return;
  }
  state.submitting = true;
  updateSubmitState();
  playTone(480, "sine", 0.08, 0.12);

  try {
    const question = state.currentQuestion;
    const payload = {
      match_id: state.matchId,
      question_id: question.question_id,
      guessed_latitude: state.guessedLatLng ? state.guessedLatLng.lat : null,
      guessed_longitude: state.guessedLatLng ? state.guessedLatLng.lng : null,
      guessed_year: question.date_mode ? Number(el.dateGuessYear.value) : null,
      guessed_month: question.date_mode ? Number(el.dateGuessMonth.value) : null,
      timed_out: fromTimeout,
    };

    const result = await api("/api/answer", {
      method: "POST",
      body: JSON.stringify(payload),
    });

    clearTimer();
    state.matchFinished = result.match_finished;

    // Release the lock before the next screen loads, otherwise the submit gate
    // and the map click handler stay frozen for the following player.
    state.submitting = false;

    if (result.round_complete) {
      await showRoundReveal(result.round_number);
      return;
    }

    // Hand over to the next player without leaking any result.
    await loadQuestion();
  } finally {
    state.submitting = false;
    updateSubmitState();
  }
}

/* ----------------------------------------------------------------- reveal */

async function showRoundReveal(roundNumber) {
  const reveal = await api("/api/round/result", {
    method: "POST",
    body: JSON.stringify({ match_id: state.matchId, round_number: roundNumber }),
  });

  showCard(el.gameCard);
  el.guessingUi.classList.add("hidden");
  el.revealUi.classList.remove("hidden");

  renderRevealSummary(reveal);
  renderRevealMap(reveal);

  el.nextRound.textContent = reveal.match_finished ? t("reveal.see_results_btn") : t("reveal.next_round_btn");
}

function renderRevealSummary(reveal) {
  el.roundMeta.textContent = t("reveal.title", reveal.round_number, reveal.total_rounds);

  el.revealActual.replaceChildren();
  const heading = document.createElement("div");
  heading.textContent = t("reveal.correct_answer");
  el.revealActual.appendChild(heading);

  if (reveal.date_mode) {
    const dateLine = document.createElement("span");
    dateLine.textContent = `${t("reveal.actual_date")} ${formatMonth(reveal.actual_year, reveal.actual_month)}`;
    el.revealActual.appendChild(dateLine);
  }
  if (reveal.location_mode) {
    const locLine = document.createElement("span");
    locLine.textContent = `${t("reveal.actual_location")} ${formatPlace(reveal)}`;
    el.revealActual.appendChild(locLine);
  }

  el.revealLegend.replaceChildren();
  if (reveal.location_mode) {
    const actualItem = document.createElement("span");
    actualItem.className = "legend-item";
    const actualBadge = document.createElement("span");
    actualBadge.className = "legend-badge";
    actualBadge.style.background = ACTUAL_COLOR;
    actualBadge.textContent = "\u2605";
    actualItem.append(actualBadge, document.createTextNode(t("reveal.actual_location_legend")));
    el.revealLegend.appendChild(actualItem);

    reveal.results.forEach((result) => {
      const item = document.createElement("span");
      item.className = "legend-item";
      item.append(
        playerBadge(result.player_name),
        document.createTextNode(`${playerInitial(result.player_name)} = ${result.player_name}`)
      );
      el.revealLegend.appendChild(item);
    });
  }

  const groups = [];
  if (reveal.location_mode) {
    groups.push({ label: t("reveal.col_location"), columns: [t("reveal.col_points"), t("reveal.col_distance_error")] });
  }
  if (reveal.date_mode) {
    groups.push({ label: t("reveal.col_date"), columns: [t("reveal.col_points"), t("reveal.col_guessed"), t("reveal.col_date_error")] });
  }
  groups.push({ label: t("reveal.col_score"), columns: [t("reveal.col_round"), t("reveal.col_total")] });

  const groupRow = document.createElement("tr");
  const playerHead = buildCell(t("reveal.col_player"), true);
  playerHead.rowSpan = 2;
  groupRow.appendChild(playerHead);
  groups.forEach((group) => {
    const cell = buildCell(group.label, true);
    cell.colSpan = group.columns.length;
    cell.className = "group-head group-start";
    groupRow.appendChild(cell);
  });

  const columnRow = document.createElement("tr");
  groups.forEach((group) => {
    group.columns.forEach((label, index) => {
      const cell = buildCell(label, true);
      if (index === 0) {
        cell.className = "group-start";
      }
      columnRow.appendChild(cell);
    });
  });
  el.revealTableHead.replaceChildren(groupRow, columnRow);

  /* ------------------------------------------------------------- visual effects */

  function launchGoldConfetti() {
    const canvas = document.getElementById("confetti-canvas");
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const width = (canvas.width = window.innerWidth);
    const height = (canvas.height = window.innerHeight);

    const colors = ["#ffd700", "#ffae00", "#f59f00", "#fff3bf", "#e65100", "#ffffff"];
    const particles = [];
    const particleCount = 130;

    for (let i = 0; i < particleCount; i++) {
      particles.push({
        x: width / 2 + (Math.random() - 0.5) * (width * 0.6),
        y: height * 0.6 + (Math.random() - 0.5) * 120,
        vx: (Math.random() - 0.5) * 14,
        vy: -Math.random() * 15 - 5,
        size: Math.random() * 9 + 4,
        color: colors[Math.floor(Math.random() * colors.length)],
        rotation: Math.random() * Math.PI * 2,
        vRot: (Math.random() - 0.5) * 0.2,
        opacity: 1,
        isStar: Math.random() > 0.35,
      });
    }

    let startTime = null;
    const duration = 3200;

    function drawStar(c, cx, cy, spikes, outerRadius, innerRadius) {
      let rot = (Math.PI / 2) * 3;
      let x = cx;
      let y = cy;
      const step = Math.PI / spikes;

      c.beginPath();
      c.moveTo(cx, cy - outerRadius);
      for (let i = 0; i < spikes; i++) {
        x = cx + Math.cos(rot) * outerRadius;
        y = cy + Math.sin(rot) * outerRadius;
        c.lineTo(x, y);
        rot += step;

        x = cx + Math.cos(rot) * innerRadius;
        y = cy + Math.sin(rot) * innerRadius;
        c.lineTo(x, y);
        rot += step;
      }
      c.lineTo(cx, cy - outerRadius);
      c.closePath();
      c.fill();
    }

    function frame(timestamp) {
      if (!startTime) startTime = timestamp;
      const elapsed = timestamp - startTime;
      const progress = elapsed / duration;

      ctx.clearRect(0, 0, width, height);

      particles.forEach((p) => {
        p.x += p.vx;
        p.y += p.vy;
        p.vy += 0.35;
        p.vx *= 0.98;
        p.rotation += p.vRot;
        p.opacity = Math.max(0, 1 - progress);

        ctx.save();
        ctx.globalAlpha = p.opacity;
        ctx.fillStyle = p.color;
        ctx.translate(p.x, p.y);
        ctx.rotate(p.rotation);

        if (p.isStar) {
          drawStar(ctx, 0, 0, 5, p.size, p.size / 2);
        } else {
          ctx.fillRect(-p.size / 2, -p.size / 2, p.size, p.size * 0.6);
        }
        ctx.restore();
      });

      if (elapsed < duration) {
        requestAnimationFrame(frame);
      } else {
        ctx.clearRect(0, 0, width, height);
      }
    }

    requestAnimationFrame(frame);
  }

  function createPerfectBadge() {
    const badge = document.createElement("span");
    badge.className = "perfect-badge";
    badge.textContent = `\u2605 ${t("reveal.perfect_badge")}`;
    return badge;
  }

  const maxPoints = reveal.score_max_points || state.scoreMaxPoints || 100;
  const maxRoundPoints = (reveal.location_mode ? maxPoints : 0) + (reveal.date_mode ? maxPoints : 0);
  let hasAnyPerfectInRound = false;

  const ordered = [...reveal.results].sort((a, b) => b.round_score - a.round_score);
  el.revealTableBody.replaceChildren();

  ordered.forEach((result) => {
    const isPerfectLocation = reveal.location_mode && (result.location_score === maxPoints || result.distance_km === 0);
    const isPerfectDate = reveal.date_mode && (result.date_score === maxPoints || result.date_diff_days === 0);
    const isPerfectRound = maxRoundPoints > 0 && result.round_score === maxRoundPoints;
    const isPerfectPlayer = isPerfectLocation || isPerfectDate || isPerfectRound;

    if (isPerfectPlayer) {
      hasAnyPerfectInRound = true;
    }

    const row = document.createElement("tr");
    if (isPerfectPlayer) {
      row.className = "is-perfect-row";
    }

    row.appendChild(buildCell(playerNameCell(result.player_name, result.timed_out)));

    const valueGroups = [];
    if (reveal.location_mode) {
      valueGroups.push({
        isPerfect: isPerfectLocation,
        items: [
          result.location_score === null ? "-" : String(result.location_score),
          result.guessed_latitude === null ? t("reveal.no_guess") : formatDistance(result.distance_km),
        ],
      });
    }
    if (reveal.date_mode) {
      valueGroups.push({
        isPerfect: isPerfectDate,
        items: [
          result.date_score === null ? "-" : String(result.date_score),
          formatMonth(result.guessed_year, result.guessed_month),
          formatMonthError(result),
        ],
      });
    }
    valueGroups.push({
      isPerfect: isPerfectRound,
      items: [String(result.round_score), String(result.total_score)],
    });

    valueGroups.forEach((group) => {
      group.items.forEach((value, index) => {
        const cell = buildCell(value);
        if (index === 0) {
          cell.classList.add("group-start");
          if (group.isPerfect) {
            cell.classList.add("is-perfect-cell");
            cell.appendChild(createPerfectBadge());
          }
        }
        row.appendChild(cell);
      });
    });

    el.revealTableBody.appendChild(row);
  });

  if (hasAnyPerfectInRound) {
    playChime();
    launchGoldConfetti();
  }
}

function renderRevealMap(reveal) {
  el.revealMapShell.classList.toggle("hidden", !reveal.location_mode);
  el.revealMapHead.classList.toggle("hidden", !reveal.location_mode);
  if (!reveal.location_mode) {
    return;
  }

  ensureRevealMap();

  state.revealLayers.forEach((layer) => state.revealMap.removeLayer(layer));
  state.revealLayers = [];

  if (reveal.actual_latitude === null || reveal.actual_longitude === null) {
    return;
  }

  const actual = L.latLng(reveal.actual_latitude, reveal.actual_longitude);
  const actualMarker = L.marker(actual, {
    icon: createPinIcon("\u2605", ACTUAL_COLOR),
    zIndexOffset: 1000,
  })
    .addTo(state.revealMap)
    .bindPopup(t("reveal.popup_actual"));
  state.revealLayers.push(actualMarker);

  const points = [actual];
  reveal.results.forEach((result) => {
    if (result.guessed_latitude === null || result.guessed_longitude === null) {
      return;
    }
    const color = playerColor(result.player_name);
    const guessed = L.latLng(result.guessed_latitude, result.guessed_longitude);
    const marker = L.marker(guessed, { icon: createPinIcon(playerInitial(result.player_name), color) })
      .addTo(state.revealMap)
      .bindPopup(t("reveal.popup_guess", result.player_name, formatDistance(result.distance_km)));
    const line = L.polyline([guessed, actual], { color, weight: 2, dashArray: "8, 10" }).addTo(state.revealMap);

    state.revealLayers.push(marker, line);
    points.push(guessed);
  });

  if (points.length > 1) {
    state.revealMap.fitBounds(L.latLngBounds(points).pad(0.3));
  } else {
    state.revealMap.setView(actual, 4);
  }
}

async function handleNextRound() {
  if (state.matchFinished) {
    await showMatchSummary();
    return;
  }
  showCard(el.gameCard);
  await loadQuestion();
}

/* ------------------------------------------------------- match conclusion */

async function showMatchSummary() {
  const summary = await api(`/api/match/${encodeURIComponent(state.matchId)}/summary`);
  showCard(el.summaryCard);
  playVictoryFanfare();

  el.summaryWinner.textContent =
    summary.winners.length > 1
      ? t("summary.tie", summary.winners.join(" & "))
      : t("summary.winner", summary.winners[0]);

  const modes = [];
  if (summary.location_mode) {
    modes.push(t("summary.mode_location"));
  }
  if (summary.date_mode) {
    modes.push(t("summary.mode_date"));
  }
  el.summaryMeta.textContent = t(
    "summary.meta",
    summary.rounds_played,
    modes.join(" + "),
    summary.library_name,
    summary.album_name
  );

  const columns = [t("summary.col_rank"), t("summary.col_player")];
  if (summary.location_mode) {
    columns.push(t("summary.col_location"));
  }
  if (summary.date_mode) {
    columns.push(t("summary.col_date"));
  }
  columns.push(t("summary.col_total"), t("summary.col_accuracy"));

  const headRow = document.createElement("tr");
  columns.forEach((label) => headRow.appendChild(buildCell(label, true)));
  el.summaryTableHead.replaceChildren(headRow);

  el.summaryTableBody.replaceChildren();
  summary.players.forEach((player) => {
    const row = document.createElement("tr");
    row.classList.toggle("is-winner", player.is_winner);

    row.appendChild(buildCell(String(player.rank)));
    row.appendChild(buildCell(playerNameCell(player.player_name)));

    if (summary.location_mode) {
      row.appendChild(buildCell(String(player.location_score ?? 0)));
    }
    if (summary.date_mode) {
      row.appendChild(buildCell(String(player.date_score ?? 0)));
    }
    row.appendChild(buildCell(`${player.total_score}/${player.max_possible_score}`));
    row.appendChild(buildCell(String(player.accuracy_pct)));

    el.summaryTableBody.appendChild(row);
  });

  el.leaderboardCard.classList.remove("hidden");
  await loadLeaderboard();
}

function returnToSetup() {
  state.matchId = null;
  state.currentQuestion = null;
  state.matchFinished = false;
  state.playedAssetIds = [];
  resetTimerBar();
  showCard(el.setupCard);
  el.leaderboardCard.classList.remove("hidden");
}

function handleAbandonGame(action) {
  const label = action === "restart" ? t("game.abandon_restart") : t("game.abandon_exit");
  if (!confirm(t("game.abandon_confirm", label))) {
    return;
  }
  clearTimer();
  if (action === "restart") {
    restartSameGame().catch((err) => showAlert(err.message));
  } else {
    returnToSetup();
  }
}

async function restartSameGame() {
  const config = state.lastMatchConfig;
  if (!config) {
    returnToSetup();
    return;
  }

  state.matchId = null;
  state.currentQuestion = null;
  state.matchFinished = false;
  state.playedAssetIds = [];
  resetTimerBar();

  const response = await api("/api/game/setup", {
    method: "POST",
    body: JSON.stringify(config),
  });

  state.matchId = response.match_id;
  state.players = response.players;
  el.leaderboardCard.classList.add("hidden");
  showCard(el.gameCard);
  await loadQuestion();
}

/* ------------------------------------------------------------ leaderboard */

/**
 * Build query params from the current setup form selections and fetch
 * leaderboard entries filtered to that exact game configuration.
 */
function setupFilterParams() {
  const albumId = el.album.value || null;
  const albumText = albumId ? el.album.options[el.album.selectedIndex].text : "-";
  const params = new URLSearchParams({
    rounds: el.roundCount.value,
    round_length: el.roundLength.value,
    location_mode: String(el.goalLocation.checked),
    date_mode: String(el.goalDate.checked),
    library: el.library.value,
    album: albumText,
  });
  return params;
}

async function loadLeaderboard() {
  const params = setupFilterParams();
  const raw = await api(`/api/leaderboard?${params}`);
  // Compute accuracy_pct client-side so it can be sorted and displayed.
  state.leaderboardRows = raw.map((row) => ({
    ...row,
    accuracy_pct: row.max_possible_score > 0
      ? Math.round(row.total_score / row.max_possible_score * 100)
      : 0,
  }));
  renderLeaderboard();
}

function renderLeaderboard() {
  const { key, asc } = state.leaderboardSort;
  const rows = [...state.leaderboardRows].sort((a, b) => {
    const av = a[key];
    const bv = b[key];

    if (typeof av === "number" && typeof bv === "number") {
      return asc ? av - bv : bv - av;
    }
    return asc ? String(av).localeCompare(String(bv)) : String(bv).localeCompare(String(av));
  });

  el.leaderboardBody.replaceChildren();
  rows.forEach((row) => {
    const tr = document.createElement("tr");
    [
      new Date(row.played_at).toLocaleString(state.language),
      row.player_name,
      `${row.accuracy_pct}%`,
      `${row.total_score}/${row.max_possible_score}`,
    ].forEach((value) => tr.appendChild(buildCell(value)));
    el.leaderboardBody.appendChild(tr);
  });

  renderSortIndicators();
}

function renderSortIndicators() {
  const { key, asc } = state.leaderboardSort;
  el.leaderboardHead.querySelectorAll("th[data-sort]").forEach((th) => {
    const arrow = th.querySelector(".sort-arrow");
    const isActive = th.getAttribute("data-sort") === key;
    if (arrow) {
      arrow.textContent = isActive ? (asc ? "\u25B2" : "\u25BC") : "";
    }
    th.setAttribute("aria-sort", isActive ? (asc ? "ascending" : "descending") : "none");
  });
}

function handleSortClick(event) {
  const th = event.target.closest("th[data-sort]");
  if (!th) {
    return;
  }

  const key = th.getAttribute("data-sort");
  if (state.leaderboardSort.key === key) {
    state.leaderboardSort.asc = !state.leaderboardSort.asc;
  } else {
    state.leaderboardSort.key = key;
    state.leaderboardSort.asc = true;
  }
  renderLeaderboard();
}

/* ----------------------------------------------------------------- events */

el.setupForm.addEventListener("submit", (event) => {
  startMatch(event).catch((err) => showAlert(err.message));
});

el.library.addEventListener("change", () => {
  initAlbums(el.library.value)
    .then(() => loadLeaderboard())
    .catch((err) => showAlert(err.message));
});

el.album.addEventListener("change", () => {
  loadLeaderboard().catch((err) => console.warn("Leaderboard refresh failed:", err));
});

el.dateGuessYear.addEventListener("change", () => renderMonthOptions(true));
bindSelectWheelScroll(el.dateGuessYear);
bindSelectWheelScroll(el.dateGuessMonth, true);

// Setup form dropdowns
bindSelectWheelScroll(el.roundCount);
bindSelectWheelScroll(el.roundLength);
bindSelectWheelScroll(el.library);
bindSelectWheelScroll(el.album);

if (el.audioToggleBtn) {
  el.audioToggleBtn.addEventListener("click", toggleAudio);
}

if (el.mediaSkipBtn) {
  el.mediaSkipBtn.addEventListener("click", () => {
    submitAnswer(true).catch((err) => showAlert(err.message));
  });
}

el.readyBtn.addEventListener("click", () => {
  if (!state.currentQuestion) {
    return;
  }
  el.passOverlay.classList.add("hidden");
  el.quizImage.src = state.currentQuestion.media_url;
  el.quizImage.classList.remove("hidden");
  el.mediaPlaceholder.classList.add("hidden");
  if (state.currentQuestion.location_mode) {
    ensureGuessMap();
  }
  startTimer(state.currentQuestion.round_length);
});

el.submitAnswer.addEventListener("click", () => {
  submitAnswer(state.timedOut).catch((err) => showAlert(err.message));
});

el.nextRound.addEventListener("click", () => {
  handleNextRound().catch((err) => showAlert(err.message));
});

el.newMatch.addEventListener("click", returnToSetup);

el.gameRestartBtn.addEventListener("click", () => handleAbandonGame("restart"));
el.gameExitBtn.addEventListener("click", () => handleAbandonGame("exit"));
el.revealRestartBtn.addEventListener("click", () => handleAbandonGame("restart"));
el.revealExitBtn.addEventListener("click", () => handleAbandonGame("exit"));

el.quizImageFullscreen.addEventListener("click", () => toggleMapFullscreen(el.mediaFrame));
el.guessMapFullscreen.addEventListener("click", () => toggleMapFullscreen(el.guessMapShell));
el.revealMapFullscreen.addEventListener("click", () => toggleMapFullscreen(el.revealMapShell));

document.addEventListener("fullscreenchange", () => {
  syncFullscreenButtons();

  // Leaflet needs to re-measure after the container resizes.
  [state.guessMap, state.revealMap].forEach((map) => {
    if (map) {
      setTimeout(() => map.invalidateSize(), 120);
    }
  });
});

// Setup form controls — reload leaderboard whenever any setting changes.
[
  el.roundCount,
  el.roundLength,
  el.goalLocation,
  el.goalDate,
].forEach((control) => {
  control.addEventListener("change", () => {
    loadLeaderboard().catch((err) => console.warn("Leaderboard refresh failed:", err));
  });
});

el.refreshLeaderboard.addEventListener("click", () => {
  loadLeaderboard().catch((err) => showAlert(err.message));
});

el.leaderboardHead.addEventListener("click", handleSortClick);

if (el.audioToggleBtn) {
  el.audioToggleBtn.addEventListener("click", (e) => {
    e.preventDefault();
    toggleAudio();
  });
}
updateAudioUi();

/* Enter or Space key triggers the primary action of whatever screen is showing. */

function activeActionButton() {
  if (!el.passOverlay.classList.contains("hidden")) {
    return el.readyBtn;
  }
  if (!el.gameCard.classList.contains("hidden")) {
    if (!el.guessingUi.classList.contains("hidden")) {
      return el.submitAnswer;
    }
    if (!el.revealUi.classList.contains("hidden")) {
      return el.nextRound;
    }
  }
  return null;
}

document.addEventListener("keydown", (event) => {
  if ((event.key !== "Enter" && event.key !== " ") || event.isComposing) {
    return;
  }
  if (event.ctrlKey || event.altKey || event.metaKey || event.shiftKey) {
    return;
  }

  const target = event.target;
  if (
    target instanceof HTMLButtonElement ||
    target instanceof HTMLInputElement ||
    target instanceof HTMLSelectElement ||
    target instanceof HTMLTextAreaElement
  ) {
    return;
  }
  if (target instanceof HTMLElement && target.closest("#setup-card")) {
    return;
  }

  const button = activeActionButton();
  if (!button || button.disabled) {
    return;
  }
  event.preventDefault();
  button.click();
});

window.addEventListener("beforeunload", (event) => {
  if (state.matchId && !state.matchFinished) {
    event.preventDefault();
  }
});

(async function bootstrap() {
  initDateDropdowns();
  syncFullscreenButtons();
  updateAudioUi();

  const startupErrors = [];
  const rememberStartupError = (scope, err) => {
    const message = err instanceof Error ? err.message : String(err);
    startupErrors.push(`${scope}: ${message}`);
    console.error(`Startup error (${scope})`, err);
  };

  // UI config and libraries must complete before the leaderboard so that the
  // setup form values (library, album) are populated when we build filter params.
  await Promise.all([
    initUiConfig().catch((err) => rememberStartupError("UI config", err)),
    initLibraries().catch((err) => rememberStartupError("Library setup", err)),
  ]);

  await loadLeaderboard().catch((err) => rememberStartupError("Leaderboard", err));

  if (startupErrors.length > 0) {
    const details = startupErrors.map((err) => translateError(err)).join("\n");
    showAlert(t("setup.startup_error", details));
  }
})();

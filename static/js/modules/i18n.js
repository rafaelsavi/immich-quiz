import { state } from "./state.js";

export const TRANSLATIONS = {
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
      `Rounds: ${rounds}\nGuess Mode: ${modes}\nLibrary: ${library} / ${album}`,
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
    "fmt.perfect_count": (n) => `\u{1F525}\u00D7${n}`,
    // Podium & Awards
    "summary.podium_score": (pts) => `${pts} pts`,
    "award.sniper": "\u{1F3AF} Sniper",
    "award.sniper_desc": (n) => `Most perfect location guesses (${n})`,
    "award.time_traveler": "\u23F3 Time Traveler",
    "award.time_traveler_desc": (n) => `Most perfect date guesses (${n})`,
    "award.speed_demon": "\u26A1 Speed Demon",
    "award.speed_demon_desc": (n) => `Most fast rounds (${n})`,
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
      `Rodadas: ${rounds}\nAdivinhação: ${modes}\nBiblioteca: ${library} / ${album}`,
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
    "fmt.perfect_count": (n) => `\u{1F525}\u00D7${n}`,
    // Podium & Awards
    "summary.podium_score": (pts) => `${pts} pts`,
    "award.sniper": "\u{1F3AF} Atirador de Élite",
    "award.sniper_desc": (n) => `Maior número de palpites perfeitos de localização (${n})`,
    "award.time_traveler": "\u23F3 Viajante do Tempo",
    "award.time_traveler_desc": (n) => `Maior número de palpites perfeitos de data (${n})`,
    "award.speed_demon": "\u26A1 Relâmpago",
    "award.speed_demon_desc": (n) => `Maior número de rodadas rápidas (${n})`,
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
export function t(key, ...args) {
  const lang = state ? state.language || "EN" : "EN";
  const dict = TRANSLATIONS[lang] || TRANSLATIONS.EN;
  const entry = key in dict ? dict[key] : TRANSLATIONS.EN[key];
  if (typeof entry === "function") {
    return entry(...args);
  }
  return entry !== undefined ? entry : key;
}

export function translateError(msg) {
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

export function showAlert(msg) {
  if (!msg) return;
  alert(translateError(msg));
}

/**
 * Apply translations to all [data-i18n] elements in the DOM.
 * Elements with a sort arrow child keep the arrow intact.
 */
export function applyLanguage() {
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

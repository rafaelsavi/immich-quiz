import { state, el } from "./state.js";

export const TRANSLATIONS = {
  EN: {
    "setup.heading": "Game Setup",
    "setup.players_label": "Players (comma separated)",
    "setup.rounds_label": "Rounds",
    "setup.round_length_label": "Round Length",
    "setup.round_30s": "30s",
    "setup.round_1m": "1 min",
    "setup.round_2m": "2 min",
    "setup.round_5m": "5 min",
    "setup.round_unlimited": "Unlimited",
    "setup.game_mode_label": "Game Mode",
    "setup.game_settings_label": "Guessing mode",
    "mode.pinpoint": "Pinpoint",
    "mode.pinpoint_desc": "One photo per turn. Pinpoint its location and date as precise as you can.",
    "mode.album_shuffle": "Album Shuffle",
    "mode.album_shuffle_desc": "Match 3 photos to map pins & order chronologically.",
    "setup.goal_location": "Location",
    "mode.goal_location_desc": "Pinpoint where the photo was taken on an interactive world map.",
    "setup.goal_date": "Date",
    "mode.goal_date_desc": "Guess the month and year when the photo was captured.",
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
    "game.help_btn": "Help",
    "game.shuffle_newest": "Newest",
    "game.shuffle_oldest": "Oldest",
    "game.shuffle_info_banner": (count) =>
      `⏳ Arrange photos from <strong>newest (#1)</strong> down to <strong>oldest (#${count})</strong>`,
    "game.shuffle_help_intro": "Use this guide whenever you want a quick reminder of the round rules.",
    "game.shuffle_help_location_title": "Location guessing",
    "game.shuffle_help_location_item1": "Choose a photo card first.",
    "game.shuffle_help_location_item2": "Then click the map pin where you think that photo was taken.",
    "game.shuffle_help_location_item3": "The selected photo card and the highlighted pin both stand out so you can track your choices.",
    "game.shuffle_help_location_item4": "You can change a pin assignment anytime by picking a different pin.",
    "game.shuffle_help_date_title": "Date guessing",
    "game.shuffle_help_date_item1": "Arrange the photo cards from newest to oldest.",
    "game.shuffle_help_date_item2": "Use the ▲ and ▼ buttons to move a card up or down in the timeline.",
    "game.shuffle_help_date_item3": "The banner shows the target order as newest (#1) down to oldest (#3).",
    "game.shuffle_help_fallback": "Choose the mode you want to play and use the controls on screen to complete the round.",
    "game.shuffle_help_footer": "When you are finished, press Submit to lock in your answers.",
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
    "reveal.col_pins_correct": "Pins Correct",
    "reveal.col_order_correct": "Order Correct",
    "reveal.photo_breakdown_title": "Photo Breakdown",
    "reveal.col_photo": "Photo",
    "reveal.col_true_values": "True Values",
    "reveal.col_pin_guess": "Pin Guess",
    "reveal.col_rank_guess": "Rank Guess",
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
    "fmt.year": "year",
    "fmt.years": "years",
    "fmt.mon": "mon",
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
    // Map theme layers
    "map.layer_streets": "Streets",
    "map.layer_satellite": "Satellite",
    "map.layer_control_title": "Layers",
    "game.fullscreen_map_title": "Toggle fullscreen map",
    "game.fullscreen_image_title": "Toggle fullscreen image",
    "game.view_fullscreen_photo": "View fullscreen photo",
    "game.close_btn": "Close",
    "game.fullscreen_photo_alt": "Fullscreen photo",
    // Summary Journey & Memory Cards
    "summary.journey_map_heading": "World Journey Map",
    "summary.polaroids_heading": "Match Memory Cards",
    "summary.share_btn": "Share Match",
    "summary.share_copied": "Match summary copied to clipboard!",
    "summary.journey_round": (n) => `Round ${n}`,
    "audio.enabled": "Sound Effects: Enabled",
    "audio.muted": "Sound Effects: Muted",
    "audio.toggle_title": "Toggle Sound Effects",
    "lang.title": "Language: English",
    "lang.toggle_title": "Switch Language",
    "game.shuffle_help_title": "Album Shuffle Help",
  },
  PT: {
    "setup.heading": "Configuração do Jogo",
    "setup.players_label": "Jogadores (separados por vírgula)",
    "setup.rounds_label": "Rodadas",
    "setup.round_length_label": "Duração da Rodada",
    "setup.round_30s": "30s",
    "setup.round_1m": "1 min",
    "setup.round_2m": "2 min",
    "setup.round_5m": "5 min",
    "setup.round_unlimited": "Ilimitado",
    "setup.game_mode_label": "Modo de Jogo",
    "setup.game_settings_label": "Modo de adivinhação",
    "mode.pinpoint": "Mira Certa",
    "mode.pinpoint_desc": "Uma foto por rodada. Adivinhe a localização e data o mais preciso que puder.",
    "mode.album_shuffle": "Álbum Embaralhado",
    "mode.album_shuffle_desc": "Associe 3 fotos aos pinos do mapa e ordene-as cronologicamente.",
    "setup.goal_location": "Localização",
    "mode.goal_location_desc": "Descubra onde a foto foi tirada num mapa interativo.",
    "setup.goal_date": "Data",
    "mode.goal_date_desc": "Adivinhe o mês e ano em que a foto foi capturada.",
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
    "game.help_btn": "Ajuda",
    "game.shuffle_newest": "Mais recente",
    "game.shuffle_oldest": "Mais antiga",
    "game.shuffle_info_banner": (count) =>
      `⏳ Organize as fotos da <strong>mais recente (#1)</strong> até a <strong>mais antiga (#${count})</strong>`,
    "game.shuffle_help_intro": "Use este guia sempre que quiser um lembrete rápido das regras da rodada.",
    "game.shuffle_help_location_title": "Adivinhação de localização",
    "game.shuffle_help_location_item1": "Primeiro, escolha uma foto da lista.",
    "game.shuffle_help_location_item2": "Depois, clique no pino do mapa onde acha que essa foto foi tirada.",
    "game.shuffle_help_location_item3": "A foto selecionada e o pino destacado ficam em evidência para você acompanhar suas escolhas.",
    "game.shuffle_help_location_item4": "Você pode mudar a atribuição a qualquer momento escolhendo outro pino.",
    "game.shuffle_help_date_title": "Adivinhação de data",
    "game.shuffle_help_date_item1": "Organize as fotos da mais recente para a mais antiga.",
    "game.shuffle_help_date_item2": "Use os botões ▲ e ▼ para mover uma foto para cima ou para baixo na linha do tempo.",
    "game.shuffle_help_date_item3": "O banner mostra a ordem esperada da mais recente (#1) até a mais antiga (#3).",
    "game.shuffle_help_fallback": "Escolha o modo que deseja jogar e use os controles na tela para completar a rodada.",
    "game.shuffle_help_footer": "Quando terminar, pressione Enviar para confirmar suas respostas.",
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
    "reveal.col_pins_correct": "Pinos Corretos",
    "reveal.col_order_correct": "Ordem Correta",
    "reveal.photo_breakdown_title": "Detalhamento das Fotos",
    "reveal.col_photo": "Foto",
    "reveal.col_true_values": "Valores Reais",
    "reveal.col_pin_guess": "Palpite de Pino",
    "reveal.col_rank_guess": "Palpite de Ordem",
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
    "fmt.year": "ano",
    "fmt.years": "anos",
    "fmt.mon": "mes",
    "fmt.day": "dia",
    "fmt.days": "dias",
    "fmt.timed_out_tag": "TEMPO ESGOTADO",
    "fmt.perfect_count": (n) => `\u{1F525}\u00D7${n}`,
    // Podium & Awards
    "summary.podium_score": (pts) => `${pts} pts`,
    "award.sniper": "\u{1F3AF} Sniper",
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
    // Map theme layers
    "map.layer_streets": "Ruas",
    "map.layer_satellite": "Satélite",
    "map.layer_control_title": "Camadas",
    "game.fullscreen_map_title": "Alternar mapa em tela cheia",
    "game.fullscreen_image_title": "Alternar imagem em tela cheia",
    "game.view_fullscreen_photo": "Ver foto em tela cheia",
    "game.close_btn": "Fechar",
    "game.fullscreen_photo_alt": "Foto em tela cheia",
    // Summary Journey & Memory Cards
    "summary.journey_map_heading": "Mapa da Jornada Mundial",
    "summary.polaroids_heading": "Cartões de Memória da Partida",
    "summary.share_btn": "Compartilhar Partida",
    "summary.share_copied": "Resumo da partida copiado para a área de transferência!",
    "summary.journey_round": (n) => `Rodada ${n}`,
    "audio.enabled": "Efeitos de Som: Ativados",
    "audio.muted": "Efeitos de Som: Mudos",
    "audio.toggle_title": "Alternar Efeitos de Som",
    "lang.title": "Idioma: Português",
    "lang.toggle_title": "Mudar Idioma",
    "game.shuffle_help_title": "Ajuda do Álbum Embaralhado",
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

export function getInitialLanguagePreference() {
  try {
    const stored = localStorage.getItem("immich_quiz_language");
    if (stored === "PT" || stored === "EN") return stored;
  } catch (_) { }
  return null;
}

export const FLAGS = {
  EN: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 60 60" class="flag-svg" aria-hidden="true"><rect width="60" height="60" fill="#012169"/><path d="M0,0 L60,60 M60,0 L0,60" stroke="#FFFFFF" stroke-width="10"/><path d="M0,0 L60,60 M60,0 L0,60" stroke="#C8102E" stroke-width="6"/><path d="M30,0 V60 M0,30 H60" stroke="#FFFFFF" stroke-width="16"/><path d="M30,0 V60 M0,30 H60" stroke="#C8102E" stroke-width="10"/></svg>`,
  PT: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 60 60" class="flag-svg" aria-hidden="true"><rect width="60" height="60" fill="#009B3A"/><polygon points="30,10 52,30 30,50 8,30" fill="#FEDF00"/><circle cx="30" cy="30" r="12" fill="#002776"/><path d="M18,31 C23,26.5 37,26.5 42,31 C37,28 23,28 18,31 Z" fill="#FFFFFF"/></svg>`,
};

export function updateLanguageUi() {
  const lang = state ? state.language || "EN" : "EN";
  const iconEl = (el && el.langIcon) || document.getElementById("lang-icon");
  const btnEl = (el && el.langToggleBtn) || document.getElementById("lang-toggle-btn");
  if (iconEl) {
    iconEl.innerHTML = FLAGS[lang] || FLAGS.EN;
  }
  if (btnEl) {
    btnEl.setAttribute("title", t("lang.title"));
    btnEl.setAttribute("aria-label", t("lang.toggle_title"));
  }
}

export function toggleLanguage(onLanguageChanged) {
  if (!state) return;
  state.language = state.language === "PT" ? "EN" : "PT";
  try {
    localStorage.setItem("immich_quiz_language", state.language);
  } catch (_) { }
  updateLanguageUi();
  applyLanguage();
  if (typeof onLanguageChanged === "function") {
    onLanguageChanged();
  }
}

/**
 * Apply translations to all [data-i18n], [data-i18n-title], and [data-i18n-placeholder] elements in the DOM.
 * Elements with a sort arrow child keep the arrow intact.
 * Dynamic function-valued keys (expecting parameters) are skipped to avoid overwriting runtime state.
 */
export function applyLanguage() {
  document.querySelectorAll("[data-i18n]").forEach((element) => {
    const key = element.getAttribute("data-i18n");
    const lang = state ? state.language || "EN" : "EN";
    const dict = TRANSLATIONS[lang] || TRANSLATIONS.EN;
    const rawEntry = key in dict ? dict[key] : TRANSLATIONS.EN[key];

    // Skip dynamic entries whose translation value is a function needing arguments
    if (typeof rawEntry === "function") {
      return;
    }

    const translation = rawEntry !== undefined ? rawEntry : key;
    if (typeof translation !== "string") {
      return;
    }

    const arrow = element.querySelector(".sort-arrow");
    if (arrow) {
      const arrowClone = arrow.cloneNode(true);
      element.textContent = translation;
      element.appendChild(arrowClone);
    } else if (element.tagName === "INPUT" || element.tagName === "TEXTAREA") {
      element.setAttribute("placeholder", translation);
    } else if (translation.includes("<") && translation.includes(">")) {
      element.innerHTML = translation;
    } else {
      element.textContent = translation;
    }
  });

  document.querySelectorAll("[data-i18n-title]").forEach((element) => {
    const key = element.getAttribute("data-i18n-title");
    element.setAttribute("title", t(key));
  });

  document.querySelectorAll("[data-i18n-aria-label]").forEach((element) => {
    const key = element.getAttribute("data-i18n-aria-label");
    element.setAttribute("aria-label", t(key));
  });

  document.querySelectorAll("[data-i18n-alt]").forEach((element) => {
    const key = element.getAttribute("data-i18n-alt");
    element.setAttribute("alt", t(key));
  });

  document.querySelectorAll("[data-i18n-placeholder]").forEach((element) => {
    const key = element.getAttribute("data-i18n-placeholder");
    element.setAttribute("placeholder", t(key));
  });
}

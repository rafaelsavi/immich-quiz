import { state, el } from "./state.js";

export const TRANSLATIONS = {
  EN: {
    "setup.heading": "Game Setup",
    "setup.players_label": "Players",
    "setup.players_placeholder": "Add player name...",
    "setup.players_add_btn": "Add",
    "setup.players_count_solo": "1 player (Solo)",
    "setup.players_count_multi": (count) => `${count} players`,
    "setup.players_count_none": "No players",
    "setup.players_duplicate_error": "Player name already exists",
    "setup.players_empty_error": "Enter a player name",
    "setup.players_max_limit": (max) => `Maximum of ${max} players reached`,
    "setup.players_remove_title": (name) => `Remove ${name}`,
    "setup.rounds_label": "Rounds",
    "setup.round_length_label": "Round Length",
    "setup.round_30s": "30s",
    "setup.round_1m": "1 min",
    "setup.round_2m": "2 min",
    "setup.round_5m": "5 min",
    "setup.round_unlimited": "Unlimited",
    "setup.game_mode_label": "Game Mode",
    "setup.game_settings_label": "What to Guess",
    "setup.challenges_hint": "Select 1 or both",
    "mode.pinpoint": "Pinpoint",
    "mode.pinpoint_desc": "1 photo per round",
    "mode.album_shuffle": "Album Shuffle",
    "mode.album_shuffle_desc": "3 photos per round",
    "setup.goal_location": "Location",
    "mode.pinpoint.goal_location_desc": "Pin the photo location on the map",
    "mode.album_shuffle.goal_location_desc": "Match 3 photos to existing map pins",
    "setup.goal_date": "Date",
    "mode.pinpoint.goal_date_desc": "Guess the capture month and year",
    "mode.album_shuffle.goal_date_desc": "Arrange the photos in chronological order",
    "setup.library_label": "Library",
    "setup.sync_label": "Sync",
    "setup.sync_label_never_synced": "Sync library",
    "setup.syncing_label": "Syncing...",
    "setup.sync_count": (count) => `${count.toLocaleString()} synced`,
    "setup.sync_stage_initializing": "Initializing...",
    "setup.sync_stage_fetching_albums": "Fetching albums...",
    "setup.sync_stage_albums_progress": (done, total) => `Albums ${done}/${total}`,
    "setup.sync_stage_scanning_assets": "Scanning photos...",
    "setup.sync_stage_checking_updates": "Checking updates...",
    "setup.sync_stage_updating_assets": (count) => `Updating (${count.toLocaleString()})...`,
    "setup.sync_stage_pruning": "Pruning deleted...",
    "setup.sync_stage_finalizing": "Finalizing...",
    "setup.sync_title": "Sync library metadata from Immich",
    "setup.sync_title_never_synced": "Library not yet synced. Click to sync metadata from Immich.",
    "setup.sync_title_with_date": (dateStr) => `Sync library metadata from Immich\nLast sync: ${dateStr}`,
    "setup.library_not_synced_warning": "This library has not been synced yet. Click 'Sync library' above to sync metadata and start playing.",
    "setup.album_label": "Album",
    "setup.all_photos": "-",
    "setup.album_search_placeholder": "Search albums...",
    "setup.clear_search": "Clear search",
    "setup.select_all": "All",
    "setup.deselect_all": "None",
    "setup.no_albums_found": "No albums found",
    "setup.albums_selected": (count) => `${count} albums selected`,
    "setup.filters_heading": "Library Filters",
    "setup.filters_summary_default": "All media",
    "setup.filters_active_count": (count) => `${count} filter${count > 1 ? "s" : ""} active`,
    "setup.reset_filters": "Reset all filters",
    "setup.include_shared_photos": "Include shared photos",
    "setup.date_range_label": "Date Range",
    "setup.all_dates": "All Time",
    "setup.countries_label": "Countries",
    "setup.all_countries": "-",
    "setup.country_search_placeholder": "Search countries...",
    "setup.no_countries_found": "No countries found",
    "setup.countries_selected": (count) => `${count} countries selected`,
    "setup.cities_label": "Cities",
    "setup.all_cities": "-",
    "setup.city_search_placeholder": "Search cities...",
    "setup.no_cities_found": "No cities found",
    "setup.cities_selected": (count) => `${count} cities selected`,
    "setup.people_label": "People",
    "setup.all_people": "-",
    "setup.people_search_placeholder": "Search people...",
    "setup.no_people_found": "No people found",
    "setup.people_selected": (count) => `${count} people selected`,
    "setup.people_mode_any": "Any",
    "setup.people_mode_all": "All",
    "setup.filter_people": "People (Any)",
    "setup.filter_countries": "Countries",
    "setup.filter_cities": "Cities",
    "setup.start_btn": "Start Match",
    "setup.not_enough_media": (found, required) =>
      `Cannot start match: only ${found} matching ${found === 1 ? "photo" : "photos"} found, but ${required} ${required === 1 ? "is" : "are"} required.`,
    "setup.preflight_count": (n) => `${n} ${n === 1 ? "photo" : "photos"} available`,
    "setup.preflight_count_both": (n) => `${n} ${n === 1 ? "photo" : "photos"} with GPS & date`,
    "setup.preflight_count_gps": (n) => `${n} ${n === 1 ? "photo" : "photos"} with GPS`,
    "setup.preflight_count_date": (n) => `${n} ${n === 1 ? "photo" : "photos"} with date`,
    "setup.preflight_count_all": (n) => `${n} ${n === 1 ? "photo" : "photos"} available`,
    "setup.preflight_count_breakdown_tooltip": (total, gps, date, both) =>
      `Total: ${total} | GPS: ${gps} | Date: ${date} | Eligible: ${both}`,
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
      return "Date Range";
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
    "game.shuffle_newest": "Last",
    "game.shuffle_oldest": "First",
    "game.shuffle_help_location_title": "Location guessing",
    "game.shuffle_help_location_item1": "Choose a photo card first.",
    "game.shuffle_help_location_item2": "Then click the map pin where you think that photo was taken.",
    "game.shuffle_help_location_item3": "The selected photo card and the highlighted pin both stand out so you can track your choices.",
    "game.shuffle_help_date_title": "Date guessing",
    "game.shuffle_help_date_item1": "Arrange the photo cards from oldest to newest.",
    "game.shuffle_help_date_item2": "Use the ▲ and ▼ buttons to move a card up or down in the timeline.",
    "game.round_meta": (roundNum, totalRounds, playerNum, totalPlayers, playerName) =>
      `Round ${roundNum} of ${totalRounds}\nPlayer ${playerNum}: ${playerName}`,
    "game.round_label": (roundNum, totalRounds) => `Round ${roundNum} of ${totalRounds}`,
    "game.player_label": (playerNum, playerName) => (playerNum ? `Player ${playerNum}: ${playerName}` : playerName),
    "reveal.badge": "Reveal",
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
    "reveal.correct_answer": "Answer",
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
    "summary.new_match_btn": "Back to home",
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
    "leaderboard.empty": "No games recorded for this configuration yet.",
    "leaderboard.perfect_badge": "100%",
    "leaderboard.scope_all": "Full Library",
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
    "map.reset_zoom_title": "Reset map view",
    "map.focus_region_title": "Focus match region",
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
    "setup.players_label": "Jogadores",
    "setup.players_placeholder": "Adicionar jogador...",
    "setup.players_add_btn": "Adicionar",
    "setup.players_count_solo": "1 jogador (Solo)",
    "setup.players_count_multi": (count) => `${count} jogadores`,
    "setup.players_count_none": "Nenhum jogador",
    "setup.players_duplicate_error": "Nome de jogador já existe",
    "setup.players_empty_error": "Digite o nome do jogador",
    "setup.players_max_limit": (max) => `Limite máximo de ${max} jogadores atingido`,
    "setup.players_remove_title": (name) => `Remover ${name}`,
    "setup.rounds_label": "Rodadas",
    "setup.round_length_label": "Duração da Rodada",
    "setup.round_30s": "30s",
    "setup.round_1m": "1 min",
    "setup.round_2m": "2 min",
    "setup.round_5m": "5 min",
    "setup.round_unlimited": "Ilimitado",
    "setup.game_mode_label": "Modo de Jogo",
    "setup.game_settings_label": "O que Adivinhar",
    "setup.challenges_hint": "Escolha 1 ou ambos",
    "mode.pinpoint": "Mira Certa",
    "mode.pinpoint_desc": "1 foto por rodada",
    "mode.album_shuffle": "Álbum Embaralhado",
    "mode.album_shuffle_desc": "3 fotos por rodada",
    "setup.goal_location": "Localização",
    "mode.pinpoint.goal_location_desc": "Aponte no mapa onde a foto foi tirada",
    "mode.album_shuffle.goal_location_desc": "Ligue 3 fotos aos pinos existentes no mapa",
    "setup.goal_date": "Data",
    "mode.pinpoint.goal_date_desc": "Adivinhe o mês e ano da foto",
    "mode.album_shuffle.goal_date_desc": "Ordene as fotos na linha do tempo",
    "setup.library_label": "Biblioteca",
    "setup.sync_label": "Sincronizar",
    "setup.sync_label_never_synced": "Sincronizar biblioteca",
    "setup.syncing_label": "Sincronizando...",
    "setup.sync_count": (count) => `${count.toLocaleString()} sincronizadas`,
    "setup.sync_stage_initializing": "Inicializando...",
    "setup.sync_stage_fetching_albums": "Buscando álbuns...",
    "setup.sync_stage_albums_progress": (done, total) => `Álbuns ${done}/${total}`,
    "setup.sync_stage_scanning_assets": "Varrendo fotos...",
    "setup.sync_stage_checking_updates": "Buscando alterações...",
    "setup.sync_stage_updating_assets": (count) => `Atualizando (${count.toLocaleString()})...`,
    "setup.sync_stage_pruning": "Limpando removidas...",
    "setup.sync_stage_finalizing": "Finalizando...",
    "setup.sync_title": "Sincronizar metadados da biblioteca do Immich",
    "setup.sync_title_never_synced": "Biblioteca ainda não sincronizada. Clique para sincronizar metadados do Immich.",
    "setup.sync_title_with_date": (dateStr) => `Sincronizar metadados da biblioteca do Immich\nÚltima sincronização: ${dateStr}`,
    "setup.library_not_synced_warning": "Esta biblioteca ainda não foi sincronizada. Clique em 'Sincronizar biblioteca' acima para sincronizar os metadados e começar a jogar.",
    "setup.album_label": "Álbum",
    "setup.all_photos": "-",
    "setup.album_search_placeholder": "Buscar álbuns...",
    "setup.clear_search": "Limpar busca",
    "setup.select_all": "Todos",
    "setup.deselect_all": "Nenhum",
    "setup.no_albums_found": "Nenhum álbum encontrado",
    "setup.albums_selected": (count) => `${count} álbuns selecionados`,
    "setup.filters_heading": "Filtros da Biblioteca",
    "setup.filters_summary_default": "Todas as fotos",
    "setup.filters_active_count": (count) => `${count} filtro${count > 1 ? "s" : ""} ativo${count > 1 ? "s" : ""}`,
    "setup.reset_filters": "Redefinir filtros",
    "setup.include_shared_photos": "Incluir fotos compartilhadas",
    "setup.date_range_label": "Intervalo de Datas",
    "setup.all_dates": "Todo o período",
    "setup.countries_label": "Países",
    "setup.all_countries": "-",
    "setup.country_search_placeholder": "Buscar países...",
    "setup.no_countries_found": "Nenhum país encontrado",
    "setup.countries_selected": (count) => `${count} países selecionados`,
    "setup.cities_label": "Cidades",
    "setup.all_cities": "-",
    "setup.city_search_placeholder": "Buscar cidades...",
    "setup.no_cities_found": "Nenhuma cidade encontrada",
    "setup.cities_selected": (count) => `${count} cidades selecionadas`,
    "setup.people_label": "Pessoas",
    "setup.all_people": "-",
    "setup.people_search_placeholder": "Buscar pessoas...",
    "setup.no_people_found": "Nenhuma pessoa encontrada",
    "setup.people_selected": (count) => `${count} pessoas selecionadas`,
    "setup.people_mode_any": "Qualquer um",
    "setup.people_mode_all": "Juntos",
    "setup.filter_people": "Pessoas (Qualquer uma)",
    "setup.filter_countries": "Países",
    "setup.filter_cities": "Cidades",
    "setup.start_btn": "Iniciar Partida",
    "setup.not_enough_media": (found, required) =>
      `Não é possível iniciar a partida: apenas ${found} ${found === 1 ? "foto encontrada" : "fotos encontradas"}, mas ${required === 1 ? "é necessária" : "são necessárias"} ${required}.`,
    "setup.preflight_count": (n) => `${n} ${n === 1 ? "foto disponível" : "fotos disponíveis"}`,
    "setup.preflight_count_both": (n) => `${n} ${n === 1 ? "foto com GPS e data" : "fotos com GPS e data"}`,
    "setup.preflight_count_gps": (n) => `${n} ${n === 1 ? "foto com GPS" : "fotos com GPS"}`,
    "setup.preflight_count_date": (n) => `${n} ${n === 1 ? "foto com data" : "fotos com data"}`,
    "setup.preflight_count_all": (n) => `${n} ${n === 1 ? "foto disponível" : "fotos disponíveis"}`,
    "setup.preflight_count_breakdown_tooltip": (total, gps, date, both) =>
      `Total: ${total} | GPS: ${gps} | Data: ${date} | Elegíveis: ${both}`,
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
      return "Intervalo de Datas";
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
    "game.shuffle_newest": "Última",
    "game.shuffle_oldest": "Primeira",
    "game.shuffle_help_location_title": "Adivinhar a localização",
    "game.shuffle_help_location_item1": "Primeiro, escolha uma foto da lista.",
    "game.shuffle_help_location_item2": "Depois, clique no pino do mapa onde essa foto foi tirada.",
    "game.shuffle_help_location_item3": "A foto selecionada e o pino destacado ficam em evidência para você acompanhar suas escolhas.",
    "game.shuffle_help_date_title": "Adivinhar a data",
    "game.shuffle_help_date_item1": "Organize as fotos da mais antiga (acima) para a mais recente (abaixo).",
    "game.shuffle_help_date_item2": "Use os botões ▲ e ▼ para mover uma foto para cima ou para baixo.",
    "game.round_meta": (roundNum, totalRounds, playerNum, totalPlayers, playerName) =>
      `Rodada ${roundNum} de ${totalRounds}\nJogador ${playerNum}: ${playerName}`,
    "game.round_label": (roundNum, totalRounds) => `Rodada ${roundNum} de ${totalRounds}`,
    "game.player_label": (playerNum, playerName) => (playerNum ? `Jogador ${playerNum}: ${playerName}` : playerName),
    "reveal.badge": "Revelação",
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
    "reveal.correct_answer": "Resposta",
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
    "summary.new_match_btn": "Voltar para o início",
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
    "leaderboard.empty": "Nenhuma partida registrada para esta configuração ainda.",
    "leaderboard.perfect_badge": "100%",
    "leaderboard.scope_all": "Toda a Biblioteca",
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
    "map.reset_zoom_title": "Resetar visão do mapa",
    "map.focus_region_title": "Focar região da partida",
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

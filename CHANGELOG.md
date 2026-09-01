# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed

- **Fog of War Secret Leak Prevention on Active Challenges**:
  - Fixed a vulnerability in `GET /api/challenge/{capability_token}/leaderboard` within [`challenge_routes.py`](src/api/challenge_routes.py) where unauthenticated or anonymous requests without an `X-Player-Token` on active challenges bypassed Fog of War and received full round guesses and true photo coordinates.
  - Applied `history_max_round = -1` for unauthenticated callers on active matches, strictly concealing secret photo locations and player guesses while maintaining overall player progress in `leaderboard` for the Challenges Hub standings drawer.

- **Carousel Date Chip Label Correction**:
  - Corrected the date comparison chip label in [`summary.js`](static/js/modules/challenge/summary.js) to use `t("challenge.true_date")` ("Actual Date" / "Data Real") instead of erroneously calling `t("challenge.true_location")` ("True Location" / "Localização Real").

- **Round Reveal State Synchronization**:
  - Assigned `state.lastReveal = formattedReveal` in [`reveal.js`](static/js/modules/challenge/reveal.js) during personal round review, ensuring photo inconsistency reporting (`#reveal-report-btn`) and global state listeners receive consistent payload references across both local and challenge modes.

- **Challenge Invite Screen Availability for All Finishers**:
  - Fixed an issue where the `challenge-invite` intermission screen was skipped for second and subsequent finishers due to an auto-transition check (`finishedCount >= 2`) running on the first polling tick.
  - Removed the premature auto-transition bypass in `startFinisherPolling()` within [`challenge.js`](static/js/modules/challenge.js), allowing all players who complete the final round to view the challenge invite screen, copy the share link, show the QR code, observe live finisher tally updates ("You + X friends have finished"), and advance to the Grand Reveal when they click "See Results".

- **Challenges Hub Standings Drawer Rank Column**:
  - Fixed a bug where `.col-rank` in `.standings-table-wrap` always displayed `"unknown"` instead of player rankings due to erroneously calling geographic formatter `formatPlace()` instead of a rank formatter.
  - Implemented and exported `formatRank(rank, options)` in [`formatters.js`](static/js/modules/formatters.js) with medals for top 3 (`🥇 1`, `🥈 2`, `🥉 3`) and plain numbers for remaining places.
  - Applied `.col-rank` and table header classes to `<th>` elements and ensured `white-space: nowrap;` and `vertical-align: middle;` in [`challenge.css`](static/css/components/challenge.css).

### Changed

- **Challenge Card Header Containment and Share Icon Button Simplification**:
  - Enforced strict horizontal containment for `.card-header-actions` (the Share and Deactivate buttons) inside `.card-header-row` via `flex-wrap: nowrap;`, `align-items: flex-start;`, and `flex-shrink: 0;` in [`challenge.css`](static/css/components/challenge.css).
  - Added `overflow-wrap: break-word;` and `word-break: break-word;` to `.detailed-challenge-title` to prevent long challenge titles from pushing header actions out of bounds.
  - Simplified `.btn-share-challenge-hub` in [`challenges.js`](static/js/modules/screens/challenges.js) to display only the share SVG icon symbol in all viewports, removing `.btn-share-text` while maintaining full accessibility via `aria-label` and `title`.
  - Styled `.btn-share-challenge-hub` uniformly as a 34x34px square icon button across all screen sizes and container query breakpoints.

- **Architecture Refactoring: Challenge Mode Modularization, Screens Organization & Shared Utilities**:
  - Decomposed the 1,598-line `challenge.js` monolith into a cohesive sub-package under [`static/js/modules/challenge/`](static/js/modules/challenge/):
    - `session.js`: Centralized challenge reactive state, session storage keys, reset routine, and Leaflet map lifecycle management.
    - `landing.js`: Landing screen, resume detection, new player join form, error screens, and dynamic language switcher refresh.
    - `game.js`: Challenge question loading, active game mode mounting, countdown timer coordination, and answer submission.
    - `reveal.js`: Round personal reveal, 3-second social polling, and dynamic opponent pin drop animations.
    - `intermission.js`: Post-round-N "Invite Friends" intermission screen, SVG QR code generation, 1-click URL copy, and live finisher polling.
    - `summary.js`: Grand Reveal summary screen, 3D podium, awards, scatter-map carousel, and chronological journey map.
    - `index.js`: Unified facade assembling all submodules into the singleton `challenge` interface.
    - Fully migrated all consumers to import directly from `static/js/modules/challenge/index.js` and removed legacy `static/js/modules/challenge.js`.
  - Relocated `challenges_page.js` to [`static/js/modules/screens/challenges.js`](static/js/modules/screens/challenges.js) to establish architectural parity across all primary screen lifecycle controllers (`setup.js`, `game.js`, `reveal.js`, `summary.js`, `challenges.js`), migrated all consumers, and removed legacy `static/js/modules/challenges_page.js`.
  - Cleaned up legacy re-exports across modules (`openPhotoLightbox` in `album_shuffle.js`, `updateSubmitState` in `screens/game.js`, and legacy state getters/setters in `challenge/index.js`).
  - Extracted shared modal photo lightbox into [`static/js/modules/components/lightbox.js`](static/js/modules/components/lightbox.js) with click-outside and Escape key dismissal, eliminating duplicate modal creation between Album Shuffle mode and summary polaroids.
  - Extracted shared `formatRelativeTime(diffMs, isPast)` helper into [`formatters.js`](static/js/modules/formatters.js), deduplicating relative time logic across screens.
  - Restructured the `tests/` directory to mirror the implementation folder hierarchy in `src/`:
    - `tests/api/`: FastAPI route tests (`test_api.py`, `test_challenge_api.py`, `test_filters_api.py`).
    - `tests/app_logging/`: Observability and logging tests (`test_logging.py`).
    - `tests/game/`: Question candidate selection and candidate diversity tests (`test_diversity.py`).
    - `tests/immich/`: Immich client adapter tests (`test_immich_client.py`).
    - `tests/storage/`: Storage subsystem tests (`test_challenge_storage.py`, `test_leaderboard.py`, `test_metadata_storage.py`).
    - `tests/frontend/`: Frontend regression, component, and DOM interaction tests (`test_frontend_regressions.py`, `test_multi_select.py`, `test_player_input.py`, `test_range_slider.py`).
    - Root `tests/`: Domain unit tests (`test_config.py`, `test_models.py`, `test_scoring.py`, `test_adaptive_scoring.py`, `test_i18n.py`, `test_version.py`).

- **Standardized and Reusable Leaderboard & Standings Elements**:
  - Centralized rank formatting and badges into [`formatters.js`](static/js/modules/formatters.js) via `createRankBadge()`, `formatRankBadge()`, and `formatRank()`, eliminating duplicate imperative badge creation across [`leaderboard.js`](static/js/modules/leaderboard.js), [`summary/table.js`](static/js/modules/summary/table.js), [`challenge.js`](static/js/modules/challenge.js), and [`challenges_page.js`](static/js/modules/challenges_page.js).
  - Centralized rounds completion pills into `formatRoundsBadge()` with unified `.challenge-rounds-pill` (`finished` vs `in-progress`), deprecating divergent `.progress-badge` markup.
  - Centralized player cell rendering into `formatPlayerCellHtml()` and `playerNameCell()`, ensuring consistent `.player-cell`, `.legend-badge`, `.player-name-text`, and `.winner-crown` across DOM-based and HTML template-based standings tables.
  - Standardized standings table structure with `.standings-table`, `.table-scroll`, and shared column styling (`.col-rank`, `.col-player`, `.col-rounds` / `.col-progress`, `.col-score`, `.col-acc` / `.col-accuracy`) across Grand Reveal, match summary, and Challenges Hub views.

### Added

- **Standardized Carousel Photo Layout & Mobile Optimization for Challenge Play Summary**:
  - Replaced ad-hoc dark styling on `.carousel-photo-shell` with `.media-frame` semantic class, `#eef2fb` background, `#d5dcec` border, 14px border radius, and synchronized desktop height (`var(--quiz-map-height, 420px)`) matching the scatter map and regular quiz photo view.
  - Replaced the ad-hoc emoji zoom button (`🔍`) with the standard `.map-fullscreen-btn` featuring a crisp SVG expand icon positioned at top-right for consistent user interaction.
  - Optimized the Challenge Play Summary (Grand Reveal) screen for mobile viewports (<=768px and <=480px):
    - Scaled down and word-wrapped the match title header (`.grand-reveal-header h2`) and metadata to prevent horizontal overflow and text clipping on small screens.
    - Adjusted padding and typography on `.challenge-provisional-card` and `.challenge-carousel-card`.
    - Compacted `.carousel-nav-controls` and navigation buttons (`.carousel-nav-btn`) with `width: auto`, preventing button overflow and ensuring `Round X of Y` indicator fits cleanly across narrow viewports.
    - Added `.hide-on-mobile` to `.col-accuracy` in `#grand-reveal-table` to prevent table horizontal overflow while maintaining core standings columns.
    - Structured `.summary-actions` buttons as full-width vertical stacks on phone screens for comfortable thumb reach, and added a direct `Challenges Hub` button (`#grand-reveal-hub-btn`) navigating directly to `/challenges`.

- **Interactive Share Drawer & Dynamic Results Button in Challenges Hub**:
  - Replaced redundant card copy buttons with a header **Share** button (`.btn-share-challenge-hub`) that smoothly expands a dedicated **Share Drawer** (`.challenge-hub-share-drawer`) with a dynamically rendered zero-dependency SVG QR code and a direct URL input with 1-click clipboard copy.
  - Converted the disabled "Expired" button into an active **Results** deep link button (`.btn-results-challenge`) navigating to `/play/:token/summary` when a challenge is inactive or expired, allowing instant review of match summaries and leaderboards.
  - Removed duplicate CSS button definitions and added responsive layout rules for the share drawer on mobile screens.
  - Removed redundant `.host-avatar` placeholder element and styling from challenge card subtitles, keeping player avatar badges strictly reserved for active game participants.
  - Added localized strings across [`en_US.js`](immich-quiz/static/js/modules/locales/en_US.js) and [`pt_BR.js`](immich-quiz/static/js/modules/locales/pt_BR.js).

- **Individual Participant Icon Colors for Challenge Mode**:
  - Assigned each participant starting a challenge an individual, distinct avatar icon color from a shared 16-color palette based on chronological join order (`started_at`), exactly mirroring the local game player roster assignment.
  - Added `player_color` column to `challenge_sessions` in database schema with automatic backward-compatible migration in `src/storage/leaderboard.py`.
  - Added `participants` list, `participant_index`, and `player_color` to `ChallengeDetailResponse`, `ChallengeStartResponse`, `ChallengeAnswerResponse`, `ChallengeLeaderboardEntry`, and `ChallengeRoundGuessData` in `src/models.py`.
  - Added live avatar color preview on the Challenge Landing screen with dynamic initials generation on `#player-name-input` and personalized colored resume pill.
  - Displayed assigned individual icon colors and multi-letter clash-free initials on in-game round headers, map guess markers, round reveal score table, Grand Reveal standings, carousel scatter map, and the Challenges Hub page standings drawer.

- **Home Leaderboard PlayMode Column & Challenge Results Support**:
  - Added a dedicated sortable **Mode** column to the home page leaderboard table displaying styled badges for `Local` (`👥`), `Challenge` (`🌐`), and `Room` (`⚡`) match sessions.
  - Included challenge match results seamlessly alongside local matches in global leaderboard listings.
  - Added internationalized labels and descriptions across [`en_US.js`](immich-quiz/static/js/modules/locales/en_US.js) and [`pt_BR.js`](immich-quiz/static/js/modules/locales/pt_BR.js).

- **Unified Match Meta Items in Collapsed Filters Accordion**:
  - Rendered active filter configurations as rich `.match-meta-items` chips inside the `#filters-toggle-btn` header when the Library & Photo Filters accordion is collapsed.
  - Dynamically updates filter chips in real-time as users adjust library, places, albums, people, date ranges, and shared album settings.
  - Seamlessly hides metadata chips when the accordion is expanded for full filter customization.

- **Unified Challenge Round Review Screen with Live Opponent Updates**:
  - Combined the Challenge Mode personal round review and the intermission waiting screen into a single unified round review screen based on the classical round review (`#reveal-ui`).
  - Added real-time polling during round review that dynamically drops opponent pins onto the active reveal map (`state.revealMap`) with dashed lines from the true location, pulse animations, and sound effects.
  - Dynamically updates the reveal score breakdown table with all participants who completed the round.
  - Clicking "Next Round" advances directly to the next question (`loadRound(roundIndex + 1)`) without an intermediate intermission screen.

- **World Journey Map & Polaroid Gallery for Album Shuffle Challenges**:
  - Replaced the single-target `challenge-carousel-card` (which was conceptually designed for Pinpoint mode) with the **World Journey Map** and **Match Memory Cards (Polaroid Gallery)** in Album Shuffle mode challenges.
  - Placed the Final Standings Table directly beneath the Podium/Awards, followed by the World Journey Map (with numbered pins such as `1-A`, `1-B`, etc. and spiderfy clustering) and interactive Polaroid cards with photo lightbox viewing, matching the Local Mode finish screen layout.
  - Preserved the interactive round-by-round scatter-map carousel for Pinpoint challenges.
  - Extended `ChallengeLeaderboardResponse` with `round_history` (including `batch_reveal`), `location_mode`, and `date_mode`, strictly enforcing Fog of War for unplayed rounds.
  - Enhanced [`renderJourneyMap`](immich-quiz/static/js/modules/maps.js) and [`renderPolaroidGallery`](immich-quiz/static/js/modules/summary/polaroids.js) to support custom containers and lifecycle management.

- **Challenge Carousel Photo Integration & Target-Aware Review**:
  - Added round photo preview (`/api/media/{asset_id}`) inside `.challenge-carousel-card` alongside the scatter map, complete with lightbox zoom viewing on click.
  - Made carousel layout target-aware: in Date-Only mode (`location_mode: false`), hides the scatter map and displays a centered photo card with date chips; in Location-Only mode (`date_mode: false`), hides the date comparison chips.

- **Conditional Podium Completion Requirement Notice**:
  - Made the `🏁 Podium results only count for players who completed all rounds.` notice conditional on `#grand-reveal-podium` and `.mini-podium-bar`: only displayed when there are active/unfinished participants, and automatically omitted when all players have finished to keep the layout clean and compact.
  - Display "Current Leader: {player}" (or "Current Leaders: {tie}") while a challenge is still in progress, only crowning "Winner: {player}" once the challenge has concluded (expired or closed by host).
  - Filtered podium standings and winner determinations in `static/js/modules/challenge.js` and `static/js/modules/challenges_page.js` to strictly include participants who completed all rounds (`is_finished=True`).
  - Updated `src/storage/leaderboard.py` so `is_winner=True` is strictly reserved for finished participants with the best score among completed attempts.
  - Added `is_concluded` to `ChallengeLeaderboardResponse` and allowed `GET /api/challenge/{capability_token}` to return challenge metadata with `is_active=False` for concluded/expired challenges, enabling direct results viewing from landing cards.

### Fixed

- **Challenge Mode Guess Map Player Marker Initial & Color**:
  - Attached `sessionPlayerName` to `state.currentQuestion` in `challenge.js` upon question load, and added a safe fallback to `state.players[0]` in `ensureGuessMap()`, ensuring the Leaflet guess map marker correctly renders the player's initial and individual color instead of defaulting to `?` and red.

- **Eliminated N+1 Query in Challenge Standings Calculation**:
  - Batch-prefetched guess rows across all challenge participants in a single indexed query in `LeaderboardStore.get_challenge_standings`, reducing $N$ sequential SQL queries per 3-second social polling request down to a single O(1) in-memory grouping.
  - Unified challenge `total_rounds` determination in standings to consistently respect Album Shuffle batches and actual asset pool sizes.

- **Indexed Subquery Optimization for Challenge Guess & History Queries**:
  - Replaced dynamic SQL parameter list construction (`IN (?, ?, ...)`) in `get_challenge_round_guesses` and `get_challenge_round_history` with indexed SQLite subqueries (`WHERE match_id IN (SELECT match_id FROM challenge_sessions WHERE challenge_id = ?)`), avoiding SQLite parameter limits and accelerating execution.

- **Eliminated Redundant Database Query in Challenge Detail API**:
  - Removed an unused `get_challenge_participant_count` call in `GET /api/challenge/{capability_token}` that was immediately overwritten by session participant length, pruning the unneeded `LeaderboardStore` dependency from the endpoint.

- **Enhanced Clipboard Utility with Rich HTML Feedback**:
  - Added `copiedHtml` support to `copyToClipboard` in `share.js` to preserve and restore complex inner HTML structures on copy buttons.
  - Removed manual `_copyResetTimer`, `clearTimeout`, and innerHTML swapping from `admin.js`.

- **Background Tab Polling Guard in Challenge Mode**:
  - Added `document.hidden` guards to `startPolling` and `startFinisherPolling` in `challenge.js` to suspend background network polling when the user switches tabs or minimizes the window.

- **Optimized Media Proxy Asset Validation in Active Challenges**:
  - Replaced O(N×M) in-memory JSON deserialization and linear scans in `is_asset_in_active_challenge` with an indexable SQLite query using `json_each()`, eliminating high CPU and memory overhead during `/media/{asset_id}` proxy requests.

- **Race Condition Resilience in Challenge Session Creation**:
  - Handled concurrent `sqlite3.IntegrityError` in `get_or_resume_player_session` when simultaneous requests join with the same player name, gracefully catching the conflict and returning the existing session instead of throwing a 500 error.

- **Robust Clipboard Sharing & Fallback Error Handling**:
  - Extracted a unified `copyToClipboard()` utility in `summary/share.js` featuring support for modern async Clipboard API with fallback to `document.execCommand('copy')` for insecure/HTTP contexts, full error handling, and animated button feedback.
  - Replaced 4 duplicate copy implementations across `challenge.js`, `challenges_page.js`, `admin.js`, and `share.js`.

- **Deduplicated Database Row Mapping & Total Rounds Logic**:
  - Centralized repeated `challenges` table row-to-dictionary mapping into `ChallengeStore._row_to_challenge_dict`, removing 30+ lines of duplicate deserialization logic.
  - Unified mode-dependent challenge round counting into `get_challenge_total_rounds()`, eliminating 6 duplicate branches across `challenge_routes.py` and `challenge_service.py`.

- **Internationalization Fallback Helper & Error Card Resolution**:
  - Introduced `t_or()` / `tOr()` helper in both Python backend and JS frontend for clean translation lookups with fallbacks, simplifying `match_meta.js`.
  - Streamlined error card message key resolution across all locales dynamically in `challenge.js`.

- **Challenge Exit Game Button & In-Card Error Screen Consistency**:
  - Fixed an unhandled `ReferenceError: clearTimer is not defined` in [`static/js/modules/screens/setup.js`](immich-quiz/static/js/modules/screens/setup.js) when clicking Exit during challenge mode.
  - Ensured `handleAbandonGame` cleanly tears down challenge state, stops timers, clears route classes, resets game UI, and navigates back to setup lobby via `returnToSetup()`.
  - Replaced browser `alert()` popups with consistent in-card `.challenge-error` screens when challenges are stopped or expired during attempt start, round loading, or guess submissions.

- **Past Challenge Standings for Concluded & Expired Matches**:
  - Allowed `GET /api/challenge/{capability_token}/leaderboard` to return standings and rankings even when a challenge has been deactivated or expired (`include_inactive=True` in `get_challenge_by_token`), ensuring `.challenge-standings-drawer` always displays past results.
  - Automatically lifted Fog of War (`max_round_filter = None`, `is_game_over = True`) when a challenge is closed or expired, enabling complete score breakdowns and standings inspection for all past participants.
  - Cleared frontend standings drawer cache (`_cachedStandings.clear()`) on list reload and refresh to ensure newly completed rounds display immediately.

- **Challenge Error Card Dynamic Language Refresh**:
  - Fixed an issue where the `.challenge-error` screen failed to update its localized title, message, and action button when toggling language via `#lang-toggle-btn`.
  - Added `data-i18n` attributes to all translatable elements in `.challenge-error` (`challenge.error_title`, `challenge.back_home`, and error message key) so `applyLanguage()` translates them in-place.
  - Consolidated duplicate `refreshLanguage()` declarations in [`challenge.js`](immich-quiz/static/js/modules/challenge.js) into a unified handler that re-renders the error screen, landing screen, and invite counter seamlessly.

- **Round Reveal & Map Fullscreen Toggle Controls**:
  - Resolved an issue where clicking `#reveal-map-fullscreen` (and other pre-rendered `.map-fullscreen-btn` elements) failed to toggle fullscreen due to missing event listener attachments during map instantiation.
  - Updated [`ensureMapFullscreenButton`](immich-quiz/static/js/modules/maps.js) to reliably bind `onclick` handlers and disable Leaflet propagation regardless of whether the button was pre-rendered in HTML or created dynamically.
  - Added global [`initMapFullscreenControls`](immich-quiz/static/js/modules/maps.js) invoked on bootstrap to wire up all static and dynamic fullscreen buttons (`#reveal-map-fullscreen`, `#guess-map-fullscreen`, `#journey-map-fullscreen`, `#quiz-image-fullscreen`).
  - Added `fullscreenchange` and `webkitfullscreenchange` listeners to automatically synchronize button states, aria attributes, and invoke [`refitAllMaps`](immich-quiz/static/js/modules/maps.js) with container size invalidation on enter/exit.
  - Updated global `f` keyboard shortcut to properly toggle active map fullscreen across `reveal`, `guessing`, and `summary` screens.

- **Accurate Time Limit & Match Settings in Game Review Specs**:
  - Fixed an issue in [`static/js/modules/components/match_meta.js`](immich-quiz/static/js/modules/components/match_meta.js) where `round_length` in local game reviews always fell back to default (`1 min`) because match configuration properties reside inside nested `summary.config`.
  - Added fallback checks to `data.config` for `round_length`, `round_count`, `location_mode`, `date_mode`, and `game_mode`.
  - Standardized round length display values to use localized labels (e.g. `2 min`, `30s`, `Unlimited`).
  - Added regression tests in [`tests/test_frontend_regressions.py`](immich-quiz/tests/test_frontend_regressions.py) and [`tests/e2e/test_summary_and_effects.py`](immich-quiz/tests/e2e/test_summary_and_effects.py).

### Changed

- **Horizontal Match Metadata Categories with Category Tooltip**:
  - Simplified `.match-meta-cat-header` into a compact icon placed to the left of `.match-meta-items`, saving a full line of vertical space per category block across match summary, challenges hub, and challenge cards.
  - Replaced the separate `.match-meta-cat-title` text with a semantic `title` tooltip on `.match-meta-category` displaying the localized heading (e.g., *Game Setup*, *Library Filters*).
  - Maintained full responsive wrapping for `.match-meta-items` chips with flexbox alignment.

- **Preserved Full Card Contrast on Inactive & Expired Challenges**:
  - Updated `.detailed-challenge-card.card-inactive` to use standard card background (`var(--card)`) and border (`var(--border-light)`), removing the dull greyed-out appearance so past match specifications, participants, and results remain prominent and legible.

- **Standardized Challenge Standings Toggle Button & Inactive Card Contrast**:
  - Standardized `.btn-standings-toggle` label format to always display participant count uniformly (e.g. `Ver Classificação (N)` / `View Standings (N)`), resolving inconsistency where 0-participant challenges omitted the verb and count badge.
  - Aligned button typography, padding, borders (`1.5px solid var(--border)`), background (`var(--card)`), and hover animations across `.btn-standings-toggle`, `.btn-copy-challenge-link`, and `.footer-left-actions .btn-secondary`.
  - Removed root `opacity: 0.75` and `filter: grayscale(0.2)` from `.detailed-challenge-card.card-inactive`, maintaining full crisp contrast, legibility, and homogeneous styling for interactive buttons across both active and expired challenges.

- **Challenge Standings and Round Progress Clarity**:
  - Enhanced challenge standings tables (including Grand Reveal table) to explicitly show each player's round completion progress with visual status badges (e.g. `🏁 5/5` Finished vs `⏳ 2/5` In Progress).
  - Clearly separated Round Points from Total Points and added Average Points per Round to prevent players with fewer completed rounds from being misinterpreted as scoring poorly.

- **Challenge Game Summary and Review Enhancements**:
  - **Dashed Connector Lines & Star Pin**: Added dashed connector polylines linking each player's guess to the true target coordinate on the Grand Reveal scatter map, and upgraded the true answer marker to a star icon (`★`).
  - **Leaflet Reset Zoom Button Layout**: Added `.map-shell` container styling to `#scatter-map-shell` to ensure `.map-reset-zoom-btn` and Leaflet controls adhere to standard control positioning and formatting.
  - **Homogenized Summary Table Design**: Standardized the Grand Reveal standings table with `.summary-table` styling, consistent column headers, and avatar chips matching local play mode.
  - **Dedicated Standings Route (`/play/:token/summary`)**: Introduced a dedicated challenge summary route allowing direct viewing and sharing of standings and round breakdowns.
  - **Provisional Status & Conditional Podium**: Handled in-progress challenges gracefully by displaying a provisional status banner until $\ge 2$ players complete the game, unlocking the winner podium and performance awards.
  - **Fixed Duplicate Participant Count**: Corrected internationalized pluralization formatting in `grand-reveal-meta`.
  - **Challenge Invite Finisher Counter Clarity**:
    - Updated `#challenge-finisher-count` (`#finisher-count-text`) on the Challenge Invite screen to clearly present the finisher tally as "You + {count} friends have finished" (and "Você + {count} amigos concluíram").
    - Added explicit `zero`, `one`, and `other` pluralization categories across [`en_US.js`](immich-quiz/static/js/modules/locales/en_US.js) and [`pt_BR.js`](immich-quiz/static/js/modules/locales/pt_BR.js).
    - Updated [`i18n.js`](immich-quiz/static/js/modules/i18n.js) `plural` and `t` functions to support custom `forms.zero` definitions.
    - Added [`challenge.refreshLanguage()`](immich-quiz/static/js/modules/challenge.js) to dynamically update the invite counter whenever the application language is toggled.

- **Challenges Hub Total Counter Badge Placement**:
  - Relocated the challenges counter badge (`#challenges-page-total-badge`) from the page header title group into the `.challenges-toolbar` within `.challenges-filters-group`.
  - Refined `.challenges-counter-pill` layout styles (`display: inline-flex; align-items: center; white-space: nowrap;`) to seamlessly integrate with toolbar search and filter controls.

## [3.0.0] - 2026-09-01

### Fixed

- **Human-Readable People and Album Names in Match Summaries and Challenges**:
  - Resolved an issue where person IDs (UUIDs) were displayed instead of human-readable display names in match summaries.
  - Added `person_names_json` column and backward-compatible database schema migration to SQLite `matches` table.
  - Added [`MetadataStore.get_album_names`](immich-quiz/src/storage/metadata.py) to resolve album IDs to display names matching existing `get_person_names`.
  - Updated [`ChallengeService.create_challenge`](immich-quiz/src/game/challenge_service.py) to automatically resolve `album_names` and `person_names` from `MetadataStore` when challenges are configured with ID lists.
  - Updated [`LeaderboardStore.get_match_summary`](immich-quiz/src/storage/leaderboard.py) and `append_match` to preserve `person_names` and resolve fallback IDs using `MetadataStore`.
  - Added test `test_match_summary_person_and_album_names` in [`tests/test_leaderboard.py`](immich-quiz/tests/test_leaderboard.py).

- **Dynamic Language Updates for Challenges Hub List**:
  - Resolved an issue where `#challenges-hub-list` and hero statistics required a manual page reload to reflect UI language toggles.
  - Exported [`refreshChallengesPageLanguage`](immich-quiz/static/js/modules/challenges_page.js) to re-render challenge cards, match specifications, status badges, and open standings tables dynamically with active locale strings upon language changes.
  - Integrated `refreshChallengesPageLanguage()` into `refreshActiveScreenLanguage` in [`static/js/app.js`](immich-quiz/static/js/app.js).
  - Added regression test `test_challenges_hub_list_updates_language_dynamically` in [`tests/test_frontend_regressions.py`](immich-quiz/tests/test_frontend_regressions.py).

- **Clean Filter Dimensions & Game Setup via `config: MatchConfig` in Match Summary**:
  - Cleaned up [`MatchSummaryResponse`](immich-quiz/src/models.py) to encapsulate all match configuration and filter dimensions (`libraries`, `albums`, `album_names`, `people`, `person_names`, `people_mode`, `countries`, `cities`, `min_date`, `max_date`, `include_shared`, `round_count`, `round_length`, `location_mode`, `date_mode`, `game_mode`) within `config: MatchConfig`.
  - Removed duplicate, bloated top-level filter attributes from `MatchSummaryResponse`, standardizing it with `LeaderboardEntry.config`.
  - Updated [`GameService.get_match_summary`](immich-quiz/src/game/service.py) and [`LeaderboardStore.get_match_summary`](immich-quiz/src/storage/leaderboard.py) to construct and serialize the full `MatchConfig`.
  - Updated frontend summary helpers ([`static/js/modules/components/match_meta.js`](immich-quiz/static/js/modules/components/match_meta.js) and [`static/js/modules/summary/share.js`](immich-quiz/static/js/modules/summary/share.js)) to read all configuration directly from `config`.

- **Instant Header Challenges Badge Display on Startup**:
  - Configured background preloading of active challenges during application bootstrap in `static/js/app.js` (`loadChallengesList`).
  - Ensured `#header-challenges-badge` displays the active challenge count immediately upon initial homepage load without requiring a click on the navigation button.

### Changed

- **Enhanced Location, Date Decay, & Map Auto-Zoom Calibration Logging**:
  - Upgraded logging in [`calculate_location_decay`](immich-quiz/src/scoring.py) and [`calculate_date_decay`](immich-quiz/src/scoring.py) to explicitly detail all inputs (pool size, valid coordinate/date counts, geographic/temporal spans, percentile ranges, divisor ratios, and clamp boundaries) and final outputs (scaled decay, clamped decay, or fallback defaults).
  - Added calibration logging to [`calculate_match_bounds`](immich-quiz/src/game/selector.py) detailing pool size, valid coordinate counts, diagonal span, latitude/longitude bounds & spans, max span thresholds, and resulting calibrated `MapBounds` (or global fallback reasons).
  - Promoted fallback and edge case logs from `DEBUG` to `INFO` level to ensure scoring parameters and reasoning are always visible in standard server logs.
  - Added unit tests in `tests/test_adaptive_scoring.py` and `tests/test_api.py` verifying log formatting and input/output reporting.

- **Disallowed Match Restarting in Non-Local Games**:
  - Enforced single-attempt integrity for challenge matches by hiding and disallowing `#game-restart-btn` (`el.gameRestartBtn`) and `#reveal-restart-btn` (`el.revealRestartBtn`) during non-local / challenge mode gameplay.
  - Updated Album Shuffle reveal screen (`album_shuffle.js`) to omit the dynamically created restart button when playing in challenge mode.
  - Added guards across `restartSameGame()`, `handleAbandonGame("restart")`, and `confirmAbandonMatch("restart")` in `setup.js` and `common.js` to ensure challenge matches cannot be inadvertently restarted or wiped.
  - Added guards to restart button click handlers and keyboard shortcuts (`onRestartMatch`) in `app.js`.
  - Added regression test `test_challenge_mode_disallows_game_restart` in `tests/test_frontend_regressions.py`.

- **Streamlined Challenges Hub UI & Minimalistic Refresh Buttons**:
  - Replaced bulky `#challenges-hero-stats` (4 metric cards) with a compact active/total summary counter badge (`#challenges-page-total-badge`) in the Challenges Hub header.
  - Resolved filter pill line wrapping in `.challenges-toolbar` by enforcing `white-space: nowrap;` and shortening tab labels to `Expired` / `Expirados`.
  - Removed redundant "Back to Lobby" button (`#challenges-page-back-btn`) in favor of standard header navigation.
  - Restructured detailed challenge cards (`detailed-challenge-card`): removed `.detailed-card-top-bar`, placed `.challenge-status-pill` cleanly before `.detailed-challenge-title`, and aligned `.card-time-status` next to `.created-date` with bullet separation.
  - Converted `#challenges-page-refresh-btn` and `#refresh-leaderboard` into sleek, minimalist icon-only buttons (`.btn-icon-action`) with accessible tooltips and rotation micro-animations.

- **Challenge Landing Screen Dual-Path Clarification**:
  - Redesigned the challenge entry screen when an active local session is detected into two clearly distinct, well-labeled choice paths:
    - **Path 1 (Resume Active Game)**: Highlighted option card with `Active Session` badge, live pulse indicator, player identity pill (e.g. `👤 Rafa`), and a direct `▶ Continue as [Player]` action button.
    - **Visual Divider**: Center-aligned `— OR —` separator line distinguishing ongoing vs. new attempts.
    - **Path 2 (Play as Someone Else)**: Secondary option card with clean player name input (not pre-filled with active session name) and a `Start Challenge →` action button to easily join with another name or switch players.
  - Preserved a streamlined single-card join form with autofocus for first-time players.
  - Added localized strings for path headers, badges, button text, and descriptions across English and Portuguese (`en-US.json`, `pt-BR.json`, `en_US.js`, `pt_BR.js`).
  - Added CSS classes for `.challenge-paths-container`, `.challenge-path-card`, `.challenge-path-resume`, `.challenge-path-new`, `.challenge-path-badge`, `.challenge-player-pill`, and `.challenge-paths-divider` in `challenge.css`.

- **Unified 2-Category Match Specifications & Library Filters**:
  - Replaced ambiguous, unlabelled chips with a standardized, structured 2-category match specification component (`static/js/modules/components/match_meta.js`):
    - **Category 1 (Game Setup)**: Explicit indicators for Game Mode (`📍 Mode: Pinpoint` / `🔀 Mode: Album Shuffle`), Targets / Guessing Mode (`🎯 Targets: Location & Date` / `🎯 Targets: Pins & Timeline`), Rounds (`🔢 Rounds: 10`), and Round Time Limit (`⏱️ Time Limit: 1m`).
    - **Category 2 (Library Filters)**: Dedicated explicit badges for each active filter dimension: Libraries (`📚 Library: Rafael`), Places (`🌍 Places: Argentina`), Albums (`📁 Albums: Vacations`), People (`👤 People: Ana, Leo`), Dates (`🗓️ Dates: 2018 → 2024`), Shared Content (`🔗 Shared: Included`), or Full Library (`🌐 Scope: Full Library`).
  - Standardized this 2-category layout across the Match Results Summary (`#summary-meta` in `summary/table.js`), Challenges Hub cards (`detailed-challenge-card` in `challenges_page.js`), and Challenge Landing screens (`challenge-landing-specs` in `challenge.js`).
  - Added bilingual translations and CSS styling (`.match-meta-section`, `.match-meta-category`, `.match-meta-item`, `.match-meta-item-label`, `.match-meta-item-val`) across `leaderboard.css`, `challenge.css`, `en_US.js`, `pt_BR.js`, `en-US.json`, and `pt-BR.json`.

### Added

- **Home Navigation Button in Header Controls**:
  - Added a dedicated Home navigation button (`#home-nav-btn`) in `.header-controls` beside `#challenges-nav-btn` for direct, 1-click returning to the Game Lobby from any view.
  - Added synchronized active route state styling (`.home-nav-btn.active`) highlighting the home icon when viewing the lobby and toggling active states when visiting Challenges Hub.
  - Added bilingual localization strings (`nav.home_title`) across English (`en_US.js`) and Brazilian Portuguese (`pt_BR.js`).

- **QR Code Sharing for Multiplayer Challenges**:
  - Added a dedicated QR code action button (`#challenge-qr-btn`) with `.qr-btn-text` beside the `"Copy Link"` button (`#challenge-copy-link-btn`, `.copy-btn-text`) in the Prepare Game challenge share box.
  - Implemented a zero-dependency, client-side QR Code vector SVG generator ES module (`static/js/modules/components/qrcode.js`) supporting automatic version selection, Reed-Solomon error correction, and crisp retina rendering without external network requests.
  - Added smooth animated QR code card preview (`#challenge-qr-container`) with mobile camera scan hints to easily scan and join challenge games from phones or tablets.
  - Added QR code sharing button and preview to the post-game `"Invite Friends"` intermission screen in `challenge.js`.
  - Added bilingual translations for `challenge.qr_code`, `challenge.qr_code_title`, and `challenge.scan_qr_hint` across English and Portuguese.

- **Unified Prepare Game Modal & Home Launch Flow**:
  - Replaced the separate "Start Match" and "Create challenge link" buttons with a single primary `"Prepare game"` button on the lobby setup card.
  - Streamlined the lobby setup card into a clean game rule & photo scope configurator by moving local player list collection into the `"Local Match"` tab of the Prepare Game modal.
  - Added a 2-tab Prepare Game modal (`#prepare-game-modal`):
    - **Local Match Tab**: Houses player chips management (`PlayerInput`), configured match summary chips (mode, rounds, time, active filters scope), live preflight asset verification status, and the `"Start Match"` action button.
    - **Challenge Link Tab**: Collects host/creator name, automatically generated smart challenge title based on active configuration (e.g. `Rio de Janeiro • Pinpoint (5R)` or `Album Shuffle • 5 Rounds`), expiration duration, photo filter scope summary, and `"Generate Challenge Link"` action button with 1-click URL sharing.
  - Added full bilingual translations for `setup.prepare_game_btn`, `setup.prepare_modal_title`, `setup.tab_local`, `setup.tab_challenge`, `setup.local_match_desc`, `setup.challenge_match_desc`, and `setup.configured_match_summary` across `en-US.json`, `pt-BR.json`, `en_US.js`, and `pt_BR.js`.
  - Removed `#challenges-page-create-btn` from Challenges Hub header and wired empty-state creation to open the Prepare Game modal directly on the Challenge tab.
  - Created `ChallengeStore` in `src/storage/challenge.py` for creating deterministic challenge match seeds, managing capability tokens, and tracking persistent player attempts.
  - Added `challenge_sessions` table and unique constraint `UNIQUE(challenge_id, player_name)` to `LEADERBOARD_SCHEMA_SQL` in `src/storage/leaderboard.py` for persistent session resumption across server restarts.
  - Implemented Fog of War query methods in `LeaderboardStore` (`get_challenge_standings`, `get_challenge_round_guesses`, `get_challenge_participant_count`, `record_challenge_round_guess`, `finalize_challenge_player_match`).
  - Added challenge request and response Pydantic models in `src/models.py` (`ChallengeCreateRequest`, `ChallengeCreateResponse`, `ChallengeDetailResponse`, `ChallengeStartRequest`, `ChallengeStartResponse`, `ChallengeQuestionResponse`, `ChallengeAnswerRequest`, `ChallengeAnswerResponse`, `ChallengeLeaderboardEntry`, `ChallengeLeaderboardResponse`, `ChallengeRoundGuessData`).
  - Created comprehensive test suite in `tests/test_challenge_storage.py`.
- **Challenge Mode REST API & Service Engine (Stage 1 Phase 2)**:
  - Implemented `ChallengeService` in `src/game/challenge_service.py` to orchestrate deterministic asset selection with diversity sampling, pre-computation of frozen scoring decay constants (`location_decay_km`, `date_decay_days`, `map_bounds`), Album Shuffle batch pre-assignment and randomized pin assignment, secure question delivery, server-side timer grace window enforcement (`round_length + 5s`), answer scoring with frozen decay values, session advancement, and match finalization.
  - Created `/api/challenge/*` route family in `src/api/challenge_routes.py`:
    - `POST /api/challenge/create` for creating challenge match seeds with capability URLs.
    - `GET /api/challenge/{capability_token}` for public challenge details and participant counts.
    - `POST /api/challenge/{capability_token}/start` for starting or resuming deduplicated player sessions.
    - `GET /api/challenge/{capability_token}/question/{round_index}` for security-enforced sequential question retrieval.
    - `POST /api/challenge/{capability_token}/answer` for scoring answers and returning immediate personal reveals.
    - `GET /api/challenge/{capability_token}/leaderboard` for Fog-of-War filtered standings and opponent guesses.
  - Added `get_asset_answer(asset_id)` to `MetadataStore` in `src/storage/metadata.py` to query ground truth coordinates and capture timestamps for scoring.
  - Updated media proxy route in `src/api/routes.py` to authorize photo access for assets in active challenges via `ChallengeStore.is_asset_in_active_challenge`.
- **Challenge Mode Frontend Experience & Social Intermission (Stage 1 Phase 3)**:
  - Created `challenge.js` frontend controller module in `static/js/modules/challenge.js` managing full async/hybrid multiplayer lifecycle:
    - Landing and player entry screen with capability URL validation and local session resume detection (`localStorage`).
    - Round-by-round **Personal Reveal** after each answer, showing player's score, animated map distance line, and location details immediately before intermission.
    - **Social Intermission Screen with 3-second polling** and animated Leaflet friend pin drops, live pulse indicator, and standings sidebar.
    - **"Invite Friends" screen** after final round with 1-click URL copy, live finisher counter, and auto-transition to Grand Reveal at $\ge 2$ finishers.
    - **Grand Reveal Summary Screen** featuring victory fanfare, confetti, podium, performance awards (🎯 Sniper, ⏳ Time Traveler, ⚡ Speed Demon), full standings table, and interactive round breakdown carousel with multi-pin scatter map and date guess comparison.
    - Support for both **Pinpoint** and **Album Shuffle** game modes.
  - Added dedicated modular styling in `static/css/components/challenge.css` with responsive mobile layout and dark glassmorphic cards.
  - Integrated `RouteType.CHALLENGE` deep link handler (`/play/{token}`) in `static/js/app.js` and `static/js/modules/router.js`.
- **Challenge Mode Admin Creator UI & Security Hardening (Stage 1 Phase 4)**:
  - Built `admin.js` frontend module in `static/js/modules/admin.js` providing the Challenge Creator & Management modal:
    - Host creation controls with game mode selection (📍 Pinpoint vs 🔀 Album Shuffle), customizable expiration windows (`1h`, `6h`, `24h`, `48h`, `7d`, `never`), round counts (`3`, `5`, `10`, `20`), and round lengths (`30s`, `1m`, `2m`, `5m`, `unlimited`).
    - Live preflight check validation (`POST /api/game/preflight`) calculating candidate asset count against requirements in real time.
    - One-click "Copy Link" capability URL sharing with clipboard toast notifications.
    - "Active Challenges" management tab for viewing active links, participant counts, creation/expiration dates, and revoking challenges via instant deactivation.
  - Added backend challenge management routes in `src/api/challenge_routes.py`:
    - `GET /api/challenge/list` for listing created challenges with participant totals.
    - `POST /api/challenge/{challenge_id}/deactivate` for admin revocation of active challenge seeds.
  - Hardened Docker Compose deployment (`docker-compose.example.yml`) with non-root user execution (`user: "1000:1000"`), isolated bridge network (`quiz-net`), and security best practice guidelines.
  - Added bilingual localization for all `admin.*` keys across English (`en_US.js`) and Brazilian Portuguese (`pt_BR.js`).
- **Dedicated Challenges Hub Page & Header Navigation**:
  - Created dedicated Challenges Page (`/challenges`, `RouteType.CHALLENGES`) providing comprehensive discovery and tracking for multiplayer challenge links.
  - Added navigation button (`#challenges-nav-btn`) in `.header-controls` with live active challenge count badge (`#header-challenges-badge`) for seamless 1-click toggling between Game Lobby and Challenges Hub.
  - Built `challenges_page.js` frontend module in `static/js/modules/challenges_page.js` featuring:
    - **Hero Metrics Bar**: Live counters for active challenges, total players across all challenges, total challenges created, and most popular challenge.
    - **Search & Filters Toolbar**: Live keyword search (title, host, albums, people, locations), status tabs (All, Active, Expired / Inactive), game mode dropdown (All, Pinpoint, Album Shuffle), and sorting options (Newest, Most Players, Ending Soonest, Title A-Z).
    - **Rich Challenge Cards**: Host avatar & name, live expiration countdowns with pulsing active status, game mode badges, photo scope tag cloud (libraries, albums, people, date ranges, geographic filters, shared media status), 1-click URL sharing, and direct Play CTA.
    - **Expandable Standings Drawer**: Inline top 3 podium preview (1st, 2nd, 3rd with medals and accuracy %) and complete rankings table with individual scores, accuracy %, completed rounds progress, and total time.
  - Enriched `ChallengeListItem` in `src/models.py` and `src/api/challenge_routes.py` with `libraries`, `location_mode`, `date_mode`, `filter_tooltip`, and complete `config` dictionary.
  - Added comprehensive responsive styling in `static/css/components/challenge.css` and `static/css/components/buttons.css`.
  - Added full bilingual localization for all `challenges_page.*` and `nav.*` keys across English (`en_US.js`) and Brazilian Portuguese (`pt_BR.js`).

### Fixed

- **Challenge Mode Answer Submission Routing & 422 Error**:
  - Resolved conflicting event handler execution where global `#submit-answer` and `#next-round` event listeners in `app.js` and keyboard shortcuts (`Enter`) concurrently invoked local match methods (`game.js:submitAnswer` / `reveal.js:handleNextRound`) while in Challenge mode.
  - Added delegation guards in `app.js`, `screens/game.js`, and `screens/reveal.js` checking `challenge.isActive()` to correctly route guess submissions and round advances through `challenge.submitAnswer()` and `challenge.handleNextRound()`.
  - Fixed `api()` in `static/js/modules/api.js` to preserve `Content-Type: application/json` headers when custom request headers (such as `X-Player-Token`) are supplied.
  - Added lifecycle safeguards in `static/js/modules/maps.js` and `static/js/modules/modes/pinpoint.js` (`ensureGuessMap`, `ensureRevealMap`, `fitMapToBounds`, `spawnPinPulseEffect`, `unmount`) to prevent detached Leaflet container positioning errors (`_leaflet_pos`) across round transitions.
  - Added automated end-to-end Playwright test suite in `tests/e2e/test_challenge_gameplay.py` covering multi-round challenge gameplay, button and shortcut answer submissions, personal reveals, social intermission, and Grand Reveal transitions.

- **Leaderboard Scope Pill Lifecycle & Empty State**:
  - Added `.leaderboard-scope-pill:empty { display: none; }` in `static/css/components/leaderboard.css` to prevent rendering a blank badge placeholder before content is rendered.
  - Added immediate synchronous call to `updateLeaderboardScope()` in `refreshActiveScreenLanguage()` (`static/js/app.js`) to guarantee scope text is populated on initial bootstrap and localized when changing languages.
- **Challenge UI & Admin Localization**:
  - Corrected plural translation lookup for `challenge.participants` in `static/js/modules/admin.js` to ensure participant counters render localized plural strings properly instead of raw key names.
- **Intermission Standings Timing**:
  - Deduplicated elapsed time calculations across multi-photo rounds in `LeaderboardStore.get_challenge_standings` to prevent Album Shuffle intermission Fog of War standings from tripling player time metrics.
  - De-duplicated round iterations in `challenge.js` `buildPlayerStats` so Album Shuffle rounds increment the fast-round counter once per round index.
- **Challenge API Bounds Validation**:
  - Added boundary validation for `round_index` in `ChallengeService._score_pinpoint` to return HTTP 400 Bad Request instead of unhandled server index errors on invalid indices.

### Removed

- **Redundant Modal Preflight Status**:
  - Removed `#challenge-preflight-status` and `#local-preflight-status` elements from the Prepare Game modal along with redundant modal-level preflight polling in `static/js/modules/admin.js` and associated CSS styles in `static/css/components/modals.css`.

## [2.5.0] - 2026-08-29

### Added

- **Photo Inconsistency Reporting & Source Links**:
  - Added "Report Issue" button (🚩) and accessible modal dialog to the round reveal screen across both Pinpoint and Album Shuffle game modes.
  - Three-field issue reporting: Inaccurate GPS / Map Location (`flag_coordinates`), Wrong Date / EXIF Timestamp (`flag_date`), and Free-text notes (`other`).
  - Active reporting player name attribution (`reported_by`) captured and persisted with each flagged asset.
  - Direct Immich Web link (`https://<immich-url>/photos/{asset_id}`) within the modal for quick source metadata editing in Immich.
  - SQLite persistent storage (`flagged_assets` table) tracking reported asset IDs, issue types, notes, reporting player, and timestamps with automatic migration.
  - REST API endpoints for flagging (`POST /api/assets/flag`), listing (`GET /api/assets/flagged`), and unflagging (`DELETE /api/assets/flagged/{asset_id}`).
  - Backend configuration safeguard `EXCLUDE_FLAGGED_ASSETS=true` (default: `True`) to automatically filter reported photos out of candidate pools without needing intrusive UI toggles.
  - Playwright E2E test suite for the reporting workflow (`tests/e2e/test_report_issue.py`).
  - Full bilingual localization (English & Brazilian Portuguese) for report modal and notification strings.

## [2.4.1] - 2026-08-28

### Added

- **Playwright End-to-End (E2E) Test Suite**:
  - Live FastAPI test harness with simulated Immich client (`tests/e2e/conftest.py`).
  - Pinpoint map pin placement, distance lines, and round reveal tests (`test_pinpoint_gameplay.py`).
  - Dual-handle timeline range slider and single-year/month date guessing tests (`test_date_selection.py`).
  - Album Shuffle photo card reordering and multi-pin (A, B, C) placement tests (`test_album_shuffle_gameplay.py`).
  - Client routing, deep links, reload recovery, and guard tests (`test_routing_and_recovery.py`).
  - Score rollup animations, podium rendering, and polaroid gallery tests (`test_summary_and_effects.py`).
  - Playwright Chromium installation in CI workflow and pre-push git hook.
- **Match Place Metadata Persistence**: Stored `actual_city` and `actual_country` in SQLite `match_round_guesses` for replayable match summaries.

### Changed

- **Unified Place Formatting**: Standardized polaroid cards and journey maps to display `City, Country` across all game modes.

### Fixed

- **Audio & Haptic Autoplay Restrictions**: Added user-activation guards to prevent browser console warnings on page reload.
- **Victory Fanfare Trigger**: Scoped fanfare audio to active match completions, suppressing it during page refreshes and direct permalinks.
- **Frontend Controller Cleanup**: Added missing module imports, fixed button click bindings with safe null checks, and resolved DOM ID collision in Album Shuffle reveal tables.
- **UI Config Endpoint**: Aligned frontend configuration request with `/api/ui-config`.
- **Game Mode Initialization**: Fixed mode selector settings initialization on startup.

## [2.4.0] - 2026-08-28

### Added

- **Client-Side History API Router & Deep Links**:
  - Direct URL routing for `/` (Lobby), `/game/{match_id}` (Active Match), and `/game/{match_id}/summary` (Replay & Podium).
  - In-game session recovery from `sessionStorage` on page reload.
  - Dedicated "Match Ended" screen with quick links when visiting expired matches.
  - In-game navigation guards to prevent accidental tab closing or abandonment.
  - Shareable match summary permalink URLs.
- **Permanent SQLite Match History**: Replaced in-memory match summaries with persistent SQLite storage (`LeaderboardStore`) and authorized photo proxy access (`/api/media/{asset_id}`) for replays.
- **FastAPI SPA Catch-All Route**: Added `/{full_path:path}` fallback handler and updated PWA service worker caching for seamless offline routing.

### Changed

- **Modular Screen Controllers**: Refactored monolithic `app.js` into focused controllers under `static/js/modules/screens/` (`setup.js`, `game.js`, `reveal.js`, `summary.js`, `common.js`).
- **Datetime Safety**: Added safe ISO datetime parsers in SQLite storage and a typed `.seconds` helper on `RoundLength`.

### Fixed

- **Pass-and-Play Timer**: Fixed round timer ticking during the "Pass Device" screen and prior to clicking "I'm ready".

## [2.3.0] - 2026-08-28

### Added

- **Album Shuffle Partial Credit Scoring**:
  - Nearby map pin credit based on distance error instead of all-or-nothing points.
  - Close timeline date credit for near-accurate chronological order.
  - Batch-adaptive scoring scaling adjusted to the photo pool's geographic and temporal span.
  - Detailed per-photo distance errors and day differences in round telemetry.
- **Structured Console & Container Logging**: Color-coded, timestamped console logs with match tracing, request ID tracking, and automatic Immich API credential masking.
- **Smooth 60 FPS Countdown Timer**: Fluid progress bar driven by `requestAnimationFrame`, dynamic color transitions (Teal → Amber → Crimson), rising-pitch audio ticks (440 Hz → 880 Hz), and smart `M:SS` / `Xs` time formatting.

### Changed

- **Location Sensitivity Tuning**: Adjusted base decay scaling (5 km base for neighborhoods, up to 200 km for worldwide albums).
- **Audio Synchronization**: Centralized score rollup sound effects across multiplayer reveals.
- **Scoring Engine**: Unified adaptive decay functions across all game modes.

### Removed

- **Redundant Config**: Removed unused `LOCATION_MAX_SPAN_KM` environment setting.

### Fixed

- **Double-Click Protection**: Prevented duplicate match creation when rapidly clicking "Start Match".
- **Score Rollup Animation**: Fixed score counter speed inconsistencies on reveal and summary screens.

## [2.2.0] - 2026-08-25

### Added

- **Progressive Web App (PWA)**: Installable standalone web app with service worker offline shell caching, in-app install prompt, and high-DPI icon suite.
- **Mobile Ergonomics & Haptics**: Added iOS notch/safe-area insets (`env(safe-area-inset-*)`) and Web Vibration API haptics for timer countdowns, buzzer, pin drops, and victory fanfares.
- **Wall-Clock Timer Synchronization**: Real-time timer calculation against target timestamps (`Date.now()`) with Page Visibility API sync to prevent timer freezing in background tabs.
- **Navigation Protection**: Added confirmation dialogs for browser back navigation and tab closure during active rounds.
- **Internationalization (i18n)**: Migrated to BCP-47 language tags (`en-US`, `pt-BR`), externalized JSON catalogs, RFC 9110 `Accept-Language` negotiation, and Unicode CLDR plural/date formatting.

## [2.1.0] - 2026-08-24

### Added

- **Dynamic Scoring Decay**: Replaced static global decay constants with per-match calculations tailored to the geographic and temporal distribution of candidate photos.

### Changed

- **Smart Map Initial Zoom**: Increased maximum initial zoom to level 13 for tighter framing on neighborhood and city-scale albums.

### Removed

- **Static Decay Configuration**: Removed `LOCATION_SCORE_DECAY_KM` and `DATE_SCORE_DECAY_DAYS` environment variables in favor of dynamic per-match calculations.

## [2.0.0] - 2026-08-17

### Added

- **Local Metadata Storage & Sync Engine**: SQLite-backed caching layer (`data/metadata.db`) for assets, albums, recognized faces, and geographic places with automatic background sync.
- **Library & Photo Filters Accordion**: Collapsible filter section for Libraries, Multi-Album selection, Date Range, Geography (Countries & Cities), and People (ANY/ALL matching).
- **Dynamic Date Range Slider**: Dual-handle interactive range slider with year-month resolution and live timeline boundary discovery.
- **Photo Play Tracking & Diversity**: Tracks photo play frequencies in SQLite (`times_played`) to prioritize unplayed photos, paired with spatial (≥100m) and temporal (≥60s) downsampling.
- **Relational Match & Multiplayer Schema**: 4-table SQLite schema (`matches`, `match_entries`, `match_round_guesses`, `challenges`) under `data/leaderboard.db` tracking detailed round telemetry and fair tiebreaking.
- **Live Preflight Counter**: Real-time counter showing eligible photo counts and filter breakdown tooltips before starting a match.
- **Interactive Player Input**: Chip-based player input with avatar badges, player colors, duplicate detection, and keyboard navigation.
- **Tag Filtering**: Global `TAG_WHITELIST` and `TAG_BLACKLIST` support for server-level asset eligibility filtering.

### Changed

- **Setup Screen Hierarchy**: Streamlined match setup flow into logical sections: Players, Dataset Filters, Game Mode, and Guessing Settings.
- **Leaderboard API**: Enhanced `/api/leaderboard` with filtering by `player_name`, `is_custom_filtered`, and `limit`.

### Removed

- **Legacy CSV Storage**: Removed CSV leaderboard persistence in favor of SQLite databases (`metadata.db` and `leaderboard.db`).
- **Redundant Settings**: Removed static photo diversity and map zoom environment variables in favor of automatic heuristics.

## [1.2.1] - 2026-08-15

### Fixed

- **Shared Album Filtering**: Ensured user-owned shared albums remain visible when `INCLUDE_SHARED_ALBUMS=false`.

## [1.2.0] - 2026-08-13

### Added

- **Smart Map Zoom (Pinpoint Mode)**: Geographic auto-framing based on match photo distribution, eliminating repetitive manual map zooming.
- **Regional Focus Button**: Added a Leaflet toolbar control to snap back to the album's regional view at any time.
- **Map Canvas Zoom Bounds Guard**: Computed dynamic `minZoom` to prevent tiles from rendering smaller than the container canvas.

### Changed

- **Setup Layout**: Reorganized match setup into Player Settings, Library Settings, and Game Settings.

## [1.1.0] - 2026-08-13

### Added

- **Searchable Multi-Select Album Selector**: Added real-time text searching of albums, multi-album selection, and batch Select All / Deselect All actions.

## [1.0.2] - 2026-08-12

### Fixed

- **Round Reset**: Fixed game state reset when restarting rounds.

### Added

- **Map Reset Control**: Added button to reset map view to default zoom.

### Changed

- **Map Creation**: Unified Leaflet map initialization and Immich query controls.

## [1.0.1] - 2026-08-12

### Fixed

- **Design Polish**: Standardized UI element styling and layout consistency.

## [1.0.0] - 2026-08-08

### Added

- **Album Shuffle Game Mode**: Hybrid batch mode where players match 3 photos to map pins (`A`, `B`, `C`) and sort them chronologically (`1st`, `2nd`, `3rd`).
- **On-the-Fly Language Toggle**: Dynamic switching between English (EN) and Brazilian Portuguese (PT) without resetting active game state.
- **Extended Round Lengths**: Added `2m` and `5m` timers for batch photo sessions.
- **Mobile Responsive Layout**: Optimized UI dimensions and touch controls for narrow screens.
- **Audio Playground**: Web Audio API oscilloscope and sound effect testing suite (`/audio-test`).
- **Frontend Regression Tests**: Automated structural tests for HTML markup, IDs, and script exports.

### Changed

- **Modular Code Architecture**: Modularized frontend scripts (`modules/modes/`) and stylesheets (`static/css/`).

### Fixed

- **Date Error Rounding**: Fixed precision rounding for date error deltas.
- **Multiplayer Tie-Breaking**: Improved leaderboard tiebreaker resolution.

## [0.3.0] - 2026-08-08

### Added

- **UI Animations**: Visual transitions for modals, round reveals, and buttons.
- **i18n Expansion**: Expanded translations across all screens.

### Changed

- **Podium Awards**: Scoped podium avatars exclusively to multiplayer matches.
- **Map Rendering**: Improved Leaflet auto-centering and viewport responsiveness.

## [0.2.0] - 2026-08-08

### Added

- **Audio Playground**: Audition and test Web Audio sound effects.

## [0.1.2] - 2026-08-08

### Added

- **Developer Tooling**: Added VS Code task definitions, git pre-push hooks, and GitHub Actions release workflows.
- **URL Normalization**: Automatically appends `/api` to server endpoints if omitted.

### Changed

- **Album Ordering**: Sorted album dropdown items alphabetically.

### Fixed

- **Audio Preference Persistence**: Fixed localStorage audio setting persistence.

## [0.1.0] - 2026-08-08

### Added

- Initial release of **Immich Quiz**.
- Single photo **Pinpoint** mode (Location and Date guessing).
- Immich API integration with asset preflight validation.
- Pass-and-play local multiplayer with performance awards (**Sniper**, **Time Traveler**, **Speed Demon**).
- Web Audio sound engine.

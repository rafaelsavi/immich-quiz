# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **Consolidated Challenge Replays in Catalog (`/replays`, `/api/matches`)**:
  - Grouped multi-player challenge sessions into a single match item in `list_matches_history` by `COALESCE(challenge_id, match_id)` so individual players' plays do not spawn disjoint replay entries.
  - Aggregated participating players, top scores, and calculated overall winners across all challenge sessions.
  - Displayed challenge name, creator, and player roster chips on challenge replay cards in the catalog.
  - Set `replay_match_id` in challenge results to `challenge_id` so completion links lead directly to the consolidated replay.
- **Accurate Media Filters in Match Replay Meta (`match-meta-items`)**:
  - Populated parent `matches` table rows in `record_challenge_round_guess` from `challenges.config_json` and `challenges.libraries_json` instead of default `NULL`s.
  - Added database migration to backfill `challenge_id` and filter columns from `challenges` to any existing challenge match rows.
  - Enhanced `get_match_replay` and `get_match_summary` to read authoritative filters and metadata directly from `challenges.config_json` and `challenges.libraries_json`, preventing incorrect fallback to "Full Library".
- **Challenge Name & Creator in Replay Header (`.replay-header-main`)**:
  - Rendered the challenge title in `#replay-heading-title` and host badge/name in `#replay-match-title` within `.replay-header-main`.
  - Preserved full dynamic re-translation on language toggle via `refreshReplayPageLanguage`.

### Changed

- **Replay Photo Date Display**:
  - Formatted `#replay-photo-date` using `formatDate` without clock time (e.g. `Sep 13, 2026`) matching other photo date captions in the application.
- **Rebranded Batch Photo Game Mode to "Unshuffle"**:
  - Renamed the English user-facing game mode title from "Album Shuffle" to "Unshuffle" across home setup screen, challenges hub filter, replay catalog filters, and help modals.
  - Synchronized English locale resources (`locales/en-US.json`, `static/js/modules/locales/en_US.js`) and Portuguese help titles (`locales/pt-BR.json`, `static/js/modules/locales/pt_BR.js`).

### Removed

- **Match Replay Catalog Card Metadata Row (`.replay-item-meta`)**:
  - Removed redundant `.replay-item-meta` container, round count pill (`.replay-meta-pill`), accuracy pill (`.replay-acc-pill`), and associated styles from `replay.js` and `replay.css` to streamline replay catalog cards.
- **Grand Reveal Redundant Action Buttons (`#grand-reveal-home-btn`, `#grand-reveal-hub-btn`)**:
  - Removed duplicate Home and Challenges Hub buttons and their associated event listeners from the challenge grand reveal summary screen, leaving the focused Watch Replay action and standard navigation.

### Fixed

- **Replay Media Frame Vertical Letterboxing on Narrow Screens (`.replay-media-frame`)**:
  - Removed unwanted vertical letterbox space above and below photos on narrow screens ($\le 768\text{px}$) by setting `height: auto; min-height: 0;` on `.replay-media-frame` and fluid `width: 100%; height: auto; max-height: var(--quiz-image-max-height, 320px);` on `.replay-photo-img`.
  - Preserved full-height centering in `:fullscreen` view across desktop and mobile.

- **Challenges Hub Toolbar Responsive Layout (`.challenges-toolbar`)**:
  - Resolved multi-column wrapping bug on viewports $\le 900\text{px}$ (and split screens) where `.hub-toolbar` retained `flex-wrap: wrap` in column direction and search box expanded vertically to 100% height, pushing filter pills and selects off-screen to the right.
  - Standardized `.hub-search-box` height to `var(--toolbar-control-height, 38px)` (`flex: none; width: 100%`) under column layouts and set `flex-wrap: nowrap`.
  - Added dedicated $\le 1100\text{px}$ breakpoint for `.challenges-toolbar` to ensure full-width search on row 1 and balanced multi-control filters on row 2.
  - Added full-width fluid segmented pills on mobile ($\le 480\text{px}$) with equal-width tab buttons (`flex: 1 1 0`).
  - Proactively purged dead legacy media query rules for `.challenges-toolbar` from `challenge.css`.

- **Table Mobile Optimization & Replay Icon Unification**:
  - Replaced verbose "Watch replay" text across table rows with a compact clapper icon button (`🎬`) in both the Homepage Leaderboard (`#leaderboard-table`) and Player Profile Recent Matches (`.recent-matches-table`), preserving accessible `aria-label` and localized `title` tooltips.
  - Omitted `.playmode-badge .playmode-label` on mobile screens (`<= 768px`) in the Homepage Leaderboard, showing only the mode icon (`🎯` / `🔀`) and allocating freed horizontal space to player names and accuracy columns to eliminate awkward text wrapping and date line breaks.
  - Reallocated mobile column widths for `#leaderboard-table` (Date 23%, Mode 11%, Player 37%, Accuracy 18%, Replay 11%) and `.recent-matches-table` (Date 24%, Mode 11%, Rank 11%, Score 16%, Accuracy 24%, Replay 14%).
  - Wrapped `.recent-matches-table` in `.table-scroll` container for resilient horizontal overflow protection on narrow devices.
  - Styled compact `.replay-action-btn` (32x28px rounded icon button) with elevation hover effects and dark theme contrast.
- **Match Replay Header & Stepper Optimization**:
  - Simplified the guesses & scoreboard section header to a unified "Player Guesses" heading (`replay.player_guess_heading`), removing the redundant `replay.scoreboard` key across all 4 locale files and ensuring clean real-time dynamic language toggling.
  - Relocated `.replay-header-controls` (round stepper) from the top-level match metadata header into `.replay-content-grid`, placing it directly above the active round's photo and map stage where its state changes apply.
  - Removed redundant round count from `#replay-match-title` subtitle, relying on the unified `match-meta-section` specification panel.
  - Removed redundant `#replay-badge-row` (`#replay-mode-badge` and `#replay-type-badge`) from `.replay-header-main`.
  - Cleaned up dead CSS rules and media queries for `.replay-badge-row` and `.replay-title-row` in `replay.css`.
- **Dedicated Players and Replays Pages (`/players`, `/replays`)**:
  - Split the Statistics Hub into two distinct, dedicated pages: **Players** (`/players`) and **Match Replays** (`/replays`), removing the segmented `#stats-tabs-bar`.
  - Added dedicated top header navigation buttons: Players (`👥`, `#stats-nav-btn`) and Replays (`🎬`, `#replays-nav-btn`) with active route indicators.
  - Extracted the Match Replays catalog from `#stats-page-card` into its own dedicated `#replays-page-card`.
  - Updated player profile routes to `/players/:playerName` with return navigation to `/players`.
  - Updated SPA catch-all and direct deep-linking on FastAPI backend to serve `/players` and `/replays`.
- **Header Settings Dropdown Menu (`#settings-dropdown`)**:
  - Consolidated standalone language (`#lang-toggle-btn`) and audio (`#audio-toggle-btn`) header buttons into a space-saving gear settings icon (`⚙️`, `#settings-toggle-btn`).
  - Hovering over or clicking the gear reveals an animated dropdown menu containing the language flag button and sound effects toggle.
  - Supports hover bridge on desktop, touch/click toggle on mobile, outside click dismissal, and Escape key dismissal.
  - Fully localized in English (`en-US`) and Portuguese (`pt-BR`).
- **Detailed Challenge Card Replay Link (`.btn-replay-challenge`)**:
  - Added direct match replay link button (`🎬 Replay`) to `.footer-left-actions` of `.detailed-challenge-card` in the Challenges Hub (`#challenges-page-card`).
  - Enables single-click navigation to `/game/:challengeId/replay` directly from any challenge card on both desktop and mobile viewports.
  - Fully localized in English (`en-US`) and Portuguese (`pt-BR`).
- **Standardized Hub Page Headers (`.hub-page-header`)**:
  - Unified header layout, title hierarchy, subtitle typography, section badges, and card container padding across **Challenges** (`/challenges`), **Match Replays** (`/replays`), **Player Directory & Statistics** (`/players`), and **Reported Photos Moderation** (`/reported`).
  - Standardized card container padding to `1.5rem` (24px) with responsive `1rem` on mobile, eliminating cramped card margins on Players, Replays, and Moderation.
  - Standardized headings (`h2`) to `1.85rem` bold with `line-height: 1.2` and unified `0.35rem` vertical gap above descriptions, eliminating the unstyled browser default and `0.8rem` margin gap on Players and Replays.
  - Standardized section badges with cohesive soft pill styling (`0.75rem` uppercase, `0.24rem 0.65rem` padding, `999px` border radius) and dedicated section theme accents: Teal for Challenges (`.badge-challenges`), Indigo for Match Replays (`.badge-replays`), Purple for Players (`.badge-players`), and Rose / Crimson for Moderation (`.badge-reported`).
  - Removed outdated `border-bottom` divider line from `#challenges-page-card` to eliminate duplicate borders above the shaded `.hub-toolbar` deck.
  - Implemented full mobile responsiveness with pinned top-right refresh buttons and dark theme (`[data-theme="dark"]`) support.

### Changed

- **CSS Architecture & Bloat Cleanup**:
  - Removed obsolete `.stats-tabs-bar` and `.stats-tab-btn` rules (~120 lines of dead CSS and SVG masks) from `stats.css` following the separation of Players and Match Replays.
  - Relocated Match Replay catalog card styling (`.replay-catalog-item`, `.replay-item-header`, `.replay-player-chip`, `.replay-item-footer`, etc.) from `stats.css` into `replay.css`, restoring clean stylesheet encapsulation and reducing `stats.css` by ~40%.
  - Consolidated `.replay-back-btn` to use the standardized `.page-back-btn` from `buttons.css`.
  - Removed duplicate header rules from `reported.css` in favor of the unified `hub_header.css` system.
- **Database Schema Indexing**:
  - Added case-insensitive indices `idx_match_entries_player_nocase` and `idx_match_round_guesses_player` directly to `LEADERBOARD_SCHEMA_SQL` in `src/storage/leaderboard.py`.

### Fixed

- **Player Accuracy Tiers & Analytics Translation Fixes**:
  - Fixed unlinked translation keys and `undefined` badges on the Player Profile page (`/players/:name`):
    - Resolved `stats.tier_undefined` by correcting `tier.tier` to `tier.tier_key` in `stats.js:createTiersHtml`, mapping backend `AccuracyTierBucket` tiers (`top`, `great`, `moderate`, `low`) properly.
    - Added missing pluralization keys `stats.round_single` and `stats.rounds_plural` across all 4 locale files (`locales/en-US.json`, `locales/pt-BR.json`, `static/js/modules/locales/en_US.js`, `static/js/modules/locales/pt_BR.js`), eliminating raw translation keys.
    - Resolved `undefined` values in Location and Date accuracy highlights by mapping `PlayerAccuracyAnalytics` properties correctly: `perfect_location_rounds_count` (instead of nonexistent `perfect_location_guesses`), `exact_year_month_pct` and `perfect_date_rounds_count` (instead of nonexistent `best_date_diff_days` and `perfect_date_guesses`).
    - Fixed player KPI cards mapping `player.matches_won` (instead of nonexistent `player.wins_count`).
    - Added missing translation keys across all 4 locale files: `game.date_label`, `stats.best_date_diff`, `stats.best_match`, `stats.days_plural`, `stats.days_single`, `stats.last_played`, `stats.matches_played_count`, `stats.perfect_guesses`, `stats.podium_rate`, `stats.response_time`, `stats.round_single`, `stats.rounds_plural`, `stats.speed_and_timing`, `stats.wins_count`.
    - Maintained 100% 4-file parity across backend and frontend English and Portuguese dictionaries.
- **Client-Side Localization Sync & Counter Badges**:
  - Synchronized `summary.share_failed` into client locales (`en_US.js` and `pt_BR.js`), ensuring clipboard failure messages display properly in Portuguese.
  - Localized telemetry counter badges across Player Directory (`#stats-players-total-badge`) and Match Replays (`#stats-replays-total-badge`) using dynamic pluralized `t(...)` keys in English and Portuguese.

### Fixed

- **Player Directory & Statistics Cartesian Product Multiplication**:
  - Fixed a Cartesian product in `get_all_players_directory`, `get_player_profile`, and `get_known_player_names` where a direct `LEFT JOIN challenge_sessions cs ON e.player_name = cs.player_name` caused players who participated in multiple challenges to have their match records duplicated.
  - Resolved Pydantic `ValidationError` on `PlayerSummaryItem` where duplicated win counts caused `win_rate_pct` to exceed 100% (e.g. 120%), triggering an HTTP 500 error that manifested in the UI as "No players found".
  - Refactored the join to group `challenge_sessions` by player prior to joining, added defensive bounds clamping `[0.0, 100.0]` on `win_rate_pct` and `avg_accuracy_pct`, and updated the frontend error catch block in `stats.js` to show an actionable error state with a retry button.
- **Match Replay Catalog Card Rendering & Styling**:
  - Fixed player name extraction in the Match Replays catalog (`/replays`), which erroneously assumed player array items were objects instead of player name strings returned by `/api/matches`, causing empty player names, fallback initial `?`, and broken red avatar blocks.
  - Fixed winner identification in catalog items to compare player names against the `m.winners` list rather than `p.player_name === winnerName` (which evaluated to `undefined === undefined` and awarded crowns to every player).
  - Added full CSS styling for `.replay-catalog-item`, `.replay-item-header`, `.replay-item-body`, `.replay-player-chip`, `.replay-player-avatar`, `.replay-player-name`, `.replay-winner-crown`, and `.replay-item-footer`.
  - Added mobile responsive layout and dark mode support for the Match Replays catalog cards.
- **Challenge Chip & Badge Design Standardization**:
  - Resolved CSS collision where an unscoped `.badge-challenge` rule in `challenge.css` applied landing page banner styling (`text-transform: uppercase`, `letter-spacing: 0.08em`, `border-radius: 999px`, and `box-shadow: 0 4px 12px rgba(...)`) to replay match chips.
  - Replaced `badge-challenge` with `badge-type-challenge` in `replay.js` and scoped `challenge.css` banner styles to header and landing containers.
  - Standardized challenge chips in `replay.css` and `stats.css` to use the standard 6px border radius, Title Case typography ("Challenge" / "Desafio"), zero drop-shadow, and harmonious violet badge styling with light and dark mode support, matching the styling of `Pinpoint`, `Album Shuffle`, and `Local` match chips.

## [3.1.0] - 2026-09-13

- **Automatic Gameplay Viewport Auto-Scroll (`#game-card`)**:
  - Automatically smooth-scrolls the viewport to `#game-card` when starting matches, loading questions, and advancing rounds in both local multiplayer and challenge modes.
  - Scrolls `.app-header` out of view during active gameplay to maximize vertical screen real estate for maps, photo media frames, and interactive inputs.
  - Preserves top-of-page scroll on Lobby Setup, Summary, and Hub pages where header navigation remains relevant.
  - Configured `scroll-margin-top: env(safe-area-inset-top, 0px)` on `#game-card` in `layout.css` for optimal mobile status bar / notch alignment.

- **Challenge Play Mode Icon Unification (`⚔️`)**:
  - Unified the challenge play mode icon to crossed swords (`⚔️`) across all UI elements, including modal tabs (`#tab-challenge-game`), leaderboard play mode badges (`.playmode-badge.mode-challenge`), match replay headers, challenge grand reveal navigation, and documentation.
  - Resolved inconsistent icon usage where globe (`🌐`) or trophy (`🏆`) were previously displayed for challenge play modes.

- **Unified Hub Toolbar Design System (`.hub-toolbar`)**:
  - Standardized the search, sort, and filter toolbars across **Challenges Hub** (`#challenges-page-card`) and **Player Statistics & Replays** (`#stats-page-card`) with a cohesive shaded deck container (`background: var(--bg-surface-secondary)`, subtle borders, rounded corners).
  - Introduced standard 38px control height token (`--toolbar-control-height`) aligning search inputs, segmented pill switches, and dropdown selects on the exact same horizontal baseline.
  - Replaced system emoji icons (`🔍`) with accessible, inline vector SVG magnifying glasses across all search inputs.
  - Added interactive search clear buttons (`✕`) that automatically toggle visibility and reset search queries with single-click ease.
  - Added real-time telemetry counter badges (`#stats-players-total-badge`, `#stats-replays-total-badge`) for Player Directory and Match Replays.
- **Animated Sync Completion Popup (`.sync-popup`)**:
  - Added an animated popup notification anchored beneath `#sync-library-btn` upon sync completion, displaying what was synced in rich detail.
  - Features real-time sync metrics including sync mode (Quick Update vs. Full Sync), photo count (updated vs. indexed vs. up-to-date), albums linked, tags indexed, pruned assets, and execution duration.
  - Implemented using existing design system tokens (`--card`, `--ink`, `--accent`, `--border-light`, `--radius-lg`, `--shadow-md`, glassmorphism) and the existing `@keyframes modalPop` entrance animation.
  - Displays speech-bubble pointer arrow dynamically aligned with the center of the Sync button, auto-dismisses after 6 seconds with a countdown progress bar, and supports close button (`×`), outside click, and keyboard Escape dismissal.
  - Backed by backend `last_sync_summary` telemetry in `SyncStateResponse` and `SyncEngine`.
  - Fully localized in English and Portuguese (`en-US`, `pt-BR`).
- **Challenge Summary Match Replay Unification (`/challenges/:token/summary`)**:
  - Replaced the legacy single-column `.challenge-carousel-card` and static journey map on the Challenge Grand Reveal summary screen with direct integration into the Match Replay engine via the primary action button (`#grand-reveal-replay-action-btn`) linking directly to `/game/:matchId/replay`.
  - Removed redundant middle banner (`.challenge-replay-banner`) in favor of the unified `#grand-reveal-replay-action-btn` action bar button.
  - Added multi-player challenge replay aggregation to `get_match_replay` in `src/storage/leaderboard.py`, enabling challenge replays to display all participants' guesses, distance lines, round scores, and dynamic standings simultaneously across all completed challenge sessions.
  - Added `match_id` field to `ChallengeLeaderboardEntry` and `ChallengeLeaderboardResponse` models in `src/models.py`.
  - Resolved Album Shuffle games rendering blank space in challenge summaries by leveraging the full Match Replay engine with batch photo navigation tabs.
  - Enforced strict Fog-of-War protection so unfinished participants cannot access match replay telemetry prematurely.
- **Match Specification Panel in Replays (`.match-meta-section`)**:
  - Integrated the unified 2-category specification panel (`#replay-match-meta-container`) into the Match Replay screen header.
  - Displays full Game Setup (Game Mode, Targets/Guessing, Rounds, Time Limit) and Library Filters (Libraries, Places, Albums, People, Dates, Shared Scope) for complete match context.
  - Enhanced `MatchReplayResponse` API model and `get_match_replay` database query to deserialize and return `config: MatchConfig`.
  - Re-renders specification items dynamically upon runtime language toggle.

### Changed

- **Elevated Segmented Tabs for Statistics Hub (`#stats-tabs-bar`)**:
  - Transformed flat, unbordered tab bar into a modern, prominent segmented pill control with subtle container background, elevated active card surface, and smooth micro-animations.
  - Added SVG mask icons (`👥` Player Directory, `🎬` Match Replays) that preserve exact button text nodes for i18n and automated tests.
  - Added dynamic item count pill badges (`data-count`) indicating total player profiles and recorded match replays.
  - Added rich guided empty states with feature highlights and prominent CTAs ("Start a Game" and "Browse Challenges") for first-time visitors or clean databases.
  - Automatically hide the search/filter toolbar when no global records exist to center focus on guided onboarding.

### Fixed

- **Challenge Summary Grand Reveal Undefined Variables (`capabilityToken` / `callerCompletedRound`)**:
  - Fixed runtime `ReferenceError: capabilityToken is not defined` and `ReferenceError: callerCompletedRound is not defined` when opening challenge game summaries (`/play/:token/summary`), which previously displayed an error screen ("Desafio Indisponível").
  - Corrected `callerCompletedRound` derivation from `data.up_to_round` and updated `replayMatchId` resolution to safely use `capToken` with fallback to `data.challenge_id`.
- **Challenge Card & Modal Autocomplete Dropdown Overflow (`cards.css`, `modals.css`)**:
  - Allowed `#challenge-card` and `#pane-challenge-game` to have `overflow: visible`, ensuring the player name autocomplete dropdown extends cleanly beyond the challenge card boundary without being clipped by container overflow rules.
- **Stats Hub Routing Parameter Bug (`router.js`)**:
  - Fixed an issue where visiting `/stats` caused `parseRoute` to decode `undefined` regex capture groups into the string `"undefined"`, hiding both tabs and leaving the page blank.
  - Fixed dark mode text contrast for `.player-card-name` and `.player-stat-val` in player directory cards.
- **Challenges & Stats Toolbar Desktop Layout & Styling (`toolbar.css`)**:
  - Resolved an unclosed CSS brace in `challenge.css` line 524 on `.mini-podium-container` that broke stylesheet parsing for `.challenges-toolbar`.
  - Overrode global form reset styles (`select { width: 100%; }`) on toolbar selects with `width: auto`, keeping dropdowns and counter badges aligned on a single horizontal row on desktop.

### Added

- **Player Statistics & Match Replays Page (`/stats`)**:
  - Dedicated hub featuring a Player Directory (`/stats/players`), Match Replay catalog (`/stats/replays`), and embedded Leaderboard (`/stats/leaderboard`).
  - Added primary navigation button (`🏆`) in the header navbar and quick-access banner card on the home lobby.
  - Deep-linkable client-side routing supporting `/stats`, `/stats/players`, `/stats/players/:playerName`, and `/game/:matchId/replay`.
- **Comprehensive Player Profiles & Accuracy Analytics (`/stats/players/:playerName`)**:
  - Built dedicated player legacy dashboard querying relational match records in SQLite.
  - Symmetrical 4-tier accuracy distribution analytics for Location and Date (Top Tier 90–100%, Great 75–89%, Moderate 50–74%, Low <50%).
  - Detailed performance metrics: career points, win rate, podium count, lifetime peak match accuracy, best distance (km), perfect round tallies, and average response times.
  - Game Mode Mastery breakdown (Pinpoint vs. Album Shuffle matches, win rates, and average accuracy).
  - Recent matches log with direct links to interactive replays.
- **Interactive Round-by-Round Match Replay Engine (`/game/:matchId/replay`)**:
  - Direct reuse of standard `.media-frame` image canvas and `#photo-lightbox` modal preview with keyboard escape and click-outside dismissal.
  - Direct reuse of standard `.map-shell` Leaflet architecture, featuring tile layer switching (Streets / Satellite), reset zoom control, map fullscreen toggle, and `fitMapToBounds` bounds framing.
  - Interactive map displaying true photo locations alongside all player guess pins with connecting distance lines and spiderfied coordinates.
  - Running round-by-round scoreboard tracking cumulative standings, points gained per round, and rank progression.
  - Streamlined manual replay navigation with preserved DOM nodes and existing Leaflet map instances across rounds.
- **Smart Player Name Autocomplete (`PlayerAutocomplete`)**:
  - Reusable dropdown querying `/api/players/names` with match counts, recency, and avatar initials.
  - Seamlessly integrated into Local Game setup, Challenge creation form, and Challenge join landing screens.
  - Extended dropdown to full container width (`.player-input-container`) rather than being constrained to the text input wrapper.
  - Resolved modal clipping and scrollbar issues by configuring overflow-visible containers and elevated z-index (`2500`) over modal footers.
  - Added responsive upward flipping (`.open-upwards`) when viewport space below is tight (especially on mobile keyboards and bottom sheets).
  - Enhanced touch interaction support with `pointerdown` listeners and 48px tap targets preventing premature blur dismissals.
  - Keyboard accessible (`ArrowUp`, `ArrowDown`, `Enter`, `Escape`) with non-intrusive dismiss behavior on blur, form submit, and outside pointer events.
- **New REST API Endpoints**:
  - `GET /api/players/names` (autocomplete query with match frequency).
  - `GET /api/players` (player directory with sorting by matches, win rate, points, or name).
  - `GET /api/players/{player_name}/profile` (detailed career profile and accuracy analytics).
  - `GET /api/matches` (paginated match history filterable by game mode, play mode, and player).
  - `GET /api/match/{match_id}/replay` (round-by-round guess telemetry and cumulative scoreboard).

### Fixed

- **Modal Backdrop Drag-Selection Dismissal Protection**:
  - Prevented modals (`#prepare-game-modal`, `#report-issue-modal`, `#album-shuffle-help-modal`, `#pinpoint-help-modal`) from prematurely closing when dragging a text selection from inside an input (e.g. `challenge-creator-name-input`) and releasing the mouse outside the modal card.
  - Required that mouse/touch down events originate directly on the backdrop overlay before a backdrop click dismisses the modal.
- **Match Replay Standard Avatar Color Sequence**:
  - Fixed avatar colors inside match replay (`/game/:matchId/replay`) to strictly follow the standard application palette sequence (`PLAYER_COLORS`: Coral Red `#f25f5c`, Teal `#0f7c7f`, Purple `#7048e8`, etc.) rather than string ASCII character hashing.
  - Added `player_color` column to `match_entries` SQLite table with automatic schema migration.
  - Preserved roster turn order in replay reconstruction from match round guesses and entries, ensuring backwards compatibility with legacy match records.
  - Added client-side color registration in `replay.js` and sequential fallback in `formatters.js` to guarantee consistent colors across map pins, connection lines, player guesses, and scoreboards.
- **Match Replay Photo Caption Visual Balance**:
  - Balanced visual importance between photo date (`.replay-photo-date`, `.replay-polaroid-date`) and location (`.replay-photo-loc`, `.replay-polaroid-loc`) by unifying font-weight (`500`), font size (`0.88rem`), and text color, avoiding disparate bolding.
- **Match Replay Header Reorganization (`.replay-page-header`)**:
  - Restructured the match replay header into a clean, modern two-tier layout separating top-level navigation actions from match identity and metadata.
  - Placed the back button (`#replay-back-btn`) and round stepper (`#replay-round-indicator`, controls) on a dedicated top navigation bar, eliminating horizontal crowding.
  - Added dedicated page title heading (`🎬 Match Replay` / `Replay da Partida`) with localized subtitle meta line (`#replay-match-title`).
  - Implemented pill badge styling with `white-space: nowrap` for mode and play type badges (`#replay-mode-badge`, `#replay-type-badge`), completely eliminating awkward multi-line word wrapping.
  - Optimized responsive styles across desktop, tablet, and small mobile viewports (down to 375px).
- **Navigation Back Button Standardization (`.page-back-btn`)**:
  - Standardized `#profile-back-to-hub-btn`, `#profile-back-btn`, and `#replay-back-btn` under the reusable `.page-back-btn` class.
  - Unified typography (`0.88rem`, semi-bold), padding (`0.42rem 0.85rem`), border radius (`9px`), and hover micro-interaction (`translateX(-2px)`).
  - Aligned the Player Profile header hierarchy, placing the back button neatly on top above the player hero identity card.
- **Recent Matches Rank Column & Medal Badges**:
  - Fixed rank formatting in the Player Profile's Recent Matches table using standard `formatRankBadge(rank, { dot: true })`.
  - Added dedicated `.col-rank` CSS class (50px fixed width, centered) to cleanly present medals (`🥇`, `🥈`, `🥉`) and numbered positions (`4.`) without column overflow.
- **Standardized Replay Guess Metrics**:
  - Upgraded round guess details in match replay to leverage `formatDistance` and `formatMonthError` from `formatters.js`.
  - Enclosed distance (`📍 80 m`), date delta (`📅 12 days`), and response times (`⏱️ 3.8s`) in styled `.replay-guess-metric-item` pill tags with tabular numerals and dark mode support.
- **Home Leaderboard Deep Integration & Stats Streamlining**:
  - Streamlined `/stats` by removing the redundant embedded leaderboard tab, keeping the primary leaderboard on the home screen where it responds to active filter selections.
  - Added interactive links on player names in the home leaderboard routing directly into `/stats/players/:playerName`.
  - Added a dedicated Replay column (`<th class="col-replay">`) with interactive `[🎬 Replay]` action button to jump directly into `/game/:matchId/replay`.

## [3.0.4] - 2026-09-11

### Added

- **Immich 3.2+ Search API v2 Support & Modernization**:
  - Implemented automatic Immich server version detection via `GET /server/version` (`get_server_version()` & `supports_search_v2()`).
  - Added support for Immich 3.2+ structured Search API v2 (`filter: { ... }`) and cursor-based pagination (`cursor` / `nextCursor`).
  - Added explicit exclusion of trashed assets (`trashedAt: { eq: null }`) to mirror legacy behavior in Search API v2.
  - Retained 100% backward compatibility with pre-3.2 Immich instances using automatic fallback to legacy flat search parameters (`page`, `updatedAfter`).
  - Future-proofed the sync engine for the planned removal of flat search parameters in Immich v4.0.0.

## [3.0.3] - 2026-09-11

### Added

- **Album Shuffle Direct Pin Chip Selectors**:
  - Replaced the static `📍 -` text with direct interactive `[A] [B] [C]` pin chip selectors on each photo card.
  - Tapping a chip matches the photo to that lettered map pin with zero modal ambiguity and smart auto-swapping.
- **Album Shuffle Photo Pin Heads on Map**:
  - Map markers now display the photo's circular thumbnail directly inside the pin head when assigned, accompanied by a color-coded letter badge.
  - Retains crisp, high-contrast letter styling when unassigned, enabling immediate visual verification of photo locations on the map.

### Changed

- **Album Shuffle Help Balloons and Guidance**:
  - Updated in-game help text across English and Portuguese to reflect direct card chip selection and visual photo pin heads on the map.
  - Streamlined `docs/GAMEPLAY.md` documentation for Album Shuffle matching rules.

## [3.0.2] - 2026-09-11

### Added

- **Scoped Challenge Public Routes & Seed-Validated Media Proxy**:
  - Consolidated all public participant challenge access under `/play/*` (`/play/api/:token/*` and `/play/media/:token/:asset_id`).
  - Added strict server-side capability and challenge seed validation (`is_asset_in_challenge`): participants can only fetch image thumbnails belonging to their active, unexpired challenge match, preventing arbitrary Immich library scanning.
  - Added in-game photo inconsistency reporting via `POST /play/api/{token}/flag` allowing challenge players to report misplaced GPS tags or dates without exposing administrative moderation APIs.
- **Dynamic Preflight Count Updates by Guess Mode**:
  - Preflight counter in setup and home screen now dynamically updates based on active guess mode toggles (Location/GPS, Date, or both).
  - Toggling Location or Date immediately recalculates eligible counts and warnings using `both_count`, `gps_count`, and `date_count`, and triggers a debounced server check.
  - Added `both_count` field to `PreflightResponse` and `MetadataStore.get_asset_counts` to provide full breakdown data.
  - Bound event listeners to `#game-settings-container` and `#round-count` to react to mode toggles and round requirement changes instantly.
- **Streamlined Zero Trust & Reverse Proxy Path Security**:
  - Simplified Cloudflare Access, Caddy, Nginx, and Traefik deployment by exposing only `/play/*` and `/static/*` for public challenge participants.
  - Keeps root (`/`), Challenges Hub (`/challenges`), Moderation Dashboard (`/reported`), and administrative endpoints (`/api/*`) strictly protected behind host authentication with zero complex reverse-proxy path regexes or priority conflicts.

### Changed

- **Clean Architectural Separation of Host and Player APIs**:
  - Split challenge router into host management (`/api/challenge/*`) and player participant routes (`/play/api/*`, `/play/media/*`).
  - Updated all challenge game engine views (Game, Intermission, Reveal, and Summary) and in-game report modals to consume the scoped `/play/*` APIs.
  - Enhanced router navigation state to support silent history updates, preventing redundant re-render loops on URL parameter updates.

### Fixed

- **Service Worker and HTTP Dynamic Response Caching**:
  - Updated Service Worker (`sw.js`) to bypass caching for `/play/api/` and `/play/media/`, ensuring real-time multi-tab and multiplayer standings are never served from stale caches.
  - Hardened dynamic API endpoints with HTTP `Cache-Control: no-store, no-cache, must-revalidate, max-age=0` headers while preserving immutable client caching for static and media proxy assets.

## [3.0.1] - 2026-09-09

### Fixed

- **Leaderboard data selection**: Fixed leaderboard query to correctly filter when no media filters are applied.

## [3.0.0] - 2026-09-07

### Added

- **Asynchronous Multiplayer Challenge Mode**:
  - Seed-based deterministic challenges with shareable capability URLs, vector QR codes, and native 1-click sharing.
  - Dedicated **Challenges Hub** (`/challenges`) with discovery metrics, search, status filters (Active/Expired), and interactive standings drawer.
  - Real-time multiplayer feedback: live activity toasts, animated opponent pin drops on reveal maps, pulsing header badges, and dynamic podium transitions.
  - Standalone summary route (`/play/:token/summary`) with mode-tailored Grand Reveal scatter maps and photo journey galleries.
  - 16-color clash-free participant avatar palette maintained across maps, round headers, and leaderboards.
- **Reported Asset Moderation Dashboard (`/reported`)**:
  - Dedicated admin dashboard to search, filter, and inspect flagged assets with direct Immich Web deep links.
  - Resolution workflow to unflag assets and return them to the active photo pool in real time.
- **Setup Controls & Interactive Help Modals**:
  - Tactile segmented button controls for rounds and duration with responsive mobile bottom-sheet styling.
  - Dedicated contextual help modals for Pinpoint and Album Shuffle accessible directly from the lobby and in-game headers.
  - Accessible modal focus trapping and native Web Share API integration with SVG icons and animated copy feedback.
- **Universal Dynamic Localization & Automated Verification**:
  - Seamless runtime language switching across all screens without page reloads.
  - Automated DOM scanner and E2E test suites verifying 100% translation key parity between English and Brazilian Portuguese.
- **Performance & Infrastructure Hardening**:
  - Authenticated media proxy with HTTP `ETag` / `304 Not Modified` caching for smooth photo transitions.
  - Periodic SQLite checkpointing, thread-pool offloading via `asyncio.to_thread()`, and container least-privilege non-root execution (`1000:1000`).
  - Optimized CI/CD and release pipeline with automated changelog extraction in GitHub Releases, QEMU multi-arch Docker builds (`linux/amd64`, `linux/arm64`), and dedicated [Release Guidelines](docs/RELEASES.md).

### Changed

- **Terminology Standardization & UI Copy Simplification**:
  - Unified consistent, accessible naming in English and Portuguese across navigation, game setup, play styles, and awards (e.g., *"Solo"*, *"Pass & Play"*, *"Submit Guess"*, *"Photo Memories"*).
  - Streamlined mode descriptions, scoring documentation, and help modal instructions.
- **Symmetric Architecture & Decoupled Game Engines**:
  - Symmetrically decoupled data models (`PinpointReveal`, `UnshuffleAnswerItem`), unified backend round state (`RoundData`), and cleanly scoped frontend state.
  - Standardized round review layout, responsive map token heights, and full-resolution lightbox support across all game modes.
- **Dynamic Asset Stamping & Caching**:
  - Automatic version stamping in HTML templates and Service Worker (`sw.js`) eliminating stale cache issues on upgrades.

### Fixed

- **Opponent Round Reveal Telemetry & Pin Placement**: Fixed game-mode detection bug in round reveals, restoring opponent distance errors, dates, timeout badges, and live participant counts.
- **Navigation & Submission Safety**: Added in-progress match notices for new tabs and optimistic locking to prevent duplicate round submissions.
- **Cross-Platform & Environment Compatibility**: Resolved UTF-8 console emoji logging crashes on Windows and ensured backend translation files are bundled in Docker builds.

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

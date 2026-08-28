# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.4.1] - 2026-08-28

### Added

- **Automated Playwright End-to-End (E2E) Test Suite**:
  - **E2E Browser Test Harness**: Integrated session-scoped live uvicorn server harness with mock Immich server and test database seeding in `tests/e2e/conftest.py`.
  - **Pinpoint Interactive Gameplay Tests**: Implemented comprehensive two-tap Leaflet map pin placement, distance error calculation, and round reveal map polyline/star marker validation (`tests/e2e/test_pinpoint_gameplay.py`).
  - **Date Selection & Filtering Tests**: Added automated verification for dual-handle timeline date range slider and single-year/month date guessing with dynamic month constraints (`tests/e2e/test_date_selection.py`).
  - **Album Shuffle Interactive Gameplay Tests**: Added photo card reordering tests with rank up/down buttons and multi-pin (A, B, C) map marker assignment and scoring validation (`tests/e2e/test_album_shuffle_gameplay.py`).
  - **Client-Side Routing & Session Recovery Tests**: Added automated tests for deep links (`/`, `/stats`, `/unknown`), active match page reload state recovery from `sessionStorage`, and expired match fallback rendering (`tests/e2e/test_routing_and_recovery.py`).
  - **Summary & Visual Effects Tests**: Added automated verification for score rollup animations, podium rendering, polaroid memory cards gallery, and post-game summary navigation (`tests/e2e/test_summary_and_effects.py`).
  - **Match Lifecycle & Guard Coverage**: Added automated tests for in-game exit/abandonment confirmation dialogs, countdown timer timeout zero-crossings, and multiplayer pass-and-play overlays with podium ranking resolution (`tests/e2e/test_routing_and_recovery.py`, `tests/e2e/test_date_selection.py`, `tests/e2e/test_summary_and_effects.py`).
  - **CI & Git Hook Integration**: Added Playwright Chromium installation step to GitHub Actions CI workflow (`.github/workflows/ci.yml`) and local pre-push git hook (`.githooks/pre-push`).

- **Self-Contained Match Place Persistence**:
  - Added `actual_city` and `actual_country` columns to `match_round_guesses` table in `src/storage/leaderboard.py`.
  - Enriched both single-photo (Pinpoint) and multi-photo (Album Shuffle) guess records with snapshot ground truth city and country metadata at match completion.
  - Reconstructed match history and batch reveals from SQLite `LeaderboardStore` with place names and ISO capture dates for permanent, replayable match summaries.

### Changed

- **Unified Polaroid & Journey Map Place Formatting**:
  - Unified `renderPolaroidGallery()` in `static/js/modules/summary/polaroids.js` to format place labels via `formatPlace()` across all game modes, ensuring consistent display hierarchy (`City, Country` -> `Coordinates` -> `Unknown place`).
  - Standardized single-photo pin popups in `static/js/modules/maps.js` with `formatPlace()` and localized calendar capture date formatting.

### Fixed

- **UI Config API Endpoint URL Alignment**: Corrected the frontend UI config request from `/api/config` to `/api/ui-config` in `static/js/app.js` to ensure clean route alignment.
- **Audio Context & Vibration Autoplay Restrictions on Page Reload**:
  - Added `hasUserActivation()` checks, unified `shouldPlay()` audio guard, and running AudioContext state guards in `static/js/modules/audio.js` to eliminate browser autoplay and vibration policy console warnings (`navigator.vibrate` and `AudioContext` start blocks) on fresh page loads and refreshes.
  - Scoped `playVictoryFanfare()` to trigger only on active match transitions in `summary.js` and `reveal.js` rather than on passive page reloads or direct permalink navigation.
- **Frontend Missing Module Imports**: Added missing `saveActiveMatchSession` (from `./modules/state.js`) and `renderSummaryContent` (from `./modules/screens/summary.js`) imports in `static/js/app.js` to resolve runtime `ReferenceError` during pass-and-play ready button interactions and dynamic language refreshes.
- **Frontend Event Listener DOM References & Cleanup**: Fixed `el.shareSummaryBtn` event listener binding in `static/js/app.js`, eliminated duplicate state declarations, and unified safe null-checked event listeners via a `bindClick` helper.
- **Game Mode Dynamic Settings Initialization**: Added `initModeSelector` in `static/js/modules/setup_filters.js` to initialize active game mode settings and button state bindings on startup.
- **Album Shuffle Table DOM ID Collision**: Renamed dynamic reveal score table ID in `album_shuffle.js` to `shuffle-reveal-table` to prevent duplicate ID collisions in the DOM.

## [2.4.0] - 2026-08-28

### Added

- **Client-Side History API Router & Deep Links**:
  - **Match URLs & Navigation**: Added zero-dependency History API client-side routing supporting `/` (Lobby), `/game/{match_id}` (Active Match), and `/game/{match_id}/summary` (Shareable Replay & Podium).
  - **Active Session State Recovery**: Page refreshes during active gameplay seamlessly restore match state from `sessionStorage`.
  - **Ended Match View**: Navigating to an expired or ended match URL displays a dedicated Match Ended card with quick paths to the match summary or lobby.
  - **In-Game Navigation Guards**: Prevents accidental abandonment by intercepting browser back/forward buttons and tab closes with localized confirmation dialogs.
  - **Shareable Permalink URLs**: "Share Match" payloads now include canonical summary URLs (`/game/{match_id}/summary`).

- **Permanent SQLite Match Summaries & Single Source of Truth**:
  - **Lifetime Match Replays**: Finished match summaries and full round histories are permanently stored and queried directly from SQLite (`LeaderboardStore`), eliminating in-memory expiration for completed games.
  - **Media Access for Recorded Matches**: Proxied media endpoint (`/api/media/{asset_id}`) authorizes photo assets for all recorded match summaries in SQLite history, ensuring polaroid gallery and journey map images always load on shared permalinks.

- **FastAPI SPA Catch-All Route & PWA Navigation Caching**:
  - **Catch-All Handler**: Backend route `/{full_path:path}` serves `index.html` with security headers and language negotiation while strictly preserving 404s for missing `/api/*` and `/static/*` paths.
  - **Service Worker Navigation Fallback**: Updated `sw.js` (cache `immich-quiz-v2`) with navigation fallback to the app shell and precached router modules.

### Changed

- **Frontend Screen Controllers Modularization**:
  - Refactored monolithic `app.js` into domain-focused screen controllers under `static/js/modules/screens/` (`setup.js`, `game.js`, `reveal.js`, `summary.js`, `common.js`).
  - Centralized game mode strategy accessor into `static/js/modules/modes/index.js`.
  - Streamlined `app.js` into a lightweight (~450 lines) coordinator handling router dispatch, PWA lifecycle, and global shortcuts.

- **Backend Code Quality & Datetime Safety**:
  - Added safe ISO datetime parsers (`_parse_iso_datetime`) in `src/storage/leaderboard.py` to prevent unhandled exceptions on malformed timestamps.
  - Added typed `.seconds` property on `RoundLength` model in `src/models.py`.

### Fixed

- **Pass-and-Play Timer Handover**: Fixed an issue where the round timer would tick in the background while waiting on the "Pass Device" screen or following a page reload prior to clicking "I'm ready".

## [2.3.0] - 2026-08-28

### Added

- **Album Shuffle Partial Credit Scoring**:
  - **Nearby Map Pin Credit**: Swapping two close pins (like two landmarks in the same city during a worldwide match) now earns high partial points based on actual distance instead of giving zero points.
  - **Close Timeline Date Credit**: Flipping photos taken only a few days apart in a multi-year album now gives nearly full score instead of punishing minor ordering errors.
  - **Batch-Adaptive Scaling**: Scoring sensitivity automatically adjusts to the geographic span and date range of each photo batch.
  - **Per-Photo Round Telemetry**: Detailed match history now records individual photo distance errors, day differences, and points earned.

- **Structured Console & Container Logging**:
  - **Clean Formatted Logs**: Added color-coded, timestamped console logs (`YYYY-MM-DD HH:MM:SS [LEVEL] [subsystem] Message`) optimized for Docker (`docker logs`) and local terminal debugging.
  - **Match & Request Tracing**: Automatically tracks `match_id`, `player_name`, `library_name`, and `request_id` across all log messages.
  - **Automatic Credential Masking**: Automatically redacts Immich API keys and Bearer tokens in log output.
  - **HTTP Request Duration Logging**: Measures and logs API endpoint response times with clean status summaries.
  - **Customizable Log Levels**: Set overall level with `LOG_LEVEL` or configure individual subsystems (`LOG_LEVEL_SCORING`, `LOG_LEVEL_SYNC`, `LOG_LEVEL_IMMICH`, etc.).

- **Smooth 60 FPS Countdown Timer & Dynamic Audio**:
  - **Fluid Progress Bar**: Timer drains continuously at 60 FPS using `requestAnimationFrame`, eliminating 1-second stepped jumps.
  - **Dynamic Color Transitions**: Smoothly transitions from Teal (100%) to Amber (50%) to Crimson (0%) with pulsating warning animations in the final 5 seconds.
  - **Rising Pitch Audio Ticker**: Replaced monotone beeps with a frequency-rising audio ticker (440 Hz up to 880 Hz) during the last 10 seconds, paired with device vibration.
  - **Smart Time Display**: Shows `M:SS` (e.g. `1:15`) for long timers and `Xs` (e.g. `45s`) for sub-minute rounds.

### Changed

- **Tuned Location Scoring Sensitivity**: Adjusted distance scaling to make city/neighborhood rounds more forgiving (5 km base) while keeping nationwide and worldwide rounds appropriately challenging (200 km maximum decay).
- **Synchronized Score Rollup Sounds**: Centralized audio ticker playback during score rollup animations so multiplayer reveals play one smooth rising tone.
- **Unified Scoring Engine**: Replaced rigid matching code with shared adaptive decay functions across all game modes.

### Removed

- **Unused `LOCATION_MAX_SPAN_KM` Config**: Removed redundant maximum span setting, as the maximum decay setting already sets the scoring ceiling.

### Fixed

- **Start Match Double-Clicking**: Prevented duplicate match creation and duplicate photo loading when clicking "Start Match" multiple times on slow connections.
- **Score Rollup Animation Timing**:
  - Fixed speed inconsistencies on round reveal tables so score counting rolls up smoothly across all rounds regardless of total points.
  - Fixed summary table score animation duration for single-mode games (location-only or date-only).

## [2.2.0] - 2026-08-25

### Added

- **Progressive Web App (PWA) Support**: Installable standalone application with web app manifests, service worker offline shell caching, in-app install button, and high-DPI vector/raster icon suite (`favicon.svg`, Apple Touch Icon, Android Chrome launchers).
- **Mobile Ergonomics & Tactile Haptics**: Added iOS notch/safe-area insets (`env(safe-area-inset-*)`) and Web Vibration API haptics for countdowns, buzzer, map pin drops, submit confirmations, and victory fanfares.
- **Wall-Clock Timer Synchronization**: Real-time round timer calculation against target epoch timestamps (`Date.now()`) with Page Visibility API sync to prevent timer freezing when minimizing the browser or locking the screen.
- **In-Game Navigation & Tab-Close Protection**: Added browser Back button (`popstate`) and tab close/refresh (`beforeunload`) confirmation guards during active gameplay to prevent accidental match abandonment while maintaining seamless setup and summary transitions.
- **Enterprise Internationalization (i18n)**: Migrated to BCP-47 language tags (`en-US`, `pt-BR`), externalized JSON catalogs (`locales/`), RFC 9110 `Accept-Language` negotiation, Unicode CLDR plural rules (`Intl.PluralRules`), relative timestamps (`Intl.RelativeTimeFormat`), conjunction lists (`Intl.ListFormat`), and locale-aware sorting (`Intl.Collator`).

## [2.1.0] - 2026-08-24

### Added

- **Dynamic / Adaptive Scoring Decay**: Replaced static global decay constants with per-match dynamic calculations tailored to the geographic and temporal distribution of candidate photos in the match pool.

### Changed

- **Smart Map Initial Zoom**: Increased `SMART_MAP_MAX_INITIAL_ZOOM` to `13` (neighborhood / street zoom level) in Pinpoint mode for tighter initial framing on city and neighborhood-scale albums.

### Removed

- **Static Decay Environment Variables**: Removed `LOCATION_SCORE_DECAY_KM` and `DATE_SCORE_DECAY_DAYS` configuration parameters from `AppSettings`, `.env.example`, and server validation in favor of automated per-match calculations.

## [2.0.0] - 2026-08-17

### Added

- **Local Metadata Storage & Sync Engine**: SQLite-backed metadata caching layer (`data/metadata.db`) storing assets, albums, recognized faces, and geographic places locally. Includes manual and automatic background sync (`SyncEngine`) with real-time indexing status indicators and instant 0ms query response times.
- **Library & Photo Filters Accordion**: Collapsible section grouping dataset filters (Library, Multi-Album, Date Range, Geography, People) with dynamic active filter count badge and one-click reset.
- **Dynamic Date Range Slider**: Dual-handle interactive range slider with year-month resolution, live readouts, and automatic Immich timeline bucket boundary discovery.
- **Geographic Granularity (Countries & Dependent Cities)**: Searchable multi-select dropdowns for countries and cities with cascading dependencies (selecting a country dynamically filters the available cities).
- **Face Recognition / People Filter with Match Modes**: Searchable multi-select dropdown for recognized people with support for both `ANY` (Any person) and `ALL` (All people together in the same photo).
- **Photo Play Frequency Tracking & Least-Played Prioritization**: Automatically tracks `times_played` and `last_played_at` per asset in SQLite to prioritize unplayed and least-frequently seen photos (`ORDER BY a.times_played ASC, RANDOM()`), maximizing photo discovery and freshness across matches without sync data loss.
- **Smart Photo Diversity Downsampling**: Soft prioritization sampling strategy in candidate photo selection that prioritizes photos with spatial (>= 100m) and temporal (>= 60s) separation against previously played match photos, while gracefully falling back to unplayed candidates when playing clustered single-event or local albums (preventing premature 404 match aborts).
- **Dynamic Shared & Partner Library Toggles**: Added setup filter toggles to dynamically include or exclude shared albums and partner assets per-match without restarting the server.
- **Modern Interactive Player Input**: Tag/chip based player management component with avatar badges, game-matched player colors, duplicate detection, keyboard shortcuts, paste splitting, and touch-screen virtual keyboard optimizations.
- **Live Preflight Counter**: Live feedback counter displaying eligible photos and breakdown tooltips (GPS, Date, Eligible total) dynamically updating on every filter or game mode change.
- **Per-Library Filter Persistence**: Active filter selections saved in `localStorage` per library, automatically restoring when switching libraries.
- **Asset Tag Whitelist & Blacklist**: Added `TAG_WHITELIST` and `TAG_BLACKLIST` configuration settings enforcing global server-level safeguards across SQLite metadata queries and in-memory asset filtering. Assets labeled with any blacklisted tag are strictly excluded from candidate pools, and when a whitelist is specified, only assets tagged with at least one whitelisted tag are eligible.
- **Unified 4-Table Relational Match & Multiplayer Foundation**: Implemented a comprehensive relational SQLite schema (`challenges`, `matches`, `match_entries`, `match_round_guesses`) under `data/leaderboard.db`. Features type-safe `PlayMode` enum (`local`, `challenge`, `room`), exact per-photo round guess records (`photo_index`), actual and guessed coordinates/dates, sub-score breakdowns, and active response time tracking (`time_taken_seconds`, `total_time_seconds`) for fair tiebreaking.

### Changed

- **Photo Diversity Decoupling**: Decoupled candidate diversity checks from global configuration parameters into internal defaults within the sampling engine, ensuring Preflight filtering remains the single source of truth for photo eligibility.
- **Setup Screen Hierarchy**: Reorganized match setup into top-down logical flow: Players, Library & Photo Filters, Game Mode, and Guessing Mode settings.
- **Preflight & Setup Validation**: Hardened validation to disable start match button and show informative warnings when insufficient matching media is available.
- **Leaderboard API & Querying**: Updated `/api/leaderboard` endpoint with support for querying by `player_name`, `is_custom_filtered`, and `limit`.

### Removed

- **Photo Diversity Configuration**: Removed `PHOTO_DIVERSITY_MIN_DISTANCE_KM` and `PHOTO_DIVERSITY_MIN_TIME_SECONDS` configuration parameters from `AppSettings` and `.env` in favor of internal sampling parameters.
- **Smart Map Zoom Config**: Removed `SMART_MAP_ZOOM` environment toggle in favor of built-in internal safeguards.
- **Legacy CSV Storage**: Removed `LEADERBOARD_CSV_PATH` configuration and CSV-based leaderboard persistence in favor of dedicated SQLite storage under `DATA_PATH` (`metadata.db` and `leaderboard.db`).

## [1.2.1] - 2026-08-15

### Fixed

- **Shared Album Filtering**: Fixed `INCLUDE_SHARED_ALBUMS=false` filtering so shared albums owned by the authenticated user are kept and only albums shared with the user by others are hidden.

## [1.2.0] - 2026-08-13

### Added

- **Smart Map Zoom (Pinpoint Mode)**: Added dynamic geographic auto-framing for Pinpoint guess maps based on the overall geographic distribution of photos selected for the match, eliminating repetitive manual zooming when playing regional or trip albums.
- **Regional Focus Map Control**: Added a dedicated "Focus match region" button to Leaflet map toolbars, allowing players to snap back to the album's regional view at any point during a round.
- **Map Canvas Zoom Bounds Guard**: Implemented dynamic `minZoom` computation on all Leaflet maps to prevent over-zooming out where map tiles are smaller than the container canvas height.

### Changed

- **Setup Screen Organization**: Reordered the match setup screen into clear logical groups: Player Settings (Players, Rounds, Round Length), Library Settings (Library, Albums), and Game Settings (Game Mode, Guessing Mode).

## [1.1.0] - 2026-08-13

### Added

- **Searchable Multi-Select Album Selector**: Added a searchable multi-select album dropdown component on the setup screen, allowing real-time text searching of albums, multi-album selection, and batch quick actions (Select All / Deselect All).

## [1.0.2] - 2026-08-12

### Fixed

- **Round Reset**: Fixed round reset to properly reset game state

### Added

- **Button to reset map to default zoom**

### Refactored

- **Unified map creation**
- **Better Immich query controls**

## [1.0.1] - 2026-08-12

### Fixed

- **Improved design uniformization**

## [1.0.0] - 2026-08-08

### Added

- **Album Shuffle Game Mode** (`album_shuffle`): Introduced a new hybrid batch mode where players guess locations by matching a batch of photos ($N=3$) to lettered map pins (`A`, `B`, `C`) and sort photos chronologically (`1st`, `2nd`, `3rd`).
- **On-the-Fly Language Toggle**: Added header button to dynamically toggle between English (EN) and Brazilian Portuguese (PT) without resetting game state.
- **Improved support for mobile screens**: Adjusted content and dimensions for narrow screens.
- **Extended Round Length Options**: Added `2m` and `5m` round length options optimized for batch photo sessions.
- **Auto-Zoom & Smooth Map Navigation**: Automatic map bounding box zoom during reveal phase and turn interactions.
- **Automatic Valid Photo Reload**: Automatic fallback and recovery if photo media fails to load or lacks valid metadata.
- **Audio Testing Playground Enhancements**: Added dedicated countdown timer simulator, submit confirmation cue (`playSubmitTone`), and real-time Web Audio oscilloscope visualizer.
- **Frontend Regression Test Suite**: Added `test_frontend_regressions.py` covering HTML structure, modal accessibility, and script references.
- **Footnote**: Added footnote containing app version.

### Changed

- **Setup Layout Re-ordering**: Moved Game Mode selector to the bottom of the setup options list for improved visual hierarchy.

### Fixed

- **Date Error Rounding**: Fixed rounding calculation errors when displaying date error deltas.
- **Multiplayer Leaderboard Tie-Breaking**: Improved tie-breaking algorithm when multiple players achieve identical scores.

### Refactored

- **Modular Frontend Architecture**: Split monolithic game UI logic into specialized ES modules (`static/js/modules/modes/album_shuffle.js`, `pinpoint.js`, `common.js`).
- **Modular CSS Architecture**: Refactored monolithic `static/css/style.css` into domain-focused sub-stylesheets

## [0.3.0] - 2026-08-08

### Added

- **UI Animations**: Added visual animations and dynamic transition effects for UI components and round reveals.
- **i18n Updates**: Expanded internationalization support across game views.

### Changed

- **Map Interaction & View**: Improved Leaflet map view rendering, auto-centering, and interaction behavior.
- **Multiplayer Awards & Podium**: Refined award criteria calculations and updated post-game end screens to display podium awards exclusively for multiplayer sessions.
- **Reveal Screen Layout**: Reordered reveal phase elements to present scoring and metadata details more clearly.

### Fixed

- **Tie-Breaking Logic**: Enhanced leaderboard tie-breaking for equal score results.
- **General Robustness**: Hardened edge-case handling across map rendering and turn transitions.

## [0.2.0] - 2026-08-08

### Added

- **Interactive Audio Playground**: Introduced a dedicated audio testing route (`/audio-test`) to audition and test Web Audio API sound effects.

## [0.1.2] - 2026-08-08

### Added

- **Developer & Pipeline Tooling**: Added VS Code `launch.json`/`tasks.json`, a Git pre-push hook for automated testing, and a GitHub Actions release workflow (`release.yml`) with automated Docker image tagging based on `pyproject.toml`.
- **Project Ownership**: Added `CODEOWNERS` file.
- **Server URL Normalization**: Automatically appends `/api` to server URLs if omitted during setup.

### Changed

- **Album Selection**: Sorted album selection dropdown alphabetically.
- **Scoring System**: Updated scoring rounding calculation (`round` instead of `floor`) and adjusted location distance decay scaling.
- **JS Modularity**: Refactored frontend scripts to improve module structure.

### Fixed

- **Audio Settings Toggle**: Fixed issue where disabling audio feedback did not persist correctly.

## [0.1.0] - 2026-08-08

### Added

- Initial release of **Immich Quiz**.
- Single photo **Pinpoint** mode for Location and Date guessing.
- Immich API integration with preflight asset validation.
- Pass-and-play local multiplayer support with end-of-match performance awards (**Sniper**, **Time Traveler**, **Speed Demon**).
- CSV-backed Leaderboard persistence.
- Zero-dependency Web Audio sound engine.

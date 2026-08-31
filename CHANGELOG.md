# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

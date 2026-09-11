# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
  - Symmetrically decoupled data models (`PinpointReveal`, `AlbumShuffleAnswerItem`), unified backend round state (`RoundData`), and cleanly scoped frontend state.
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

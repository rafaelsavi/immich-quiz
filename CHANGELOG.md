# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.0.0] - 2026-08-15

### Added

- **Local Metadata Storage & Sync Engine**: SQLite-backed metadata caching layer (`data/metadata.db`) storing assets, albums, recognized faces, and geographic places locally. Includes manual and automatic background sync (`SyncEngine`) with real-time indexing status indicators and instant 0ms query response times.
- **Library & Photo Filters Accordion**: Collapsible section grouping dataset filters (Library, Multi-Album, Date Range, Geography, People) with dynamic active filter count badge and one-click reset.
- **Dynamic Date Range Slider**: Dual-handle interactive range slider with year-month resolution, live readouts, and automatic Immich timeline bucket boundary discovery.
- **Geographic Granularity (Countries & Dependent Cities)**: Searchable multi-select dropdowns for countries and cities with cascading dependencies (selecting a country dynamically filters the available cities).
- **Face Recognition / People Filter with Match Modes**: Searchable multi-select dropdown for recognized people with support for both `OR` (Any person) and `AND` (All people together in the same photo).
- **Strict Diversity Safeguards**: Strict candidate separation enforcement (`PHOTO_DIVERSITY_MIN_DISTANCE_KM` and `PHOTO_DIVERSITY_MIN_TIME_SECONDS`) and preflight rejection when diversity cannot be guaranteed.
- **Modern Interactive Player Input**: Tag/chip based player management component with avatar badges, game-matched player colors, duplicate detection, keyboard shortcuts, paste splitting, and touch-screen virtual keyboard optimizations.
- **Live Preflight Counter**: Live feedback counter displaying eligible photos and breakdown tooltips (GPS, Date, Eligible total) dynamically updating on every filter or game mode change.
- **Per-Library Filter Persistence**: Active filter selections saved in `localStorage` per library, automatically restoring when switching libraries.
- **SQLite Leaderboard Storage with Extended Columns**: Migrated leaderboard persistence from flat CSV to indexed SQLite relational schema (`leaderboard_matches`, `leaderboard_entries`). Captures full match filter presets (albums, people, countries, cities, date ranges, match mode), sub-score breakdowns (Location vs Date), player match rankings, winner status, accuracy percentage, and performance awards.

### Changed

- **Setup Screen Hierarchy**: Reorganized match setup into top-down logical flow: Players, Library & Photo Filters, Game Mode, and Guessing Mode settings.
- **Preflight & Setup Validation**: Hardened validation to disable start match button and show informative warnings when insufficient matching media is available.
- **Leaderboard API & Querying**: Updated `/api/leaderboard` endpoint with support for querying by `player_name`, `is_custom_filtered`, and `limit`.

### Removed

- **Legacy CSV Storage**: Removed `LEADERBOARD_CSV_PATH` configuration and CSV-based leaderboard persistence in favor of unified SQLite database management (`METADATA_DB_PATH`).

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

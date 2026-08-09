# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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

### Changed

- **Setup Layout Re-ordering**: Moved Game Mode selector to the bottom of the setup options list for improved visual hierarchy.

### Fixed

- **Date Error Rounding**: Fixed rounding calculation errors when displaying date error deltas.
- **Multiplayer Leaderboard Tie-Breaking**: Improved tie-breaking algorithm when multiple players achieve identical scores.

### Refactored

- **Modular Frontend Architecture**: Split monolithic game UI logic into specialized ES modules (`static/js/modules/modes/album_shuffle.js`, `pinpoint.js`, `common.js`).
- **Modular CSS Architecture**: Refactored monolithic `static/css/style.css` into domain-focused sub-stylesheets

---

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

---

## [0.2.0] - 2026-08-08

### Added

- **Interactive Audio Playground**: Introduced a dedicated audio testing route (`/audio-test`) to audition and test Web Audio API sound effects.

---

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

---

## [0.1.0] - 2026-08-08

### Added

- Initial release of **Immich Quiz**.
- Single photo **Pinpoint** mode for Location and Date guessing.
- Immich API integration with preflight asset validation.
- Pass-and-play local multiplayer support with end-of-match performance awards (**Sniper**, **Time Traveler**, **Speed Demon**).
- CSV-backed Leaderboard persistence.
- Zero-dependency Web Audio sound engine.

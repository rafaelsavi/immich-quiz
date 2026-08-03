# Changelog

All notable changes to **Immich Quiz** are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.0.0] - 2026-08-03


### Added

- **Album Shuffle Game Mode**:
  - Added 5-photo batch round mode matching map pins (A..E) to photo cards and ordering photos chronologically on a timeline.
  - Added strict batch pin matching (`batch_strict_location_score`) and Kendall-Tau timeline sequence inversion score (`kendall_tau_inversion_score`).
  - Added support for Date-Only Album Shuffle (enables answer submission without requiring location pins when `location_mode = False`).
  - Added dynamic map pin badges displaying `PinID-CardIndex` (e.g. `A-1`) for assigned photo cards.
  - Improved shuffle card image resolution by requesting appropriately sized Immich preview thumbnails.
- **Polaroid Memory Gallery & World Journey Map**:
  - Added Polaroid card gallery to the match summary screen with image click lightboxes for full-resolution viewing.
  - Added Leaflet World Journey Map rendering with automatic coordinate offset clustering for overlapping photo pins.
- **Backend Service Layer (`src/game/service.py`)**:
  - Introduced `GameService` application layer encapsulating match preflight, setup, question drawing, score computation, and leaderboard persistence.
- **Backend Question Selector & Mode Engines**:
  - Created `src/game/selector.py` for candidate pool sampling and candidate distance/time separation rules (100m distance, 60s date separation).
  - Created `src/game/modes.py` for Pinpoint and Album Shuffle score evaluation.
- **Frontend View Controllers & Mode Packages**:
  - Standardized UI strategy using W3C Native HTML `<template id="tmpl-mode-${name}">` tags and `mountModeTemplate()` strategy helper.
  - Eliminated all cross-mode DOM hiding logic across game modes for maximum open-closed architectural isolation.
  - Extracted shared photo lightbox image viewer into `static/js/modules/components/lightbox.js`.
  - Refactored `album_shuffle.js` monolith into a clean modular package under `static/js/modules/modes/album_shuffle/` (`index.js`, `board.js`, `map.js`, `reveal.js`, `help.js`).
- **Architecture Documentation**:
  - Updated [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) with complete Module Map, Data Flow diagrams, Anti-Cheat boundaries, Strategy pattern contracts, and Extensibility guidelines.

### Fixed

- **Null Island (0,0) Coordinates Filtering**:
  - Added strict coordinate checks (`abs(lat) < 1e-6 and abs(lon) < 1e-6`) across candidate eligibility checks (`is_eligible_asset`), batch candidate filtering (`is_asset_valid_for_batch`), journey map pin rendering, and frontend place formatters (`formatPlace`).
- **Calendar Month Step Arithmetic**:
  - Refactored `date_diff_parts()` calendar arithmetic in `src/scoring.py` to step forward full years, then full months, then measure remaining days, eliminating month-boundary double counting.
- **Album Shuffle Timeout Scoring**:
  - Fixed timed-out Album Shuffle answers to yield `0` points instead of `100` points by incorporating `total_items` into Kendall-Tau sequence scoring.
- **Candidate Pool Fallback Safety**:
  - Handled empty asset pool edge cases in `_select_batch_round_assets` to prevent `IndexError` server errors on constrained library/album pools.
- **Frontend Formatter Safety**:
  - Updated `formatPlace()` to safely handle `null`, `undefined`, and zero coordinates without raising JavaScript `TypeError` exceptions.
- **Pydantic Validation Alignment**:
  - Aligned unit tests and game setup payloads to enforce `round_count` in `{5, 10, 20}`.

### Changed

- Refactored `src/api/routes.py` from 925 lines down to 600 lines by delegating endpoint handling to `GameService`.

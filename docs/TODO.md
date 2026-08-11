# Immich Quiz Roadmap & TODO List

This document lists planned features, design ideas, and technical debt items for **Immich Quiz**.

---

## 🚀 Future Feature Concepts

- **Online multiplayer**: Extend pass-and-play local multiplayer to support multi-device real-time lobbies. Design specification defined in docs\next-release-milestone\online-multiplayer

- **Improve Audio Effects / Soundtrack**

- **Smart map zoom**: Dynamically adjust initial pinpoint guess map zoom & framing based on the geographic distribution of photos fetched for the current game session, eliminating tedious manual zooming when playing local/regional albums.
  - **Match Bounding Box Calculation**: During `/api/game/setup`, calculate the bounding box (min/max latitude & longitude) encompassing all sampled photos for the match. Return `map_bounds` in `SetupResponse`.
  - **Anti-Spoiler & Privacy Safeguards**:
    - **Match-Wide Scope**: Bounds are computed across all rounds in the match (never per-photo), ensuring initial map framing does not reveal the answer to the current round.
    - **Max Zoom Cap / Min Spread**: Enforce a maximum initial zoom level (e.g. `maxZoom: 6` / ~300km minimum span) so single-location or single-city albums don't start zoomed directly onto exact street addresses.
    - **Fallback**: Default to global world view (`[20, 0], zoom 2`) if photos span globally (> certain distance)
  - **Frontend & UX Improvements**:
    - Initial round setup calls `fitMapToBounds()` with padding instead of hardcoded world view `[20, 0]`.
    - Add a "Focus Match Region" map control button on Leaflet maps so players can quickly snap back to the album's regional view at any point.
    - Optional lobby setting in location setup: `Smart Map Zoom` (`Auto-Region` vs `World View (Classic)`).

- **Filter & Quiz by Country**: Add an alternative photo selection filter based on Country (e.g., "Quiz photos from Japan only").
  - **Immich API & Performance**: Immich natively supports `country` parameter filtering in `POST /search/metadata` and `POST /search/random`. Because filtering is processed server-side via Immich's indexed database, performance is fast and sub-second (< 200ms) even with thousands of photos per country.
  - **Implementation**: Add `list_countries(library_name)` to `ImmichClient`, support `country` in `search_assets`/`search_random_assets` payloads, and add a Country selector in the frontend lobby setup UI.

- **Leaderboard availability**: By ditching scores in leaderboard and using only accuracy, game scores can be shared shown simultaneously independently of the round count.

- **Improve design of round-meta-text**: In the guessing & results screens, the round-meta-text at the top is currently just a simple text line. It should be more prominent and better integrated with the overall design.

- **Better game reveal in album shuffle mode**: Instead of isolated `true-val-banner`, integrate it better in `shuffle-card-guesses`.

---

## 🧹 Code Health & Maintenance

- **Automated E2E Testing**: Add Playwright browser end-to-end tests for two-tap map/timeline interactions.

- **Simplify Immich Client Search & Helper Functions (`src/immich/client.py`)**:
  - **Refactor `search_assets` & `search_random_assets`**: Both functions repeat identical search payload construction (`size`, `albumIds`, `withPartners`, `isShared`, `withExif`). Extract a `_build_search_payload(...)` helper to eliminate repetitive dictionary construction across search endpoints and fallback loops.
  - **Unify Owner ID Extraction (`_asset_owner_id` & `_album_owner_id`)**: Consolidate redundant property lookups (`ownerId` top-level string vs. `owner.id` object) into a common `_extract_owner_id` helper.
  - **Lazy-Load `/users/me` User ID**: In `list_albums`, `search_assets`, and `search_random_assets`, defer fetching `current_user_id` until owner filtering is actually required (e.g., skip `/users/me` HTTP call entirely when `include_shared_albums=True` or when an explicit `album_id` is targeted).
  - **Add Async Context Manager Support (`__aenter__` / `__aexit__`)**: Implement `__aenter__` and `__aexit__` on `ImmichClient` to allow safe, clean usage via `async with ImmichClient(...) as client:`.
  - **Simplify `_filter_assets_by_owner` & Logging Consistency**: Clean up complex nested boolean expressions in `_filter_assets_by_owner` and replace f-strings in `logger.warning` with standard deferred logging args.
- **Uniform map implementation**: Standardize maps to use the same implementation and features everywhere.

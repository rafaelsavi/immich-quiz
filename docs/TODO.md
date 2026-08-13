# Immich Quiz Roadmap & TODO List

This document lists planned features, design ideas, and technical debt items for **Immich Quiz**.

---

## 🚀 Future Feature Concepts

- **Online multiplayer**: Extend pass-and-play local multiplayer to support multi-device real-time lobbies. Design specification defined in docs\next-release-milestone\online-multiplayer

- **Improve Audio Effects / Soundtrack**

- [x] **Smart map zoom**: Dynamically adjust initial pinpoint guess map zoom & framing based on the geographic distribution of photos fetched for the current game session, eliminating tedious manual zooming when playing local/regional albums.
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

- **Add more library filter settings**

- **Player statistics**: TBD

---

## 🧹 Code Health & Maintenance

- **Automated E2E Testing**: Add Playwright browser end-to-end tests for two-tap map/timeline interactions.

- [x] **Uniform map implementation**: Standardize maps to use the same implementation and features everywhere.

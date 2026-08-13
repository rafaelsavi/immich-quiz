# Immich Quiz Roadmap & TODO List

This document lists planned features, design ideas, and technical debt items for **Immich Quiz**.

---

## 🚀 Future Feature Concepts

- **Online multiplayer**: Extend pass-and-play local multiplayer to support multi-device real-time lobbies. Design specification defined in docs\next-release-milestone\online-multiplayer

- **Improve Audio Effects / Soundtrack**

- **Add more library filter settings**
  - **Filter & Quiz by Country**: Add an alternative photo selection filter based on Country (e.g., "Quiz photos from Japan only").
    - **Immich API & Performance**: Immich natively supports `country` parameter filtering in `POST /search/metadata` and `POST /search/random`. Because filtering is processed server-side via Immich's indexed database, performance is fast and sub-second (< 200ms) even with thousands of photos per country.
    - **Implementation**: Add `list_countries(library_name)` to `ImmichClient`, support `country` in `search_assets`/`search_random_assets` payloads, and add a Country selector in the frontend lobby setup UI.

- **Player statistics**: Create a page to show player statistics (best scores, most played modes, etc.)

---

## 🧹 Code Health & Maintenance

- **Automated E2E Testing**: Add Playwright browser end-to-end tests for two-tap map/timeline interactions.

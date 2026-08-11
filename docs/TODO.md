# Immich Quiz Roadmap & TODO List

This document lists planned features, design ideas, and technical debt items for **Immich Quiz**.

---

## 🚀 Future Feature Concepts

- **Multiplayer WebSockets / Remote Play**: Extend pass-and-play local multiplayer to support multi-device real-time lobbies via WebSockets. Use this area to brainstorm ideas.

- **Improve Audio Effects / Soundtrack**

- **Smart map zoom**: For pinpoint location guesses, initial map zoom may may be different than world view depending on the photos fetched for that game.

- **Filter & Quiz by Country**: Add an alternative photo selection filter based on Country (e.g., "Quiz photos from Japan only").
  - **Immich API & Performance**: Immich natively supports `country` parameter filtering in `POST /search/metadata` and `POST /search/random`. Because filtering is processed server-side via Immich's indexed database, performance is fast and sub-second (< 200ms) even with thousands of photos per country.
  - **Implementation**: Add `list_countries(library_name)` to `ImmichClient`, support `country` in `search_assets`/`search_random_assets` payloads, and add a Country selector in the frontend lobby setup UI.

---

## 🧹 Code Health & Maintenance

- **Automated E2E Testing**: Add Playwright browser end-to-end tests for two-tap map/timeline interactions.

- **Simplify Immich Client Search & Helper Functions (`src/immich/client.py`)**:
  - **Refactor `search_assets` & `search_random_assets`**: Both functions repeat identical search payload construction (`size`, `albumIds`, `withPartners`, `isShared`, `withExif`). Extract a `_build_search_payload(...)` helper to eliminate repetitive dictionary construction across search endpoints and fallback loops.
  - **Unify Owner ID Extraction (`_asset_owner_id` & `_album_owner_id`)**: Consolidate redundant property lookups (`ownerId` top-level string vs. `owner.id` object) into a common `_extract_owner_id` helper.
  - **Lazy-Load `/users/me` User ID**: In `list_albums`, `search_assets`, and `search_random_assets`, defer fetching `current_user_id` until owner filtering is actually required (e.g., skip `/users/me` HTTP call entirely when `include_shared_albums=True` or when an explicit `album_id` is targeted).
  - **Add Async Context Manager Support (`__aenter__` / `__aexit__`)**: Implement `__aenter__` and `__aexit__` on `ImmichClient` to allow safe, clean usage via `async with ImmichClient(...) as client:`.
  - **Simplify `_filter_assets_by_owner` & Logging Consistency**: Clean up complex nested boolean expressions in `_filter_assets_by_owner` and replace f-strings in `logger.warning` with standard deferred logging args.

# Immich Quiz Roadmap & TODO List

This document lists planned features, design ideas, and technical debt items for **Immich Quiz**.

---

## 🚀 Future Feature Concepts

- **Multiplayer WebSockets / Remote Play**: Extend pass-and-play local multiplayer to support multi-device real-time lobbies via WebSockets. Use this area to brainstorm ideas.

- **Improve Audio Effects / Soundtrack**

- **Smart map zoom**: For pinpoint location guesses, initial map zoom may may be different than world view depending on the photos fetched for that game.

---

## 🧹 Code Health & Maintenance

- **Automated E2E Testing**: Add Playwright browser end-to-end tests for two-tap map/timeline interactions.

- **Simplify Immich Client Search & Helper Functions (`src/immich/client.py`)**:
  - **Refactor `search_assets` & `search_random_assets`**: Both functions repeat identical search payload construction (`size`, `albumIds`, `withPartners`, `isShared`, `withExif`) and identical owner-filtering post-processing (`_current_user_id` call + `_filter_assets_by_owner`). Extract a `_build_search_payload(...)` helper and standard post-processing helper to streamline both methods.
  - **Unify Owner ID Extraction (`_asset_owner_id` & `_album_owner_id`)**: Consolidate redundant property lookups (`ownerId` top-level string vs. `owner.id` object) into a common `_extract_owner_id` helper.


# Immich Quiz Roadmap & TODO List

This document lists planned features, design ideas, and technical debt items for **Immich Quiz**, sorted by implementation priority and dependencies.

---

## 🚀 Prioritized TODO List

- [x] v2.4.0: **1. Client-Side Routing & Match URLs**
  - [x] Implement History API router (`pushState`, `popstate`) supporting deep links:
    - `/` (Lobby & match setup)
    - `/game/{match_id}` (Active match with state recovery from local/session storage - only while active, otherwise show page informing that it has ended and offer path to summary or homepage)
    - `/game/{match_id}/summary` (Shareable match replay & podium)
    - `/play/{token}` (Challenge entry & player lobby redirect until v3.0)
    - `/stats` (Leaderboard & player statistics redirect to lobby)
  - [x] Add FastAPI backend catch-all route (`/{path:path}` -> `index.html`) so direct URL navigation and page refreshes never return 404.
  - [x] Update PWA Service Worker (`sw.js`) navigation fallback to cache the app shell and handle offline/cached route transitions.
  - [x] Refine in-game navigation guards (intercepting browser back/forward and accidental tab closes during active rounds).

- [ ] v2.4.0: **2. Automated E2E Testing (Playwright)**
  - [ ] Setup Playwright browser test harness integrated with CI and local test runner.
  - [ ] Implement core interactive gameplay test suites:
    - Two-tap Leaflet map pin placement and distance line calculation in Pinpoint mode.
    - Dual-handle timeline range and single-year/month date selection.
    - Album Shuffle photo card reordering and multi-pin placement.
  - [ ] Add route navigation and reload recovery test cases (verifying match state recovers on `/game/{match_id}` refresh).
  - [ ] Add score rollup animation and post-game summary award rendering verification.

- [ ] v2.5.0 **3. Report Map or Date Inconsistencies**
  - [ ] Add "Report Issue" button and modal to the round reveal screen (flag bad GPS coordinates, wrong EXIF date, or face tag).
  - [ ] Store flagged asset records in SQLite (`flagged_assets` table) tracking `asset_id`, `issue_type`, `reported_at`, and optional notes.
  - [ ] Add "Exclude Flagged Photos" toggle in match setup filters to dynamically omit reported assets from candidate pools.
  - [ ] Include direct Immich Web link (`https://<immich-url>/photos/{asset_id}`) in report modal/admin view for quick metadata fixing at the source.

- [ ] v2.6.0 **4. Safety Against Attacks & Media Anti-Cheat**
  - [ ] Implement server-side EXIF/GPS tag stripping on proxied image endpoints (`/media/{asset_id}`) to prevent DevTools inspection cheating in multiplayer.
  - [ ] Add capability token authorization for media assets (verifying the requested asset belongs to an active match or valid challenge).
  - [ ] Configure API rate limiting on match creation, guess submissions, and challenge polling endpoints.
  - [ ] Document Cloudflare Zero Trust path protection rules (protecting `/admin*` and challenge creation via host email, bypassing `/play/*`).

- [ ] v3.0.0 **5. Multiplayer Challenges (Async & Hybrid)**
  - [ ] Implement challenge seed generator and storage (`src/storage/challenge.py`, `src/models.py`) with 128-bit unguessable capability tokens and customizable expiration windows (`1h`, `6h`, `24h`, `48h`, `7d`, `Never`).
  - [ ] Add server-enforced Fog of War on `/api/challenge/*` (strictly withholding opponent scores and pins for round $N$ until the player submits round $N$).
  - [ ] Build Challenge frontend experience (`static/js/modules/challenge.js`):
    - Capability URL landing screen (`/play/{token}`) with player entry.
    - 3-second polling intermission screen with Leaflet pin drop animations as friends finish rounds.
    - Grand reveal comparison screen with multi-player pin scatters, timeline comparisons, and podium.
  - [ ] Add host challenge management modal (view active challenges, copy links, see completion count, cancel early).
  - [ ] Implement periodic background cleanup task in FastAPI lifespan to auto-prune expired challenges.
  - [ ] Specified in [`docs/next-milestones/online-multiplayer`](next-milestones/online-multiplayer/00_OVERVIEW.md).

- [ ] v3.1.0 **6. Player Statistics & Match Replays**
  - [ ] Build dedicated player profile & stats dashboard querying relational data in `data/leaderboard.db`.
  - [ ] Visual accuracy analytics:
    - Distance error distribution histograms (<5 km, 5–50 km, 50–500 km, >500 km).
    - Date accuracy metrics (exact year/month percentage, average day delta).
    - Best score streaks, average response time, and most-played libraries.
  - [ ] Interactive match replay view allowing players to step through past games round-by-round with maps and polaroid cards.

- [ ] v3.2.0 **7. Add Support for Videos**
  - [ ] Integrate Immich video streaming adapter using transcoded preview streams (`/api/asset/video/playback/{id}` or `encoded-video`) instead of raw 4K originals.
  - [ ] Implement in-game video player UI with autoplay, seamless loop, mute/unmute toggle, and poster image fallback.
  - [ ] Update metadata sync and preflight filter to index video duration and ensure video GPS/date metadata validity.
  - [ ] Add setup filter "Media Type" toggle (*Photos Only*, *Videos Only*, *Photos & Videos*).

- [ ] v4.0.0 **8. Multiplayer Live Lounge (Real-Time Synchronous)**
  - [ ] Implement backend room coordinator and WebSocket manager (`src/room/manager.py`, `src/room/websocket.py`) supporting room codes, lobby state broadcasts, and host controls.
  - [ ] Implement WebSocket event pipeline (`LOBBY_UPDATE`, `ROUND_START`, `TIME_TICK`, `LOCK_IN`, `ROUND_REVEAL`, `GAME_OVER`).
  - [ ] Build frontend Live Lounge lobby UI (`static/js/modules/room.js`) with room codes, live player list, and ready-up buttons.
  - [ ] Synchronize live gameplay (`static/js/modules/live_gameplay.js`): player lock-in indicators, server-synced countdown timers, and simultaneous reveal auto-advance.
  - [ ] Add reconnection resilience handling brief network drops and mobile screen locks via session tokens.

- [ ] v4.1.0 **9. Improve Audio Effects & Soundtrack**
  - [ ] Expand runtime Web Audio synthesized procedural background music with game state mood transitions (setup -> tense round -> victory fanfare).
  - [ ] Add transitional sound cues (whoosh screen transitions, high-score chimes, round buzzer variations).
  - [ ] Add volume sliders and audio mute/unmute toggles in settings.
  - [ ] Keep [`static/audio-playground.html`](../static/audio-playground.html) updated with new synth sound design tools.

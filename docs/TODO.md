# Immich Quiz Roadmap & TODO List

This document lists planned features, design ideas, and technical debt items for **Immich Quiz**, sorted by implementation priority and dependencies.

---

## 🚀 Prioritized TODO List

- [x] v3.0.0 **4. Multiplayer Challenges (Async & Hybrid)**
  - [x] Implement challenge seed generator and storage (`src/storage/challenge.py`, `src/models.py`) with 128-bit unguessable capability tokens and customizable expiration windows (`1h`, `6h`, `24h`, `48h`, `7d`, `Never`).
  - [x] Implement server-side EXIF/GPS tag stripping on proxied image endpoints (`/media/{asset_id}`) to prevent DevTools inspection cheating in multiplayer.
  - [x] Add capability token authorization for media assets (verifying the requested asset belongs to an active match or valid challenge).
  - [x] Add server-enforced Fog of War on `/api/challenge/*` (strictly withholding opponent scores and pins for round $N$ until the player submits round $N$).
  - [x] Build Challenge frontend experience (`static/js/modules/challenge.js`):
    - Capability URL landing screen (`/play/{token}`) with player entry.
    - 3-second polling intermission screen with Leaflet pin drop animations as friends finish rounds.
    - Grand reveal comparison screen with multi-player pin scatters, timeline comparisons, and podium.
  - [x] Add host challenge management modal (`static/js/modules/admin.js`) with game mode selection, live preflight validation, 1-click URL sharing, and challenge deactivation.
  - [x] Document Cloudflare Zero Trust path protection rules and Docker security hardening (`docker-compose.example.yml`).
  - [x] Specified in [`docs/next-milestones/online-multiplayer`](next-milestones/online-multiplayer/00_OVERVIEW.md).

- [ ] v3.1.0 **5. Admin Area & Reported Asset Moderation**
  - [ ] Build dedicated admin interface (`/admin` / `static/admin.html`) with authentication/Zero Trust protection.
  - [ ] Review dashboard for flagged/reported assets with detailed issue breakdown (GPS mismatch, incorrect date, face tag, custom notes).
  - [ ] Interactive asset inspection view with side-by-side preview and direct deep links to Immich Web for quick metadata correction.
  - [ ] Moderation workflows: mark issues as resolved, reinstate false alarms, or permanently exclude problematic assets from quiz candidate pools.
  - [ ] Moderation summary metrics (total reports, pending vs. resolved counts, frequent issue categories).

- [ ] v3.2.0 **6. Player Statistics & Match Replays**
  - [ ] Build dedicated player profile & stats dashboard querying relational data in `data/leaderboard.db`.
  - [ ] Visual accuracy analytics:
    - Distance error distribution histograms (<5 km, 5–50 km, 50–500 km, >500 km).
    - Date accuracy metrics (exact year/month percentage, average day delta).
    - Best score streaks, average response time, and most-played libraries.
  - [ ] Interactive match replay view allowing players to step through past games round-by-round with maps and polaroid cards.

- [ ] v3.3.0 **7. Improve Share Functionality & Social Scorecards**

- [ ] v3.4.0 **8. Add Support for Videos**
  - [ ] Integrate Immich video streaming adapter using transcoded preview streams (`/api/asset/video/playback/{id}` or `encoded-video`) instead of raw 4K originals.
  - [ ] Implement in-game video player UI with autoplay, seamless loop, mute/unmute toggle, and poster image fallback.
  - [ ] Update metadata sync and preflight filter to index video duration and ensure video GPS/date metadata validity.
  - [ ] Add setup filter "Media Type" toggle (*Photos Only*, *Videos Only*, *Photos & Videos*).

- [ ] v4.0.0 **9. Multiplayer Live Lounge (Real-Time Synchronous)**
  - [ ] Implement backend room coordinator and WebSocket manager (`src/room/manager.py`, `src/room/websocket.py`) supporting room codes, lobby state broadcasts, and host controls.
  - [ ] Implement WebSocket event pipeline (`LOBBY_UPDATE`, `ROUND_START`, `TIME_TICK`, `LOCK_IN`, `ROUND_REVEAL`, `GAME_OVER`).
  - [ ] Build frontend Live Lounge lobby UI (`static/js/modules/room.js`) with room codes, live player list, and ready-up buttons.
  - [ ] Synchronize live gameplay (`static/js/modules/live_gameplay.js`): player lock-in indicators, server-synced countdown timers, and simultaneous reveal auto-advance.
  - [ ] Add reconnection resilience handling brief network drops and mobile screen locks via session tokens.

- [ ] v4.1.0 **10. Improve Audio Effects & Soundtrack**
  - [ ] Expand runtime Web Audio synthesized procedural background music with game state mood transitions (setup -> tense round -> victory fanfare).
  - [ ] Add transitional sound cues (whoosh screen transitions, high-score chimes, round buzzer variations).
  - [ ] Add volume sliders and audio mute/unmute toggles in settings.
  - [ ] Keep [`static/audio-playground.html`](../static/audio-playground.html) updated with new synth sound design tools.

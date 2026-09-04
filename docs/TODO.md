# Immich Quiz Roadmap & TODO List

This document lists planned features, design ideas, and technical debt items for **Immich Quiz**, sorted by implementation priority and dependencies.

---

## 🚀 Prioritized TODO List

still missing: reveal-actual pinpoint-actual, round-meta, reveal-table, leaflet-control-layers-list, timeout-notice, shuffle-help-btn, shuffle-card-meta, shuffle-reveal-table, timer-head
you should find a smart way of checking simply all components of all pages for this dynamic language conversion, without having to name each one, so that you dont forget in the future.

- [ ] v3.0.1 **Better release strategy**

- [ ] v3.1.0 **Player Statistics & Match Replays**
  - [ ] Build dedicated player profile & stats dashboard querying relational data in `data/leaderboard.db`.
  - [ ] Visual accuracy analytics:
    - Distance error distribution histograms (<5 km, 5–50 km, 50–500 km, >500 km).
    - Date accuracy metrics (exact year/month percentage, average day delta).
    - Best score streaks, average response time, and most-played libraries.
  - [ ] Interactive match replay view allowing players to step through past games round-by-round with maps and polaroid cards.

- [ ] v3.2.0 **Improve Share Functionality & Social Scorecards**

- [ ] v3.3.0 **Add Support for Videos**
  - [ ] Integrate Immich video streaming adapter using transcoded preview streams (`/api/asset/video/playback/{id}` or `encoded-video`) instead of raw 4K originals.
  - [ ] Implement in-game video player UI with autoplay, seamless loop, mute/unmute toggle, and poster image fallback.
  - [ ] Update metadata sync and preflight filter to index video duration and ensure video GPS/date metadata validity.
  - [ ] Add library filter "Media Type" toggle (*Photos Only*, *Videos Only*, *Photos & Videos*).

- [ ] v4.0.0 **Multiplayer Live Lounge (Real-Time Synchronous)**
  - [ ] Implement backend room coordinator and WebSocket manager (`src/room/manager.py`, `src/room/websocket.py`) supporting room codes, lobby state broadcasts, and host controls.
  - [ ] Implement WebSocket event pipeline (`LOBBY_UPDATE`, `ROUND_START`, `TIME_TICK`, `LOCK_IN`, `ROUND_REVEAL`, `GAME_OVER`).
  - [ ] Build frontend Live Lounge lobby UI (`static/js/modules/room.js`) with room codes, live player list, and ready-up buttons.
  - [ ] Synchronize live gameplay (`static/js/modules/live_gameplay.js`): player lock-in indicators, server-synced countdown timers, and simultaneous reveal auto-advance.
  - [ ] Add reconnection resilience handling brief network drops and mobile screen locks via session tokens.

- [ ] v4.1.0 **Improve Audio Effects & Soundtrack**
  - [ ] Expand runtime Web Audio synthesized procedural background music with game state mood transitions (setup -> tense round -> victory fanfare).
  - [ ] Add transitional sound cues (whoosh screen transitions, high-score chimes, round buzzer variations).
  - [ ] Add volume sliders and audio mute/unmute toggles in settings.
  - [ ] Keep [`static/audio-playground.html`](../static/audio-playground.html) updated with new synth sound design tools.

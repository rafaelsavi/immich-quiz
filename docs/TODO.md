# Immich Quiz Roadmap & TODO List

This document lists planned features, design ideas, and technical debt items for **Immich Quiz**, sorted by implementation priority and dependencies.

---

## 🚀 Prioritized TODO List

- [x] v3.1.0 **Player Statistics & Match Replays**
  - [x] Create a new page for player statistics, match replays, leaderboard etc.
  - [x] When entering names, show dropdown of already used names if exists. Used to build up player history and legacy.
  - [x] Build dedicated player profile & stats dashboard querying relational data in `data/leaderboard.db`.
  - [x] Visual accuracy analytics:
    - Symmetrical 4-tier accuracy distribution for Location and Date (Top Tier 90–100%, Great 75–89%, Moderate 50–74%, Low <50%).
    - Date accuracy metrics (exact year/month percentage, exact year percentage, perfect date round count).
    - Lifetime peak match accuracy, podium finishes, average response time, and Game Mode Mastery.
  - [x] Interactive match replay view allowing players to step through past games round-by-round with maps and polaroid cards.

- Phisically block sync from being triggered too often
- review unshuffle mode in replay
- add real home button and move current home to a "game" page; formulate 3 levels of access rights: creator / user / guest:
  - (limited user list) creator can access all
  - (broader user list) user can see players page, replays page, challenges page, but cannot create any game or fetch any image not belonging to an existing game created by creator
  - (public access) guest can only play games it was invited to

- [ ] v3.2.0 **Improve Share Functionality & Social Scorecards**

- [ ] v3.3.0 **Add Support for Videos**
  - [ ] Integrate Immich video streaming adapter using transcoded preview streams (`/api/asset/video/playback/{id}` or `encoded-video`) instead of raw 4K originals.
  - [ ] Implement in-game video player UI with autoplay, seamless loop, mute/unmute toggle, and poster image fallback.
  - [ ] Update metadata sync and preflight filter to index video duration and ensure video GPS/date metadata validity.
  - [ ] Add library filter "Media Type" toggle (*Photos Only*, *Videos Only*, *Photos & Videos*).

- [ ] v3.4.0 **Smart album filtering by person**
  - [ ] Find an elegant way to allow to say "I want all albums where person X and Y appear in at least one photo"

- [ ] v3.5.0 **Improve Audio Effects & Soundtrack**
  - [ ] Expand runtime Web Audio synthesized procedural background music with game state mood transitions (setup -> tense round -> victory fanfare).
  - [ ] Add transitional sound cues (whoosh screen transitions, high-score chimes, round buzzer variations).
  - [ ] Add volume sliders and audio mute/unmute toggles in settings.
  - [ ] Keep [`static/audio-playground.html`](../static/audio-playground.html) updated with new synth sound design tools.

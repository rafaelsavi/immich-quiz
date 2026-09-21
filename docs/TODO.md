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
  - [x] Unified Match Review & Replay Screen: merged summary and replay flows with Winner Podium, Standings Table, and universal 3-tab ReviewDeck (Match Replay, Journey Map, Photo Memories).

- [x] v3.2.0 **User Access Control & RBAC**
  - [x] Three-tier role hierarchy: `Guest < User < Creator`.
    - `Guest`: Can play public challenges (`/play/:token`), nothing else.
    - `User`: Can play games, see player directory & stats (`/players`), and browse match replays (`/replays`).
    - `Creator`: Full access to create games, view raw libraries, sync metadata, and moderate photos.
  - [x] Cloudflare Access integration via `Cf-Access-Authenticated-User-Email` header with configurable `AUTH_MODE`, `CF_CREATOR_EMAILS`, and `CF_USER_EMAILS`.
  - [x] Backward-compatible disabled mode (`AUTH_MODE=disabled`) defaulting to `Creator` for local and offline use.
  - [x] Dedicated Home Landing Card (`#home-card`) with challenge join input and quick links for Guests and Users.
  - [x] Backend role protection dependency (`require_role(min_role)`) returning HTTP 403.
  - [x] Frontend client-side navigation guards with localized alerts and auto-redirect to `/`.
  - [x] Lightweight identity & role badge in header (`GET /api/auth/me`).

- Dark mode missing improvement: accordion-title; date-range-slider; multi-select-dropdown
- dont forget no need for theme "auto". Keep button switch only between light and dark
- [x] player-kpis-grid is too big for what it displays. Make design more compact
- "mode-buttons guess-mode-buttons" should update ranking table the same way it updates preflight

- [ ] v3.3.0 **Improve Share Functionality & Social Scorecards**

- [ ] v3.4.0 **Add Support for Videos**
  - [ ] Integrate Immich video streaming adapter using transcoded preview streams (`/api/asset/video/playback/{id}` or `encoded-video`) instead of raw 4K originals.
  - [ ] Implement in-game video player UI with autoplay, seamless loop, mute/unmute toggle, and poster image fallback.
  - [ ] Update metadata sync and preflight filter to index video duration and ensure video GPS/date metadata validity.
  - [ ] Add library filter "Media Type" toggle (*Photos Only*, *Videos Only*, *Photos & Videos*).

- [ ] v3.5.0 **Improve Audio Effects & Soundtrack**
  - [ ] Expand runtime Web Audio synthesized procedural background music with game state mood transitions (setup -> tense round -> victory fanfare).
  - [ ] Add transitional sound cues (whoosh screen transitions, high-score chimes, round buzzer variations).
  - [ ] Add volume sliders and audio mute/unmute toggles in settings.
  - [ ] Keep [`static/audio-playground.html`](../static/audio-playground.html) updated with new synth sound design tools.

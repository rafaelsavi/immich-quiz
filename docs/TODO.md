# Immich Quiz Roadmap & TODO List

This document lists planned features, design ideas, and technical debt items for **Immich Quiz**.

---

## 🚀 Future Feature Concepts

- **Online Multiplayer (Milestone 1: Challenge Links & Fog-of-War Engine)**: Asynchronous and hybrid multi-device trivia with capability links, customizable expiration windows, server-enforced Fog of War, 3-second polling intermission with animated Leaflet pin drops, and grand reveal map/timeline. Defined in [`docs/next-release-milestone/online-multiplayer`](next-release-milestone/online-multiplayer/00_OVERVIEW.md).
- **Online Multiplayer (Milestone 2: Synchronous Live Lounge)**: Real-time host-controlled lobbies with WebSockets, live countdown timers, and synchronized auto-advance (planned as a future extension).
- **Future-Proof Unified SQLite Persistence**: Clean 4-table schema (`challenges`, `matches`, `match_entries`, `match_round_guesses`) supporting round-by-round replay maps, active response time tracking (`time_taken_seconds`), and all player modes.
- **Improve Audio Effects / Soundtrack**: Expand runtime Web Audio synthesized tracks and transitional sound cues.
- **Player Statistics & Match Replays**: Dedicated view displaying player metrics, all-time best scores, distance accuracy distribution, and round replay maps.
- **PWA & Mobile Haptics**: Make the web app installable as a Progressive Web App (manifest, standalone display, icons) with haptic vibration feedback for mobile map interactions, timeline adjustments, and timer alerts.
- **Safety Against Attacks**: Cloudflare Zero Trust path-based rules, rate limiting, and capability URL security.
- **Change Config Format to YAML**

---

## 🧹 Code Health & Maintenance

- **Automated E2E Testing**: Add Playwright browser end-to-end tests for two-tap map and timeline interactions.

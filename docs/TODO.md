# Immich Quiz Roadmap & TODO List

This document lists planned features, design ideas, and technical debt items for **Immich Quiz**.

---

## 🚀 Active & Planned Milestones

- **Multiplayer challenges**: Asynchronous and hybrid multi-device trivia with capability links, customizable expiration windows, server-enforced Fog of War, 3-second polling intermission with animated Leaflet pin drops, and grand reveal map/timeline. Specified in [`docs/next-milestones/online-multiplayer`](next-milestones/online-multiplayer/00_OVERVIEW.md).
- **Multiplayer live game**: Real-time host-controlled lobbies with WebSockets, live countdown timers, and synchronized auto-advance built on top of the Challenge seed engine.
- **Improve Audio Effects / Soundtrack**: Expand runtime Web Audio synthesized tracks and transitional sound cues.
- **Player Statistics & Match Replays**: Dedicated view displaying player metrics, all-time best scores, distance accuracy distribution, and round replay maps.
- **PWA & Mobile Haptics**: Make the web app installable as a Progressive Web App (manifest, standalone display, icons) with haptic vibration feedback for mobile map interactions, timeline adjustments, and timer alerts.
- **Safety Against Attacks**: Cloudflare Zero Trust path-based rules, rate limiting, and capability URL security.
- **Add support for videos**
- **Add option to report map or date inconsistencies in round reveal**
- **Adaptive scoring**:
  - [x] **Phase 1 (Pool-Aware Dynamic Decay)**: Automatically calculates spatial ($\text{decay\_km}$) and temporal ($\text{decay\_days}$) decay rates from the active candidate pool bounds ($D_{\text{span}}$ and $\Delta T_{\text{days}}$) so city walks and vacation albums reward localized precision.
  - [ ] **Phase 2 (Album Shuffle Inversions)**: Partial credit for timeline permutation ordering (Kendall Tau distance) and spatial pin proximity.
  - [ ] **Phase 3 (Speed & Momentum)**: Optional accuracy-scaled speed bonuses and combo streak multipliers.

---

## 🧹 Code Health & Maintenance

- **Automated E2E Testing**: Add Playwright browser end-to-end tests for two-tap map and timeline interactions.

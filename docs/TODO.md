# Immich Quiz Roadmap & TODO List

This document lists planned features, design ideas, and technical debt items for **Immich Quiz**.

---

## 🚀 Future Feature Concepts

- **Online multiplayer**: Extend pass-and-play local multiplayer to support multi-device real-time lobbies. Design specification defined in `docs\next-release-milestone\online-multiplayer`
- **Improve Audio Effects / Soundtrack**
- **Add more library filter settings**: Design specification defined in `docs\next-release-milestone\library-filters`
- **Player statistics**: Create a page to show player statistics (best scores, most played modes, etc.)
- **PWA & Mobile Haptics**: Make the web app installable as a Progressive Web App (manifest, standalone display, icons) with haptic vibration feedback for mobile map interactions, timeline adjustments, and timer alerts.
- **Safety against attacks**: Protect against attacks from malicious or accidental participants.

---

## 🧹 Code Health & Maintenance

- **Automated E2E Testing**: Add Playwright browser end-to-end tests for two-tap map/timeline interactions.

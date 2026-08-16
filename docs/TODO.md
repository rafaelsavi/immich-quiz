# Immich Quiz Roadmap & TODO List

This document lists planned features, design ideas, and technical debt items for **Immich Quiz**.

---

## 🚀 Future Feature Concepts

- **Online multiplayer**: Extend pass-and-play local multiplayer to support multi-device real-time lobbies with WebSockets. Design specification defined in [`docs/next-release-milestone/online-multiplayer`](file:///d:/Rafael/Projects/immich-quiz/docs/next-release-milestone/online-multiplayer).
- **Improve Audio Effects / Soundtrack**: Expand runtime Web Audio synthesized tracks and transitional sound cues.
- **Player statistics**: Dedicated view displaying player metrics, all-time best scores, accuracy distribution, and favorite game modes.
- **PWA & Mobile Haptics**: Make the web app installable as a Progressive Web App (manifest, standalone display, icons) with haptic vibration feedback for mobile map interactions, timeline adjustments, and timer alerts.
- **Safety against attacks**: Rate limiting and payload sanitation against malicious participants.
- **Change config format to yaml**

---

## 🧹 Code Health & Maintenance

- **Automated E2E Testing**: Add Playwright browser end-to-end tests for two-tap map and timeline interactions.

# Online Multiplayer ("Player Mode") — Architecture & Roadmap Overview

## 1. What This Feature Is

Immich Quiz expands from a single-device **local pass-and-play** trivia game into a multi-device multiplayer platform.

We introduce two multiplayer paradigms built on a single unified data foundation:

1. **Challenge Links (Asynchronous & Hybrid Multiplayer — Milestone 1)**
   - **How it works:** An admin generates a match seed with an unguessable capability URL (e.g. `https://quiz.example.com/play/ch_9f8e2a...`) and a customizable expiration window (e.g., 6h, 24h, 7d, or Never).
   - **Asynchronous Play:** Friends can open the link anytime during the window on their phone or desktop and play through the rounds at their own pace.
   - **Hybrid "Socially Synced" Play:** Friends jump on a Discord/voice call and all click the same link. An **Intermission Screen with 3-second polling** shows friend's pins dynamically dropping on the map as they finish each round.
   - **Anti-Cheat / Fog of War:** Server strictly withholds opponent answers for Round $N$ until the player has submitted their own Round $N$ guess.
   - **Grand Reveal Screen:** Final podium, round-by-round interactive Leaflet multi-pin scatter map, and horizontal date guess timeline.

2. **The Live Lounge (Synchronous Multiplayer — Milestone 2, Future Extension)**
   - **How it works:** Real-time host-controlled lobby with WebSockets, live countdown timers, and synchronized auto-advance (Jackbox / Kahoot style). Built directly on top of the Milestone 1 Challenge seed engine.

---

## 2. Architecture Rules (DO NOT VIOLATE)

1. **Additive & Backward-Compatible:** Existing single-player and pass-and-play local game modes must continue working unchanged.
2. **Unified Relational Persistence (Day 1 Clean Schema):** Because SQLite persistence is unreleased, we implement the complete 4-table relational schema (`challenges`, `matches`, `match_entries`, `match_round_guesses`) directly without legacy migration shims.
3. **Stateless First (Milestone 1):** Challenge Links use standard HTTP REST + SQLite. No persistent socket connections, zero connection drops when mobile screens lock, zero memory leaks.
4. **Server-Authoritative & Secure:** The server validates answer scoring. Capability tokens protect private matches. Thumbnails proxied through FastAPI strip all EXIF/GPS metadata before reaching the browser.
5. **No New Heavy Dependencies:** Standard Python standard library (`sqlite3`, `secrets`, `dataclasses`, `uuid`) and FastAPI.

---

## 3. Column Semantics Matrix Across All Player Modes

| Column | Local (Pass & Play) | Challenge Link (Async / Hybrid) | Live Room (Sync) |
| :--- | :--- | :--- | :--- |
| **`matches.play_mode`** | `'local'` | `'challenge'` | `'room'` |
| **`matches.challenge_id`** | `NULL` | Links to `challenges.challenge_id` | Links to `challenges.challenge_id` |
| **`matches.duration_seconds`** | Total game wall-clock time | Total player attempt duration | Total live room duration |
| **`match_entries.total_time_seconds`** | Sum of player's active turn times | Sum of player's active answer times (Fair tiebreaker) | Sum of player's active answer times |
| **`match_round_guesses.time_taken_seconds`** | Active seconds from question render to "Submit" | Active seconds from question render to "Submit" | Active seconds from question render to "Submit" |
| **`challenges.expires_at`** | `NULL` | ISO8601 UTC (Customizable) or `NULL` (Never) | Session TTL |

> [!NOTE]
> **Active Response Time vs. Wall-Clock Duration:** `time_taken_seconds` is recorded client-side as active seconds spent on the question screen. If a player pauses for 15 minutes on the intermission screen, their active score time is unaffected.

---

## 4. Cloudflare Zero Trust & Network Security

```
                  [ Public Internet / Friends ]
                               │
               (HTTPS) quiz.yourdomain.com
                               │
                ▼                             ▼
       /admin* or /create*            /play/* or /media/*
      ┌─────────────────────┐       ┌───────────────────────┐
      │  Cloudflare Access  │       │   Cloudflare Access   │
      │   (Email: Host)     │       │ Bypass (Everyone)     │
      └──────────┬──────────┘       └───────────┬───────────┘
                 │                              │
                 └──────────────┬───────────────┘
                                │ (Cloudflare Tunnel)
                                ▼
                   ┌─────────────────────────┐
                   │  Docker: immich-quiz    │
                   │  (Unprivileged User)    │
                   └────────────┬────────────┘
                                │ (Internal Docker Network)
                                ▼
                   ┌─────────────────────────┐
                   │  Docker: immich-server  │
                   │  (Locked from Public)   │
                   └─────────────────────────┘
```

- **/admin\* and /api/challenge/create:** Cloudflare Access policy set to `Allow` (Include: Host Email). Only the server owner can generate challenges.
- **/play\* and /api/challenge/\*:** Cloudflare Access policy set to `Bypass`. Unguessable 128-bit capability tokens (`/play/{token}`) protect challenge confidentiality with zero login friction for friends.
- **Image Proxying:** Images are served via `/media/{asset_id}` which validates that the asset belongs to an active match or valid challenge, and Immich preview generation strips EXIF/GPS tags.

---

## 5. Implementation Phases Roadmap

### Milestone 1: Challenge Links & Fog-of-War Engine (Active Implementation)

- **[Phase 1: Storage & Models](01_PHASE_CHALLENGE_STORAGE.md)** (`src/storage/leaderboard.py`, `src/models.py`)
  - Clean 4-table SQLite schema (`challenges`, `matches`, `match_entries`, `match_round_guesses`).
  - `ChallengeStore` with challenge creation, player attempt recording, and Fog-of-War query helpers.
- **[Phase 2: REST API Routes](02_PHASE_CHALLENGE_API.md)** (`src/api/challenge_routes.py`, `src/api/routes.py`)
  - Endpoints: `POST /api/challenge/create`, `GET /api/challenge/{token}`, `POST /api/challenge/{token}/start`, `GET /api/challenge/{token}/question/{round}`, `POST /api/challenge/{token}/answer`, `GET /api/challenge/{token}/leaderboard`.
  - Media asset authorization check for challenge assets.
- **[Phase 3: Frontend Challenge Experience](03_PHASE_CHALLENGE_FRONTEND.md)** (`static/js/modules/challenge.js`, `static/index.html`, `static/css/`)
  - Capability route handler (`/play/{token}` or `#challenge={token}`).
  - Player entry lobby screen.
  - Intermission Screen with 3s polling and animated Leaflet opponent pin drops.
  - Grand Reveal summary (Podium, interactive round-by-round Leaflet guess scatter plot, horizontal date timeline).
- **[Phase 4: Admin Creator & Security Hardening](04_PHASE_ADMIN_AND_SECURITY.md)**
  - Admin Challenge Creator UI with customizable expiration dropdown (`1h`, `6h`, `24h`, `48h`, `7d`, `Never`).
  - Cloudflare Tunnel and Zero Trust configuration guide.

### Milestone 2: Synchronous Live Lounge (Future Extension)

- **[Phase 5: Backend Room Coordinator](05_PHASE_BACKEND_ROOM.md)** (`src/room/manager.py`, `src/room/websocket.py`)
- **[Phase 6: Room Routes & Events](06_PHASE_BACKEND_ROOM_ROUTES.md)** (`src/api/room_routes.py`)
- **[Phase 7: Frontend Room UI](07_PHASE_FRONTEND_ROOM_UI.md)** (`static/js/modules/room.js`)
- **[Phase 8: Frontend Live Gameplay](08_PHASE_FRONTEND_LIVE_GAMEPLAY.md)** (`static/js/app.js`)
- **[Phase 9: Reconnection & Polish](09_PHASE_RECONNECTION_POLISH.md)**


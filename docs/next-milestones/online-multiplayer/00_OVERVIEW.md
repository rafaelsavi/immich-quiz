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
| **`matches.play_mode`** | `PlayMode.local` (`'local'`) | `PlayMode.challenge` (`'challenge'`) | `PlayMode.room` (`'room'`) |
| **`matches.challenge_id`** | `NULL` | Links to `challenges.challenge_id` | Links to `challenges.challenge_id` |
| **`matches.room_id`** | `NULL` | `NULL` | Unique Room UUID4 session ID |
| **`matches.room_name`** | `NULL` | `NULL` | Optional Room display name |
| **`matches.duration_seconds`** | Total game wall-clock time | Total player attempt duration | Total live room duration |
| **`match_entries.total_time_seconds`** | Sum of player's active turn times | Sum of player's active answer times (Fair tiebreaker) | Sum of player's active answer times |
| **`match_round_guesses.photo_index`** | `0` (Pinpoint) / `0, 1, 2` (Album Shuffle) | `0` (Pinpoint) / `0, 1, 2` (Album Shuffle) | `0` (Pinpoint) / `0, 1, 2` (Album Shuffle) |
| **`match_round_guesses.time_taken_seconds`** | Active seconds from question render to "Submit" | Active seconds from question render to "Submit" | Active seconds from question render to "Submit" |
| **`challenges.title`** | `NULL` | Custom challenge title (or auto fallback) | Custom challenge title (or room name) |
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

## 5. Multiplayer Implementation Roadmap

The online multiplayer evolution is organized into two sequential upcoming stages built on top of the completed v2.0.0 foundation:

---

### [🚀 Stage 1: Active Milestone — Challenge Mode (Asynchronous & Hybrid Multiplayer)](stage-1-challenge-mode/01_PHASE_CHALLENGE_STORAGE.md)

- **Goal:** Shareable capability URLs, server-enforced Fog of War, and 3s polling intermission.

- **[Phase 1: Storage & Models](stage-1-challenge-mode/01_PHASE_CHALLENGE_STORAGE.md)** (`src/storage/challenge.py`, `src/models.py`): `ChallengeStore`, capability tokens, expiration checks, player attempt records.
- **[Phase 2: REST API Routes](stage-1-challenge-mode/02_PHASE_CHALLENGE_API.md)** (`src/api/challenge_routes.py`): `/api/challenge/*` endpoints, server-side Fog-of-War answer filtering, media asset authorization.
- **[Phase 3: Frontend Challenge Experience](stage-1-challenge-mode/03_PHASE_CHALLENGE_FRONTEND.md)** (`static/js/modules/challenge.js`): Capability URL entry point (`/play/{token}`), player entry lobby, 3s polling intermission with Leaflet pin drops, grand reveal comparison.
- **[Phase 4: Admin Creator & Security Hardening](stage-1-challenge-mode/04_PHASE_ADMIN_AND_SECURITY.md)**: "Create Challenge" modal with expiration options (`1h`, `6h`, `24h`, `48h`, `7d`, `Never`), Cloudflare Zero Trust deployment guide.

---

### Stage 2: Future Extension — Synchronous Live Lounge (Real-Time WebSockets)

- **Goal:** Real-time host-controlled lobby, synchronized timers, and simultaneous auto-advance.

- **[Phase 5: Backend Room Coordinator](stage-2-live-room/05_PHASE_BACKEND_ROOM.md)** (`src/room/manager.py`, `src/room/websocket.py`): Room manager, WebSocket connection pool, broadcast channels.
- **[Phase 6: Room Routes & Events](stage-2-live-room/06_PHASE_BACKEND_ROOM_ROUTES.md)** (`src/api/room_routes.py`): Join codes, REST & WebSocket events (`LOBBY_UPDATE`, `ROUND_START`, `TIME_TICK`, `ROUND_REVEAL`, `GAME_OVER`).
- **[Phase 7: Frontend Room UI](stage-2-live-room/07_PHASE_FRONTEND_ROOM_UI.md)** (`static/js/modules/room.js`): Lobby room code, player list, ready-up buttons, host controls.
- **[Phase 8: Frontend Live Gameplay](stage-2-live-room/08_PHASE_FRONTEND_LIVE_GAMEPLAY.md)** (`static/js/modules/live_gameplay.js`): Synchronized countdowns, lock-in states, auto-advancing reveal screen.
- **[Phase 9: Reconnection & Polish](stage-2-live-room/09_PHASE_RECONNECTION_POLISH.md)**: Heartbeats, reconnection tokens, mobile sleep recovery, host migration.

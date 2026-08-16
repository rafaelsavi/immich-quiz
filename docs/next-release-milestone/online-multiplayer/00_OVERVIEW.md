# Online Multiplayer ("Player Mode") — Overview

## What This Feature Is

Immich Quiz is currently a local **pass-and-play** game where all players share one device. We are adding an **online mode** where each player connects from their own device via WebSockets.

The user chooses a "Player Mode" in the setup screen:
- **Local** — existing pass-and-play (unchanged)
- **Online** — host creates a room, guests join via a short code, everyone plays simultaneously on separate devices

## Key Terminology

- **Game Room**: A persistent lobby with a short join code (e.g. `A3K9`). Survives across multiple matches.
- **Host**: Creates the room, controls settings, starts matches.
- **Guest**: Joins via code. Can toggle "Ready".
- **Lobby**: Pre-match state where players gather.
- **Match**: A single game (N rounds) inside a room. Multiple matches can run sequentially in the same room.

## Architecture Rules (DO NOT VIOLATE)

1. **Additive only.** The existing REST endpoints, `GameService`, `SessionStore`, `scoring.py`, and game mode engines (`PinpointEngine`, `AlbumShuffleEngine`) must NOT be modified. Online mode adds a new coordination layer on top.
2. **Hybrid REST + WebSocket.** Game actions (setup, question, answer, result) use the existing REST API. WebSocket is ONLY for real-time notifications/events (player joined, round complete, etc.).
3. **Server-authoritative.** The server owns all game state. Clients are display-only. No answer data ever goes through WebSocket.
4. **No new dependencies.** FastAPI has native WebSocket support via Starlette. No new pip packages needed.

## Existing Codebase Structure (For Reference)

```
src/
├── main.py              # App factory, lifespan, static mount
├── config.py            # AppSettings from env vars
├── models.py            # Pydantic request/response models
├── scoring.py           # Pure scoring functions (DO NOT MODIFY)
├── version.py           # Version string
├── game/
│   ├── __init__.py      # Package exports
│   ├── modes.py         # BaseGameModeEngine, PinpointEngine, AlbumShuffleEngine, GameModeRegistry (DO NOT MODIFY)
│   ├── selector.py      # Asset selection with diversity filters (DO NOT MODIFY)
│   └── service.py       # GameService: orchestrates setup, questions, answers, results (DO NOT MODIFY)
├── api/
│   └── routes.py        # All REST API endpoints (DO NOT MODIFY)
├── immich/
│   └── client.py        # Immich HTTP client (DO NOT MODIFY)
└── storage/
    ├── db.py            # SQLite DatabaseManager connection lifecycle (DO NOT MODIFY)
    ├── metadata.py      # MetadataStore local index (DO NOT MODIFY)
    ├── sync.py          # SyncEngine background indexing (DO NOT MODIFY)
    ├── session.py       # SessionStore, MatchState, QuestionState (DO NOT MODIFY)
    └── leaderboard.py   # SQLite leaderboard persistence (DO NOT MODIFY)

static/
├── index.html           # Main HTML (WILL BE MODIFIED)
├── js/
│   ├── app.js           # Main app controller (WILL BE MODIFIED)
│   └── modules/
│       ├── state.js     # Centralized app state (WILL BE MODIFIED)
│       ├── api.js       # REST client helper (unchanged)
│       ├── i18n.js      # Translations EN/PT (WILL BE MODIFIED - add strings)
│       ├── maps.js      # Leaflet map logic (unchanged)
│       ├── audio.js     # Sound effects (unchanged)
│       ├── effects.js   # Confetti/animations (unchanged)
│       ├── formatters.js# Display helpers (unchanged)
│       ├── leaderboard.js# Leaderboard UI (unchanged)
│       └── modes/
│           ├── pinpoint.js      # Pinpoint mode UI (unchanged)
│           ├── album_shuffle.js # Album Shuffle mode UI (unchanged)
│           └── common.js        # Shared mode helpers (unchanged)
├── css/
│   ├── style.css        # Master CSS import (WILL BE MODIFIED - add import)
│   ├── base/            # Reset, variables, layout (unchanged)
│   ├── components/      # Buttons, cards, maps, modals, leaderboard (unchanged)
│   └── modes/           # Pinpoint, album_shuffle styles (unchanged)
```

## Implementation Phases

This feature is split into **5 sequential phases**. Each phase is a self-contained document. Complete them in order:

1. **Phase 1**: Backend room infrastructure (`src/room/`)
2. **Phase 2**: Backend room API routes (`src/api/room_routes.py`)
3. **Phase 3**: Frontend room UI (HTML + CSS + room.js)
4. **Phase 4**: Frontend online gameplay integration (app.js wiring)
5. **Phase 5**: Reconnection, edge cases, polish

Each phase document contains:
- Exact files to create or modify
- Complete code structure with signatures
- Inline context from existing code where needed
- Acceptance criteria

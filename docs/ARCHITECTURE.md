# Architecture

## Local-First Design

- Backend: FastAPI with async endpoints, served by Uvicorn.
- Frontend: static HTML/CSS/JS with Leaflet (no build step).
- Session persistence: in-memory for active games.
- Historical persistence: CSV file for leaderboard rows.

---

## Module Map

```
immich-quiz/
├── src/
│   ├── main.py          App factory and lifespan. Creates ImmichClient,
│   │                    SessionStore, and LeaderboardStore; validates Immich
│   │                    access on startup; mounts static files and routes.
│   ├── config.py        AppSettings dataclass. Parses and validates all env
│   │                    vars at startup; raises ConfigError on bad input.
│   ├── models.py        Pydantic request/response models for all endpoints.
│   ├── scoring.py       Pure scoring functions: haversine_km, location_score,
│   │                    date_diff_days, date_score, timeline_inversion_score,
│   │                    batch_location_match_score, accuracy_pct.
│   ├── game/            Modular game mode system and session orchestration.
│   │   ├── modes.py     GameMode abstract base, PinpointGameMode,
│   │   │                AlbumShuffleGameMode, and GameModeRegistry.
│   │   ├── selector.py  Candidate asset selection, spatial (≥100m) & temporal (≥60s)
│   │   │                diversity filters.
│   │   └── service.py   GameService managing match state, question drawing,
│   │                    and answer scoring.
│   ├── api/
│   │   └── routes.py    All API endpoints. Depends on SessionStore,
│   │                    ImmichClient, and LeaderboardStore via FastAPI DI.
│   ├── immich/
│   │   └── client.py    ImmichClient adapter. Wraps httpx AsyncClient.
│   │                    Provides: validate_access, list_albums, search_assets,
│   │                    search_random_assets, get_asset_bytes.
│   └── storage/
│       ├── session.py   In-memory state. SessionStore holds MatchState objects.
│       └── leaderboard.py LeaderboardStore appends and reads rows from CSV.
└── static/              Vanilla HTML/CSS/JS frontend.
    ├── index.html       Main quiz application HTML.
    ├── audio-playground.html Interactive Web Audio testing playground page.
    ├── js/app.js        Main application controller & UI router.
    ├── js/audio-playground.js Playground controller & visualizer logic.
    └── js/modules/      Modular ES modules:
        ├── modes/       Game mode UI controllers (pinpoint.js, album_shuffle.js, common.js).
        ├── api.js       API HTTP request client.
        ├── audio.js     Zero-dependency Web Audio sound synthesizer engine.
        ├── effects.js   Canvas confetti, animations, and visual transitions.
        ├── formatters.js Distance/date formatters and string helpers.
        ├── i18n.js      Multi-language translation engine (EN/PT) with live switcher.
        ├── leaderboard.js Leaderboard UI rendering and filtering.
        ├── maps.js      Leaflet map wrapper, marker placement, and auto-zoom.
        └── state.js     Centralized reactive application state store.
```

---

## Round Data Flow

```
GET /api/ui-config
  └── Returns max image height, language, max score settings to frontend

POST /api/game/preflight
  └── Validates asset pool eligibility (location/date/date-range requirements)
  └── Confirms eligible photo count >= requested round count

POST /api/game/setup
  └── routes.py resolves album name from ImmichClient
  └── Creates MatchState in SessionStore (players, round config, empty rounds)
  └── Returns match_id and total turns

POST /api/question
  └── routes.py dispatches through GameModeRegistry to active GameMode
  └── Draws candidate asset(s) using selector.py with diversity constraints:
      - Location distance >= 0.1 km (100m) using haversine_km
      - Time separation >= 60 seconds using capture_datetime
  └── Creates QuestionState with full RoundAsset (lat/lon/date) stored server-side
  └── Returns sanitized QuestionResponse (no coordinates, no capture dates)

GET /api/media/{asset_id}
  └── routes.py verifies asset_id was issued in a live match (rejects any other)
  └── Calls ImmichClient.get_asset_bytes → proxies preview thumbnail bytes
  └── Browser never contacts Immich directly

POST /api/answer
  └── routes.py looks up QuestionState
  └── Dispatches to active GameMode score_answer method
  └── Stores guess + scores in QuestionState
  └── Returns acknowledgement only (no answer data)

POST /api/round/result
  └── routes.py checks all players in round have answered (409 if not)
  └── Returns actual coordinates, actual date, actual location, all guesses, per-player scores
```

---

## Game Mode Extensibility Architecture

Game modes implement the `GameMode` abstract interface in `src/game/modes.py`:

- `name`: Unique mode identifier (`"pinpoint"`, `"album_shuffle"`).
- `prepare_question(...)`: Generates single or batch question payloads.
- `score_answer(...)`: Evaluates player answers using mode-specific scoring algorithms.
- `evaluate_awards(...)`: Determines eligibility for performance badges (**Sniper**, **Time Traveler**, **Speed Demon**).

New game modes can be added by implementing `GameMode` and registering them with `@GameModeRegistry.register`.

---

## Anti-Cheat Boundary

The answer data boundary is enforced entirely inside `storage/session.py`.
`QuestionState` holds the `RoundAsset` (actual latitude, longitude, capture
date) in-memory and never exposes it through the question or answer responses.

| Endpoint                 | Returns answer data?                                           |
|--------------------------|----------------------------------------------------------------|
| `POST /api/question`     | No — stripped by `routes.py` before response                   |
| `GET /api/media/…`       | No — proxy bytes carry no EXIF/GPS (Immich preview re-encodes) |
| `POST /api/answer`       | No — acknowledgement only                                      |
| `POST /api/round/result` | Yes — only after every player in the round has answered        |

---

## Startup Validation

`main.py` calls `ImmichClient.validate_access` for every configured library
key during the lifespan startup phase. Keys that fail are excluded from
`/api/libraries` and reported in the `unavailable` field; the app continues
with the remaining keys rather than refusing to start.

---

## Future Migration

- All runtime config flows through `AppSettings` (env vars only).
- No hardcoded paths outside configurable defaults.
- Moving the folder to a dedicated repository requires only adding a
  `Dockerfile`. See [MIGRATION.md](MIGRATION.md).

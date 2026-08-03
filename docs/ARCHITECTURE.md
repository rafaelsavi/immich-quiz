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
│   │                    date_diff_days, date_score, accuracy_pct.
│   ├── api/
│   │   └── routes.py    All API endpoints. Depends on SessionStore,
│   │                    ImmichClient, and LeaderboardStore via FastAPI DI.
│   ├── immich/
│   │   └── client.py    ImmichClient adapter. Wraps httpx AsyncClient.
│   │                    Provides: validate_access, list_albums, search_assets,
│   │                    search_random_assets, get_asset_bytes.
│   │                    One shared AsyncClient per app instance (connection
│   │                    pooling). All Immich calls are made here; no other
│   │                    module calls Immich directly.
│   └── storage/
│       ├── session.py   In-memory state. SessionStore holds MatchState objects
│       │                keyed by match_id. MatchState owns the round list,
│       │                player rotation, and QuestionState per turn.
│       │                QuestionState holds the answer data (RoundAsset) and
│       │                the player's submitted guess + computed scores.
│       └── leaderboard.py LeaderboardStore appends and reads rows from a CSV
│                            file using the exact required schema.
└── static/              Vanilla HTML/CSS/JS frontend.
    ├── index.html       Main quiz application HTML.
    ├── audio-playground.html Interactive Web Audio testing playground page.
    ├── js/app.js        Main application controller & UI router.
    ├── js/audio-playground.js Playground controller & visualizer logic.
    └── js/modules/      ES modules (api, state, leaderboard, map, quiz, audio, setup, i18n, formatters).
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
  └── routes.py looks up MatchState by match_id
  └── Draws candidate asset(s) using _select_round_asset (Pinpoint) or
      _select_batch_round_assets (Album Shuffle)
  └── Evaluates candidate assets with _is_asset_valid_for_batch against
      previously played match assets (and batch items):
      - Location distance >= 0.1 km (100m) using haversine_km (when location_mode is active)
      - Time separation >= 60 seconds using capture_datetime (when date_mode is active)
      - Graceful fallback if pool is constrained
  └── Creates QuestionState with full RoundAsset (lat/lon/date) stored server-side
  └── Returns sanitized QuestionResponse — no coordinates, no capture date

GET /api/media/{asset_id}
  └── routes.py verifies asset_id was issued in a live match (rejects any other)
  └── Calls ImmichClient.get_asset_bytes → proxies preview thumbnail bytes
  └── Browser never contacts Immich directly

POST /api/answer
  └── routes.py looks up QuestionState
  └── Calls scoring.py: location_score, date_diff_days, date_score
  └── Stores guess + scores in QuestionState
  └── Returns acknowledgement only (no answer data)

POST /api/round/result
  └── routes.py checks all players in round have answered (409 if not)
  └── Returns actual coordinates, actual date, actual location, all guesses, per-player scores
```

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

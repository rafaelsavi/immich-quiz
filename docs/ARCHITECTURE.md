# Architecture

## Local-First Design

- Backend: FastAPI with async endpoints, served by Uvicorn.
- Frontend: static HTML/CSS/JS with Leaflet (no build step).
- Session persistence: in-memory for active games.
- Historical persistence: SQLite databases (`data/metadata.db` for metadata cache, `data/leaderboard.db` for player match history).

---

## Module Map

```
immich-quiz/
├── src/
│   ├── main.py          App factory and lifespan. Creates ImmichClient,
│   │                    SessionStore, MetadataStore, and LeaderboardStore;
│   │                    validates Immich access on startup; mounts static files and routes.
│   ├── config.py        AppSettings dataclass. Parses and validates all env
│   │                    vars at startup; raises ConfigError on bad input.
│   ├── models.py        Pydantic request/response models for all endpoints.
│   ├── scoring.py       Pure scoring functions: haversine_km, location_score,
│   │                    date_diff_days, date_score, batch_strict_location_score,
│   │                    batch_strict_date_score, accuracy_pct.
│   ├── game/            Modular game mode system and session orchestration.
│   │   ├── modes.py     BaseGameModeEngine, PinpointEngine,
│   │   │                AlbumShuffleEngine, and GameModeRegistry.
│   │   ├── selector.py  Candidate asset selection, spatial (≥100m) & temporal (≥60s)
│   │   │                diversity filters, and least-played prioritization.
│   │   └── service.py   GameService managing match state, question drawing,
│   │                    preflight checks, and answer scoring.
│   ├── api/
│   │   └── routes.py    All API endpoints. Depends on SessionStore,
│   │                    ImmichClient, MetadataStore, and LeaderboardStore via FastAPI DI.
│   ├── immich/
│   │   └── client.py    ImmichClient adapter. Wraps httpx AsyncClient.
│   │                    Provides: validate_access, list_albums, search_assets,
│   │                    search_random_assets, list_people, get_timeline_bounds, get_asset_bytes.
│   └── storage/
│       ├── db.py        DatabaseManager for SQLite connection lifecycle and WAL mode.
│       ├── metadata.py  MetadataStore with indexed relational schema, query parity
│       │                builder, filter options extraction, and asset pruning/invalidation.
│       ├── sync.py      SyncEngine for asynchronous background indexing from Immich.
│       ├── session.py   In-memory state. SessionStore holds MatchState objects.
│       └── leaderboard.py LeaderboardStore appends and reads rows from SQLite.
└── static/              Vanilla HTML/CSS/JS frontend.
    ├── index.html       Main quiz application HTML.
    ├── audio-playground.html Interactive Web Audio testing playground page.
    ├── css/             Modular CSS stylesheets:
    │   ├── style.css    Master entrypoint (@importing base, components, modes).
    │   ├── base/        Design tokens (variables.css), resets (reset.css), app shell (layout.css).
    │   ├── components/  UI components (buttons.css, cards.css, maps.css, leaderboard.css, modals.css, multi_select.css, range_slider.css, filters.css).
    │   └── modes/       Game mode styles (pinpoint.css, album_shuffle.css).
    ├── js/app.js        Main application controller & UI router.
    ├── js/audio-playground.js Playground controller & visualizer logic.
    └── js/modules/      Modular ES modules:
        ├── components/  Reusable UI components:
        │   ├── multi_select.js Searchable tag-based multi-select with select-all/clear.
        │   └── range_slider.js Dual-handle Year-Month range slider.
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
  └── Returns max image height, language, max score settings, and version to frontend

GET /api/sync/status?library_name={name}
  └── Returns current synchronization status, total asset count, and synced asset progress

POST /api/sync?library_name={name}
  └── Triggers background asynchronous metadata sync from Immich to SQLite

GET /api/filters?library_name={name}
  └── Returns timeline date bounds, countries, cities (with country mapping), and people for library
  └── Queries local SQLite metadata index when populated (instant response); falls back to Immich API
  └── Backed by in-memory TTLCache (5-minute TTL) on the server
  └── Frontend hydrates multi-selects and range slider; restores per-library localStorage

POST /api/game/preflight
  └── Validates asset pool eligibility against active filters (albums, date range, countries, cities, people)
  └── Evaluates fast indexed SQLite query (or sampling fallback) with identical query clauses
  └── Enforces people matching mode (OR / AND)
  └── Confirms eligible photo count >= requested round count

POST /api/game/setup
  └── routes.py resolves album names and active filter parameters
  └── Creates MatchState in SessionStore (players, round config, filter criteria, empty rounds)
  └── Pre-computes match bounding box for smart map auto-zoom
  └── Returns match_id, total turns, and map_bounds

POST /api/question
  └── routes.py dispatches through GameModeRegistry to active GameMode
  └── Draws candidate asset(s) using selector.py backed by MetadataStore with diversity constraints:
      - Location distance >= 0.1 km (100m) using haversine_km
      - Time separation >= 60 seconds using capture_datetime
      - Prioritizes unplayed / least-played photos (times_played ASC)
  └── Creates QuestionState with full RoundAsset (lat/lon/date) stored server-side
  └── Returns sanitized QuestionResponse (no coordinates, no capture dates)

GET /api/media/{asset_id}
  └── routes.py verifies asset_id was issued in a live match (rejects any other)
  └── Calls ImmichClient.get_asset_bytes → proxies preview thumbnail bytes
  └── If asset fails to load, marks asset invalid in SQLite metadata index
  └── Browser never contacts Immich directly

POST /api/answer
  └── routes.py looks up QuestionState
  └── Dispatches to active GameMode evaluate_and_apply_answer method
  └── Stores guess + scores in QuestionState
  └── If match is completed, writes full match entry and awards to SQLite leaderboard
  └── Returns acknowledgement only (no answer data)

POST /api/round/result
  └── routes.py checks all players in round have answered (409 if not)
  └── Returns actual coordinates, actual date, actual location, all guesses, per-player scores
```

---

## Game Mode Extensibility Architecture

Game modes implement the `BaseGameModeEngine` abstract interface in `src/game/modes.py`:

- `select_question(...)`: Selects candidate photos respecting active filters, candidate diversity, and least-played priority, registering the question in the session store.
- `build_question_response(...)`: Generates sanitized single (Pinpoint) or batch (Album Shuffle) question payloads for the client.
- `evaluate_and_apply_answer(...)`: Evaluates player guesses using mode-specific scoring algorithms and records round scores in session state.
- `format_round_reveal(...)`: Formats round reveal data (actual locations, capture dates, distance/date errors, and player score breakdowns).

Performance awards (**Sniper**, **Time Traveler**, **Speed Demon**) are evaluated dynamically on match completion and persisted into SQLite (`leaderboard.db`).

New game modes can be added by implementing `BaseGameModeEngine` and registering them with `default_game_mode_registry.register(GameMode.name, EngineInstance)`.

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

## Deployment & Self-Hosting

- All runtime configuration is driven by `AppSettings` through environment variables (`.env`).
- Persistent state is isolated under `DATA_PATH` (`data/metadata.db` and `data/leaderboard.db`).
- Containerized deployment is supported out-of-the-box via the root `Dockerfile` and `docker-compose.example.yml`.

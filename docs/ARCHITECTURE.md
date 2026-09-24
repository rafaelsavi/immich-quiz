# Architecture

## Local-First Design

- Backend: FastAPI with async endpoints, served by Uvicorn.
- Frontend: static HTML/CSS/JS with Leaflet (no build step).
- Session persistence: in-memory for active games.
- Historical persistence: SQLite databases (`data/metadata.db` for metadata cache, `data/leaderboard.db` for the 5-table relational match & challenge schema: `challenges`, `challenge_sessions`, `matches`, `match_entries`, `match_round_guesses`) operating in WAL mode with `synchronous=NORMAL`, automated post-sync checkpoints, periodic 6-hour journal truncation, and shutdown maintenance.
- Metadata synchronization: Background asynchronous full & delta indexing from Immich (see [`docs/SYNC.md`](SYNC.md) for full architecture).

---

## Module Map

```
immich-quiz/
├── src/
│   ├── main.py          App factory and lifespan. Creates ImmichClient,
│   │                    SessionStore, MetadataStore, and LeaderboardStore;
│   │                    validates Immich access on startup; mounts static files and routes;
│   │                    schedules periodic background delta sync tasks.
│   ├── config.py        AppSettings dataclass. Parses and validates all env
│   │                    vars at startup; raises ConfigError on bad input.
│   ├── models.py        Pydantic request/response models and enums (PlayMode, GameMode,
│   │                    PeopleMode, RoundLength, SyncStatus, etc.) for all endpoints.
│   ├── scoring.py       Pure scoring functions: haversine_km, location_score,
│   │                    date_diff_days, date_score, batch_exponential_location_score,
│   │                    batch_exponential_date_score, calculate_location_decay,
│   │                    calculate_date_decay, accuracy_pct.
│   ├── i18n.py          Backend localization for filter summaries and tooltips.
│   ├── version.py       Semantic application version string (APP_VERSION).
│   ├── auth/            Authentication and Role-Based Access Control (RBAC).
│   │   ├── models.py    Role enum (GUEST, USER, CREATOR) and AuthContext dataclass.
│   │   └── service.py   Cloudflare Access header resolver and require_role dependency.
│   ├── api/
│   │   ├── auth_routes.py Identity and role introspection endpoint (/api/auth/me).
│   │   ├── routes.py    Standard local match API endpoints (setup, question, answer, result).
│   │   └── challenge_routes.py Async & hybrid multiplayer challenge endpoints (create, start, question, answer, leaderboard, deactivate).
│   ├── game/            Modular game mode system and session orchestration.
│   │   ├── modes.py     BaseGameModeEngine, PinpointEngine,
│   │   │                UnshuffleEngine, and GameModeRegistry.
│   │   ├── selector.py  Candidate asset selection, spatial (≥100m) & temporal (≥60s)
│   │   │                diversity filters, and least-played prioritization.
│   │   ├── service.py   GameService managing match state, question drawing,
│   │   │                preflight checks, answer scoring, and match finish persistence.
│   │   └── challenge_service.py ChallengeService managing deterministic match seeds,
│   │                    frozen decay calculations, capability tokens, and player sessions.
│   ├── immich/
│   │   └── client.py    ImmichClient adapter. Wraps httpx AsyncClient.
│   │                    Provides: validate_access, list_albums, list_tags, search_assets,
│   │                    search_random_assets, list_people, get_timeline_bounds, get_asset_bytes.
│   ├── app_logging/     Structured logging and observability subsystem.
│   │   ├── context.py   Async contextvars tracking (match_id, request_id, player_name).
│   │   ├── filters.py   ContextFilter record enrichment and RedactionFilter secret scrubbing.
│   │   ├── formatter.py ConsoleLogFormatter with color badges and Docker stdout optimization.
│   │   ├── middleware.py FastAPI ASGI middleware for X-Request-ID and access logs.
│   │   └── setup.py     Central logging configuration and subsystem level overrides.
│   └── storage/
│       ├── db.py        DatabaseManager for SQLite connection lifecycle and WAL mode.
│       ├── metadata.py  MetadataStore with indexed relational schema, query parity
│       │                builder, filter options extraction, and asset pruning/invalidation.
│       ├── sync.py      SyncEngine for full and incremental delta metadata indexing.
│       ├── session.py   In-memory state. SessionStore holds MatchState objects and tracks
│       │                active response times per turn.
│       ├── challenge.py ChallengeStore managing challenges and challenge_sessions SQLite tables.
│       └── leaderboard.py LeaderboardStore managing the 5-table relational match & challenge
│                        schema (`challenges`, `challenge_sessions`, `matches`, `match_entries`, `match_round_guesses`),
│                        career player performance analytics, and interactive match replay datasets.
└── static/              Vanilla HTML/CSS/JS frontend.
    ├── index.html       Main quiz application HTML.
    ├── audio-playground.html Interactive Web Audio testing playground page.
    ├── css/             Modular CSS stylesheets:
    │   ├── style.css    Master entrypoint (@importing base, components, modes).
    │   ├── base/        Design tokens (variables.css), resets (reset.css), app shell (layout.css).
    │   ├── components/  UI components (auth.css, buttons.css, cards.css, maps.css, leaderboard.css, challenge.css, modals.css, multi_select.css, player_input.css, range_slider.css, reported.css, filters.css, timer.css, toolbar.css, hub_header.css, stats.css, round_stage.css, reveal_table.css, replay.css, review_deck.css, summary.css).
    │   └── modes/       Game mode styles (pinpoint.css, unshuffle.css).
    ├── js/app.js        Main application coordinator and match lifecycle state machine.
    ├── js/audio-playground.js Playground controller & visualizer logic.
    └── js/modules/      Modular ES modules:
        ├── components/  Reusable UI components:
        │   ├── activity_toast.js Glassmorphic activity toast notifications for real-time multiplayer.
        │   ├── focus_trap.js Accessible modal focus trap utility (Tab / Shift+Tab) restoring focus.
        │   ├── lightbox.js  Zero-dependency modal photo lightbox with click-outside and Escape dismissal.
        │   ├── match_meta.js Match configuration rendering, game setup & library filter summary badges.
        │   ├── match_replay.js Standardized multi-round replay canvas, round stepper, Leaflet map with spider lines, and reveal table.
        │   ├── multi_select.js Searchable tag-based multi-select with select-all/clear.
        │   ├── player_input.js Interactive player chip input with duplicate detection & colors.
        │   ├── qrcode.js    Zero-dependency SVG QR code generator for challenge links.
        │   ├── range_slider.js Dual-handle Year-Month range slider.
        │   ├── report_modal.js Photo issue reporting dialog with 3-field validation & Immich Web link.
        │   ├── reveal_table.js Standardized 2-tier grouped header reveal table with score rollups.
        │   ├── review_deck.js Universal 3-tab review deck (Match Replay, Journey Map, Photo Memories) with Leaflet dimension invalidation and location mode gating.
        │   ├── round_stage.js Single source of truth for photo canvas, batch photo tabs, Leaflet map split view, and metadata caption pill chips across Live Pinpoint Reveal, Live Unshuffle Reveal, Match Replay, and Summary views.
        │   ├── settings_menu.js Settings gear dropdown menu with click-outside and Escape dismissal.
        │   └── share_box.js Reusable, standardized share URL box, icon-only action button row, and QR code component.
        ├── challenge/   Modular challenge play mode sub-package:
        │   ├── session.js   Challenge state store, localStorage keys, reset, and map cleanup.
        │   ├── landing.js   Lobby/landing screen, resume detection, join form, and error views.
        │   ├── game.js      Challenge question loading, timer management, and answer submission.
        │   ├── reveal.js    Round personal reveal, 3-second social polling, and opponent pin drops.
        │   ├── intermission.js Final round "Invite Friends" intermission, QR code, and finisher polling.
        │   ├── summary.js   Grand Reveal summary coordinator delegating to the unified review controller, managing live multiplayer background polling, activity toast notifications, provisional-to-podium transitions, and table updates.
        │   └── index.js     Unified facade re-assembling the challenge singleton interface.
        ├── modes/       Game mode strategy definitions & registry:
        │   ├── index.js     Mode registry and getActiveMode() strategy accessor.
        │   ├── pinpoint.js  Pinpoint single-photo mode strategy.
        │   ├── unshuffle.js Unshuffle multi-photo mode strategy.
        │   └── common.js    Shared mode helpers.
        ├── screens/     Screen lifecycle controllers:
        │   ├── common.js    Card switching (showCard), DOM resets (resetGameUi), and navigation guards.
        │   ├── setup.js     Match configuration, preflight checks, returnToSetup, and restart.
        │   ├── game.js      Question fetching, media pre-verification, pass-device coordination, and answer submit.
        │   ├── reveal.js    Round results aggregation, reveal rendering, and turn progression.
        │   ├── summary.js   Unified match review & replay controller (/game/:id/summary, /play/:token/summary, /game/:id/replay) managing Winner Podium, Standings Table, ReviewDeck (#summary-card), invite drawer, and ended card (#game-ended-card).
        │   ├── challenges.js Challenges Hub screen controller (#challenges-page-card, live timers, drawers).
        │   ├── stats.js     Player Statistics Directory & Profile controller (#stats-page-card).
        │   ├── replay.js    Match Replays Catalog & History controller (#replays-page-card).
        │   └── reported.js  Reported Asset Moderation Dashboard screen controller (#reported-page-card).
        ├── summary/     Post-game summary rendering submodules:
        │   ├── podium.js    3D podium and winner banner.
        │   ├── awards.js    Client-side performance awards (Sniper, Time Traveler, Speed Demon).
        │   ├── table.js     Scores, rankings, and metadata table.
        │   ├── polaroids.js Memory cards photo gallery and lightbox triggers.
        │   └── share.js     Web Share API and clipboard copy toast.
        ├── admin.js     Admin modal, match termination, and challenge management actions.
        ├── api.js       API HTTP request client.
        ├── audio.js     Zero-dependency Web Audio sound synthesizer engine.
        ├── effects.js   Canvas confetti, animations, and visual transitions.
        ├── formatters.js Distance/date formatters, relative time formatters, and string helpers.
        ├── i18n.js      Multi-language translation engine (EN/PT) with live switcher.
        ├── leaderboard.js Leaderboard UI rendering and filtering.
        ├── maps.js      Leaflet map wrapper, marker placement, auto-zoom, and updateSubmitState.
        ├── router.js    Client-side History API router (normalizePath, parseRoute, setNavigationGuard).
        ├── setup_filters.js Setup filter controls, dependent cities, persistence, and live preflight.
        ├── shortcuts.js Global keyboard navigation (<kbd>Space</kbd> / <kbd>Enter</kbd>).
        ├── state.js     Centralized reactive application state store.
        ├── sync.js      Library metadata sync trigger, polling, and status badges.
        ├── theme.js     Clear / Dark theme controller with instant toggle and zero-flash localStorage persistence.
        └── timer.js     Silky-smooth 60 FPS countdown timer, smart time formatting (M:SS), pause/resume, audio ticks, and timeout dispatch.
└── tests/               Test suites and quality verification harness (mirrors src/ structure).
    ├── conftest.py      Pytest fixtures, mock Immich test client, and synthetic asset factories.
    ├── api/             FastAPI endpoint route tests (test_api.py, test_challenge_api.py, test_filters_api.py).
    ├── app_logging/     Observability and logging subsystem tests (test_logging.py).
    ├── e2e/             Playwright end-to-end browser automation test suites.
    │   ├── conftest.py  Live FastAPI test server fixture and async page context manager.
    │   ├── test_challenge_gameplay.py Challenge lobby, rounds, polling, and Grand Reveal.
    │   ├── test_date_selection.py Timeline range slider and single year/month selection.
    │   ├── test_filters_accordion.py Filter accordion expansion and preflight reactivity.
    │   ├── test_language_switch.py Dynamic bilingual toggle and label reactivity.
    │   ├── test_pinpoint_gameplay.py Pinpoint Leaflet pin placement, polyline, and reveal.
    │   ├── test_preflight_guess_mode.py Preflight validation for location and date game modes.
    │   ├── test_replay_catalog_challenge_chip.py Challenge badge and type chips in replay catalog.
    │   ├── test_replay_components_reuse.py Review deck, media frame, map shell, and strategy reuse.
    │   ├── test_report_issue.py Report Issue modal dialog, form validation, and submission.
    │   ├── test_reported_moderation.py Moderation dashboard list, search, filter, and resolve.
    │   ├── test_routing_and_recovery.py Deep links, SPA routing, and reload recovery.
    │   ├── test_summary_and_effects.py Score rollup animations and post-game awards.
    │   ├── test_sync_popup.py Metadata synchronization trigger and progress telemetry.
    │   ├── test_universal_language_switch.py Automated full-DOM translation parity scanner.
    │   └── test_unshuffle_gameplay.py Photo card reordering and multi-pin placement.
    ├── frontend/        Frontend regression and component tests (test_frontend_regressions.py, test_setup_card_bento_regression.py, test_multi_select.py, test_player_input.py, test_range_slider.py).
    ├── game/            Match selection, candidate pools, and diversity tests (test_diversity.py).
    ├── immich/          Immich client adapter tests (test_immich_client.py).
    ├── storage/         Storage subsystem tests (test_challenge_storage.py, test_leaderboard.py, test_metadata_storage.py).
    ├── test_adaptive_scoring.py Adaptive scoring calibration tests.
    ├── test_config.py   Settings parsing and validation tests.
    ├── test_i18n.py     Localization key completeness tests.
    ├── test_models.py   Pydantic schema validation tests.
    ├── test_scoring.py  Mathematical scoring formulas and accuracy calculations.
    └── test_version.py  Semantic application version string tests.
```

---

## Round Data Flow

```
GET /api/ui-config
  └── Returns language, max score settings, and version to frontend

GET /api/sync/status
  └── Returns current synchronization telemetry and status across all configured libraries

POST /api/sync?force_full=false
  └── Triggers background asynchronous metadata sync from Immich to SQLite across all configured libraries

GET /api/filters?libraries={name}
  └── Returns timeline date bounds, countries, cities (with country mapping), and people for selected libraries
  └── Queries local SQLite metadata index when populated (instant response); falls back to Immich API
  └── Backed by in-memory TTLCache (5-minute TTL) on the server
  └── Frontend hydrates multi-selects and range slider; restores filter state from localStorage

POST /api/game/preflight
  └── Validates asset pool eligibility against active filters (albums, date range, countries, cities, people)
  └── Evaluates fast indexed SQLite query (or sampling fallback) with identical query clauses
  └── Enforces people matching mode (ANY / ALL)
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
  └── Stores guess, scores, active response time (time_taken_seconds), and timestamp in QuestionState
  └── If match is completed, aggregates total match duration, player active response times,
      assembles per-photo round guesses, and writes full match records to SQLite leaderboard
      (matches, match_entries, match_round_guesses)
  └── Returns acknowledgement only (no answer data)

POST /api/round/result
  └── routes.py checks all players in round have answered (409 if not)
  └── Returns actual coordinates, actual date, actual location, all guesses, per-player scores
```

---

## Challenge Mode Data Flow

```
POST /api/challenge/create
  └── Validates eligible photo count with preflight logic
  └── Selects diverse photo candidate pool (spatial >=100m, temporal >=60s)
  └── Computes frozen exponential decay constants (location_decay_km, date_decay_days, map_bounds)
  └── Generates 128-bit unguessable capability_token (secrets.token_urlsafe(16))
  └── Persists challenge record and returns capability URL and SVG QR code

GET /api/challenge/{capability_token}
  └── Returns public challenge metadata, rules, filters, and participant roster for the landing screen

POST /api/challenge/{capability_token}/start
  └── Registers new player or resumes existing incomplete attempt
  └── Assigns distinct player color and clash-free initials
  └── Returns session_token and current round index

GET /api/challenge/{capability_token}/question/{round_index}
  └── Validates X-Player-Token header and enforces sequential progression (no skipping)
  └── Returns sanitized question payload (no true coordinates, no capture dates)

GET /api/media/{asset_id}
  └── Validates that asset_id belongs to the active challenge seed or local match
  └── Scrubs all EXIF tags, GPS coordinates, and camera timestamps in-memory before streaming bytes

POST /api/challenge/{capability_token}/answer
  └── Validates X-Player-Token header and checks submission against server timer grace window
  └── Evaluates guess using frozen decay parameters stored in challenge config
  └── Records guess in match_round_guesses
  └── Returns immediate personal reveal scores and true coordinates/dates for that round

GET /api/challenge/{capability_token}/leaderboard
  └── Polled every 3s during reveal screen and finisher intermission
  └── Enforces Fog of War:
      - Unauthenticated callers on active matches receive redacted history ([])
      - Active players only receive round guesses/history for rounds <= completed_round
      - Concluded challenges or finished players receive full match history and guesses
```

---

## Setup Filters & Multi-Select Data Flow

The `filters-accordion` UI dynamically coordinates multi-select controls, dependent geographic options (Countries $\rightarrow$ Cities), people match modes (ANY/ALL), date sliders, and live preflight validation.

See [`docs/FILTERS.md`](FILTERS.md) for the full architecture, interaction matrix, cascading dependency graph, and preflight feedback loop.

---

## Game Mode Extensibility Architecture

Game modes implement the `BaseGameModeEngine` abstract interface in `src/game/modes.py`:

- `select_question(...)`: Selects candidate photos respecting active filters, candidate diversity, and least-played priority, registering the question in the session store.
- `build_question_response(...)`: Generates sanitized single (Pinpoint) or batch (Unshuffle) question payloads for the client.
- `evaluate_and_apply_answer(...)`: Evaluates player guesses using mode-specific scoring algorithms and records round scores in session state.
- `format_round_reveal(...)`: Formats round reveal data (actual locations, capture dates, distance/date errors, and player score breakdowns).

Performance awards (**Sniper**, **Time Traveler**, **Speed Demon**) are dynamically computed and rendered on the client side (`static/js/modules/summary/awards.js`), while raw physical metrics (`distance_km`, `date_diff_days`, `time_taken_seconds`) are persisted in SQLite (`leaderboard.db`).

New game modes can be added by implementing `BaseGameModeEngine` and registering them with `default_game_mode_registry.register(GameMode.name, EngineInstance)`.

---

## Anti-Cheat Boundary

The answer data boundary is enforced entirely inside `storage/session.py`.
`QuestionState` holds the `RoundAsset` (actual latitude, longitude, capture
date) in-memory and never exposes it through the question or answer responses.

| Endpoint                                         | Returns answer data?                                                                          |
|--------------------------------------------------|------------------------------------------------------------------------------------------------|
| `POST /api/question`                             | No — stripped by `routes.py` before response                                                   |
| `GET /api/challenge/{token}/question/{round}`    | No — stripped by `challenge_service.py` before response                                        |
| `GET /api/media/…`                               | No — proxy bytes carry no EXIF/GPS (Immich preview re-encodes and server-side tags stripped)    |
| `POST /api/answer`                               | No — acknowledgement only                                                                      |
| `POST /api/round/result`                         | Yes — only after every player in the round has answered                                        |
| `POST /api/challenge/{token}/answer`             | Yes (personal only) — immediate personal score and true answer for the submitted round only    |
| `GET /api/challenge/{token}/leaderboard`         | Filtered by Fog of War — opponent answers for round N are withheld until the player submits round N |

---

## Startup Validation

`main.py` calls `ImmichClient.validate_access` for every configured library
key during the lifespan startup phase. Keys that fail are excluded from
`/api/libraries` and reported in the `unavailable` field; the app continues
with the remaining keys rather than refusing to start.

---

## Access Control & Role-Based Permissions (RBAC)

The application enforces a 3-tier hierarchical role architecture:

- **`Guest`**: Can play public multiplayer challenges (`/play/:token`), submit answers, and view challenge outcomes. Cannot view player directories, historical match replays, or create games.
- **`User`**: (Family and regular players). Can play games, explore the Player Directory (`/players`), browse Match Replays (`/replays`), and view public challenge feeds. Cannot access raw Immich libraries, initiate metadata sync, create local games, or moderate photos.
- **`Creator`**: (Instance owner). Full administrative privileges across all endpoints and UI screens.

### Zero Trust Authentication Model

- **Disabled Mode (`AUTH_MODE=disabled`)**: Default setting for local development and CI testing. Everyone resolves to `Creator`, preserving backward compatibility. Display name defaults to `'Host'`.
- **Cloudflare Access & Reverse Proxy Mode (`AUTH_MODE=cloudflare`)**: Resolves identity from incoming headers (`Cf-Access-Authenticated-User-Email`, `Cf-Access-Authenticated-User-Name`, `X-User-Name`, `X-Auth-Name`, `X-Forwarded-User`, `Remote-User`) or extracts claims from the `Cf-Access-Jwt-Assertion` token payload.
  - Identifiers matching `CF_CREATOR_EMAILS` (by verified email or lowercase username) receive `Creator`.
  - Identifiers matching `CF_USER_EMAILS` receive `User`.
  - Unrecognized or missing headers resolve to `Guest`.
  - User display name resolves from custom name headers, JWT claims, or falls back to capitalized email prefix.
- **Backend Enforcement**: FastAPI routes are protected via `dependencies=[Depends(require_role(min_role))]`, rejecting unauthorized callers with HTTP 403 Forbidden.
- **Client-Side Guards**: Navigation router enforces `ROUTE_MIN_ROLES`, redirecting unauthorized URL transitions to `/` with localized user-friendly toast alerts.

---

## Internationalization (i18n) Architecture

The application provides first-class bilingual support for English (`en-US`) and Brazilian Portuguese (`pt-BR`) across all backend API metadata and frontend Single-Page Application (SPA) screens.

### Strict 4-File Parity Mandate

The localization system maintains exactly four catalogs with 100% identical top-level key counts, key names, and hierarchical structure:

1. `locales/en-US.json` (Backend reference English catalog)
2. `locales/pt-BR.json` (Backend reference Portuguese catalog)
3. `static/js/modules/locales/en_US.js` (Frontend ES module English catalog)
4. `static/js/modules/locales/pt_BR.js` (Frontend ES module Portuguese catalog)

This parity is enforced on every commit and CI run via automated regression test `test_strict_4_locale_file_parity`.

### Namespaces & Semantic Organization

- **`common.*`**: Universal UI actions and controls shared across multiple modals, screen headers, and dialogs (`common.cancel`, `common.refresh`, `common.loading`, `common.back`, `common.close`, `common.clear`, `common.retry`, `common.copy`, `common.copied`, `common.pts`). Prevents cross-domain borrowing.
- **`meta.*`**: Unified match specification panel (`match_meta.js`) describing game configuration, round lengths, and photo library scopes (`meta.scope_heading`, `meta.scope_all_desc`, `meta.scope_shared_desc`).
- **`mode.*`**: Core game mode labels and concise chip descriptions (`mode.pinpoint`, `mode.unshuffle`, `mode.pinpoint_desc`, `mode.unshuffle_desc`).
- **`setup.*`**: Pre-game configuration, library selector, and player name inputs.
- **`game.*` & `reveal.*`**: In-game guessing controls, timer, round reveal breakdown, and true answer presentation.
- **`summary.*`**: Post-game review deck, performance podium, and medal awards.
- **`challenges_page.*`**: Multiplayer challenge lobby, hero metrics, card statuses, and host actions.
- **`stats.*`**: Player statistics hub, career analytics KPIs, accuracy tiers, and parameterized match counters.
- **`replay.*`**: Historical match replay catalog, filter controls, round stepper, and telemetry viewers.
- **`auth.*`**: Role-based access control badges and permission alerts.

Dynamic units and plural forms must always use parameterized interpolation (`{count}` or `{0}`) via `t("...", count)` or `plural(...)` rather than hardcoded string concatenation.

---

## Deployment & Self-Hosting

- All runtime configuration is driven by `AppSettings` through environment variables (`.env`).
- Persistent state is isolated under `DATA_PATH` (`data/metadata.db` and `data/leaderboard.db`).
- Containerized deployment is supported out-of-the-box via the root `Dockerfile` and `docker-compose.example.yml`.

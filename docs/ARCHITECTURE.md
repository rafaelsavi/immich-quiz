# Architecture

## Local-First Design

- **Backend**: FastAPI with async endpoints, served by Uvicorn.
- **Frontend**: Vanilla HTML5/CSS3/JavaScript (ES modules) with Leaflet maps (no build step).
- **Session Persistence**: In-memory `SessionStore` for active matches.
- **Historical Persistence**: Append-only CSV file (`LeaderboardStore`) for leaderboard score history.

---

## Module Map

```
immich-quiz/
├── src/
│   ├── main.py          App factory and lifespan. Creates ImmichClient, SessionStore,
│   │                    LeaderboardStore, and GameService; validates Immich access on startup.
│   ├── config.py        AppSettings dataclass. Parses and validates env vars at startup.
│   ├── models.py        Pydantic request/response models for all endpoints.
│   ├── scoring.py       Pure scoring functions: haversine_km, location_score, date_diff_days,
│   │                    date_score, kendall_tau_inversion_score, accuracy_pct.
│   ├── game/            Game engine, service layer & mode handlers.
│   │   ├── service.py   GameService application layer orchestrating match flow.
│   │   ├── selector.py  Candidate pool management and photo selection algorithms.
│   │   └── modes.py     Mode-specific score evaluation for Pinpoint & Album Shuffle.
│   ├── api/
│   │   └── routes.py    FastAPI HTTP routing handlers. Clean endpoint delegation via GameService.
│   ├── immich/
│   │   └── client.py    ImmichClient adapter. Wraps httpx AsyncClient for Immich API calls.
│   └── storage/
│       ├── session.py   In-memory match state (`MatchState`, `SessionStore`).
│       └── leaderboard.py LeaderboardStore appends and reads rows from CSV storage.
└── static/              Vanilla HTML/CSS/JS frontend.
    ├── index.html       Main quiz application HTML.
    ├── css/style.css    Custom responsive styling & game mode layouts.
    ├── js/app.js        Main application entry point & router coordinator.
    └── js/modules/      ES modules:
        ├── api.js       HTTP fetch API wrapper.
        ├── audio.js     Web Audio API sound effects system.
        ├── effects.js   Confetti, floating scores & score rollup animation effects.
        ├── formatters.js Distance, place, date & badge formatting utilities.
        ├── i18n.js      Localization dictionary & language switching (EN, PT).
        ├── leaderboard.js Leaderboard table DOM rendering controller.
        ├── maps.js      Leaflet map initialization & journey map.
        ├── state.js     Global reactive state & DOM element references.
        ├── summary.js   Polaroid gallery rendering.
        ├── components/  Shared UI components:
        │   └── lightbox.js   Full-resolution photo lightbox overlay.
        ├── modes/       Game mode UI strategies:
        │   ├── common.js     Shared mode settings UI renderer.
        │   ├── pinpoint.js   Pinpoint mode strategy strategy.
        │   └── album_shuffle/ Album Shuffle modular package:
        │       ├── index.js  Mode strategy entrypoint contract.
        │       ├── board.js  Turn question board & 5-card list UI.
        │       ├── map.js    Leaflet map engine, custom pin markers & highlights.
        │       ├── reveal.js Round reveal tables & score rollup view.
        │       └── help.js   Interactive help modal component.
        └── views/       Screen View Controllers:
            ├── setup_view.js   Game setup form & preflight checking.
            ├── game_view.js    Active question turn & submit handling.
            ├── reveal_view.js  Round reveal & score rollup animation.
            └── summary_view.js Match summary leaderboard & journey map.
```

---

## Round Data Flow

```
GET /api/ui-config
  └── Returns max image height, language, max score settings to frontend

POST /api/game/preflight
  └── GameService validates asset pool eligibility (location/date/date-range requirements)
  └── Confirms eligible photo count >= requested round count

POST /api/game/setup
  └── GameService resolves album name server-side from ImmichClient
  └── Creates MatchState in SessionStore (players, round config, empty round slots)
  └── Returns match_id and total_turns

POST /api/question
  └── GameService looks up MatchState by match_id
  └── Draws candidate asset(s) using select_round_asset (Pinpoint) or
      select_batch_round_assets (Album Shuffle)
  └── Evaluates candidate assets with is_asset_valid_for_batch against previously
      played match assets (enforces distance >= 0.1km and time separation >= 60s)
  └── Registers QuestionState with full RoundAsset (lat/lon/date) stored server-side
  └── Returns sanitized QuestionResponse — no coordinates, no capture date

GET /api/media/{asset_id}
  └── routes.py verifies asset_id was issued in a live match (rejects unregistered assets)
  └── ImmichClient.get_asset_bytes proxies preview thumbnail bytes
  └── Browser never contacts Immich directly

POST /api/answer
  └── GameService looks up QuestionState
  └── Delegates to src.game.modes: evaluate_pinpoint_answer or evaluate_album_shuffle_answer
  └── Stores guess + scores in QuestionState via SessionStore.apply_score
  └── On match completion, automatically appends summary to LeaderboardStore
  └── Returns AnswerResponse acknowledgement

POST /api/round/result
  └── GameService verifies all players in the round have locked in answers
  └── Assembles RoundResultResponse: actual coordinates, actual date, actual location,
      per-player guesses & scores

GET /api/match/{match_id}/summary
  └── GameService computes final player rankings, winner list, and accuracy percentages
```

---

## Anti-Cheat Boundary

The answer data boundary is enforced entirely inside `storage/session.py` and `game/service.py`.
`QuestionState` holds the `RoundAsset` (actual latitude, longitude, capture date) in-memory and never exposes it through question or answer responses.

| Endpoint                 | Returns answer data?                                           |
|--------------------------|----------------------------------------------------------------|
| `POST /api/question`     | No — stripped by `routes.py` / `GameService` before response   |
| `GET /api/media/…`       | No — proxy bytes carry no EXIF/GPS (Immich preview re-encodes) |
| `POST /api/answer`       | No — acknowledgement & turn progression only                   |
| `POST /api/round/result` | Yes — only after every player in the round has locked in answer|

---

## Startup Validation

`main.py` calls `ImmichClient.validate_access` for every configured library key during the lifespan startup phase. Keys that fail are excluded from `/api/libraries` and reported in the `unavailable` field; the app continues with remaining keys rather than refusing to start.

---

## Game Mode Strategy Architecture

The codebase separates **Shared Core Infrastructure** from **Mode-Specific Logic** using a Strategy pattern on both the backend and frontend.

```
+-----------------------------------------------------------------------+
|                       Shared Core Infrastructure                       |
|  SessionStore | ImmichClient | LeaderboardStore | GameService | i18n   |
+-----------------------------------------------------------------------+
                                   |
           +-----------------------+-----------------------+
           |                                               |
           v                                               v
+-----------------------+                       +-----------------------+
|     Pinpoint Mode     |                       |  Album Shuffle Mode   |
| - Single photo draw   |                       | - 5-photo batch draw  |
| - Lat/Lon + Month     |                       | - Pin-pair + Timeline |
| - Exponential decay   |                       | - Kendall-Tau order   |
+-----------------------+                       +-----------------------+
```

### Shared vs Mode-Specific Boundaries

| Layer / Component | Shared Core Infrastructure | Mode-Specific Logic |
|---|---|---|
| **Immich Adapter** | Asset search, metadata parsing, image proxy `/api/media/{id}` | Eligibility bounds, date filters |
| **Session Store** | `MatchState`, `SessionStore`, turn rotation, player scores | `batch_assets`, `batch_pins`, `album_shuffle_guesses` |
| **Scoring Engine** | Pure formulas (`haversine_km`, `location_score`, `date_score`) | Mode composition (`kendall_tau_inversion_score`, `batch_strict_location_score`) |
| **Backend Engine** | `GameService` match orchestration | `src/game/modes.py` mode evaluation strategies |
| **Frontend UI** | Router (`app.js`), View Controllers (`views/`), `maps.js`, `audio.js` | Mode strategies (`modes/pinpoint.js`, `modes/album_shuffle.js`) |

### Frontend Game Mode Interface Contract

Every frontend game mode module in `static/js/modules/modes/` exports an object implementing this contract:

```javascript
const gameModeStrategy = {
  name: "mode_id",

  // 1. Render mode settings toggles/cards on setup screen
  renderSettings(containerEl) {},

  // 2. Extract settings payload for POST /api/game/setup
  getModePayload() {},

  // 3. Mount game board UI for active turn (uses mountModeTemplate to clone <template id="tmpl-mode-${name}">)
  renderQuestion(uiContainer, questionData) {
    const activeUi = mountModeTemplate(this.name, uiContainer);
    // Bind event listeners and data to activeUi
  },

  // 4. Build payload for POST /api/answer
  buildAnswerPayload(questionData, timedOut) {},

  // 5. Mount round reveal UI
  renderReveal(revealUi, revealData) {},
};
```

---

## Code Shareability & Extensibility Guidelines

To keep the codebase maintainable as multiple developers work on it:

1. **Adding a New Game Mode**:
   - **Backend**: Implement candidate selection in `src/game/selector.py` and scoring evaluation in `src/game/modes.py`.
   - **Frontend**: Create a new mode handler in `static/js/modules/modes/<new_mode>.js` implementing the `gameModeStrategy` contract. Register it in `static/js/modules/modes/common.js`.

2. **Frontend View Controllers**:
   - Keep top-level router orchestration in `app.js`.
   - Implement screen-specific controllers in single-responsibility modules under `static/js/modules/views/`.

3. **Backend Service Layering**:
   - HTTP routes in `src/api/routes.py` handle request parsing and delegate directly to `GameService`.
   - Algorithms (distance calculations, scoring math, candidate selection) belong in pure helper packages (`src/scoring.py`, `src/game/`).

---

## Future Migration

- All runtime config flows through `AppSettings` (env vars only).
- No hardcoded paths outside configurable defaults.
- Moving the folder to a dedicated repository requires only adding a `Dockerfile`. See [MIGRATION.md](MIGRATION.md).

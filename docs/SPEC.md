> **Internal design specification.** This document defines intended behavior for contributors and maintainers. For setup and usage see [README.md](README.md); for how the game works see [docs/GAMEPLAY.md](docs/GAMEPLAY.md).

# Immich Quiz v1.0 Specification

## 1. Purpose

Immich Quiz is a self-hosted, web-based, pass-and-play trivia game powered by personal photos from Immich.

The game must support one or more players, configurable rounds, and one or two scoring goals:

1. Location guessing on a map.
2. Date guessing at month precision.

This specification defines a local-first implementation that can later be moved to a dedicated repository and deployed in Docker without architectural rewrite.

## 2. Scope

### 2.1 In Scope for v1

1. Local web application with backend and frontend in a single project.
2. Integration with one Immich server and one or more library API keys.
3. Pass-and-play multiplayer on one shared device.
4. Round generation with anti-cheat guarantees.
5. Scoring and per-match leaderboard persistence in CSV.
6. Test suite and maintained technical documentation.

### 2.2 Out of Scope for v1

1. Multi-device real-time multiplayer.
2. User authentication for the quiz app itself.
3. Cloud deployment automation.
4. Database persistence for live game state.

## 3. Technology Stack: Where and Why

### 3.1 Backend

1. Python 3.13.
2. FastAPI.
3. Uvicorn.
4. httpx for asynchronous Immich API access.
5. Pydantic for request and response schema validation.
6. uv for environment and dependency management.

Why:

1. Python 3.13 provides modern typing and strong ecosystem support.
2. FastAPI plus Pydantic gives strict contracts and predictable API behavior.
3. Uvicorn provides efficient local async serving.
4. httpx is used directly instead of a generated Immich SDK. The application needs only a few Immich calls (albums, metadata search, random search, thumbnail bytes), so a thin adapter avoids coupling the game to an SDK release cycle and keeps error handling explicit. A single shared AsyncClient is reused for connection pooling.

Where used:

1. API endpoints and validation in backend modules.
2. Immich client adapter for libraries, albums, asset search, and media bytes retrieval.
3. Scoring and session orchestration in backend domain modules.

### 3.2 Frontend

1. Vanilla HTML, CSS, and JavaScript.
2. Leaflet for interactive map and reveal visualization.

Why:

1. No build pipeline required for local-first development.
2. Fast iteration and transparent browser behavior.
3. Leaflet is stable, lightweight, and ideal for point and distance visualization.

Where used:

1. Setup page for players and game options.
2. Active round view and pass-device overlay.
3. Reveal canvas with guessed versus actual locations.
4. Leaderboard view with sorting and badges.

### 3.3 Storage

1. In-memory session state for active matches.
2. CSV file for historical leaderboard rows.

Why:

1. In-memory state is sufficient for local single-instance runtime.
2. CSV persistence is simple, portable, and easy to inspect and back up.

## 4. Configuration Contract

### 4.1 Environment Variables

Required:

1. IMMICH_SERVER_URL: Base URL ending with /api.
2. IMMICH_LIBRARIES: JSON object mapping library name to API key.

Optional:

1. LEADERBOARD_CSV_PATH: Path to leaderboard file. Default is leaderboard.csv in application working directory.
2. APP_HOST: Default 127.0.0.1.
3. APP_PORT: Default 8010.
4. SCORE_MAX_POINTS: Per-goal maximum score. Default 100.
5. LOCATION_SCORE_DECAY_KM: Location exponential decay constant in km. Default 700.
6. DATE_SCORE_DECAY_DAYS: Date exponential decay constant in days. Default 500.

### 4.2 Local Development

1. Values may be stored in a local .env file.
2. Committed examples must use placeholders and no personal hostnames or keys.

### 4.3 Startup Validation

The backend must fail fast on startup if:

1. IMMICH_SERVER_URL is missing or malformed.
2. IMMICH_LIBRARIES is missing, invalid JSON, or empty.
3. Any listed library key cannot read assets from its corresponding library context.

## 5. Domain Model

### 5.1 Core Entities

1. Player: name and running score totals.
2. Match: match id, players, selected library, optional album, round count, round length, enabled goals.
3. Round: round index, assigned player, chosen asset id, sanitized question payload, hidden answer payload.
4. Guess: optional location guess and optional date guess.
5. Round Result: location score, date score, total score, reveal payload.
6. Leaderboard Row: CSV-compatible summary per player per match.

### 5.2 Match Rules

1. At least one player is required.
2. Round count allowed values are 5, 10, or 20. Default is 10.
3. Round length allowed values are 30s, 60s, or unlimited.
4. At least one goal must be enabled: location or date.

## 6. Game Setup and Runtime Flow

### 6.1 Setup Inputs

1. Players: one or more names.
2. Round count: 5, 10, or 20.
3. Round length: 30s, 60s, unlimited.
4. Goals: location, date, or both.
5. Library selector: populated from IMMICH_LIBRARIES keys.
6. Album selector: optional, populated from selected library. Default is "-" meaning all photos.

### 6.2 Round Lifecycle

1. Pre-round pass-device overlay appears for the active player.
2. On ready action, question payload and proxied image are shown.
3. Player submits guesses for enabled goals.
4. Reveal view shows ground truth and scores.
5. Next player and round progression continues until all rounds are complete.

### 6.3 State Machine

1. setup
2. pass_overlay
3. active_round
4. reveal_round
5. final_leaderboard

Transitions are deterministic and must not skip reveal when at least one goal is enabled.

## 7. Asset Selection and Anti-Cheating Requirements

### 7.1 Asset Eligibility Rules

For each candidate asset:

1. Must be still image type only: type equals IMAGE.
2. Reject videos, animated assets, and motion photos.
3. If location mode is enabled: latitude and longitude must both exist and be non-zero.
4. If date mode is enabled: dateTimeOriginal or fileCreatedAt must parse into valid timestamp.

### 7.2 Duplicate Prevention

1. The backend tracks played asset ids per match and never repeats one.
2. The client may send played_asset_ids, but it is advisory only. Correctness must not depend on client-supplied state.

### 7.2.1 Shared Round Photo

1. One photo is drawn per round and reused for every player in that round, so all players answer the same question and their scores are directly comparable.
2. Turn order is round-major: within a round each player takes one turn, then the next round draws a new photo.
3. A photo used by one round is never reused by a later round in the same match.

### 7.3 Question Payload Hygiene

The question endpoint must never expose answer data. It must strip:

1. EXIF object.
2. Latitude and longitude.
3. Original date metadata.
4. Any nested fields that directly infer location or day-level date answer.

### 7.4 Media Proxy

1. Media endpoint fetches raw bytes using the correct library key.
2. Response content type must be image/jpeg for v1.
3. Browser must never call Immich directly for gameplay images.

## 8. Scoring Specification

Each goal is scored from 0 to SCORE_MAX_POINTS per round.

### 8.1 Location Score

Let d be geodesic distance in kilometers between guessed and actual coordinates using Haversine.

S_loc = max(0, floor(SCORE_MAX_POINTS * exp(-d / LOCATION_SCORE_DECAY_KM)))

### 8.2 Date Score

The player guesses a **year and a month** (month-resolution). The guess covers
the entire guessed month; scoring uses the minimum day distance from the actual
capture date to the boundary of the guessed month:

- If the actual date falls inside the guessed month: delta_days = 0.
- If the actual date is before the guessed month: delta_days = days from the 1st of the guessed month to the actual date.
- If the actual date is after the guessed month: delta_days = days from the last day of the guessed month to the actual date.

S_date = max(0, floor(SCORE_MAX_POINTS * exp(-delta_days / DATE_SCORE_DECAY_DAYS)))

### 8.3 Round and Match Aggregation

1. round_total = S_loc + S_date for enabled goals.
2. max_possible_score = rounds_played * (SCORE_MAX_POINTS if location enabled else 0 + SCORE_MAX_POINTS if date enabled else 0).
3. total_score = sum of round totals for that player.
4. accuracy_pct = round((total_score / max_possible_score) * 100, 1).

## 9. Leaderboard CSV Contract

### 9.1 Exact Header

match_id,played_at,player_name,library_name,album_name,rounds_played,max_possible_score,location_score,date_score,total_score,accuracy_pct

### 9.2 Field Rules

1. played_at is ISO-8601 UTC timestamp.
2. location_score is empty string when location mode was disabled.
3. date_score is empty string when date mode was disabled.
4. Numeric fields must be written as plain decimal strings.
5. Parser must preserve compatibility with prior rows that follow this exact header.

## 10. API Contract

### 10.1 General API Rules

1. All endpoints are under /api.
2. JSON request and response unless media endpoint.
3. Validation errors return 422 for schema violations.
4. Domain errors return 400 with actionable message.

### 10.2 Required Endpoints

1. GET /api/health
Purpose: liveness probe.

2. GET /api/libraries
Purpose: list configured libraries, plus any that failed key validation at startup.

3. GET /api/albums?library_name={name}
Purpose: list albums visible for selected library key.

4. POST /api/game/setup
Purpose: create match session from setup form. Album name is resolved server-side from album_id.

5. POST /api/question
Purpose: return sanitized question payload with chosen asset id and media URL.
Returns the same question while the current turn is unanswered, and never returns an asset already played in the match.

6. POST /api/answer
Purpose: evaluate guess, compute scores, and return reveal payload.
Returns 409 if the question was already answered.

7. GET /api/media/{asset_id}?library_name={library_name}
Purpose: proxy image bytes from Immich for assets belonging to a live match.

8. GET /api/leaderboard
Purpose: return parsed leaderboard rows for UI sorting.

### 10.3 Reveal Payload Requirements

Reveal response may include:

1. actual latitude and longitude only after answer submission.
2. actual date only after answer submission.
3. computed distance and day delta.
4. per-goal and total scores.

## 11. Frontend Requirements

### 11.1 Setup Screen

1. Player name entry with add and remove.
2. Round count selector with default 10.
3. Round length selector.
4. Goal checkboxes.
5. Library and album selectors populated from API.
6. Start game action.

### 11.2 Active Round Screen

1. Header text with active player and round index.
2. Full-size gameplay image served only through backend media proxy.
3. Map input when location mode is enabled.
4. Date input when date mode is enabled.
5. Countdown for limited round length.

### 11.3 Pass-Device Overlay

1. Mandatory overlay before each player turn in multiplayer.
2. Blocks image visibility until ready confirmation.

### 11.4 Reveal Screen

1. Leaflet map with guessed and actual points.
2. Dashed polyline from guess to actual location.
3. Date reveal and difference in days.
4. Round score summary.

### 11.5 Leaderboard Screen

1. Sortable table by total score, accuracy, and date.
2. Match metadata badges for library and album.
3. Timestamp display using played_at.

## 12. Non-Functional Requirements

1. Local-first execution on Windows/Linux/macOS.
2. Deterministic scoring for identical inputs.
3. No answer leakage in any pre-answer API payload.
4. Clear error messages for config and Immich permission failures.
5. Code and docs remain anonymous and safe for public repository publication.

## 13. Testing Requirements

### 13.1 Unit Tests

1. Haversine and score formulas, including boundary conditions.
2. Date parsing and day-difference behavior.
3. CSV write and parse against exact header.

### 13.2 API Tests

1. Question payload excludes answer fields.
2. Duplicate asset id is never returned in same match.
3. Answer endpoint returns expected reveal and score structure.
4. Media endpoint returns expected content type and bytes.

### 13.3 Integration and UI Smoke

1. Single-player full match flow.
2. Multi-player pass-device flow.
3. Leaderboard persistence and rendering.

## 14. Documentation Maintenance Rules

Any behavior change must update at least one of:

1. This specification.
2. API documentation.
3. Testing documentation.
4. Migration documentation.

Pull requests are incomplete if implementation, tests, and docs are not aligned.

## 15. Future Migration Constraints

Design v1 so migration is packaging-only:

1. All runtime config via environment variables.
2. No hardcoded local file paths outside configurable defaults.
3. Session storage boundary isolated behind storage module.
4. Media proxy and Immich integration isolated behind client adapter.
5. Dockerization later should require Dockerfile and compose additions, not core game logic changes.

## 16. Acceptance Criteria

v1 is complete only when all criteria pass:

1. Local app starts from environment configuration.
2. Host can configure and run a full match with one or more players.
3. Asset filtering and duplicate prevention rules are enforced.
4. Question payload contains no answer metadata.
5. Location and date scoring formulas match this spec exactly.
6. leaderboard.csv is written and parsed using exact required schema.
7. Automated tests pass for unit and API suites.
8. Documentation is up to date with final behavior.

## 17. Deferred Functional Changes

The following are agreed as out of scope for the current defect-fix pass and are
pending a separate gameplay discussion.

1. Round timer enforcement. The countdown is currently display-only and does not
   auto-submit when it reaches zero.
2. Skipping the pass-device overlay in single-player matches.
3. End-of-match summary screen with per-player totals.
4. Difficulty presets tuning the scoring decay constants. The current curve is
   forgiving: 100 km still scores 90, and a one-year date error still scores 44.
5. Year-only or decade date mode for old scanned photos.
6. Speed and streak bonuses.
7. "Who is in the photo" mode using Immich people data.
8. Progressive hints that cost points.
9. Team mode.
10. Replacing browser alert() error handling with inline error UI.

Anti-cheating scope note: this application is intended for family use, so
protections are deliberately limited to cheap server-side correctness rules
(single answer per question, stable question per turn, server-tracked duplicates,
session-scoped media proxy). Heavier mechanisms such as signed tokens or
per-request nonces are intentionally not implemented.

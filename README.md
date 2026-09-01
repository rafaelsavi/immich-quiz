# Immich Quiz

[![GitHub Release](https://img.shields.io/github/v/release/rafaelsavi/immich-quiz?color=blue&logo=github)](https://github.com/rafaelsavi/immich-quiz/releases)
[![GHCR Container](https://img.shields.io/badge/docker-ghcr.io%2Frafaelsavi%2Fimmich--quiz-blue?logo=docker)](https://github.com/rafaelsavi/immich-quiz/pkgs/container/immich-quiz)
[![CI](https://github.com/rafaelsavi/immich-quiz/actions/workflows/ci.yml/badge.svg)](https://github.com/rafaelsavi/immich-quiz/actions/workflows/ci.yml)

Immich Quiz is a trivia game that generates quiz rounds directly from your Immich photo collection. Players guess where and when photos were taken in **Pinpoint** mode, or match photo batches to map pins and timeline dates in **Album Shuffle** mode.

Play locally with friends on a single screen via **👥 Pass & Play**, or share **🌐 Multiplayer Challenge Links** (with unguessable capability URLs and instant QR codes) for multi-device asynchronous or hybrid competition!

![Immich Quiz Home Screen](docs/assets/home.webp)

---

## Playing the Game

### Game Modes & Targets
- **🎯 Pinpoint**: 1 photo per round. Place a pin on the interactive Leaflet map and/or guess the capture month and year.
- **🔀 Album Shuffle**: 3 photos per round. Match photos to lettered map pins and/or arrange them in chronological sequence along a timeline.
- **Targets**: Guess **Location only**, **Date only**, or **Location & Date**.

### Play Modes
- **👥 Local Match (Pass & Play)**: Gather friends around a single device or TV. Players take turns passing the device between rounds with a privacy curtain protecting upcoming photos.
- **🌐 Multiplayer Challenges (Async & Hybrid)**: Click **Prepare Game** to generate an unguessable capability link (e.g. `/play/ch_...`) and QR code with a custom expiration window (`1h`, `6h`, `24h`, `48h`, `7d`, or `Never`). Friends join from their own mobile or desktop browsers, see live opponent pin drops as rounds complete, and view the final 3D podium.
- **Challenges Hub (`/challenges`)**: Browse, search, share, track active challenges, and view past match summaries.

### Library Filters & Preflight
Optionally filter photos by album, custom date range, country, city, or tagged people (with Any / All matching). A live preflight indicator verifies that enough diverse, geotagged, and dated photos exist before the match starts.

See [docs/GAMEPLAY.md](docs/GAMEPLAY.md) for the full gameplay walkthrough, [docs/CHALLENGES.md](docs/CHALLENGES.md) for the multiplayer challenge guide, and [docs/SCORING.md](docs/SCORING.md) for mathematical scoring details.

---

## Self-Hosting

### Container Image & Tag Reference

The official Docker image is published to GitHub Container Registry (GHCR):

`ghcr.io/rafaelsavi/immich-quiz`

| Tag                  | Description                       | Command                                             |
|----------------------|-----------------------------------|-----------------------------------------------------|
| `:latest`            | Latest build from `main` branch   | `docker pull ghcr.io/rafaelsavi/immich-quiz:latest` |
| `:rc`                | Latest Release Candidate build    | `docker pull ghcr.io/rafaelsavi/immich-quiz:rc`     |
| `:v1.0.0` / `:1.0.0` | Specific semantic release version | `docker pull ghcr.io/rafaelsavi/immich-quiz:v1.0.0` |
| `:<sha>`             | Exact commit hash build           | `docker pull ghcr.io/rafaelsavi/immich-quiz:<sha>`  |

### Starting the server

Create your `.env` configuration file from `.env.example`:

```bash
cp .env.example .env
```

Edit `.env` to set your `IMMICH_SERVER_URL`, `IMMICH_LIBRARIES`, and optional settings.

Start the container with Docker Compose using the provided [docker-compose.example.yml](docker-compose.example.yml):

```bash
cp docker-compose.example.yml docker-compose.yml
docker compose up -d
```

Docker Compose reads configuration directly from your `.env` file via `env_file`. Mount the `./data` volume to store the SQLite database and persist metadata index and leaderboard scores across container restarts.

### Environment Variables

| Variable                         | Required | Default       | Notes                                                                                 |
|----------------------------------|----------|---------------|---------------------------------------------------------------------------------------|
| `IMMICH_SERVER_URL`              | Yes      | —             | Full URL to the Immich API, e.g. `https://photos.example.com/api`                     |
| `IMMICH_LIBRARIES`               | Yes      | —             | JSON object mapping display names to API keys, e.g. `{"Family": "key123"}`            |
| `APP_TITLE`                      | No       | `Immich Quiz` | Browser tab title and main heading shown on the landing page                          |
| `APP_TAGLINE`                    | No       |               | Optional tagline shown below the main heading on the landing page                     |
| `DATE_LOWER_BOUND`               | No       | —             | Inclusive lower date bound (`YYYY-MM-DD`) for photos fetched into quiz rounds         |
| `DATE_UPPER_BOUND`               | No       | —             | Inclusive upper date bound (`YYYY-MM-DD`) for photos fetched into quiz rounds         |
| `COUNTRY_WHITELIST`              | No       | —             | Comma-separated list of allowed countries in filters (case-insensitive)               |
| `COUNTRY_BLACKLIST`              | No       | —             | Comma-separated list of excluded countries in filters (case-insensitive)              |
| `CITY_WHITELIST`                 | No       | —             | Comma-separated list of allowed cities/regions in filters (case-insensitive)          |
| `CITY_BLACKLIST`                 | No       | —             | Comma-separated list of excluded cities/regions in filters (case-insensitive)         |
| `PEOPLE_WHITELIST`               | No       | —             | Comma-separated list of allowed people names or IDs in filters (case-insensitive)     |
| `PEOPLE_BLACKLIST`               | No       | —             | Comma-separated list of excluded people names or IDs in filters (case-insensitive)    |
| `TAG_WHITELIST`                  | No       | —             | Comma-separated list of allowed asset tag names or IDs in filters (case-insensitive)  |
| `TAG_BLACKLIST`                  | No       | —             | Comma-separated list of excluded asset tag names or IDs in filters (case-insensitive) |
| `DATA_PATH`                      | No       | `data`        | Directory for SQLite persistence (`metadata.db` and `leaderboard.db`)                 |
| `AUTO_SYNC_ON_STARTUP`           | No       | `true`        | Auto-trigger metadata sync in the background on server startup                        |
| `AUTO_DELTA_SYNC_INTERVAL_HOURS` | No       | `6`           | Interval in hours for periodic delta metadata sync (`0` disables)                     |
| `AUTO_FULL_SYNC_INTERVAL_HOURS`  | No       | `120`         | Interval in hours for periodic full metadata sync & pruning (`0` disables)            |
| `APP_HOST`                       | No       | `127.0.0.1`   | Set to `0.0.0.0` in Docker so the port is reachable from the host                     |
| `APP_PORT`                       | No       | `8010`        | Port the app listens on                                                               |
| `LOG_LEVEL`                      | No       | `INFO`        | Global logging verbosity (`DEBUG`, `INFO`, `WARNING`, `ERROR`)                        |
| `LANGUAGE`                       | No       | `EN`          | UI language (`EN` for English, `PT` for Brazilian Portuguese)                         |

### Immich API Key Permissions

The `IMMICH_LIBRARIES` variable is a JSON object where keys are display names for your libraries and values are Immich API keys (e.g. `{"Family": "apiKey123"}`).

API keys can be generated in Immich under **Account Settings > API Keys**. Following the principle of least privilege, each API key only requires read/view access. To enable all application features (metadata indexing, round image previews, album filtering, face/people filters, asset tag filters, and shared library segregation), custom-scope each key with the following permissions:

| Permission Scope | Required For                | Endpoints Used                                       | Description                                                                                                                           |
|:-----------------|:----------------------------|:-----------------------------------------------------|:--------------------------------------------------------------------------------------------------------------------------------------|
| `asset.read`     | Asset Metadata & Sync       | `POST /search/metadata`<br>`POST /search/statistics` | Discovers photos/videos, extracts EXIF coordinates/dates, computes library statistics, and validates connection.                      |
| `asset.view`     | Gameplay Image Previews     | `GET /assets/{id}/thumbnail`                         | Streams compressed preview thumbnails during active quiz rounds. *(Original full-resolution files are never accessed or downloaded).* |
| `album.read`     | Album Filtering & Shuffle   | `GET /albums`<br>`GET /albums/{id}`                  | Fetches album listings and album asset associations for setup filters and Album Shuffle mode.                                         |
| `person.read`    | People / Face Filters       | `GET /people`                                        | Discovers recognized people and names for setup filtering (Any / All matching) and whitelist/blacklist rules.                         |
| `tag.read`       | Asset Tag Filters           | `GET /tags`                                          | Retrieves custom asset tags for setup filtering and tag whitelist/blacklist rules.                                                    |
| `user.read`      | Ownership & Sharing Context | `GET /users/me`                                      | Identifies the authenticated account to distinguish personal photos from shared albums and partner assets.                            |

---

## Development

### Quick Start

1. Install dependencies and browser binaries:

```bash
uv sync --extra dev
uv run playwright install chromium
```

2. Use `.env.example` to create a local `.env` file for local development.
3. Start the app:

```bash
uv run -m src.main
```

### Tests and Quality Gates

#### Pre-push Hook

To enable automatic pre-push CI checks locally:

```bash
git config core.hooksPath .githooks
```

#### Run tests manually

```bash
# Run unit and integration tests
uv run pytest tests/ -k "not e2e"

# Run Playwright end-to-end browser tests
uv run pytest tests/e2e

# Run linters and type checkers
uv run ruff check .
uv run mypy src

# Run full test suite with coverage
uv run pytest --cov=src --cov-report=term-missing
```

### VS Code Integration (Tasks & Debugging)

If you use VS Code, pre-configured tasks and launch files are available in `.vscode/`:

- **Run / Debug App (`F5`)**: Use the `FastAPI: Debug App (Uvicorn)` launch profile or press **F5** to start the app with debugging and hot reload.
- **Run Tasks (`Ctrl+Shift+B` / `Cmd+Shift+B`)**: Access project tasks via **Terminal > Run Task**:
  - `Run App`: Start the dev server (`uv run python src/main.py`).
  - `Run Pytest`: Execute unit and integration tests.
  - `Run E2E Tests (Playwright)`: Execute Playwright browser test suite.
  - `Run All CI Checks`: Run Ruff, Mypy, and Pytest coverage in sequence.

### Audio Testing Playground

An interactive playground is available at [`/audio-playground`](http://localhost:8010/audio-playground) (or [`/static/audio-playground.html`](http://localhost:8010/static/audio-playground.html)) for testing, custom-synthesizing, and auditing sound effects built into `static/js/modules/audio.js`. See [docs/AUDIO_PLAYGROUND.md](docs/AUDIO_PLAYGROUND.md) for details.

### Documentation

- [CHANGELOG.md](CHANGELOG.md) — release history and notable changes
- [docs/GAMEPLAY.md](docs/GAMEPLAY.md) — gameplay rules, setup parameters, and UI walkthrough
- [docs/CHALLENGES.md](docs/CHALLENGES.md) — multiplayer challenge mode guide, capability tokens, and architecture
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — module design, anti-cheat boundary, and data flow
- [docs/FILTERS.md](docs/FILTERS.md) — setup filter architecture, cascading multi-selects, and live preflight validation
- [docs/SYNC.md](docs/SYNC.md) — metadata synchronization engine, SQLite schema, and background worker architecture
- [docs/API.md](docs/API.md) — full API contract and response schemas
- [docs/SCORING.md](docs/SCORING.md) — mathematical scoring formulas and decay reference tables
- [docs/AUDIO_PLAYGROUND.md](docs/AUDIO_PLAYGROUND.md) — Web Audio sound engine documentation and testing playground guide
- [docs/AWARDS.md](docs/AWARDS.md) — guide to performance awards, criteria, and customization instructions
- [docs/TODO.md](docs/TODO.md) — project roadmap and backlog for planned features and technical tasks

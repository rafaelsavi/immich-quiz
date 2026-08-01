# Immich Quiz

Immich Quiz is a local-first, pass-and-play trivia game that generates rounds from your Immich photos. Players take turns guessing where and when each photo was taken, scored on map distance and date accuracy.

![Immich Quiz Home Screen](docs/assets/home.webp)

---

## Playing the Game

1. Open the app in your browser after starting the server (see [Self-Hosting](#self-hosting) or [Development](#development) below).
2. Enter player names, choose round count, goals, and a library.
3. Pass the device to each player when prompted.
4. After all rounds the leaderboard appears.

See [docs/GAMEPLAY.md](docs/GAMEPLAY.md) for a full explanation of setup options, round flow, and scoring.
For scoring details see [docs/SCORING.md](docs/SCORING.md).

---

## Self-Hosting

### Starting the server

To run with Docker Compose use the provided [docker-compose.example.yml](docker-compose.example.yml) and edit it to your needs. Mount `./data` volume to store the leaderboard CSV file and persist scores across container restarts. Pass environment variables to the container to configure the app.

### Environment Variables

| Variable                        | Required | Default           | Notes                                                                         |
|---------------------------------|----------|-------------------|-------------------------------------------------------------------------------|
| `IMMICH_SERVER_URL`             | Yes      | —                 | Full URL to the Immich API, e.g. `https://photos.example.com/api`             |
| `IMMICH_LIBRARIES`              | Yes      | —                 | JSON object mapping display names to API keys, e.g. `{"Family": "key123"}`    |
| `APP_TITLE`                     | No       | `Immich Quiz`     | Browser tab title and main heading shown on the landing page                  |
| `APP_TAGLINE`                   | No       |                   | Optional tagline shown below the main heading on the landing page             |
| `INCLUDE_SHARED_ALBUMS`         | No       | `false`           | Set to `true` to include shared albums by default                             |
| `FETCH_PHOTOS_DATE_LOWER_BOUND` | No       | —                 | Inclusive lower date bound (`YYYY-MM-DD`) for photos fetched into quiz rounds |
| `FETCH_PHOTOS_DATE_UPPER_BOUND` | No       | —                 | Inclusive upper date bound (`YYYY-MM-DD`) for photos fetched into quiz rounds |
| `LEADERBOARD_CSV_PATH`          | No       | `data/leaderboard.csv` | Path to leaderboard CSV file (relative to working dir or absolute path)       |
| `APP_HOST`                      | No       | `127.0.0.1`       | Set to `0.0.0.0` in Docker so the port is reachable from the host             |
| `APP_PORT`                      | No       | `8010`            | Port the app listens on                                                       |
| `QUIZ_IMAGE_MAX_HEIGHT_PX`      | No       | `420`             | Max displayed quiz image height in px; valid range `200` to `1600`            |
| `SCORE_MAX_POINTS`              | No       | `100`             | Max points per enabled goal, per turn                                         |
| `LOCATION_SCORE_DECAY_KM`       | No       | `500`             | Location decay constant in km for `exp(-distance/decay)`                      |
| `DATE_SCORE_DECAY_DAYS`         | No       | `500`             | Date decay constant in days for `exp(-delta_days/decay)`                      |
| `LANGUAGE`                      | No       | `EN`              | UI language (`EN` for English, `PT` for Brazilian Portuguese)                 |

### Immich API Token Permissions

The `IMMICH_LIBRARIES` value is a JSON object where keys are display names of the libraries and values are Immich v3 API keys. Each API key must be custom-scoped with exactly the following permissions:

- `asset.read` — required for photo search.
- `album.read` — required for album listing.
- `asset.view` — required for visualization.

The app requests preview thumbnails only; original files are never downloaded.

---

## Development

### Quick Start

1. Install dependencies:

```bash
uv sync --extra dev
```

1. Use `.env.example` to create a local `.env` file for local development.
2. Start the app:

```bash
uv run src.main
```

### Tests and Quality Gates

#### Pre-push Hook

To enable automatic pre-push CI checks locally:

```bash
git config core.hooksPath .githooks
```

#### Run all tests manually

```bash
uv run pytest -q
uv run ruff check .
uv run mypy src
uv run pytest --cov=src --cov-report=term-missing
```

### Documentation

- [docs/GAMEPLAY.md](docs/GAMEPLAY.md) — gameplay rules, setup parameters, and UI walkthrough
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — module design, anti-cheat boundary, and data flow
- [docs/API.md](docs/API.md) — full API contract and response schemas
- [docs/SCORING.md](docs/SCORING.md) — mathematical scoring formulas and decay reference tables

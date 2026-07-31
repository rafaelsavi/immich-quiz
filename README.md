# Immich Quiz

Immich Quiz is a local-first, pass-and-play trivia game that generates rounds from your Immich photos. Players take turns guessing where and when each photo was taken, scored on map distance and date accuracy.

See [docs/GAMEPLAY.md](docs/GAMEPLAY.md) for a full explanation of setup options, round flow, and scoring.

---

## Playing the Game

1. Open the app in your browser after starting the server (see [Self-Hosting](#self-hosting) or [Development](#development) below).
2. Enter player names, choose round count, goals, and a library.
3. Pass the device to each player when prompted.
4. After all rounds the leaderboard appears.

For scoring details see [docs/SCORING.md](docs/SCORING.md).

---

## Self-Hosting

### Immich API Token Permissions

Immich v3 API keys are permission-based. Create a custom-scoped key with exactly:

- `asset.read` — required for photo search.
- `album.read` — required for album listing.
- `asset.view` — required for thumbnail proxy.

The app requests preview thumbnails only; original files are never downloaded.

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
| `LOCATION_SCORE_DECAY_KM`       | No       | `700`             | Location decay constant in km for `exp(-distance/decay)`                      |
| `DATE_SCORE_DECAY_DAYS`         | No       | `500`             | Date decay constant in days for `exp(-delta_days/decay)`                      |
| `LANGUAGE`                      | No       | `EN`              | UI language (`EN` for English, `PT` for Brazilian Portuguese)                 |

### Docker

A `Dockerfile` is included for container builds (e.g. in GitHub Actions release pipelines).

**Leaderboard persistence**: mount `./data` volume to persist scores across container restarts.

#### Example `docker run` (Self-Hosters)

```bash
docker run -d \
  --name immich-quiz \
  -p 8010:8010 \
  -e IMMICH_SERVER_URL=https://photos.example.com/api \
  -e 'IMMICH_LIBRARIES={"Family": "your-api-key"}' \
  -v ./data:/app/data \
  ghcr.io/rafaelsavi/immich-quiz:latest
```

#### Example Docker Compose (Self-Hosters)

To run with Docker Compose, create a `docker-compose.yml` on your server (or copy [docker-compose.example.yml](docker-compose.example.yml)):

```yaml
services:
  immich-quiz:
    image: ghcr.io/rafaelsavi/immich-quiz:latest
    container_name: immich-quiz
    restart: unless-stopped
    ports:
      - "8010:8010"
    environment:
      IMMICH_SERVER_URL: "https://photos.example.com/api"
      IMMICH_LIBRARIES: '{"Family": "your-api-key"}'
    volumes:
      - ./data:/app/data
```

---

## Development

### Privacy and Public-Repo Safety

- Committed config files use placeholder URLs and keys.
- Put your real server URL and API keys only in a local `.env` file (never committed).

### Quick Start

1. Install dependencies:

```bash
uv sync --extra dev
```

2. Create local config:

```bash
copy .env.example .env
```

3. Edit `.env` with your real values.
4. Start the app:

```bash
uv run uvicorn src.main:app --reload --host 127.0.0.1 --port 8010
```

5. Open http://127.0.0.1:8010

### Tests and Quality Gates

See [docs/TESTING.md](docs/TESTING.md) for the full test strategy.

```bash
uv run pytest -q
uv run ruff check .
uv run mypy src
uv run pytest --cov=src --cov-report=term-missing
```

### Further Reading

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — module structure and data flow
- [docs/API.md](docs/API.md) — full API endpoint reference
- [docs/SCORING.md](docs/SCORING.md) — scoring formulas
- [docs/SPEC.md](docs/SPEC.md) — internal design specification

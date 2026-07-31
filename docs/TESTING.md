# Testing Strategy

## Unit Tests

- scoring formula correctness and configurability (custom decay constants and max points)
- accuracy uses half-up rounding, not banker's rounding
- CSV schema and disabled-mode column behavior
- configuration validation errors (missing URL, malformed JSON, bad port)
- asset eligibility matrix (video rejected, zero/missing coordinates, unparseable date)

## API Tests

- question endpoint anti-cheat payload stripping
- repeated question requests return the same question (no reroll)
- answering twice returns 409 and cannot inflate scores or leaderboard rows
- duplicate assets never repeat even when the client sends an empty played list
- every player in a round receives the same photo, and rounds use different photos
- players rotate in order within a round
- media proxy rejects assets that belong to no live match
- media bytes come from the preview thumbnail and contain no EXIF/GPS markers
- album name is resolved server-side and unknown album ids are rejected

## Run

```bash
uv run pytest -q
```

## Quality Gates

```bash
uv run ruff check .
uv run mypy src
uv run pytest --cov=src --cov-report=term-missing
```

## Definition of Done

1. All tests pass.
2. Lint and type checks pass.
3. New gameplay behavior includes tests.
4. Documentation updated in docs/ and README.

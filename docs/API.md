# API Contract

All endpoints are served under `/api`. Schema violations return `422`; domain
errors return `400`, `404` or `409` with an actionable `detail` message.

## System & Config

### GET /api/health

- `GET /api/health` -> `{"status": "ok"}`

### GET /api/ui-config

Returns frontend configuration parameters:

```json
{
  "language": "EN",
  "score_max_points": 100
}
```

## Setup and Metadata

### GET /api/libraries

```json
{
  "libraries": ["family_library"],
  "unavailable": { "broken_library": "Immich API error 401 ..." }
}
```

Libraries whose API key failed validation at startup are reported in
`unavailable` and omitted from `libraries`. A bad key no longer stops the app.

### GET /api/albums?library_name={name}&include_shared_albums={bool}

Returns `{"albums": [{"id": "...", "name": "..."}]}`.
By default this includes only albums owned by the authenticated user.
The default can be configured with `INCLUDE_SHARED_ALBUMS`.
Set `include_shared_albums=true` or `false` to explicitly override.

### POST /api/game/preflight

Validates whether the selected library or album contains enough eligible media assets for the requested match parameters before starting a game.

Request:

```json
{
  "players": ["Alice", "Bob"],
  "round_count": 10,
  "location_mode": true,
  "date_mode": true,
  "library_name": "family_library",
  "album_ids": []
}
```

Response:

```json
{
  "eligible_count": 45,
  "required": 10,
  "ok": true,
  "active_filters": ["location", "date"],
  "min_date": null,
  "max_date": null
}
```

### POST /api/game/setup

Request:

```json
{
  "players": ["Alice", "Bob"],
  "round_count": 10,
  "round_length": "1m",
  "location_mode": true,
  "date_mode": true,
  "game_mode": "pinpoint",
  "library_name": "family_library",
  "album_ids": []
}
```

- `game_mode` supports `"pinpoint"` (default) or `"album_shuffle"`.
- `round_count` must be 5, 10 or 20; at least one mode (`location_mode` or `date_mode`) must be enabled.
- `round_length` supports `"30s"`, `"1m"`, `"2m"`, `"5m"`, or `"unlimited"`.
- `album_name` is resolved server-side from `album_ids`, so a client cannot
  spoof leaderboard metadata. Unknown `album_ids` returns `400`.
- Responds with `{"match_id": "...", "total_turns": N, "players": ["Alice", "Bob"]}`.

## Round Flow

### POST /api/question

Body: `{"match_id": "...", "played_asset_ids": []}`

- Returns the sanitized question payload (no EXIF, coordinates or capture date).
- Response includes round context: `question_id`, `asset_id`, `media_url`, `player_name`, `player_number`, `total_players`, `player_round_number`, `total_rounds_per_player`, `turn_number`, `total_turns`, `location_mode`, `date_mode`, and `round_length`.
- One photo is drawn per round and shared by every player in that round, so
  scores within a round are comparable.
- If the current turn already has an unanswered question, the **same** question
  is returned. Re-requesting cannot be used to reroll a different photo.
- Assets already served in the match are never repeated. The exclusion list is
  tracked server-side; `played_asset_ids` from the client is advisory only.
- `409` when the match is finished or has no remaining turns.
- `404` when no eligible asset is available.

### GET /api/media/{asset_id}?library_name={name}

- `library` is accepted as an alias for `library_name`.
- Only asset ids that were issued as a question in a live match are served.
  Any other id returns `404`, so the proxy is not an open gateway to the library.
- Bytes come from the Immich preview thumbnail, which is re-encoded and
  therefore carries no EXIF/GPS payload.

### POST /api/answer

Body: `{"match_id": "...", "question_id": "...", "guessed_latitude": 48.85, "guessed_longitude": 2.35, "guessed_year": 2022, "guessed_month": 6, "timed_out": false}`

- `guessed_year` and `guessed_month` must be supplied together (month resolution).
- `timed_out` marks an answer that was auto-submitted when the round timer hit zero.
- Returns an **acknowledgement only**: `{"player_name", "question_id",
  "round_number", "turn_completed", "total_turns", "round_complete",
  "waiting_for", "match_finished"}`. No answer data is leaked here, because the
  next player in the round has not answered yet.
- A question can be answered **once**. A second submission returns `409`,
  which prevents score farming and guarantees exactly one leaderboard row per
  player per match.

### POST /api/round/result

Body: `{"match_id": "...", "round_number": 1}`

- Reveals the round: actual coordinates (`actual_latitude`, `actual_longitude`), actual location (`actual_city`, `actual_country`), actual date (`actual_date`, `actual_year`, `actual_month`), `score_max_points`, plus every player's
  guess, per-task scores, round score, running total, distance error (`distance_km`) and
  date error (`date_diff_days` drives the score; `date_diff_months`, `date_diff_years_part`, and `date_diff_months_part` are for display).
- `409` while any player in the round still owes an answer, so results are only
  ever shown simultaneously.
- `404` for a round number outside the match.

### GET /api/match/{match_id}/summary

- Final overview: match config (`rounds_played`, `location_mode`, `date_mode`, `library_name`, `album_name`), per-player location/date/total scores, `max_possible_score`, `accuracy_pct`, `rank` and `is_winner` flags, plus the `winners` list (multiple entries on a tie).

## Leaderboard

### GET /api/leaderboard

Optional query parameters:

- `rounds`: Filter by round count (`5`, `10`, `20`)
- `round_length`: Filter by timer setting (`30s`, `1m`, `unlimited`)
- `location_mode`: Filter by location mode enabled (`true`/`false`)
- `date_mode`: Filter by date mode enabled (`true`/`false`)
- `library`: Filter by library name
- `album`: Filter by album name

Returns rows sorted by newest `played_at` first. Each entry contains `match_id`, `played_at`, `player_name`, `max_possible_score`, `total_score`, and `config` dictionary.

## Anti-Cheat Rules

Question payloads never include answer fields:

- No EXIF object
- No latitude/longitude
- No true capture date

Answer submissions return no reveal data either. Reveal data is only available
from `POST /api/round/result` once every player in the round has answered.

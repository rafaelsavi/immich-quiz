# API Contract

All endpoints are served under `/api`. Schema violations return `422`; domain
errors return `400`, `404` or `409` with an actionable `detail` message.

## Health

- `GET /api/health` -> `{"status": "ok"}`

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

### GET /api/albums?library_name={name}

Returns `{"albums": [{"id": "...", "name": "..."}]}`.
By default this includes only albums owned by the authenticated user.
The default can be changed with `INCLUDE_SHARED_ALBUMS`.
Set `include_shared_albums=true` to also include shared albums.

### POST /api/game/setup

```json
{
  "players": ["Alice", "Bob"],
  "round_count": 10,
  "round_length": "1m",
  "location_mode": true,
  "date_mode": true,
  "library_name": "family_library",
  "album_id": null
}
```

- `round_count` must be 5, 10 or 20; at least one mode must be enabled.
- `album_name` is resolved server-side from `album_id`, so a client cannot
  spoof leaderboard metadata. Unknown `album_id` returns `400`.
- Responds with `{"match_id": "...", "total_turns": N}`.

## Round Flow

### POST /api/question

Body: `{"match_id": "...", "played_asset_ids": []}`

- Returns the sanitized question payload (no EXIF, coordinates or capture date).
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

Body: `{"match_id", "question_id", "guessed_latitude", "guessed_longitude", "guessed_year", "guessed_month", "timed_out"}`

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

Body: `{"match_id", "round_number"}`

- Reveals the round: actual coordinates, actual year/month, plus every player's
  guess, per-task scores, round score, running total, distance error and
  date error (`date_diff_days` drives the score; the month breakdown is for
  display).
- `409` while any player in the round still owes an answer, so results are only
  ever shown simultaneously.
- `404` for a round number outside the match.

### GET /api/match/{match_id}/summary

- Final overview: per-player location/date/total scores, accuracy, rank and
  winner flags, plus the `winners` list (multiple entries on a tie).

## Anti-Cheat Rules

Question payloads never include answer fields:

- No EXIF object
- No latitude/longitude
- No true capture date

Answer submissions return no reveal data either. Reveal data is only available
from `POST /api/round/result` once every player in the round has answered.

## Leaderboard

- `GET /api/leaderboard` -> rows sorted by newest `played_at` first.

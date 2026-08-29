# API Contract

All endpoints are served under `/api`. Schema violations return `422`; domain
errors return `400`, `404` or `409` with an actionable `detail` message.

### Request & Correlation Tracing

All HTTP requests accept an optional `X-Request-ID` header. If omitted, the server automatically generates a unique 12-character request ID. The `X-Request-ID` is echoed in all HTTP response headers and bound to all structured backend logs emitted during request processing for distributed tracing.

## System & Config

### GET /api/health

Returns backend service health status and application version.

Response:

```json
{
  "status": "ok",
  "version": "2.4.0"
}
```

### GET /api/ui-config

Returns frontend configuration parameters and application version:

Response:

```json
{
  "language": "EN",
  "score_max_points": 100,
  "immich_web_url": "https://immich.example.com",
  "version": "2.5.0"
}
```

## Setup, Sync & Metadata

### GET /api/libraries

Returns all configured libraries and unavailable libraries that failed startup validation.

Response:

```json
{
  "libraries": ["family_library"],
  "unavailable": { "broken_library": "Immich API error 401 ..." }
}
```

Libraries whose API key failed validation at startup are reported in
`unavailable` and omitted from `libraries`. A bad key no longer stops the app.

### GET /api/albums?libraries={name}

Returns available albums across the specified libraries (or all configured libraries if omitted). Queries the local SQLite metadata index first for 0ms response time; falls back to the Immich API if the index is unpopulated.

Response:

```json
{
  "albums": [
    { "id": "album-uuid-1", "name": "Summer Vacation 2024" },
    { "id": "album-uuid-2", "name": "Family Roadtrip" }
  ]
}
```

### GET /api/filters?libraries={name}

Returns discovered filter metadata options across the specified libraries (or all configured libraries if omitted), including timeline month boundaries, recognized people (respecting whitelist/blacklist rules), countries, and cities (with country association). Backed by in-memory `TTLCache` (5-minute TTL) and local SQLite index.

Response:

```json
{
  "date_range": {
    "min_month": "2018-05",
    "max_month": "2026-08"
  },
  "countries": ["Brazil", "France", "United States"],
  "cities": [
    { "name": "Paris", "country": "France" },
    { "name": "Rio de Janeiro", "country": "Brazil" },
    { "name": "San Francisco", "country": "United States" }
  ],
  "people": [
    { "id": "person-uuid-1", "name": "Alice" },
    { "id": "person-uuid-2", "name": "Bob" }
  ]
}
```

### GET /api/sync/status

Returns current background synchronization telemetry and status across all configured libraries. See [`docs/SYNC.md`](SYNC.md) for full architecture.

Response:

```json
{
  "libraries": ["family", "personal"],
  "is_syncing": false,
  "sync_status": "idle",
  "sync_mode": "delta",
  "sync_stage": "idle",
  "last_sync_at": "2026-08-17T10:15:30.123456+00:00",
  "last_full_sync_at": "2026-08-17T08:00:00.000000+00:00",
  "last_immich_updated_at": "2026-08-17T10:14:02.000Z",
  "total_assets": 1240,
  "synced_assets": 1240,
  "last_sync_duration_seconds": 0.35,
  "sync_error": null,
  "warnings": {}
}
```

### POST /api/sync?force_full=false

Triggers an asynchronous background metadata sync across all configured libraries from Immich into `data/metadata.db` and invalidates cached filter options.

* `force_full=false` (default): Executes an incremental **Delta Sync** querying assets modified after `last_immich_updated_at`.
* `force_full=true`: Forces a **Full Sync** scanning all assets and pruning deleted media.

Returns the updated `sync_state` immediately while the background task runs.

---

## Game Setup & Preflight

### POST /api/game/preflight

Validates whether the selected libraries and active filter criteria contain enough eligible media assets for the requested match parameters before starting a game.

Request:

```json
{
  "libraries": ["family_library"],
  "round_count": 10,
  "location_mode": true,
  "date_mode": true,
  "game_mode": "pinpoint",
  "players": ["Alice", "Bob"],
  "albums": ["album-uuid-1"],
  "people": ["person-uuid-1"],
  "people_mode": "ANY",
  "countries": ["France"],
  "cities": ["Paris"],
  "min_date": "2020-01-01",
  "max_date": "2024-12-31",
  "include_shared": false
}
```

Response:

```json
{
  "eligible_count": 45,
  "required": 10,
  "ok": true,
  "active_filters": ["location", "date", "album", "country", "city", "people", "date_range"],
  "min_date": "2020-01-01",
  "max_date": "2024-12-31",
  "total_count": 120,
  "gps_count": 95,
  "date_count": 120,
  "location_mode": true,
  "date_mode": true,
  "facet_counts": {
    "countries": { "France": 45 },
    "cities": { "Paris": 45 },
    "people": { "person-uuid-1": 30 },
    "albums": { "album-uuid-1": 45 }
  },
  "is_synced": true,
  "sync_status": "idle"
}
```

### POST /api/game/setup

Initiates a new game match, creates in-memory `MatchState`, pre-computes geographic bounding box for map auto-framing, and returns the match ID.

Request:

```json
{
  "libraries": ["family_library"],
  "round_count": 10,
  "round_length": "1m",
  "location_mode": true,
  "date_mode": true,
  "game_mode": "pinpoint",
  "players": ["Alice", "Bob"],
  "albums": ["album-uuid-1"],
  "people": [],
  "people_mode": "ANY",
  "countries": [],
  "cities": [],
  "min_date": null,
  "max_date": null,
  "include_shared": false
}
```

* `game_mode` supports `"pinpoint"` (default) or `"album_shuffle"`.
* `round_count` must be 5, 10 or 20; at least one mode (`location_mode` or `date_mode`) must be enabled.
* `round_length` supports `"30s"`, `"1m"`, `"2m"`, `"5m"`, or `"unlimited"`.
* `album_names` (list) are resolved server-side from `albums`.
* `people_mode` supports `"ANY"` (Any person) or `"ALL"` (All selected people together).

Response:

```json
{
  "match_id": "match-uuid-1234",
  "total_turns": 20,
  "players": ["Alice", "Bob"],
  "map_bounds": {
    "min_lat": 48.81,
    "max_lat": 48.90,
    "min_lng": 2.25,
    "max_lng": 2.42
  }
}
```

---

## Round Flow

### POST /api/question

Body: `{"match_id": "match-uuid-1234", "played_asset_ids": []}`

* Returns the sanitized question payload (no EXIF, coordinates or capture date).
* In **Pinpoint** mode: returns a single photo (`asset_id`, `media_url`).
* In **Album Shuffle** mode: returns a batch of 3 photos (`batch_photos`) and lettered map pins (`batch_pins`).
* One photo (or batch) is drawn per round and shared by every player in that round so scores are comparable.
* Tracks candidate diversity ($\ge 100\text{m}$ distance, $\ge 60\text{s}$ time separation) and prioritizes least-played photos (`times_played ASC`).
* `409` when the match is finished or has no remaining turns.
* `404` when no eligible asset is available.

Pinpoint Response Example:

```json
{
  "question_id": "q-uuid-1",
  "asset_id": "asset-uuid-101",
  "media_url": "/api/media/asset-uuid-101",
  "player_name": "Alice",
  "player_number": 1,
  "total_players": 2,
  "player_round_number": 1,
  "total_rounds_per_player": 10,
  "turn_number": 1,
  "total_turns": 20,
  "location_mode": true,
  "date_mode": true,
  "game_mode": "pinpoint",
  "round_length": "1m",
  "batch_photos": null,
  "batch_pins": null
}
```

Album Shuffle Response Example:

```json
{
  "question_id": "q-uuid-1",
  "asset_id": "asset-uuid-101",
  "media_url": "/api/media/asset-uuid-101",
  "player_name": "Alice",
  "player_number": 1,
  "total_players": 2,
  "player_round_number": 1,
  "total_rounds_per_player": 10,
  "turn_number": 1,
  "total_turns": 20,
  "location_mode": true,
  "date_mode": true,
  "game_mode": "album_shuffle",
  "round_length": "1m",
  "batch_photos": [
    { "photo_id": "asset-uuid-101", "media_url": "/api/media/asset-uuid-101" },
    { "photo_id": "asset-uuid-102", "media_url": "/api/media/asset-uuid-102" },
    { "photo_id": "asset-uuid-103", "media_url": "/api/media/asset-uuid-103" }
  ],
  "batch_pins": [
    { "pin_id": "A", "latitude": 48.8584, "longitude": 2.2945 },
    { "pin_id": "B", "latitude": 40.7128, "longitude": -74.0060 },
    { "pin_id": "C", "latitude": 35.6762, "longitude": 139.6503 }
  ]
}
```

### GET /api/media/{asset_id}

* Only asset IDs issued as a question in a live match are served (returns `404` for any unauthorized asset ID).
* Automatically resolves the asset's source library from metadata storage.
* Proxies re-encoded preview thumbnail bytes from Immich (carries no EXIF/GPS payload).
* If loading fails, marks the asset as invalid in `metadata.db` to prevent future selection.

### POST /api/answer

Submits a player's guess for the current turn.

Pinpoint Request:

```json
{
  "match_id": "match-uuid-1234",
  "question_id": "q-uuid-1",
  "guessed_latitude": 48.8584,
  "guessed_longitude": 2.2945,
  "guessed_year": 2023,
  "guessed_month": 7,
  "time_taken_seconds": 12.4,
  "timed_out": false
}
```

Album Shuffle Request:

```json
{
  "match_id": "match-uuid-1234",
  "question_id": "q-uuid-1",
  "album_shuffle_answers": [
    { "photo_id": "asset-uuid-101", "assigned_pin_id": "B", "assigned_timeline_index": 0 },
    { "photo_id": "asset-uuid-102", "assigned_pin_id": "A", "assigned_timeline_index": 1 },
    { "photo_id": "asset-uuid-103", "assigned_pin_id": "C", "assigned_timeline_index": 2 }
  ],
  "time_taken_seconds": 18.6,
  "timed_out": false
}
```

* Returns **acknowledgement only** (`round_complete`, `waiting_for`, etc.) without revealing answers before other players take their turn.
* A question can be answered once. Subsequent submissions return `409`.

Response:

```json
{
  "player_name": "Alice",
  "question_id": "q-uuid-1",
  "round_number": 1,
  "turn_completed": 1,
  "total_turns": 20,
  "round_complete": false,
  "waiting_for": ["Bob"],
  "match_finished": false
}
```

### POST /api/round/result

Body: `{"match_id": "match-uuid-1234", "round_number": 1}`

* Reveals actual coordinates, city, country, capture date, and all players' guesses and scores.
* `409` while any player in the round still owes an answer.

Response Example:

```json
{
  "round_number": 1,
  "asset_id": "asset-uuid-101",
  "total_rounds": 10,
  "location_mode": true,
  "date_mode": true,
  "game_mode": "pinpoint",
  "actual_latitude": 48.8584,
  "actual_longitude": 2.2945,
  "actual_date": "2023-07-14",
  "actual_year": 2023,
  "actual_month": 7,
  "actual_city": "Paris",
  "actual_country": "France",
  "batch_reveal": null,
  "results": [
    {
      "player_name": "Alice",
      "guessed_latitude": 48.8500,
      "guessed_longitude": 2.3000,
      "guessed_year": 2023,
      "guessed_month": 7,
      "location_score": 98,
      "date_score": 100,
      "round_score": 198,
      "total_score": 198,
      "distance_km": 1.02,
      "date_diff_days": 0,
      "date_diff_months": 0,
      "date_diff_years_part": 0,
      "date_diff_months_part": 0,
      "date_diff_days_part": 0,
      "timed_out": false,
      "album_shuffle_guesses": null
    }
  ],
  "match_finished": false,
  "score_max_points": 100
}
```

---

## Photo Issue Reporting

### POST /api/assets/flag

Flags an asset with coordinates, date, or other inconsistencies. When flagged, the asset is omitted from future match candidate pools (when `EXCLUDE_FLAGGED_ASSETS=true`).

Request:

```json
{
  "asset_id": "asset-uuid-101",
  "flag_coordinates": true,
  "flag_date": false,
  "other": "GPS location is off by 15km"
}
```

Response:

```json
{
  "success": true,
  "asset_id": "asset-uuid-101",
  "flag_coordinates": true,
  "flag_date": false,
  "other": "GPS location is off by 15km",
  "reported_at": "2026-08-29T18:00:00Z",
  "immich_url": "https://immich.example.com/photos/asset-uuid-101"
}
```

### GET /api/assets/flagged?limit={limit}

Returns a list of all flagged assets with report timestamps and direct Immich Web URLs:

Response:

```json
[
  {
    "id": 1,
    "asset_id": "asset-uuid-101",
    "flag_coordinates": true,
    "flag_date": false,
    "other": "GPS location is off by 15km",
    "reported_at": "2026-08-29T18:00:00Z",
    "immich_url": "https://immich.example.com/photos/asset-uuid-101"
  }
]
```

### DELETE /api/assets/flagged/{asset_id}

Removes an asset from the flagged list, unblocking it for future matches. Returns `200` with `{"success": true}` or `404` if not found.

### GET /api/match/{match_id}/summary?lang={en|pt}

Returns final match summary, player rankings, accuracy percentages, filter metadata, winner list, and full `round_history` replay records from SQLite storage. Supports optional `lang` query parameter (`en` or `pt`) for localized filter summary and tooltip text.

Response:

```json
{
  "match_id": "match-uuid-1234",
  "rounds_played": 10,
  "location_mode": true,
  "date_mode": true,
  "game_mode": "pinpoint",
  "libraries": ["family_library"],
  "album_names": ["Summer Vacation 2024"],
  "finished": true,
  "winners": ["Alice"],
  "players": [
    {
      "player_name": "Alice",
      "location_score": 940,
      "date_score": 980,
      "total_score": 1920,
      "max_possible_score": 2000,
      "accuracy_pct": 96.0,
      "rank": 1,
      "is_winner": true
    }
  ],
  "round_history": [
    {
      "round_number": 1,
      "media_url": "/api/media/asset-uuid-1",
      "actual_latitude": 48.8584,
      "actual_longitude": 2.2945,
      "actual_year": 2023,
      "actual_month": 7,
      "location_mode": true,
      "game_mode": "pinpoint",
      "batch_reveal": null
    }
  ],
  "filter_summary": "Paris • Summer Vacation 2024",
  "filter_tooltip": "Album: Summer Vacation 2024\nCities: Paris",
  "is_custom_filtered": true
}
```

---

## Leaderboard

### GET /api/leaderboard

Queries persistent SQLite leaderboard history (`data/leaderboard.db`).

Query Parameters:

* `rounds`: Filter by round count (`5`, `10`, `20`)
* `round_length`: Filter by timer setting (`30s`, `1m`, `2m`, `5m`, `unlimited`)
* `location_mode`: Filter by location mode enabled (`true`/`false`)
* `date_mode`: Filter by date mode enabled (`true`/`false`)
* `game_mode`: Filter by game mode (`pinpoint`, `album_shuffle`)
* `libraries`: Filter by JSON array or comma-separated library names
* `albums`: Filter by JSON array or comma-separated album names or IDs
* `player_name`: Filter by player name
* `countries`: Filter by JSON array or comma-separated countries
* `cities`: Filter by JSON array or comma-separated cities
* `people`: Filter by JSON array or comma-separated person names or IDs
* `people_mode`: Filter by person match mode (`ANY`, `ALL`)
* `min_date`: Filter by earliest capture date (`YYYY-MM-DD`)
* `max_date`: Filter by latest capture date (`YYYY-MM-DD`)
* `include_shared`: Filter by shared album media inclusion (`true`/`false`)
* `is_custom_filtered`: Filter by preset vs customized dataset (`true`/`false`)
* `exact_filter_match`: Filter by strict exact filter combination vs loose match (`true`/`false`, default `true`)
* `limit`: Maximum number of entries to return

Response:

```json
[
  {
    "match_id": "match-uuid-1234",
    "played_at": "2026-08-16T18:45:00Z",
    "player_name": "Alice",
    "max_possible_score": 2000,
    "total_score": 1920,
    "location_score": 940,
    "date_score": 980,
    "accuracy_pct": 96.0,
    "rank": 1,
    "is_winner": true,
    "awards": ["Sniper", "Speed Demon"],
    "filter_summary": "Paris • Summer Vacation 2024",
    "is_custom_filtered": true,
    "play_mode": "local",
    "challenge_id": null,
    "challenge_title": null,
    "room_id": null,
    "room_name": null,
    "config": {
      "rounds": 10,
      "round_length": "1m",
      "location_mode": true,
      "date_mode": true,
      "game_mode": "pinpoint",
      "libraries": ["family_library"],
      "album_names": ["Summer Vacation 2024"],
      "album_ids": ["album-uuid-1"],
      "person_ids": [],
      "people_mode": "ANY",
      "countries": ["France"],
      "cities": ["Paris"],
      "min_date": null,
      "max_date": null,
      "include_shared": false
    }
  }
]
```

---

## Flagged Asset Management

### POST /api/assets/flag

Reports an inconsistency (GPS/location, date/timestamp, or general issue) on an asset. Flagged assets are automatically excluded from future candidate selection when `EXCLUDE_FLAGGED_ASSETS=true`.

Request:

```json
{
  "asset_id": "asset-uuid-101",
  "flag_coordinates": true,
  "flag_date": false,
  "other": "Location pinned in wrong town",
  "reported_by": "Alice"
}
```

Response:

```json
{
  "success": true,
  "asset_id": "asset-uuid-101",
  "flag_coordinates": true,
  "flag_date": false,
  "other": "Location pinned in wrong town",
  "reported_by": "Alice",
  "reported_at": "2026-08-29T18:00:00Z",
  "immich_url": "https://immich.example.com/photos/asset-uuid-101"
}
```

### GET /api/assets/flagged

Lists reported asset issues for administrative inspection.

Query Parameters:

* `limit`: Maximum number of records to return (1–1000, default `100`).

Response:

```json
[
  {
    "id": 1,
    "asset_id": "asset-uuid-101",
    "flag_coordinates": true,
    "flag_date": false,
    "other": "Location pinned in wrong town",
    "reported_by": "Alice",
    "reported_at": "2026-08-29T18:00:00Z",
    "immich_url": "https://immich.example.com/photos/asset-uuid-101"
  }
]
```

### DELETE /api/assets/flagged/{asset_id}

Removes an asset from the flagged table, restoring its eligibility in matches.

Response:

```json
{
  "success": true,
  "asset_id": "asset-uuid-101"
}
```

---

## Anti-Cheat Rules

Question payloads never include answer fields:

* No EXIF metadata or capture timestamp
* No GPS coordinates (latitude / longitude)
* No city or country names

Answer submissions return no reveal data. Reveal data is only available from `POST /api/round/result` once every player in the round has completed their turn.

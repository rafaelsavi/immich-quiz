# Step 3: Update `append_match()` to Store `album_names_json`

## File
`src/storage/leaderboard.py`

## Problem
`append_match()` currently stores album names as a lossy comma-joined string:
```python
album_name = ', '.join(config.album_names) if config.album_names else '-'
```
This needs to use `_canonicalize_filter_list()` like all other multi-value filters.

## Change 1: Replace `album_name` variable construction

### Location: Line 178

**BEFORE:**
```python
        album_name = ', '.join(config.album_names) if config.album_names else '-'
```

**AFTER:**
```python
        album_names_json = _canonicalize_filter_list(config.album_names)
```

This uses the existing `_canonicalize_filter_list()` helper (line 129) which sorts and returns a canonical JSON string like `'["Trip 1", "Trip 2"]'` or `None` if the list is empty.

## Change 2: Update the INSERT column list

### Location: Lines 186–194 (the INSERT statement column names)

**BEFORE:**
```python
                INSERT OR REPLACE INTO matches (
                    match_id, challenge_id, room_id, room_name, play_mode, played_at,
                    libraries_json, game_mode,
                    rounds, round_length, location_mode, date_mode,
                    album_name, album_ids_json, person_ids_json, people_mode,
                    countries_json, cities_json, min_date, max_date,
                    include_shared, is_custom_filtered, filter_summary, duration_seconds
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
```

**AFTER:**
```python
                INSERT OR REPLACE INTO matches (
                    match_id, challenge_id, room_id, room_name, play_mode, played_at,
                    libraries_json, game_mode,
                    rounds, round_length, location_mode, date_mode,
                    album_names_json, album_ids_json, person_ids_json, people_mode,
                    countries_json, cities_json, min_date, max_date,
                    include_shared, is_custom_filtered, filter_summary, duration_seconds
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
```

Only `album_name` → `album_names_json` in the column list. The parameter count (24 `?`s) stays the same.

## Change 3: Update the parameter tuple

### Location: Lines 196–221 (the VALUES parameter tuple)

**BEFORE (line 209):**
```python
                    album_name,
```

**AFTER:**
```python
                    album_names_json,
```

The full parameter tuple should now be:
```python
                (
                    match_id,
                    challenge_id,
                    room_id,
                    room_name,
                    play_mode.value,
                    played_at,
                    libraries_json,
                    config.game_mode.value,
                    config.round_count,
                    config.round_length.value,
                    1 if config.location_mode else 0,
                    1 if config.date_mode else 0,
                    album_names_json,        # ← CHANGED
                    album_ids_json,
                    person_ids_json,
                    config.people_mode.value,
                    countries_json,
                    cities_json,
                    config.min_date.isoformat() if config.min_date else None,
                    config.max_date.isoformat() if config.max_date else None,
                    1 if config.include_shared else 0,
                    is_custom,
                    summary,
                    duration_seconds,
                ),
```

## Verification
- Tests will still fail at this point (schema and query tests reference `album_name`). That's expected.
- No need to run tests after this step; continue to Step 4.

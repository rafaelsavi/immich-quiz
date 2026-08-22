# Step 4: Update `list_entries()` — SQL, Result Parsing, and Variable Shadowing Fix

## File
`src/storage/leaderboard.py`

## Problem A: SQL SELECT references `m.album_name`
The SELECT query still fetches `m.album_name` which no longer exists in the schema.

## Problem B: Result parsing doesn't decode `album_names_json`
The `config` dict built from each row doesn't include an `album_names` key.

## Problem C: Variable shadowing
The SQL query string is assigned to a variable called `query` (line 492), which shadows the `query: LeaderboardQuery` parameter from line 299.

---

## Change 1: Fix variable shadowing — rename SQL string

### Location: Line 492 and Line 536

**BEFORE (line 492):**
```python
        query = f"""
        SELECT
```

**AFTER:**
```python
        sql = f"""
        SELECT
```

**BEFORE (line 536):**
```python
        rows = self._db.fetch_all(query, params)
```

**AFTER:**
```python
        rows = self._db.fetch_all(sql, params)
```

---

## Change 2: Update SELECT column from `album_name` to `album_names_json`

### Location: Line 511 (inside the SELECT statement)

**BEFORE:**
```python
            m.album_name,
```

**AFTER:**
```python
            m.album_names_json,
```

The full SELECT list should be (lines 493–527):
```python
        sql = f"""
        SELECT
            e.match_id,
            m.played_at,
            e.player_name,
            e.location_score,
            e.date_score,
            e.total_score,
            e.max_possible_score,
            e.accuracy_pct,
            e.rank,
            e.is_winner,
            e.total_time_seconds,
            m.rounds,
            m.round_length,
            m.location_mode,
            m.date_mode,
            m.game_mode,
            m.libraries_json,
            m.album_names_json,
            m.album_ids_json,
            m.person_ids_json,
            m.people_mode,
            m.countries_json,
            m.cities_json,
            m.min_date,
            m.max_date,
            m.include_shared,
            m.is_custom_filtered,
            m.filter_summary,
            m.duration_seconds,
            m.play_mode,
            m.challenge_id,
            m.room_id,
            m.room_name,
            c.title AS challenge_title
        FROM match_entries e
        JOIN matches m ON e.match_id = m.match_id
        LEFT JOIN challenges c ON m.challenge_id = c.challenge_id
        {where_sql}
        ORDER BY e.accuracy_pct DESC, e.total_score DESC, m.played_at DESC, e.rank ASC
        {limit_sql}
        """
```

---

## Change 3: Parse `album_names_json` in result loop

### Location: Lines 539–565 (the result parsing loop)

**BEFORE (lines 539–565):**
```python
        for row in rows:
            libraries = (
                json.loads(row['libraries_json'])
                if row.get('libraries_json')
                else []
            )
            album_ids = json.loads(row['album_ids_json']) if row['album_ids_json'] else []
            person_ids = json.loads(row['person_ids_json']) if row['person_ids_json'] else []
            countries = json.loads(row['countries_json']) if row['countries_json'] else []
            cities = json.loads(row['cities_json']) if row['cities_json'] else []

            config = {
                'rounds': row['rounds'],
                'round_length': row['round_length'],
                'location_mode': bool(row['location_mode']),
                'date_mode': bool(row['date_mode']),
                'game_mode': row['game_mode'],
                'libraries': libraries,
                'album_ids': album_ids,
                'person_ids': person_ids,
                'people_mode': row['people_mode'] or 'ANY',
                'countries': countries,
                'cities': cities,
                'min_date': row['min_date'],
                'max_date': row['max_date'],
                'include_shared': bool(row['include_shared']) if 'include_shared' in row else False,
            }
```

**AFTER:**
```python
        for row in rows:
            libraries = (
                json.loads(row['libraries_json'])
                if row.get('libraries_json')
                else []
            )
            album_names = (
                json.loads(row['album_names_json'])
                if row.get('album_names_json')
                else []
            )
            album_ids = json.loads(row['album_ids_json']) if row['album_ids_json'] else []
            person_ids = json.loads(row['person_ids_json']) if row['person_ids_json'] else []
            countries = json.loads(row['countries_json']) if row['countries_json'] else []
            cities = json.loads(row['cities_json']) if row['cities_json'] else []

            config = {
                'rounds': row['rounds'],
                'round_length': row['round_length'],
                'location_mode': bool(row['location_mode']),
                'date_mode': bool(row['date_mode']),
                'game_mode': row['game_mode'],
                'libraries': libraries,
                'album_names': album_names,
                'album_ids': album_ids,
                'person_ids': person_ids,
                'people_mode': row['people_mode'] or 'ANY',
                'countries': countries,
                'cities': cities,
                'min_date': row['min_date'],
                'max_date': row['max_date'],
                'include_shared': bool(row['include_shared']) if 'include_shared' in row else False,
            }
```

**Changes:**
1. Added `album_names` parsing block (same pattern as `libraries`)
2. Added `'album_names': album_names` to the config dict

---

## Summary of all changes in this step

| Line(s) | Change |
|---------|--------|
| 492 | `query = f"""` → `sql = f"""` |
| 511 | `m.album_name,` → `m.album_names_json,` |
| 536 | `self._db.fetch_all(query, params)` → `self._db.fetch_all(sql, params)` |
| 545 (new) | Add `album_names = json.loads(...)` parsing block |
| 557 (new) | Add `'album_names': album_names` to config dict |

## Verification
- Tests will still fail (test assertions reference old `album_name` column). Continue to Step 5.

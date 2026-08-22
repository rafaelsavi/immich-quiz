# Step 2: Replace `album_name` with `album_names_json` in Leaderboard Schema

## File
`src/storage/leaderboard.py`

## Problem
The `matches` table still has an `album_name TEXT` column from the old single-album design. With the new multi-library/multi-album approach, album names need to be stored as a canonical JSON array (just like `libraries_json`, `countries_json`, etc.) to avoid lossy comma-joining.

## Change 1: `LEADERBOARD_SCHEMA_SQL` constant

### Location: Line 54 (inside the `matches` table definition)

**BEFORE:**
```sql
    album_name         TEXT,
```

**AFTER:**
```sql
    album_names_json   TEXT,
```

## Change 2: Index rename (optional but consistent)

### Location: Line 111

There is no existing index on `album_name`, so no index needs updating.

## Change 3: `challenges` table — verify `libraries_json`

### Location: Lines 27–38

The `challenges` table already has `libraries_json TEXT` (replacing the old `library_name TEXT NOT NULL`). Confirm it looks like this — no change needed:

```sql
CREATE TABLE IF NOT EXISTS challenges (
    challenge_id       TEXT PRIMARY KEY,
    capability_token   TEXT UNIQUE NOT NULL,
    title              TEXT,
    creator_name       TEXT NOT NULL,
    libraries_json     TEXT,
    config_json        TEXT NOT NULL,
    asset_ids_json     TEXT NOT NULL,
    created_at         TEXT NOT NULL,
    expires_at         TEXT,
    is_active          INTEGER NOT NULL DEFAULT 1
);
```

## Summary of schema change

| Column | Old | New |
|--------|-----|-----|
| `matches.library_name` | `TEXT NOT NULL` | **Already removed** → `libraries_json TEXT` ✅ |
| `matches.album_name` | `TEXT` | → `album_names_json TEXT` ← **THIS STEP** |

## Important
Since there is no legacy compatibility concern, the old leaderboard DB will simply be recreated with the new schema. No migration SQL is needed.

## Verification
- Run: `.venv\Scripts\python.exe -m pytest tests/test_leaderboard.py::test_leaderboard_schema_creation -x -q`
- This test WILL FAIL after this step (it asserts `album_name` exists). That's expected — Step 5 fixes the tests.

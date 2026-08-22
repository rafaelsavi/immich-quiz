# Step 5: Update Tests for Schema Changes

## File
`tests/test_leaderboard.py`

## Problem
Two tests reference the old `album_name` column that was replaced by `album_names_json` in Step 2.

---

## Change 1: Schema creation test

### Location: Line 32

**BEFORE:**
```python
    assert 'album_name' in match_cols
```

**AFTER:**
```python
    assert 'album_names_json' in match_cols
```

### Context (lines 29–33):
```python
    match_cols = [c['name'] for c in db.fetch_all('PRAGMA table_info(matches)')]
    assert 'libraries_json' in match_cols
    assert 'album_ids_json' in match_cols
    assert 'album_names_json' in match_cols  # ← CHANGED
```

---

## Change 2: Multi-album storage test

### Location: Line 613

**BEFORE:**
```python
    assert row['album_name'] == 'Trip 1, Trip 2'
```

**AFTER:**
```python
    assert row['album_names_json'] == '["Trip 1", "Trip 2"]'
```

### Context (lines 609–620):
```python
    db = DatabaseManager(db_path)
    row = db.fetch_one('SELECT * FROM matches WHERE match_id = ?', ('m-multi-album',))
    assert row is not None
    assert row['album_ids_json'] == '["alb-1", "alb-2"]'
    assert row['album_names_json'] == '["Trip 1", "Trip 2"]'  # ← CHANGED: canonical sorted JSON

    # Query with exact album IDs via LeaderboardQuery
    q = LeaderboardQuery.from_config(config)
    res = store.list_entries(q)
    assert len(res) == 1
    assert res[0].match_id == 'm-multi-album'
    assert res[0].config['album_ids'] == ['alb-1', 'alb-2']
```

### Why the value changed
The old code stored `', '.join(album_names)` → `"Trip 1, Trip 2"` (plain comma-joined string).
The new code uses `_canonicalize_filter_list(config.album_names)` which:
1. Strips whitespace from each name
2. Sorts alphabetically
3. Returns `json.dumps(sorted_list)` → `'["Trip 1", "Trip 2"]'`

Since `"Trip 1"` sorts before `"Trip 2"` alphabetically, the order is the same here. But be aware that `_canonicalize_filter_list` always sorts, so `['B', 'A']` would become `'["A", "B"]'`.

---

## Summary of all changes in this step

| File | Line | Change |
|------|------|--------|
| `tests/test_leaderboard.py` | 32 | `'album_name'` → `'album_names_json'` |
| `tests/test_leaderboard.py` | 613 | `row['album_name'] == 'Trip 1, Trip 2'` → `row['album_names_json'] == '["Trip 1", "Trip 2"]'` |

## Verification
After this step, run:
```
.venv\Scripts\python.exe -m pytest tests/test_leaderboard.py -x -q
```

All leaderboard tests should now pass.

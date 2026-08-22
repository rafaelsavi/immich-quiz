# Step 6: Full Verification

## Run the full test suite

```
.venv\Scripts\python.exe -m pytest tests/ -x --tb=short -q
```

**Expected result**: All 246 tests pass (or 246+, if new tests were added).

## Checklist

### Schema Consistency
- [ ] `matches.album_name` column no longer exists
- [ ] `matches.album_names_json` column exists and stores canonical JSON arrays
- [ ] `matches.libraries_json` column exists (already done in prior refactor)
- [ ] `challenges.libraries_json` column exists (already done in prior refactor)
- [ ] No remaining references to `library_name` in the leaderboard schema (matches/challenges)

### Code Consistency
- [ ] `src/models.py` imports `Any` from `typing`
- [ ] `src/storage/leaderboard.py` — `append_match()` stores `album_names_json` via `_canonicalize_filter_list()`
- [ ] `src/storage/leaderboard.py` — `list_entries()` SQL selects `m.album_names_json`
- [ ] `src/storage/leaderboard.py` — `list_entries()` parses `album_names_json` into `album_names` list in config dict
- [ ] `src/storage/leaderboard.py` — SQL string variable is `sql`, not `query` (no parameter shadowing)
- [ ] No grep hits for `album_name` in `src/storage/leaderboard.py` (all references are now `album_names_json` or `album_names`)

### Grep validation commands

Run these to confirm no stale references remain:

```powershell
# Should return ZERO hits in leaderboard.py (all album_name references gone):
Select-String -Path src/storage/leaderboard.py -Pattern "album_name[^s]" -CaseSensitive

# Should return ZERO hits for old library_name in leaderboard schema:
Select-String -Path src/storage/leaderboard.py -Pattern "library_name" -CaseSensitive

# Confirm album_names_json appears in the schema, append, and list methods:
Select-String -Path src/storage/leaderboard.py -Pattern "album_names_json"
```

## What NOT to change

The following files already correctly use `album_names` (plural, as a list) and need NO changes:
- `src/models.py` — `FilterDisplayMeta.album_names`, `MatchSummaryResponse.album_names`
- `src/game/service.py` — `resolve_album_names()`, `setup.album_names`, `state.setup.album_names`
- `static/js/modules/summary/share.js` — `summary.album_names`
- `static/js/modules/summary/table.js` — `summary.album_names`
- `static/js/app.js` — `album_names: albumNames`

These all work with the new list-based approach already. ✅

## Summary of complete change set across all steps

| Step | File | Changes |
|------|------|---------|
| 1 | `src/models.py` | Add `from typing import Any` import |
| 2 | `src/storage/leaderboard.py` | Schema: `album_name TEXT` → `album_names_json TEXT` |
| 3 | `src/storage/leaderboard.py` | `append_match()`: store via `_canonicalize_filter_list(config.album_names)` |
| 4 | `src/storage/leaderboard.py` | `list_entries()`: update SQL column, parse JSON, fix `query` → `sql` shadowing |
| 5 | `tests/test_leaderboard.py` | Update 2 test assertions for new column name and JSON format |

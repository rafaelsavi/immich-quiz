# Library-as-a-Filter Refactor — Implementation Guide

## Context

This refactor treats `library_name` as a multi-select filter (like albums, countries, etc.) instead of a mandatory top-level gateway. The bulk of the work was already done by a previous AI session but left several issues that need fixing before commit.

## Current State

- **Tests**: All 246 tests pass on the current working tree
- **Pending changes**: 33 modified files, ~1575 additions, ~853 deletions (uncommitted)
- **No legacy compatibility needed** — old DB can be dropped

## Step Files

Execute these steps **in order**. Each step is self-contained with exact file paths, code locations, and the precise changes to make.

| Step | File | Description |
|------|------|-------------|
| [Step 1](step_01_models_import.md) | `src/models.py` | Add missing `Any` import |
| [Step 2](step_02_leaderboard_schema.md) | `src/storage/leaderboard.py` | Replace `album_name` column with `album_names_json` in schema |
| [Step 3](step_03_leaderboard_append.md) | `src/storage/leaderboard.py` | Update `append_match()` to store `album_names_json` |
| [Step 4](step_04_leaderboard_list.md) | `src/storage/leaderboard.py` | Update `list_entries()` SQL, result parsing, and fix variable shadowing |
| [Step 5](step_05_tests_leaderboard.md) | `tests/test_leaderboard.py` | Update tests for schema changes |
| [Step 6](step_06_verify.md) | — | Run full test suite, verify everything passes |

## Architecture Summary After Refactor

```
PhotoFilterScope          ← Pure ID-based filter dimensions (libraries, album_ids, person_ids, etc.)
FilterDisplayMeta         ← Resolved display names (album_names, person_names)
GameFilterConfig          ← PhotoFilterScope + FilterDisplayMeta + format helpers
GameRulesConfig           ← round_count, round_length, location/date mode, game_mode
BaseGameConfig            ← GameFilterConfig + GameRulesConfig (diamond composition)
LeaderboardQuery          ← Independent query model for leaderboard searches
```

`library_name` is no longer a mandatory singular field. It is now `libraries: list[str]` — a multi-select filter dimension treated identically to `countries`, `cities`, etc.

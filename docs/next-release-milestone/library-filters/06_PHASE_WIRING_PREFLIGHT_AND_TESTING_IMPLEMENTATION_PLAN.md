# Phase 6: Wiring, Preflight & Testing — Implementation Plan

## Goal

Wire the frontend filter components in `app.js`, connecting the debounced preflight checks, dependent city filtering, per-library localStorage persistence, and the filter badge summary. Add remaining test coverage and update project documentation.

---

## Proposed Changes

### 1. Frontend — `static/js/app.js`

This is the largest change. The spec defines 8 new functions and significant rewiring of the bootstrap/library-switch flow.

#### Key additions:
- **Import** `MultiSelect` and `DateRangeSlider` components
- **`initFilterComponents()`** — Instantiate `albumMultiSelect`, `countryMultiSelect`, `cityMultiSelect`, `peopleMultiSelect`, `dateRangeSlider`; bind people-mode toggle, accordion expand/collapse, and reset-filters button
- **`updateDependentCities(selectedCountries)`** — Filter city dropdown based on selected countries from cached raw cities
- **`saveCurrentLibraryFilters()` / `restoreLibraryFilters()` / `clearSavedLibraryFilters()`** — localStorage per-library state management
- **`getSelectedPeopleMode()` / `setPeopleMode()` / `resetPeopleMode()`** — People mode OR/AND toggle management
- **`updatePeopleModeToggleVisibility()`** — Show OR/AND toggle only when ≥2 people selected
- **`updateFiltersSummaryBadge()`** — Count active filters and update the badge text
- **`triggerPreflightDebounced()`** — Debounced live preflight with 500ms delay
- **`showPreflightWarning()` / `hidePreflightWarning()`** — Non-blocking preflight warnings in the UI
- **`executePreflight()`** — POST to `/api/game/preflight` with all active filter params
- **`onLibrarySelected(libraryName)`** — Replaces `initAlbums()` on library switch: fetches albums + filters in parallel, populates all filter components, restores saved state

#### Modifications:
- **`initLibraries()`** — Call `initFilterComponents()` first, then call `onLibrarySelected()` instead of `initAlbums()`
- **`el.library` change handler** — Call `onLibrarySelected()` instead of `initAlbums()`
- **`startMatch()`** — Include filter params (`person_ids`, `people_mode`, `countries`, `cities`, `min_date`, `max_date`) in both preflight and setup payloads
- Remove the legacy album multi-select UI code (~lines 50-310) since it's now handled by the `MultiSelect` component
- **`refreshActiveScreenLanguage()`** — Update filter component trigger UIs on language change

---

### 2. Tests — `tests/test_config.py`

#### [MODIFY] [test_config.py](file:///d:/Rafael/Projects/immich-quiz/tests/test_config.py)

Add `test_parse_comma_set()` to validate the `_parse_comma_set` config parser:
- `None` → `frozenset()`
- `''` → `frozenset()`
- `'  '` → `frozenset()`
- `'France, Germany, brazil '` → `frozenset({'france', 'germany', 'brazil'})`

---

### 3. Tests — `tests/test_immich_client.py`

#### [MODIFY] [test_immich_client.py](file:///d:/Rafael/Projects/immich-quiz/tests/test_immich_client.py)

Add:
- **`test_list_people_filtering`** — Mock `/people` response, verify whitelist/blacklist filtering
- **`test_is_eligible_asset_with_people_or_and_modes`** — Verify OR mode matches single person from pair; AND mode rejects single but accepts both

---

### 4. Tests — `tests/test_filters_api.py`

#### [MODIFY] [test_filters_api.py](file:///d:/Rafael/Projects/immich-quiz/tests/test_filters_api.py)

The spec's tests (filters endpoint, preflight people AND mode, preflight diversity rejection) are already substantially covered by existing tests. I will verify the existing coverage is sufficient and add any missing scenarios.

---

### 5. Documentation Updates

#### [MODIFY] [ARCHITECTURE.md](file:///d:/Rafael/Projects/immich-quiz/docs/ARCHITECTURE.md)
- Add filter components to Module Map (`components/multi_select.js`, `components/range_slider.js`)
- Add `GET /api/filters` to Round Data Flow
- Mention per-library filter persistence and server-side TTL cache

#### [MODIFY] [README.md](file:///d:/Rafael/Projects/immich-quiz/README.md)
- Add new env vars to the table: `PHOTO_DIVERSITY_MIN_DISTANCE_KM`, `PHOTO_DIVERSITY_MIN_TIME_SECONDS`, `COUNTRY_WHITELIST`, `COUNTRY_BLACKLIST`, `CITY_WHITELIST`, `CITY_BLACKLIST`, `PEOPLE_WHITELIST`, `PEOPLE_BLACKLIST`
- Update feature description to mention library filters

#### [MODIFY] [TODO.md](file:///d:/Rafael/Projects/immich-quiz/docs/TODO.md)
- Mark "Add more library filter settings" as complete (~~strikethrough~~)

---

## Verification Plan

### Automated Tests
```bash
uv run ruff check .
uv run mypy src
uv run pytest --cov=src --cov-report=term-missing
```

All 202+ tests must pass. New tests for `_parse_comma_set`, `list_people_filtering`, and `is_eligible_asset` people modes will be added.

### Manual Verification
Since the app is running (`uv run -m src.main`), I will verify the frontend wiring via the browser after implementation.

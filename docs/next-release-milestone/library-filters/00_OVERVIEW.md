# Library Filter Settings & Grouping — Overview

## What This Feature Is

Immich Quiz currently allows users to select a **Library** and optionally one or more **Albums**. We are adding advanced, granular media filtering and settings organization:

1. **Smart Photo Diversity (100m / 60s)**: Evaluates candidate photo diversity (spatial separation $\ge 100\text{m}$ and temporal separation $\ge 60\text{s}$) with soft prioritization and unplayed photo fallback, preventing photo clusters while avoiding 404 match aborts on localized albums.
2. **Dynamic Filter by Date (Year-Month resolution)**: A dual-handle range slider in the GUI that lets players narrow photo eligibility to a specific time span (e.g. `2018-05` to `2022-12`), respecting `.env` boundary limits.
3. **Geographic Granularity (Filter by Country & Dependent Cities)**: Searchable multi-select dropdowns for countries and cities/states. Cities are dynamically filtered based on currently selected countries (or all cities if no country is selected).
4. **Filter by People (with `OR` / `AND` match modes)**: A searchable multi-select dropdown to filter photos by named individuals recognized by Immich face recognition (filtered against `.env` whitelist/blacklist rules). When multiple people are selected, players can choose between:
   - **`OR` (Any)**: Photos containing at least one of the selected individuals.
   - **`AND` (All together)**: Photos containing all selected individuals together in the same photo (e.g. couple or group photos).
5. **Settings Grouping & Top-Down Hierarchy**: Dataset scoping (Library, Albums, Dates, Geography, People) comes *before* Game Mode & Rules in the setup GUI. Filters are stored in a collapsible section with an active filter badge and reset button.
6. **Per-Library Filter Persistence**: Active filter selections are saved in `localStorage` per library. Switching libraries automatically restores the previously used filters for that library.

---

## Architectural Principles & Rules

1. **Zero Full-Photo Scanning**:
   - People are fetched via Immich's indexed `GET /people` database endpoint (~20ms).
   - Date boundaries are discovered via Immich's timeline bucket index (`GET /timeline/buckets`).
   - Countries and cities with country mappings are resolved via Immich's explore/places metadata or `.env` configuration.
2. **Strict Selectables & Cascading Geography**:
   - Countries, Cities, and People must be chosen from validated multi-select dropdowns.
   - Selecting one or more countries immediately filters the City dropdown to only show cities belonging to those countries.
3. **Smart Photo Diversity Sampling (100m / 60s)**:
   - Candidate photo selection prioritizes photos with spatial ($\ge 100\text{m}$) and temporal ($\ge 60\text{s}$) separation against previously served match photos, while gracefully falling back to unplayed candidates when playing clustered single-event or local albums.
4. **Server-Side In-Memory Caching**:
   - Filter metadata (people list, country list, city-country mapping, date bounds) is cached in memory per library on the FastAPI server with a 5-minute TTL to ensure instant 0ms responses on subsequent accesses.
5. **DRY Component Architecture**:
   - Extract the custom multi-select UI into a reusable, modular JavaScript component (`MultiSelect`) used identically for Albums, Countries, Cities, and People.
6. **Preserve Scoring & Game Engines**:
   - `PinpointEngine` and `AlbumShuffleEngine` logic, round mechanics, and math scoring remain untouched; only candidate asset eligibility is refined.
7. **Bilingual Support**:
   - Every new UI element, preflight warning, and message must have complete translations in both **English (`EN`)** and **Brazilian Portuguese (`PT`)**.

---

## Codebase Map & Target Files

```
.env.example                                      # Add diversity & filter whitelist/blacklist variables
src/
├── config.py                                     # Parse diversity settings, whitelists/blacklists, date bounds
├── models.py                                     # Add FilterResponse, update Preflight/Setup requests
├── immich/
│   └── client.py                                 # Add list_people, get_timeline_bounds, search query updates
├── game/
│   ├── selector.py                               # Strict diversity evaluation and candidate pool filtering
│   └── service.py                                # Preflight and setup game with new filter parameters
└── api/
    └── routes.py                                 # Add GET /api/filters endpoint

static/
├── index.html                                    # Expandable filters section, slider, multi-selects
├── css/
│   ├── style.css                                 # Include new filter styles
│   └── components/
│       ├── multi_select.css                      # Generalized multi-select styles
│       ├── range_slider.css                      # Dual-handle date range slider styles
│       └── filters.css                           # Expandable section and filter group styling
└── js/
    ├── app.js                                    # App controller filter lifecycle & preflight
    └── modules/
        ├── state.js                              # Element references & filter state
        ├── i18n.js                               # EN & PT translation keys
        └── components/
            ├── multi_select.js                   # Reusable MultiSelect component
            └── range_slider.js                   # Dual-handle range slider component

tests/
├── test_config.py                                # Config parsing unit tests
├── test_diversity.py                             # Strict diversity safeguard unit tests
├── test_immich_client.py                         # Immich client filtering tests
├── test_filters_api.py                           # /api/filters route tests
└── test_selector.py                              # Candidate selection diversity tests
```

---

## Implementation Phases

| Phase | Title | Summary |
| :--- | :--- | :--- |
| **Phase 1** | [Strict Diversity Safeguard & Config](file:///d:/Rafael/Projects/immich-quiz/docs/next-release-milestone/library-filters/01_PHASE_STRICT_DIVERSITY_AND_CONFIG.md) | Isolate `PHOTO_DIVERSITY_MIN_DISTANCE_KM` and `PHOTO_DIVERSITY_MIN_TIME_SECONDS`, implement shared diversity evaluator, enforce strict preflight and eliminate loose selector fallbacks |
| **Phase 2** | [Filter Whitelists & Immich Client](file:///d:/Rafael/Projects/immich-quiz/docs/next-release-milestone/library-filters/02_PHASE_CONFIG_AND_IMMICH_CLIENT.md) | Whitelist/blacklist config, Immich `GET /people`, `GET /timeline/buckets`, `GET /search/explore`, and `SearchQuery` extensions |
| **Phase 3** | [Backend Models & API Routes](file:///d:/Rafael/Projects/immich-quiz/docs/next-release-milestone/library-filters/03_PHASE_BACKEND_MODELS_AND_ROUTES.md) | `GET /api/filters` endpoint, server-side caching, updated `PreflightRequest` & `GameSetupRequest` |
| **Phase 4** | [Reusable MultiSelect Component](file:///d:/Rafael/Projects/immich-quiz/docs/next-release-milestone/library-filters/04_PHASE_REUSABLE_MULTISELECT.md) | Modular JavaScript class for Albums, Countries, Cities, and People with search, tag pills, and clear actions |
| **Phase 5** | [Frontend UI, Slider & Grouping](file:///d:/Rafael/Projects/immich-quiz/docs/next-release-milestone/library-filters/05_PHASE_FRONTEND_UI_AND_GROUPING.md) | Expandable accordion container, dual-handle range slider, HTML templates, CSS, and bilingual i18n dictionary |
| **Phase 6** | [Wiring, Preflight & Testing](file:///d:/Rafael/Projects/immich-quiz/docs/next-release-milestone/library-filters/06_PHASE_WIRING_PREFLIGHT_AND_TESTING.md) | `app.js` lifecycle hooks, dependent cities, debounced live preflight, automated pytest suite, and manual verification |

---

## 🤖 How to Feed This to an AI Agent / Model

To ensure 100% bug-free execution without context fatigue, **execute one phase at a time sequentially**.

### Workflow Protocol for the Model / Developer

1. **Read Before Writing**: Always read the target phase document and its referenced codebase files first.
2. **Execute Phase Code**: Make the exact changes specified in the phase document.
3. **Verify with Tests**: Run the corresponding automated tests (`pytest`) before concluding the phase.
4. **Update Phase Status**: Check off the acceptance checklist (`[x]`) in that phase file.
5. **Global Docs at the End**: Only update global project files ([`docs/ARCHITECTURE.md`](file:///d:/Rafael/Projects/immich-quiz/docs/ARCHITECTURE.md), [`README.md`](file:///d:/Rafael/Projects/immich-quiz/README.md), [`docs/TODO.md`](file:///d:/Rafael/Projects/immich-quiz/docs/TODO.md)) after **Phase 6** is fully completed and verified.

---

### 📋 Copy-Paste Prompt Templates for Each Phase

#### Prompt for Phase 1

```text
Please implement Phase 1 of the Library Filters milestone according to the specification in docs/next-release-milestone/library-filters/01_PHASE_STRICT_DIVERSITY_AND_CONFIG.md.
Follow the implementation steps, run the pytest suite in tests/test_diversity.py, and verify all acceptance criteria.
```

#### Prompt for Phase 2

```text
Please implement Phase 2 of the Library Filters milestone according to the specification in docs/next-release-milestone/library-filters/02_PHASE_CONFIG_AND_IMMICH_CLIENT.md.
Follow the implementation steps, run the pytest suite in tests/test_config.py and tests/test_immich_client.py, and verify all acceptance criteria.
```

#### Prompt for Phase 3

```text
Please implement Phase 3 of the Library Filters milestone according to the specification in docs/next-release-milestone/library-filters/03_PHASE_BACKEND_MODELS_AND_ROUTES.md.
Follow the implementation steps, run the pytest suite in tests/test_filters_api.py, and verify all acceptance criteria.
```

#### Prompt for Phase 4

```text
Please implement Phase 4 of the Library Filters milestone according to the specification in docs/next-release-milestone/library-filters/04_PHASE_REUSABLE_MULTISELECT.md.
Build static/js/modules/components/multi_select.js and static/css/components/multi_select.css, wire unit DOM tests if applicable, and verify all acceptance criteria.
```

#### Prompt for Phase 5

```text
Please implement Phase 5 of the Library Filters milestone according to the specification in docs/next-release-milestone/library-filters/05_PHASE_FRONTEND_UI_AND_GROUPING.md.
Implement the accordion HTML, DateRangeSlider component, CSS stylesheets, and bilingual i18n keys, and verify all acceptance criteria.
```

#### Prompt for Phase 6 (Final Integration)

```text
Please implement Phase 6 of the Library Filters milestone according to the specification in docs/next-release-milestone/library-filters/06_PHASE_WIRING_PREFLIGHT_AND_TESTING.md.
Wire app.js, connect dependent cities, debounced preflight, and localStorage persistence. Run the complete pytest test suite and complete the manual verification checklist.
Once verified, update docs/ARCHITECTURE.md, README.md, and mark the item complete in docs/TODO.md.
```

# Library Filter Settings & Grouping — Overview

## What This Feature Is

Immich Quiz currently allows users to select a **Library** and optionally one or more **Albums**. We are adding advanced, granular media filtering and settings organization:

1. **Dynamic Filter by Date (Year-Month resolution)**: A dual-handle range slider in the GUI that lets players narrow photo eligibility to a specific time span (e.g. `2018-05` to `2022-12`), respecting `.env` boundary limits.
2. **Geographic Granularity (Filter by Country & City/Region)**: Searchable multi-select dropdowns to filter photos by recognized countries and cities/states (e.g. *"France"*, *"Paris"*, *"Tokyo"*), filtered against `.env` whitelist/blacklist rules.
3. **Filter by People**: A searchable multi-select dropdown to filter photos by named individuals recognized by Immich face recognition, filtered against `.env` whitelist/blacklist rules.
4. **Settings Grouping & Collapsible Section**: Clean UI organization that keeps core game rules visible while housing advanced library/media filters inside a polished, expandable section with active filter summary badges.

---

## Architectural Principles & Rules

1. **Zero Full-Photo Scanning**:
   - People are fetched via Immich's indexed `GET /people` database endpoint (~20ms).
   - Date boundaries are discovered via Immich's timeline bucket index (`GET /timeline/buckets`).
   - Countries are resolved via Immich's explore/places metadata or `.env` configuration.
2. **Strict Selectables (No Free Text)**:
   - Countries and People must be chosen from validated, searchable multi-select dropdowns to prevent typos and zero-result queries.
3. **Server-Side In-Memory Caching**:
   - Filter metadata (people list, country list, date bounds) is cached in memory per library on the FastAPI server to ensure instant 0ms responses on subsequent accesses.
4. **DRY Component Architecture**:
   - Extract the custom multi-select UI into a reusable, modular JavaScript component (`MultiSelect`) used identically for Albums, Countries, Cities, and People.
5. **Preserve Scoring & Game Engines**:
   - `PinpointEngine` and `AlbumShuffleEngine` logic, round mechanics, and math scoring remain untouched; only candidate asset eligibility is refined.
6. **Bilingual Support**:
   - Every new UI element and message must have complete translations in both **English (`EN`)** and **Brazilian Portuguese (`PT`)**.

---

## Codebase Map & Target Files

```
.env.example                                      # Add new filter config variables
src/
├── config.py                                     # Parse whitelist/blacklists and date bounds
├── models.py                                     # Add FilterResponse, update Preflight/Setup requests
├── immich/
│   └── client.py                                 # Add list_people, get_timeline_bounds, search query updates
├── game/
│   ├── selector.py                               # Filter candidate pool by people & country
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
├── test_immich_client.py                         # Immich client filtering tests
├── test_filters_api.py                           # /api/filters route tests
└── test_selector.py                              # Candidate selection diversity tests
```

---

## Implementation Phases

| Phase | Title | Summary |
| :--- | :--- | :--- |
| **Phase 1** | [Backend Config & Immich Client](file:///d:/Rafael/Projects/immich-quiz/docs/next-release-milestone/library-filters/01_PHASE_CONFIG_AND_IMMICH_CLIENT.md) | `.env` variables, `AppSettings`, Immich `GET /people`, `GET /timeline/buckets`, and `SearchQuery` extensions |
| **Phase 2** | [Backend Models & API Routes](file:///d:/Rafael/Projects/immich-quiz/docs/next-release-milestone/library-filters/02_PHASE_BACKEND_MODELS_AND_ROUTES.md) | `GET /api/filters` endpoint, server-side caching, updated `PreflightRequest` & `GameSetupRequest` |
| **Phase 3** | [Reusable MultiSelect Component](file:///d:/Rafael/Projects/immich-quiz/docs/next-release-milestone/library-filters/03_PHASE_REUSABLE_MULTISELECT.md) | Modular JavaScript class for Albums, Countries, Cities, and People with search, tag pills, and clear actions |
| **Phase 4** | [Frontend UI, Slider & Grouping](file:///d:/Rafael/Projects/immich-quiz/docs/next-release-milestone/library-filters/04_PHASE_FRONTEND_UI_AND_GROUPING.md) | Expandable accordion container, dual-handle range slider, HTML templates, CSS, and i18n dictionary |
| **Phase 5** | [Wiring, Preflight & Testing](file:///d:/Rafael/Projects/immich-quiz/docs/next-release-milestone/library-filters/05_PHASE_WIRING_PREFLIGHT_AND_TESTING.md) | `app.js` lifecycle hooks, debounced live preflight, automated pytest suite, and manual verification |

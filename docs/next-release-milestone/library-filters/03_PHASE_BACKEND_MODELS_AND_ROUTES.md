# Phase 3: Backend Models, Caching & API Routes

## Objective
Implement Pydantic request/response models in `src/models.py`, build the `GET /api/filters` endpoint with server-side in-memory caching in `src/api/routes.py`, and update `GameService` and `selector.py`.

---

## 1. Pydantic Models

### File: `src/models.py`

#### A. New Filter Models
```python
class PersonOption(BaseModel):
    id: str
    name: str

class CityOption(BaseModel):
    name: str
    country: str | None = None

class DateRangeOption(BaseModel):
    min_month: str | None = None  # Format: "YYYY-MM"
    max_month: str | None = None  # Format: "YYYY-MM"

class LibraryFiltersResponse(BaseModel):
    date_range: DateRangeOption
    countries: list[str]
    cities: list[CityOption]
    people: list[PersonOption]
```

#### B. Updated `PreflightRequest` & `GameSetupRequest`
```python
from typing import Literal

class PreflightRequest(BaseModel):
    players: list[str] = Field(default_factory=list)
    round_count: int = Field(default=10)
    location_mode: bool = True
    date_mode: bool = True
    game_mode: GameMode = GameMode.pinpoint
    library_name: str = Field(min_length=1)
    album_ids: list[str] = Field(default_factory=list)
    # New filter criteria
    person_ids: list[str] = Field(default_factory=list)
    people_mode: Literal['OR', 'AND'] = 'OR'  # 'OR' (any) | 'AND' (all together)
    countries: list[str] = Field(default_factory=list)
    cities: list[str] = Field(default_factory=list)
    min_date: date | None = None
    max_date: date | None = None

class GameSetupRequest(BaseModel):
    # Existing fields...
    players: list[str] = Field(min_length=1)
    round_count: int = Field(default=10)
    round_length: RoundLength = RoundLength.minute_1
    location_mode: bool = True
    date_mode: bool = True
    smart_map_zoom: bool = True
    game_mode: GameMode = GameMode.pinpoint
    library_name: str = Field(min_length=1)
    album_ids: list[str] = Field(default_factory=list)
    album_name: str | None = None
    # New filter criteria
    person_ids: list[str] = Field(default_factory=list)
    people_mode: Literal['OR', 'AND'] = 'OR'  # 'OR' (any) | 'AND' (all together)
    countries: list[str] = Field(default_factory=list)
    cities: list[str] = Field(default_factory=list)
    min_date: date | None = None
    max_date: date | None = None
```

---

## 2. API Route & Server-Side In-Memory Caching

### File: `src/api/routes.py`

#### Cache Setup
Add the following at the **module level** (top of `routes.py`, after imports):

```python
from cachetools import TTLCache

# 5-minute TTL for filter metadata cache. Change this constant to tune cache lifetime.
FILTERS_CACHE_TTL_SECONDS: int = 300

# Module-level cache shared across all requests: library_name -> LibraryFiltersResponse
_filters_cache: TTLCache = TTLCache(maxsize=64, ttl=FILTERS_CACHE_TTL_SECONDS)
```

> **Dependency**: Add `cachetools` to your project dependencies (`uv add cachetools`).

#### Endpoint: `GET /api/filters`
```python
@router.get('/filters', response_model=LibraryFiltersResponse)
async def library_filters(
    library_name: str,
    request: Request,
    immich: ImmichClient = Depends(get_immich_client),
) -> LibraryFiltersResponse:
    settings: AppSettings = request.app.state.settings

    # Check TTL cache first (evicts automatically after FILTERS_CACHE_TTL_SECONDS)
    cached = _filters_cache.get(library_name)
    if cached is not None:
        return cached

    try:
        # 1. Fetch people from Immich
        people_raw = await immich.list_people(
            library_name,
            whitelist=settings.people_whitelist,
            blacklist=settings.people_blacklist,
        )
        people = [PersonOption(id=p.id, name=p.name) for p in people_raw]

        # 2. Fetch timeline bounds
        bounds = await immich.get_timeline_bounds(library_name)
        min_d = settings.fetch_photos_date_lower_bound or bounds.min_date
        max_d = settings.fetch_photos_date_upper_bound or bounds.max_date

        date_range = DateRangeOption(
            min_month=min_d.strftime('%Y-%m') if min_d else None,
            max_month=max_d.strftime('%Y-%m') if max_d else None,
        )

        # 3. Fetch countries & cities (with country association)
        countries = await immich.list_countries(
            library_name,
            whitelist=settings.country_whitelist,
            blacklist=settings.country_blacklist,
        )
        cities_raw = await immich.list_cities(
            library_name,
            whitelist=settings.city_whitelist,
            blacklist=settings.city_blacklist,
        )
        cities = [CityOption(name=c.name, country=c.country) for c in cities_raw]

        response = LibraryFiltersResponse(
            date_range=date_range,
            countries=countries,
            cities=cities,
            people=people,
        )

        # Store in TTL cache — automatically expires after FILTERS_CACHE_TTL_SECONDS
        _filters_cache[library_name] = response
        return response

    except ImmichClientError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
```

---

## 3. Game Service & Candidate Selector Updates

### File: `src/game/service.py`
Update `preflight` to query with custom criteria and compute `effective_min_date` and `effective_max_date` while enforcing diversity:

```python
async def preflight(
    self,
    setup: PreflightRequest,
    settings: AppSettings,
    immich: ImmichClient,
) -> PreflightResponse:
    # Determine effective date bounds (intersection of env bounds and GUI setup bounds)
    effective_min_date = max(filter(None, [settings.fetch_photos_date_lower_bound, setup.min_date]), default=None)
    effective_max_date = min(filter(None, [settings.fetch_photos_date_upper_bound, setup.max_date]), default=None)

    query = SearchQuery(
        album_ids=tuple(setup.album_ids),
        person_ids=tuple(setup.person_ids),
        people_mode=setup.people_mode,
        countries=tuple(setup.countries),
        cities=tuple(setup.cities),
        include_shared_albums=settings.include_shared_albums,
        include_partner_assets=settings.include_partner_assets,
        min_date=effective_min_date,
        max_date=effective_max_date,
    )

    try:
        raw_assets = await immich.search_assets(
            setup.library_name,
            query=query,
            size=250,
        )
    except ImmichClientError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    active_filters: list[str] = []
    if setup.location_mode:
        active_filters.append('location')
    if setup.date_mode:
        active_filters.append('date')
    if setup.album_ids:
        active_filters.append('albums')
    if setup.person_ids:
        active_filters.append('people_all' if setup.people_mode == 'AND' and len(setup.person_ids) > 1 else 'people')
    if setup.countries:
        active_filters.append('countries')
    if setup.cities:
        active_filters.append('cities')
    if effective_min_date or effective_max_date:
        active_filters.append('date_range')

    eligible_answers = [
        ImmichClient.extract_answer(asset)
        for asset in raw_assets
        if ImmichClient.is_eligible_asset(
            asset,
            setup.location_mode,
            setup.date_mode,
            min_date=effective_min_date,
            max_date=effective_max_date,
            countries=tuple(setup.countries),
            cities=tuple(setup.cities),
            person_ids=tuple(setup.person_ids),
            people_mode=setup.people_mode,
        )
    ]

    diverse_candidates = filter_diverse_asset_answers(
        eligible_answers,
        setup.location_mode,
        setup.date_mode,
        min_dist_km=settings.photo_diversity_min_distance_km,
        min_time_sec=settings.photo_diversity_min_time_seconds,
    )

    eligible_count = len(diverse_candidates)
    required = 3 * setup.round_count if setup.game_mode == GameMode.album_shuffle else setup.round_count

    return PreflightResponse(
        eligible_count=eligible_count,
        required=required,
        ok=eligible_count >= required,
        active_filters=active_filters,
        min_date=effective_min_date,
        max_date=effective_max_date,
    )
```

### File: `src/game/selector.py`
Update `load_asset_pool` to load candidates matching all filter criteria:

```python
async def load_asset_pool(
    state: MatchState,
    immich: ImmichClient,
    min_capture_date: date | None,
    max_capture_date: date | None,
    include_shared_albums: bool = False,
    include_partner_assets: bool = False,
) -> None:
    """Populate the per-match candidate pool once with active filter criteria."""
    effective_min_date = max(filter(None, [min_capture_date, state.setup.min_date]), default=None)
    effective_max_date = min(filter(None, [max_capture_date, state.setup.max_date]), default=None)

    query = SearchQuery(
        album_ids=tuple(state.setup.album_ids),
        person_ids=tuple(state.setup.person_ids),
        people_mode=state.setup.people_mode,
        countries=tuple(state.setup.countries),
        cities=tuple(state.setup.cities),
        include_shared_albums=include_shared_albums,
        include_partner_assets=include_partner_assets,
        min_date=effective_min_date,
        max_date=effective_max_date,
    )

    raw_assets = await immich.search_random_assets(
        state.setup.library_name,
        query=query,
    )
    pool: dict[str, AssetAnswer] = {}
    for asset in raw_assets:
        if not ImmichClient.is_eligible_asset(
            asset,
            state.setup.location_mode,
            state.setup.date_mode,
            min_date=effective_min_date,
            max_date=effective_max_date,
            countries=tuple(state.setup.countries),
            cities=tuple(state.setup.cities),
            person_ids=tuple(state.setup.person_ids),
            people_mode=state.setup.people_mode,
        ):
            continue
        asset_id = str(asset.get('id', '')).strip()
        if asset_id:
            pool[asset_id] = ImmichClient.extract_answer(asset)
    state.asset_pool = pool
```

---

## 4. Acceptance Criteria
- [ ] `cachetools` is added as a project dependency and `_filters_cache` uses `TTLCache(maxsize=64, ttl=FILTERS_CACHE_TTL_SECONDS)` with `FILTERS_CACHE_TTL_SECONDS = 300` as a named constant at module level.
- [ ] `GET /api/filters?library_name=...` returns populated lists in < 50ms on first call and ≤ 1ms on cached calls, with cities carrying parent country metadata.
- [ ] Cache entries automatically expire after 5 minutes without any manual cleanup.
- [ ] `PreflightRequest` validates with custom `person_ids`, `people_mode` ('OR' | 'AND'), `countries`, `cities`, and date boundaries.
- [ ] Preflight strictly verifies that candidate photos meet diversity criteria ($\ge 100\text{m}$ / $\ge 60\text{s}$) without loose fallbacks.
- [ ] Candidate pool selection in `selector.py` respects all active filters and strict diversity constraints.
- [ ] Automated route tests added in `tests/test_filters_api.py`.

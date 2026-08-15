# Phase 6: Wiring, Live Preflight & Testing

## Objective
Wire the frontend components in `static/js/app.js`, connect the debounced preflight checks, execute match setups with active filters, and implement a full automated test suite in `tests/`.

---

## 1. Frontend Wiring & Lifecycle in `static/js/app.js`

### A. Component Instances & DOM References
```javascript
import { MultiSelect } from "./modules/components/multi_select.js";
import { DateRangeSlider } from "./modules/components/range_slider.js";

// Multi-select component instances
let albumMultiSelect;
let countryMultiSelect;
let cityMultiSelect;
let peopleMultiSelect;
let dateRangeSlider;
let cachedRawCities = []; // [{ name: "Paris", country: "France" }, ...]

const STORAGE_KEY_PREFIX = "immich_quiz_filters_";

function initFilterComponents() {
  albumMultiSelect = new MultiSelect({
    container: document.getElementById("album-multi-select"),
    nativeSelect: document.getElementById("album"),
    placeholderKey: "setup.all_photos",
    searchPlaceholderKey: "setup.album_search_placeholder",
    noResultsKey: "setup.no_albums_found",
    summaryFormatter: (count) => t("setup.albums_selected", count),
    onChange: () => {
      saveCurrentLibraryFilters();
      updateFiltersSummaryBadge();
      triggerPreflightDebounced();
    },
  });

  countryMultiSelect = new MultiSelect({
    container: document.getElementById("country-multi-select"),
    placeholderKey: "setup.all_countries",
    searchPlaceholderKey: "setup.country_search_placeholder",
    noResultsKey: "setup.no_countries_found",
    summaryFormatter: (count) => t("setup.countries_selected", count),
    onChange: () => {
      const selectedCountries = countryMultiSelect.getSelectedIds();
      updateDependentCities(selectedCountries);
      saveCurrentLibraryFilters();
      updateFiltersSummaryBadge();
      triggerPreflightDebounced();
    },
  });

  cityMultiSelect = new MultiSelect({
    container: document.getElementById("city-multi-select"),
    placeholderKey: "setup.all_cities",
    searchPlaceholderKey: "setup.city_search_placeholder",
    noResultsKey: "setup.no_cities_found",
    summaryFormatter: (count) => t("setup.cities_selected", count),
    onChange: () => {
      saveCurrentLibraryFilters();
      updateFiltersSummaryBadge();
      triggerPreflightDebounced();
    },
  });

  peopleMultiSelect = new MultiSelect({
    container: document.getElementById("people-multi-select"),
    placeholderKey: "setup.all_people",
    searchPlaceholderKey: "setup.people_search_placeholder",
    noResultsKey: "setup.no_people_found",
    summaryFormatter: (count) => t("setup.people_selected", count),
    onChange: () => {
      updatePeopleModeToggleVisibility();
      saveCurrentLibraryFilters();
      updateFiltersSummaryBadge();
      triggerPreflightDebounced();
    },
  });

  dateRangeSlider = new DateRangeSlider({
    minThumb: document.getElementById("date-slider-min"),
    maxThumb: document.getElementById("date-slider-max"),
    fillEl: document.getElementById("date-slider-fill"),
    readoutEl: document.getElementById("date-slider-readout"),
    boundMinEl: document.getElementById("date-slider-bound-min"),
    boundMaxEl: document.getElementById("date-slider-bound-max"),
    onChange: () => {
      saveCurrentLibraryFilters();
      updateFiltersSummaryBadge();
      triggerPreflightDebounced();
    },
  });

  // People Mode Segmented Toggle (OR / AND)
  const peopleModeToggleEl = document.getElementById("people-mode-toggle");
  if (peopleModeToggleEl) {
    peopleModeToggleEl.querySelectorAll(".people-mode-btn").forEach((btn) => {
      btn.addEventListener("click", () => {
        peopleModeToggleEl.querySelectorAll(".people-mode-btn").forEach((b) => b.classList.remove("active"));
        btn.classList.add("active");
        saveCurrentLibraryFilters();
        triggerPreflightDebounced();
      });
    });
  }

  // Accordion Toggle
  const toggleBtn = document.getElementById("filters-toggle-btn");
  const contentEl = document.getElementById("filters-accordion-content");
  if (toggleBtn && contentEl) {
    toggleBtn.addEventListener("click", () => {
      const isExpanded = toggleBtn.getAttribute("aria-expanded") === "true";
      toggleBtn.setAttribute("aria-expanded", String(!isExpanded));
      contentEl.classList.toggle("hidden", isExpanded);
    });
  }

  // Reset Filters Button
  const resetBtn = document.getElementById("reset-filters-btn");
  if (resetBtn) {
    resetBtn.addEventListener("click", () => {
      albumMultiSelect.clear();
      countryMultiSelect.clear();
      updateDependentCities([]);
      cityMultiSelect.clear();
      peopleMultiSelect.clear();
      dateRangeSlider.reset();
      resetPeopleMode();
      updatePeopleModeToggleVisibility();
      clearSavedLibraryFilters(el.library ? el.library.value : null);
      updateFiltersSummaryBadge();
      triggerPreflightDebounced();
    });
  }
}

function updateDependentCities(selectedCountryNames) {
  if (!selectedCountryNames || selectedCountryNames.length === 0) {
    cityMultiSelect.setItems(cachedRawCities.map((c) => ({ id: c.name, name: c.name })));
  } else {
    const filtered = cachedRawCities.filter((c) => !c.country || selectedCountryNames.includes(c.country));
    cityMultiSelect.setItems(filtered.map((c) => ({ id: c.name, name: c.name })));
  }
}

function saveCurrentLibraryFilters() {
  const libraryName = el.library ? el.library.value : null;
  if (!libraryName) return;
  const { minDate, maxDate } = dateRangeSlider ? dateRangeSlider.getSelectedRange() : { minDate: null, maxDate: null };
  const filterState = {
    album_ids: albumMultiSelect ? albumMultiSelect.getSelectedIds() : [],
    countries: countryMultiSelect ? countryMultiSelect.getSelectedIds() : [],
    cities: cityMultiSelect ? cityMultiSelect.getSelectedIds() : [],
    person_ids: peopleMultiSelect ? peopleMultiSelect.getSelectedIds() : [],
    people_mode: getSelectedPeopleMode(),
    min_month: minDate ? minDate.slice(0, 7) : null,
    max_month: maxDate ? maxDate.slice(0, 7) : null,
  };
  try {
    localStorage.setItem(STORAGE_KEY_PREFIX + libraryName, JSON.stringify(filterState));
  } catch (e) {
    console.warn("Failed to persist library filters to localStorage", e);
  }
}

function restoreLibraryFilters(libraryName) {
  if (!libraryName) return;
  try {
    const raw = localStorage.getItem(STORAGE_KEY_PREFIX + libraryName);
    if (!raw) return;
    const saved = JSON.parse(raw);
    if (saved.album_ids && albumMultiSelect) albumMultiSelect.setSelectedIds(saved.album_ids);
    if (saved.countries && countryMultiSelect) {
      countryMultiSelect.setSelectedIds(saved.countries);
      updateDependentCities(saved.countries);
    }
    if (saved.cities && cityMultiSelect) cityMultiSelect.setSelectedIds(saved.cities);
    if (saved.person_ids && peopleMultiSelect) peopleMultiSelect.setSelectedIds(saved.person_ids);
    if (saved.people_mode) setPeopleMode(saved.people_mode);
    if (dateRangeSlider && saved.min_month && saved.max_month) {
      dateRangeSlider.setSelectedRange(saved.min_month, saved.max_month);
    }
  } catch (e) {
    console.warn("Failed to restore library filters from localStorage", e);
  }
}

function clearSavedLibraryFilters(libraryName) {
  if (!libraryName) return;
  localStorage.removeItem(STORAGE_KEY_PREFIX + libraryName);
}

function getSelectedPeopleMode() {
  const activeBtn = document.querySelector("#people-mode-toggle .people-mode-btn.active");
  return activeBtn ? activeBtn.getAttribute("data-people-mode") || "OR" : "OR";
}

function setPeopleMode(mode) {
  const toggleEl = document.getElementById("people-mode-toggle");
  if (toggleEl) {
    toggleEl.querySelectorAll(".people-mode-btn").forEach((b) => {
      b.classList.toggle("active", b.getAttribute("data-people-mode") === mode);
    });
  }
}

function resetPeopleMode() {
  setPeopleMode("OR");
}

function updatePeopleModeToggleVisibility() {
  const toggleEl = document.getElementById("people-mode-toggle");
  if (!toggleEl) return;
  const selectedCount = peopleMultiSelect ? peopleMultiSelect.getSelectedIds().length : 0;
  toggleEl.classList.toggle("hidden", selectedCount < 2);
}
```

### B. Library Switch Hook
```javascript
async function onLibrarySelected(libraryName) {
  if (!libraryName) return;

  try {
    const [albumsRes, filtersRes] = await Promise.all([
      api(`/api/albums?library_name=${encodeURIComponent(libraryName)}`),
      api(`/api/filters?library_name=${encodeURIComponent(libraryName)}`),
    ]);

    cachedRawCities = filtersRes.cities || [];

    albumMultiSelect.setItems(albumsRes.albums || []);
    countryMultiSelect.setItems((filtersRes.countries || []).map((c) => ({ id: c, name: c })));
    cityMultiSelect.setItems(cachedRawCities.map((c) => ({ id: c.name, name: c.name })));
    peopleMultiSelect.setItems(filtersRes.people || []);

    if (filtersRes.date_range && filtersRes.date_range.min_month && filtersRes.date_range.max_month) {
      dateRangeSlider.setBounds(filtersRes.date_range.min_month, filtersRes.date_range.max_month);
    } else {
      dateRangeSlider.setBounds(null, null);
    }

    // Reset current UI then restore saved filters for this library
    albumMultiSelect.clear();
    countryMultiSelect.clear();
    cityMultiSelect.clear();
    peopleMultiSelect.clear();
    dateRangeSlider.reset();
    resetPeopleMode();

    restoreLibraryFilters(libraryName);

    updatePeopleModeToggleVisibility();
    updateFiltersSummaryBadge();
    triggerPreflightDebounced();
  } catch (err) {
    console.error("Failed to load library filters:", err);
  }
}
```

### C. Live Preflight & Submission
```javascript
async function executePreflight() {
  const { minDate, maxDate } = dateRangeSlider ? dateRangeSlider.getSelectedRange() : { minDate: null, maxDate: null };

  const payload = {
    players: getPlayersList(),
    round_count: parseInt(el.roundCount.value, 10),
    location_mode: isLocationModeActive(),
    date_mode: isDateModeActive(),
    game_mode: activeGameMode.name,
    library_name: el.library.value,
    album_ids: albumMultiSelect ? albumMultiSelect.getSelectedIds() : [],
    person_ids: peopleMultiSelect ? peopleMultiSelect.getSelectedIds() : [],
    people_mode: getSelectedPeopleMode(),
    countries: countryMultiSelect ? countryMultiSelect.getSelectedIds() : [],
    cities: cityMultiSelect ? cityMultiSelect.getSelectedIds() : [],
    min_date: minDate,
    max_date: maxDate,
  };

  const preflight = await api("/api/game/preflight", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!preflight.ok) {
    const filterNames = (preflight.active_filters || [])
      .map((f) => t(`setup.filter_${f}`, preflight.min_date, preflight.max_date))
      .join(", ");
    showPreflightWarning(
      t("setup.not_enough_media", preflight.eligible_count, preflight.required, filterNames)
    );
    return false;
  }
  hidePreflightWarning();
  return true;
}
```

---

## 2. Automated Test Suite

### A. Config Parsing Tests: `tests/test_config.py`
```python
def test_parse_comma_set():
    assert _parse_comma_set(None) == frozenset()
    assert _parse_comma_set("") == frozenset()
    assert _parse_comma_set("  ") == frozenset()
    assert _parse_comma_set("France, Germany, brazil ") == frozenset({"france", "germany", "brazil"})
```

### B. Immich Client Tests: `tests/test_immich_client.py`
```python
@pytest.mark.asyncio
async def test_list_people_filtering(client: ImmichClient):
    # Mock /people response with named, unnamed, and hidden people
    people = await client.list_people(
        "test_lib",
        whitelist=frozenset(["alice"]),
        blacklist=frozenset(["bob"]),
    )
    assert len(people) == 1
    assert people[0].name == "Alice"

def test_is_eligible_asset_with_people_or_and_modes():
    asset_single = {
        "id": "1",
        "type": "IMAGE",
        "exifInfo": {"latitude": 48.85, "longitude": 2.35, "country": "France", "city": "Paris"},
        "fileCreatedAt": "2020-05-15T12:00:00Z",
        "people": [{"id": "p1", "name": "Alice"}],
    }
    asset_group = {
        "id": "2",
        "type": "IMAGE",
        "exifInfo": {"latitude": 48.85, "longitude": 2.35, "country": "France", "city": "Paris"},
        "fileCreatedAt": "2020-05-15T12:00:00Z",
        "people": [{"id": "p1", "name": "Alice"}, {"id": "p2", "name": "Bob"}],
    }

    # OR mode: asset with only Alice matches (p1, p2)
    assert ImmichClient.is_eligible_asset(
        asset_single, location_mode=True, date_mode=True, person_ids=("p1", "p2"), people_mode="OR"
    )

    # AND mode: asset with only Alice FAILS (p1, p2)
    assert not ImmichClient.is_eligible_asset(
        asset_single, location_mode=True, date_mode=True, person_ids=("p1", "p2"), people_mode="AND"
    )

    # AND mode: asset with BOTH Alice and Bob SUCCEEDS (p1, p2)
    assert ImmichClient.is_eligible_asset(
        asset_group, location_mode=True, date_mode=True, person_ids=("p1", "p2"), people_mode="AND"
    )
```

### C. Filter API & Diversity Tests: `tests/test_filters_api.py`
```python
@pytest.mark.asyncio
async def test_filters_endpoint(async_client):
    res = await async_client.get("/api/filters?library_name=test_lib")
    assert res.status_code == 200
    data = res.json()
    assert "date_range" in data
    assert "countries" in data
    assert "cities" in data
    assert isinstance(data["cities"], list)
    if data["cities"]:
        assert "name" in data["cities"][0]
        assert "country" in data["cities"][0]
    assert "people" in data

@pytest.mark.asyncio
async def test_preflight_people_and_mode(async_client):
    res = await async_client.post(
        "/api/game/preflight",
        json={
            "library_name": "test_lib",
            "person_ids": ["p1", "p2"],
            "people_mode": "AND",
            "round_count": 5,
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert "people_all" in data.get("active_filters", [])

@pytest.mark.asyncio
async def test_preflight_strict_diversity_rejection(async_client):
    # If candidate photos are within 50m of each other, strict preflight fails
    res = await async_client.post(
        "/api/game/preflight",
        json={
            "library_name": "test_dense_photos_lib",
            "location_mode": True,
            "round_count": 5,
        },
    )
    assert res.status_code == 200
    data = res.json()
    # Fails if 5 diverse photos cannot be found
    if data["eligible_count"] < 5:
        assert data["ok"] is False
```

---

## 3. Manual Verification Checklist

1. **Date Slider**:
   - Slide min/max thumbs; verify readout updates (e.g. `May 2018 — Dec 2022`).
   - Verify preflight count adjusts according to the selected date window.
2. **Dependent Country & City Multi-Select**:
   - Select Country = "France": verify City dropdown immediately filters to only French cities.
   - Deselect Country: verify City dropdown restores all available cities.
   - Start match and confirm round photos are all from selected locations.
3. **People Multi-Select & Match Mode (OR / AND)**:
   - Select 1 person: verify match mode toggle is hidden.
   - Select $\ge 2$ people: verify match mode toggle appears (`Any` vs `All`).
   - Select `All`: verify preflight checks that candidates have all selected people together.
   - Start match in `All` mode and confirm all round photos contain both individuals.
4. **Strict Diversity Enforcement**:
   - Test with a cluster of photos taken in the exact same spot (< 100m) or within 30 seconds: verify preflight rejects them from exceeding the count and prevents starting the game.
5. **Per-Library `localStorage` Persistence**:
   - Select filters in Library A (e.g. Country="Japan", People=["Alice"]).
   - Switch Library dropdown to Library B: verify Library A's filters are cleared and Library B loads its own previous state.
   - Switch back to Library A: verify Country="Japan" and People=["Alice"] are immediately restored.
   - Click "Reset filters": verify all filters reset to defaults and the `localStorage` entry for that library is cleared.
6. **Accordion & Grouping**:
   - Verify expand/collapse animation is smooth and doesn't disrupt form layout.
   - Verify summary badge updates (`All media` -> `2 filters active`).
7. **Internationalization**:
   - Toggle language between English and Portuguese; verify all filter headers, labels, Any/All buttons, and badges translate immediately.

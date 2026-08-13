# Phase 5: Wiring, Live Preflight & Testing

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

function initFilterComponents() {
  albumMultiSelect = new MultiSelect({
    container: document.getElementById("album-multi-select"),
    nativeSelect: document.getElementById("album"),
    placeholderKey: "setup.all_photos",
    searchPlaceholderKey: "setup.album_search_placeholder",
    noResultsKey: "setup.no_albums_found",
    summaryFormatter: (count) => t("setup.albums_selected", count),
    onChange: () => {
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
      updateFiltersSummaryBadge();
      triggerPreflightDebounced();
    },
  });

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
      cityMultiSelect.clear();
      peopleMultiSelect.clear();
      dateRangeSlider.reset();
      updateFiltersSummaryBadge();
      triggerPreflightDebounced();
    });
  }
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

    albumMultiSelect.setItems(albumsRes.albums || []);
    countryMultiSelect.setItems((filtersRes.countries || []).map((c) => ({ id: c, name: c })));
    cityMultiSelect.setItems((filtersRes.cities || []).map((c) => ({ id: c, name: c })));
    peopleMultiSelect.setItems(filtersRes.people || []);

    if (filtersRes.date_range && filtersRes.date_range.min_month && filtersRes.date_range.max_month) {
      dateRangeSlider.setBounds(filtersRes.date_range.min_month, filtersRes.date_range.max_month);
    } else {
      dateRangeSlider.setBounds(null, null);
    }

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

def test_is_eligible_asset_with_filters():
    asset = {
        "id": "1",
        "type": "IMAGE",
        "exifInfo": {"latitude": 48.85, "longitude": 2.35, "country": "France", "city": "Paris"},
        "fileCreatedAt": "2020-05-15T12:00:00Z",
        "people": [{"id": "p1", "name": "Alice"}],
    }
    # Matches France and Alice
    assert ImmichClient.is_eligible_asset(
        asset, location_mode=True, date_mode=True, countries=("France",), person_ids=("p1",)
    )
    # Rejects non-matching country
    assert not ImmichClient.is_eligible_asset(
        asset, location_mode=True, date_mode=True, countries=("Japan",)
    )
```

### C. Filter API Tests: `tests/test_filters_api.py`
```python
@pytest.mark.asyncio
async def test_filters_endpoint(async_client):
    res = await async_client.get("/api/filters?library_name=test_lib")
    assert res.status_code == 200
    data = res.json()
    assert "date_range" in data
    assert "countries" in data
    assert "cities" in data
    assert "people" in data
```

---

## 3. Manual Verification Checklist

1. **Date Slider**:
   - Slide min/max thumbs; verify readout updates (e.g. `May 2018 — Dec 2022`).
   - Verify preflight count adjusts according to the selected date window.
2. **Country Multi-Select**:
   - Search for a country; check/uncheck items; verify pills and remove (✕) buttons work.
   - Start match and confirm round photos are all from selected countries.
3. **People Multi-Select**:
   - Select multiple people; verify preflight verifies face-tagged photos.
   - Start match and confirm round photos contain the selected individuals.
4. **Accordion & Grouping**:
   - Verify expand/collapse animation is smooth and doesn't disrupt form layout.
   - Verify summary badge updates (`All media` -> `2 filters active`).
   - Click "Reset filters" and confirm all dropdowns and slider reset to default.
5. **Internationalization**:
   - Toggle language between English and Portuguese; verify all filter headers, labels, and badges translate immediately.

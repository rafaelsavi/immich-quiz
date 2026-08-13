# Phase 1: Backend Config & Immich Client Integration

## Objective
Update `.env` configuration parsing in `src/config.py` and extend `src/immich/client.py` to fetch people, timeline date bounds, and places without downloading individual photos.

---

## 1. Environment Configuration

### File: `.env.example`
Add the following optional variables:

```env
# Comma-separated list of allowed countries (empty = allow all available)
COUNTRY_WHITELIST=
# Comma-separated list of excluded countries
COUNTRY_BLACKLIST=

# Comma-separated list of allowed cities/regions (empty = allow all available)
CITY_WHITELIST=
# Comma-separated list of excluded cities/regions
CITY_BLACKLIST=

# Comma-separated list of allowed person names (empty = allow all named people)
PEOPLE_WHITELIST=
# Comma-separated list of excluded person names
PEOPLE_BLACKLIST=
```

### File: `src/config.py`
Add parser for comma-separated string sets and update `AppSettings` and `load_settings()`:

```python
def _parse_comma_set(value: str | None) -> frozenset[str]:
    """Parse comma-separated string into a normalized lowercase set."""
    if not value or not value.strip():
        return frozenset()
    return frozenset(item.strip().lower() for item in value.split(',') if item.strip())

@dataclass(frozen=True)
class AppSettings:
    immich_server_url: str
    immich_libraries: dict[str, str]
    leaderboard_csv_path: Path
    app_title: str
    app_tagline: str
    include_shared_albums: bool
    include_partner_assets: bool
    fetch_photos_date_lower_bound: date | None
    fetch_photos_date_upper_bound: date | None
    app_host: str
    app_port: int
    score_max_points: int
    location_score_decay_km: float
    date_score_decay_days: float
    language: str
    # New filter boundaries & whitelists/blacklists
    country_whitelist: frozenset[str]
    country_blacklist: frozenset[str]
    city_whitelist: frozenset[str]
    city_blacklist: frozenset[str]
    people_whitelist: frozenset[str]
    people_blacklist: frozenset[str]
```

Inside `load_settings()`:
```python
    country_whitelist = _parse_comma_set(os.getenv('COUNTRY_WHITELIST'))
    country_blacklist = _parse_comma_set(os.getenv('COUNTRY_BLACKLIST'))
    city_whitelist = _parse_comma_set(os.getenv('CITY_WHITELIST'))
    city_blacklist = _parse_comma_set(os.getenv('CITY_BLACKLIST'))
    people_whitelist = _parse_comma_set(os.getenv('PEOPLE_WHITELIST'))
    people_blacklist = _parse_comma_set(os.getenv('PEOPLE_BLACKLIST'))
```

---

## 2. Immich Client Extensions

### File: `src/immich/client.py`

#### A. Data Models & Structures
```python
@dataclass(frozen=True)
class PersonInfo:
    id: str
    name: str

@dataclass(frozen=True)
class TimelineBounds:
    min_date: date | None
    max_date: date | None
```

#### B. Method: `list_people(self, library_name: str, whitelist: frozenset[str], blacklist: frozenset[str]) -> list[PersonInfo]`
- **Endpoint**: `GET /people`
- **Implementation**:
```python
async def list_people(
    self,
    library_name: str,
    whitelist: frozenset[str] = frozenset(),
    blacklist: frozenset[str] = frozenset(),
) -> list[PersonInfo]:
    key = self._library_key(library_name)
    raw = await self._request_json('GET', '/people', key)
    people_list = raw.get('people', raw) if isinstance(raw, dict) else (raw if isinstance(raw, list) else [])
    
    result: list[PersonInfo] = []
    for p in people_list:
        if not isinstance(p, dict):
            continue
        pid = str(p.get('id', '')).strip()
        name = str(p.get('name', '')).strip()
        is_hidden = bool(p.get('isHidden', False))
        
        if not pid or not name or is_hidden:
            continue
            
        name_lower = name.lower()
        if whitelist and name_lower not in whitelist:
            continue
        if blacklist and name_lower in blacklist:
            continue
            
        result.append(PersonInfo(id=pid, name=name))
        
    result.sort(key=lambda x: (x.name.lower(), x.id))
    return result
```

#### C. Method: `get_timeline_bounds(self, library_name: str) -> TimelineBounds`
- **Endpoint**: `GET /timeline/buckets?size=MONTH`
- **Implementation**:
```python
async def get_timeline_bounds(self, library_name: str) -> TimelineBounds:
    key = self._library_key(library_name)
    try:
        buckets = await self._request_json('GET', '/timeline/buckets?size=MONTH', key)
        if not isinstance(buckets, list) or not buckets:
            return TimelineBounds(min_date=None, max_date=None)
        
        valid_dates: list[date] = []
        for b in buckets:
            if isinstance(b, dict) and b.get('timeBucket'):
                raw_time = str(b['timeBucket']).split('T')[0]
                try:
                    valid_dates.append(date.fromisoformat(raw_time))
                except ValueError:
                    continue
                    
        if not valid_dates:
            return TimelineBounds(min_date=None, max_date=None)
            
        return TimelineBounds(min_date=min(valid_dates), max_date=max(valid_dates))
    except ImmichClientError:
        return TimelineBounds(min_date=None, max_date=None)
```

#### D. Method: `list_countries(self, library_name: str, whitelist: frozenset[str], blacklist: frozenset[str]) -> list[str]`
- **Endpoint**: `GET /search/explore` or places aggregation
- **Implementation**:
```python
async def list_countries(
    self,
    library_name: str,
    whitelist: frozenset[str] = frozenset(),
    blacklist: frozenset[str] = frozenset(),
) -> list[str]:
    key = self._library_key(library_name)
    countries: set[str] = set()
    try:
        explore = await self._request_json('GET', '/search/explore', key)
        if isinstance(explore, list):
            for item in explore:
                if isinstance(item, dict) and item.get('fieldName') == 'country':
                    for val in item.get('items', []):
                        if isinstance(val, dict) and val.get('value'):
                            countries.add(str(val['value']).strip())
    except ImmichClientError:
        pass

    # If whitelist provided, seed from whitelist
    if whitelist and not countries:
        countries = {c.title() for c in whitelist}

    filtered = [
        c for c in countries
        if (not whitelist or c.lower() in whitelist) and (not blacklist or c.lower() not in blacklist)
    ]
    filtered.sort(key=str.lower)
    return filtered
```

#### E. Method: `list_cities(self, library_name: str, whitelist: frozenset[str], blacklist: frozenset[str]) -> list[str]`
- **Endpoint**: `GET /search/explore` or `GET /search/cities`
- **Implementation**:
```python
async def list_cities(
    self,
    library_name: str,
    whitelist: frozenset[str] = frozenset(),
    blacklist: frozenset[str] = frozenset(),
) -> list[str]:
    key = self._library_key(library_name)
    cities: set[str] = set()
    try:
        explore = await self._request_json('GET', '/search/explore', key)
        if isinstance(explore, list):
            for item in explore:
                if isinstance(item, dict) and item.get('fieldName') in {'city', 'state'}:
                    for val in item.get('items', []):
                        if isinstance(val, dict) and val.get('value'):
                            cities.add(str(val['value']).strip())
    except ImmichClientError:
        pass

    if whitelist and not cities:
        cities = {c.title() for c in whitelist}

    filtered = [
        c for c in cities
        if (not whitelist or c.lower() in whitelist) and (not blacklist or c.lower() not in blacklist)
    ]
    filtered.sort(key=str.lower)
    return filtered
```

#### F. Extended `SearchQuery` & `is_eligible_asset`
Update `SearchQuery`:
```python
@dataclass(frozen=True)
class SearchQuery:
    album_ids: tuple[str, ...] = ()
    person_ids: tuple[str, ...] = ()
    countries: tuple[str, ...] = ()
    cities: tuple[str, ...] = ()
    include_shared_albums: bool = False
    include_partner_assets: bool = False
    min_date: date | None = None
    max_date: date | None = None

    @property
    def should_filter_by_owner(self) -> bool:
        if self.album_ids:
            return False
        return not (self.include_shared_albums and self.include_partner_assets)

    def build_payload(self, size: int, page: int | None = None) -> dict[str, Any]:
        payload: dict[str, Any] = {'size': size, 'withExif': True}
        if page is not None:
            payload['page'] = page
        if self.album_ids:
            payload['albumIds'] = list(self.album_ids)
        if self.person_ids:
            payload['personIds'] = list(self.person_ids)
        if self.countries and len(self.countries) == 1:
            payload['country'] = self.countries[0]
        if self.cities and len(self.cities) == 1:
            payload['city'] = self.cities[0]
        if self.min_date:
            payload['takenAfter'] = f'{self.min_date.isoformat()}T00:00:00.000Z'
        if self.max_date:
            payload['takenBefore'] = f'{self.max_date.isoformat()}T23:59:59.999Z'
        return payload
```

Update `is_eligible_asset`:
```python
@staticmethod
def is_eligible_asset(
    asset: dict[str, Any],
    location_mode: bool,
    date_mode: bool,
    min_date: date | None = None,
    max_date: date | None = None,
    countries: tuple[str, ...] = (),
    cities: tuple[str, ...] = (),
    person_ids: tuple[str, ...] = (),
) -> bool:
    # 1. Reject videos
    if asset.get('type') == 'VIDEO':
        return False

    # 2. Location mode check (valid non-zero lat/lng)
    exif = ImmichClient._exif(asset)
    if location_mode:
        lat = exif.get('latitude')
        lon = exif.get('longitude')
        if lat is None or lon is None:
            return False
        try:
            lat_val = float(lat)
            lon_val = float(lon)
            if lat_val == 0.0 and lon_val == 0.0:
                return False
        except (ValueError, TypeError):
            return False

    # 3. Date mode & min/max bounds check
    capture_dt = ImmichClient.extract_capture_datetime(asset)
    if date_mode and capture_dt is None:
        return False

    if min_date is not None or max_date is not None:
        if capture_dt is None:
            return False
        c_date = capture_dt.date()
        if min_date is not None and c_date < min_date:
            return False
        if max_date is not None and c_date > max_date:
            return False

    # 4. Country check (if countries filter specified)
    if countries:
        asset_country = (exif.get('country') or '').strip().lower()
        if not asset_country or asset_country not in {c.lower() for c in countries}:
            return False

    # 5. City check (if cities filter specified)
    if cities:
        asset_city = (exif.get('city') or '').strip().lower()
        asset_state = (exif.get('state') or '').strip().lower()
        allowed_cities = {c.lower() for c in cities}
        if not (asset_city in allowed_cities or asset_state in allowed_cities):
            return False

    # 6. Person check (if person_ids filter specified)
    if person_ids:
        asset_people = asset.get('people') or asset.get('faces') or []
        asset_person_ids = {
            str(p.get('id', '')).strip()
            for p in asset_people
            if isinstance(p, dict) and p.get('id')
        }
        if not asset_person_ids.intersection(set(person_ids)):
            return False

    return True
```

---

## 3. Acceptance Criteria
- [ ] `_parse_comma_set` properly handles empty values, spaces, and case-insensitivity.
- [ ] `ImmichClient.list_people` queries `GET /people` and filters correctly.
- [ ] `ImmichClient.get_timeline_bounds` extracts min/max dates without downloading photos.
- [ ] `ImmichClient.is_eligible_asset` verifies country and people criteria accurately.
- [ ] All new logic has corresponding unit tests in `tests/test_config.py` and `tests/test_immich_client.py`.

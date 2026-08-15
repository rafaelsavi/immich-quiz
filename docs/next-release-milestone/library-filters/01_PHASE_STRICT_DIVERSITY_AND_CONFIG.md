# Phase 1: Strict Diversity Safeguard & Configuration Isolation

## Objective
Isolate photo diversity parameters (`PHOTO_DIVERSITY_MIN_DISTANCE_KM` and `PHOTO_DIVERSITY_MIN_TIME_SECONDS`) into application settings, implement a shared deterministic diversity evaluator for candidate asset pools, enforce a hard diversity check in `service.py` (`preflight`), and eliminate loose non-diverse fallbacks in `selector.py`.

---

## 1. Configuration & Settings

### File: `.env.example`
Add the configurable diversity thresholds:

```env
# Minimum distance (in km) and time separation (in seconds) between match photos
PHOTO_DIVERSITY_MIN_DISTANCE_KM=0.1
PHOTO_DIVERSITY_MIN_TIME_SECONDS=60.0
```

### File: `src/config.py`
Add `photo_diversity_min_distance_km` and `photo_diversity_min_time_seconds` to `AppSettings` and load them in `load_settings()`:

```python
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
    # Diversity Safeguards (cleanly isolated for future tuning)
    photo_diversity_min_distance_km: float
    photo_diversity_min_time_seconds: float
```

Inside `load_settings()`:
```python
    try:
        photo_diversity_min_distance_km = float(os.getenv('PHOTO_DIVERSITY_MIN_DISTANCE_KM', '0.1'))
    except ValueError:
        photo_diversity_min_distance_km = 0.1

    try:
        photo_diversity_min_time_seconds = float(os.getenv('PHOTO_DIVERSITY_MIN_TIME_SECONDS', '60.0'))
    except ValueError:
        photo_diversity_min_time_seconds = 60.0
```

---

## 2. Shared Diversity Evaluator & Strict Selector

### File: `src/game/selector.py`

#### A. Refactor `is_asset_valid_for_batch`
Update `is_asset_valid_for_batch` to evaluate candidate diversity against an existing list of answers:

```python
def is_asset_valid_for_batch(
    candidate_ans: AssetAnswer,
    selected_answers: list[AssetAnswer] | list[RoundAsset],
    location_mode: bool,
    date_mode: bool,
    min_dist_km: float = 0.1,
    min_time_sec: float = 60.0,
) -> bool:
    """
    Determine if a candidate photo satisfies diversity separation against selected match photos.

    Enforces:
    - Non-zero valid coordinates when location_mode is active.
    - Distance separation >= min_dist_km from all selected photos when location_mode is active.
    - Time separation >= min_time_sec from all selected photos when date_mode is active.
    """
    if location_mode:
        if candidate_ans.latitude is None or candidate_ans.longitude is None:
            return False
        if abs(candidate_ans.latitude) < 1e-6 and abs(candidate_ans.longitude) < 1e-6:
            return False

    for sel in selected_answers:
        sel_ans = sel.answer if isinstance(sel, RoundAsset) else sel
        if location_mode and (
            candidate_ans.latitude is not None
            and candidate_ans.longitude is not None
            and sel_ans.latitude is not None
            and sel_ans.longitude is not None
        ):
            dist = haversine_km(
                candidate_ans.latitude,
                candidate_ans.longitude,
                sel_ans.latitude,
                sel_ans.longitude,
            )
            if dist < min_dist_km:
                return False

        if date_mode and candidate_ans.capture_datetime is not None and sel_ans.capture_datetime is not None:
            diff_sec = abs((candidate_ans.capture_datetime - sel_ans.capture_datetime).total_seconds())
            if diff_sec < min_time_sec:
                return False

    return True
```

#### B. Helper: `filter_diverse_asset_answers`
```python
def filter_diverse_asset_answers(
    eligible_answers: list[AssetAnswer],
    location_mode: bool,
    date_mode: bool,
    min_dist_km: float = 0.1,
    min_time_sec: float = 60.0,
) -> list[AssetAnswer]:
    """Greedily build a diverse subset of asset answers satisfying minimum distance and time constraints."""
    diverse: list[AssetAnswer] = []
    for ans in eligible_answers:
        if is_asset_valid_for_batch(
            ans,
            diverse,
            location_mode,
            date_mode,
            min_dist_km=min_dist_km,
            min_time_sec=min_time_sec,
        ):
            diverse.append(ans)
    return diverse
```

#### C. Strict Round Selection (Remove Loose Fallback)
In `select_round_asset` and `select_batch_round_assets`, pass `min_dist_km=settings.photo_diversity_min_distance_km` and `min_time_sec=settings.photo_diversity_min_time_seconds`. If no diverse candidate exists, return `None` rather than silently picking an unplayed non-diverse photo.

---

## 3. Preflight Hard-Check Integration

### File: `src/game/service.py`
Update `preflight()` to evaluate diversity on candidate answers:

```python
    eligible_answers = [
        ImmichClient.extract_answer(asset)
        for asset in raw_assets
        if ImmichClient.is_eligible_asset(
            asset,
            setup.location_mode,
            setup.date_mode,
            settings.fetch_photos_date_lower_bound,
            settings.fetch_photos_date_upper_bound,
        )
    ]

    diverse_answers = filter_diverse_asset_answers(
        eligible_answers,
        setup.location_mode,
        setup.date_mode,
        min_dist_km=settings.photo_diversity_min_distance_km,
        min_time_sec=settings.photo_diversity_min_time_seconds,
    )

    eligible_count = len(diverse_answers)
    required = 3 * setup.round_count if setup.game_mode == GameMode.album_shuffle else setup.round_count
    return PreflightResponse(
        eligible_count=eligible_count,
        required=required,
        ok=eligible_count >= required,
        active_filters=active_filters,
        min_date=settings.fetch_photos_date_lower_bound,
        max_date=settings.fetch_photos_date_upper_bound,
    )
```

---

## 4. Automated Test Suite

### File: `tests/test_diversity.py`
```python
from datetime import datetime, timezone
import pytest
from src.immich.client import AssetAnswer
from src.game.selector import is_asset_valid_for_batch, filter_diverse_asset_answers

def test_distance_diversity_rejection():
    # Asset 1 at Paris Eiffel Tower (48.8584, 2.2945)
    a1 = AssetAnswer(latitude=48.8584, longitude=2.2945, capture_datetime=datetime(2022, 5, 1, 12, 0, 0, tzinfo=timezone.utc))
    # Asset 2 only 20m away (48.8585, 2.2946)
    a2 = AssetAnswer(latitude=48.8585, longitude=2.2946, capture_datetime=datetime(2022, 5, 1, 14, 0, 0, tzinfo=timezone.utc))
    # Asset 3 in Lyon (> 300km away)
    a3 = AssetAnswer(latitude=45.7640, longitude=4.8357, capture_datetime=datetime(2022, 5, 1, 16, 0, 0, tzinfo=timezone.utc))

    assert not is_asset_valid_for_batch(a2, [a1], location_mode=True, date_mode=False, min_dist_km=0.1)
    assert is_asset_valid_for_batch(a3, [a1], location_mode=True, date_mode=False, min_dist_km=0.1)

def test_time_diversity_rejection():
    # Asset 1 at 12:00:00
    a1 = AssetAnswer(latitude=48.8584, longitude=2.2945, capture_datetime=datetime(2022, 5, 1, 12, 0, 0, tzinfo=timezone.utc))
    # Asset 2 at 12:00:30 (30 seconds later)
    a2 = AssetAnswer(latitude=45.7640, longitude=4.8357, capture_datetime=datetime(2022, 5, 1, 12, 0, 30, tzinfo=timezone.utc))
    # Asset 3 at 12:10:00 (10 minutes later)
    a3 = AssetAnswer(latitude=45.7640, longitude=4.8357, capture_datetime=datetime(2022, 5, 1, 12, 10, 0, tzinfo=timezone.utc))

    assert not is_asset_valid_for_batch(a2, [a1], location_mode=False, date_mode=True, min_time_sec=60.0)
    assert is_asset_valid_for_batch(a3, [a1], location_mode=False, date_mode=True, min_time_sec=60.0)
```

---

## 5. Acceptance Criteria
- [ ] Diversity settings are loaded from `.env` (`PHOTO_DIVERSITY_MIN_DISTANCE_KM`, `PHOTO_DIVERSITY_MIN_TIME_SECONDS`).
- [ ] `preflight()` evaluates `filter_diverse_asset_answers` and returns `ok = False` if candidate assets are clustered.
- [ ] In-game selection strictly rejects non-diverse candidate photos.
- [ ] All unit tests in `tests/test_diversity.py` pass.

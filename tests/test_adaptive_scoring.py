"""Unit and integration tests for pool-aware scoring decay calculations."""

from __future__ import annotations

from datetime import datetime, timezone

from src.immich.client import AssetAnswer
from src.scoring import (
    DATE_MAX_DECAY_DAYS,
    DATE_MIN_DECAY_DAYS,
    LOCATION_MAX_DECAY_KM,
    LOCATION_MIN_DECAY_KM,
    calculate_date_decay,
    calculate_location_decay,
    haversine_km,
    location_score,
)


def _make_answer(lat: float | None, lng: float | None, dt_iso: str | None) -> AssetAnswer:
    parsed_dt = datetime.fromisoformat(dt_iso).replace(tzinfo=timezone.utc) if dt_iso else None
    return AssetAnswer(
        latitude=lat,
        longitude=lng,
        capture_datetime=parsed_dt,
    )


# ---------------------------------------------------------------------------
# Location Decay Tests
# ---------------------------------------------------------------------------


def test_location_decay_empty_or_single_coord() -> None:
    assert calculate_location_decay([]) == LOCATION_MAX_DECAY_KM
    assert calculate_location_decay(None) == LOCATION_MAX_DECAY_KM

    single = [_make_answer(48.8566, 2.3522, '2024-01-01T12:00:00Z')]
    assert calculate_location_decay(single) == LOCATION_MAX_DECAY_KM


def test_location_decay_single_city_clamp() -> None:
    # Paris photos ~10 km apart:
    # Eiffel Tower: 48.8584, 2.2945
    # Notre Dame: 48.8530, 2.3499
    # Distance ~4.5 km -> 4.5 / 10.0 = 0.45 km -> Clamped to min 5.0 km
    pool = [
        _make_answer(48.8584, 2.2945, '2024-01-01T12:00:00Z'),
        _make_answer(48.8530, 2.3499, '2024-01-02T12:00:00Z'),
    ]
    decay = calculate_location_decay(pool)
    assert decay == LOCATION_MIN_DECAY_KM


def test_location_decay_regional_scaling() -> None:
    # Munich to Nuremberg ~150 km
    # Munich: 48.1351, 11.5820
    # Nuremberg: 49.4521, 11.0767
    pool = [
        _make_answer(48.1351, 11.5820, '2024-01-01T12:00:00Z'),
        _make_answer(49.4521, 11.0767, '2024-01-02T12:00:00Z'),
    ]
    decay = calculate_location_decay(pool)
    # Span ~151.7 km / 10.0 = ~15.17 km
    assert 14.0 <= decay <= 16.0


def test_location_decay_global_span_fallback() -> None:
    # Lisbon to Tokyo (span > 10,000 km, or lat/lng span > 60/90 deg)
    pool = [
        _make_answer(38.7223, -9.1393, '2024-01-01T12:00:00Z'),
        _make_answer(35.6762, 139.6503, '2024-01-02T12:00:00Z'),
    ]
    assert calculate_location_decay(pool) == LOCATION_MAX_DECAY_KM


def test_location_decay_antimeridian_crossing() -> None:
    # Fiji island photos spanning across +/- 180 Date Line (~30 km span):
    # Taveuni East: -16.79, 179.95
    # Taveuni West: -16.82, -179.95
    pool = [
        _make_answer(-16.79, 179.95, '2024-01-01T12:00:00Z'),
        _make_answer(-16.82, -179.95, '2024-01-02T12:00:00Z'),
    ]
    decay = calculate_location_decay(pool)
    # The true span is ~11 km across Date Line, so decay should clamp to min 5.0 km (not fall back to 200 km)
    assert decay == LOCATION_MIN_DECAY_KM


def test_haversine_across_antimeridian() -> None:
    # Points 0.2 degrees apart across +/- 180 at the equator (~22.2 km)
    dist = haversine_km(0.0, 179.9, 0.0, -179.9)
    assert round(dist, 1) == 22.2


# ---------------------------------------------------------------------------
# Date Decay Tests
# ---------------------------------------------------------------------------


def test_date_decay_empty_or_single_date() -> None:
    assert calculate_date_decay([]) == DATE_MAX_DECAY_DAYS
    assert calculate_date_decay(None) == DATE_MAX_DECAY_DAYS

    single = [_make_answer(48.8566, 2.3522, '2024-01-01T12:00:00Z')]
    assert calculate_date_decay(single) == DATE_MAX_DECAY_DAYS


def test_date_decay_short_vacation_clamp() -> None:
    # 7-day vacation: 7 days / 6 = 1.16 days -> Clamped to min 30.0 days
    pool = [
        _make_answer(48.8566, 2.3522, '2024-06-01T12:00:00Z'),
        _make_answer(48.8566, 2.3522, '2024-06-08T12:00:00Z'),
    ]
    assert calculate_date_decay(pool) == DATE_MIN_DECAY_DAYS


def test_date_decay_yearly_scaling() -> None:
    # 3 years (~1095 days): 1095 / 6 = ~182.5 days
    pool = [
        _make_answer(48.8566, 2.3522, '2021-01-01T12:00:00Z'),
        _make_answer(48.8566, 2.3522, '2024-01-01T12:00:00Z'),
    ]
    decay = calculate_date_decay(pool)
    assert 180.0 <= decay <= 185.0


def test_date_decay_multi_decade_ceiling() -> None:
    # 20 years (~7300 days): 7300 / 6 = 1216 days -> Clamped to max 500.0 days
    pool = [
        _make_answer(48.8566, 2.3522, '2000-01-01T12:00:00Z'),
        _make_answer(48.8566, 2.3522, '2020-01-01T12:00:00Z'),
    ]
    assert calculate_date_decay(pool) == DATE_MAX_DECAY_DAYS


# ---------------------------------------------------------------------------
# Outlier Filtering Tests
# ---------------------------------------------------------------------------


def test_location_decay_filters_gps_outlier() -> None:
    # 20 photos in Florence (~5 km spread) + 1 outlier photo in Frankfurt (~800 km away)
    florence_pool = [
        _make_answer(43.7695 + (i * 0.001), 11.2558 + (i * 0.001), '2024-06-01T12:00:00Z') for i in range(20)
    ]
    outlier = _make_answer(50.1109, 8.6821, '2024-06-01T12:00:00Z')
    pool_with_outlier = [*florence_pool, outlier]

    decay = calculate_location_decay(pool_with_outlier)
    # The 5th-95th percentile trims the Frankfurt outlier, keeping decay at the city minimum
    assert decay == LOCATION_MIN_DECAY_KM


def test_date_decay_filters_timestamp_outlier() -> None:
    # 20 photos in June 2024 (14-day vacation) + 1 corrupted scan from 1970
    vacation_pool = [_make_answer(43.7695, 11.2558, f'2024-06-{(i % 14) + 1:02d}T12:00:00Z') for i in range(20)]
    outlier = _make_answer(43.7695, 11.2558, '1970-01-01T12:00:00Z')
    pool_with_outlier = [*vacation_pool, outlier]

    decay = calculate_date_decay(pool_with_outlier)
    # The 5th-95th percentile trims the 1970 outlier, keeping decay at the vacation minimum
    assert decay == DATE_MIN_DECAY_DAYS


# ---------------------------------------------------------------------------
# Scoring Formula Impact Comparison Tests
# ---------------------------------------------------------------------------


def test_scoring_rewards_city_accuracy() -> None:
    city_decay = 5.0
    global_decay = 200.0

    # 5 km error in a city gives 37 points, while in global it gives 98 points
    city_score_5km = location_score(5.0, decay_km=city_decay)
    global_score_5km = location_score(5.0, decay_km=global_decay)

    assert city_score_5km == 37
    assert global_score_5km == 98

    # 500m (0.5 km) error in a city still gives 90 points
    city_score_500m = location_score(0.5, decay_km=city_decay)
    assert city_score_500m == 90

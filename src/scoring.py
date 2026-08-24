"""Scoring algorithms, geographical distance formulas, and temporal deviation calculations."""

from __future__ import annotations

import math
from calendar import monthrange
from collections.abc import Iterable, Mapping, Sequence
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import TYPE_CHECKING, TypeVar

if TYPE_CHECKING:
    from src.immich.client import AssetAnswer

T = TypeVar('T', float, int, date)


def _percentile_bounds(
    values: Sequence[T],
    low_pct: float = 0.05,
    high_pct: float = 0.95,
) -> tuple[T, T]:
    """Calculate (low, high) bounds with 5th-95th percentile trimming for outlier robustness.

    For small datasets (< 10 points), returns the exact (min, max).
    For datasets with 10+ points, trims the lowest 5% and highest 5% of values to prevent
    isolated layover photos, GPS glitches, or misdated scans from distorting the match scale.
    """
    if len(values) < 10:
        return min(values), max(values)
    sorted_vals = sorted(values)
    n = len(sorted_vals)
    low_idx = int(n * low_pct)
    high_idx = min(int(n * high_pct), n - 1)
    return sorted_vals[low_idx], sorted_vals[high_idx]


def _circular_percentile_lng_bounds(lngs: Sequence[float]) -> tuple[float, float, float]:
    """Calculate circular longitude bounds (min_lng, max_lng, span_degrees) across antimeridian.

    Finds the largest empty angular gap on the 360-degree circle, unwraps the longitudes
    relative to that gap, applies 5th-95th percentile trimming, and returns the bounded endpoints
    in standard [-180, 180] range alongside the angular span.
    """
    if len(lngs) < 2:
        val = lngs[0] if lngs else 0.0
        return val, val, 0.0

    # 1. Map to [0, 360) and sort
    norm = sorted((x + 360.0) % 360.0 for x in lngs)
    n = len(norm)

    # 2. Find the largest gap between consecutive points on the circle
    max_gap = 0.0
    split_idx = 0
    for i in range(n):
        curr_val = norm[i]
        next_val = norm[(i + 1) % n]
        gap = (next_val - curr_val) % 360.0
        if gap > max_gap:
            max_gap = gap
            split_idx = (i + 1) % n

    # 3. Cut circle at the start of the cluster (after the largest empty gap)
    cut = norm[split_idx]
    unwrapped = [(x - cut) % 360.0 for x in norm]

    # 4. Percentile trimming on unwrapped values
    min_u, max_u = _percentile_bounds(unwrapped)
    span_deg = max_u - min_u

    # 5. Convert endpoints back to standard [-180, 180]
    min_lng = (min_u + cut) % 360.0
    if min_lng > 180.0:
        min_lng -= 360.0

    max_lng = (max_u + cut) % 360.0
    if max_lng > 180.0:
        max_lng -= 360.0

    return min_lng, max_lng, span_deg


SCORE_MAX_POINTS: int = 100

# ---------------------------------------------------------------------------
# Spatial Scoring Constants
# ---------------------------------------------------------------------------

# Ratio connecting geographic bounding diagonal (span) to exponential distance decay.
# A ratio of 8.0 means decay = span / 8.0 (12.5% of the total map width/diagonal).
# At 12.5% map error, player earns 37 points (1/e).
# At 6.25% map error, player earns 61 points.
# At > 50% map error (halfway across the map), player score drops below 2 points (0 pts).
LOCATION_SPAN_RATIO: float = 8.0

# Minimum floor clamp for single-city or walking-tour albums (prevents overly punishing decay).
LOCATION_MIN_DECAY_KM: float = 2.5

# Maximum ceiling clamp for nationwide or worldwide matches.
LOCATION_MAX_DECAY_KM: float = 500.0

# Threshold distance before a match is treated as worldwide global coverage.
LOCATION_MAX_SPAN_KM: float = 5000.0

# ---------------------------------------------------------------------------
# Temporal Scoring Constants
# ---------------------------------------------------------------------------

# Ratio connecting total album timespan in days to exponential date decay.
# A ratio of 6.0 means decay = timespan / 6.0 (16.7% of the album's total date range).
# Players guess by whole year/month, so a slightly wider 1/6th ratio keeps month guesses
# competitive across multi-year and vacation archives.
# At 16.7% date error, player earns 37 points (1/e).
# At > 60% date error, player score drops below 4 points.
DATE_SPAN_RATIO: float = 6.0

# Minimum floor clamp for short weekend/vacation trips (30 days / 1 month).
DATE_MIN_DECAY_DAYS: float = 30.0

# Maximum ceiling clamp for multi-decade family archives (500 days / ~16 months).
DATE_MAX_DECAY_DAYS: float = 500.0


def calculate_location_decay(
    pool: Sequence[AssetAnswer] | Mapping[str, AssetAnswer] | Iterable[AssetAnswer] | None,
    *,
    span_ratio: float = LOCATION_SPAN_RATIO,
    min_decay_km: float = LOCATION_MIN_DECAY_KM,
    max_decay_km: float = LOCATION_MAX_DECAY_KM,
    max_span_km: float = LOCATION_MAX_SPAN_KM,
) -> float:
    """Calculate dynamic geographic decay (km) adapted to the match pool's bounding box span.

    Uses 5th-95th percentile trimming on latitude and circular longitude to filter out airport
    layovers or single-photo GPS glitches while seamlessly handling +/-180 antimeridian crossings.

    Formula:
        decay_km = clamp(span_diagonal_km / span_ratio, min_decay_km, max_decay_km)

    The `span_ratio` controls the scale sensitivity:
        - Ratio 8.0 sets decay to 12.5% of the pool's diagonal.
        - Guessing within 3% of the map span yields ~79 points.
        - Guessing within 12.5% of the map span (1 decay unit) yields 37 points.
        - Guessing > 50% of the map span away yields < 2 points (0 pts).

    Args:
        pool: Collection or mapping of `AssetAnswer` candidate photos.
        span_ratio: Divisor ratio of pool span distance to decay distance. Defaults to 8.0.
        min_decay_km: Minimum allowable decay clamp in kilometers. Defaults to 2.5 km.
        max_decay_km: Maximum allowable decay clamp in kilometers. Defaults to 500.0 km.
        max_span_km: Maximum geographic span before pool is considered global. Defaults to 5000.0 km.

    Returns:
        Location decay in kilometers clamped to [min_decay_km, max_decay_km].

    """
    if not pool:
        return max_decay_km

    answers = pool.values() if isinstance(pool, Mapping) else pool
    coords = [
        (ans.latitude, ans.longitude)
        for ans in answers
        if ans.latitude is not None
        and ans.longitude is not None
        and not (abs(ans.latitude) < 1e-6 and abs(ans.longitude) < 1e-6)
    ]

    if len(coords) < 2:
        return max_decay_km

    lats = [c[0] for c in coords]
    lngs = [c[1] for c in coords]
    min_lat, max_lat = _percentile_bounds(lats)
    min_lng, max_lng, lng_span = _circular_percentile_lng_bounds(lngs)

    lat_span = max_lat - min_lat

    if lat_span > 60.0 or lng_span > 90.0:
        return max_decay_km

    diagonal_km = haversine_km(min_lat, min_lng, max_lat, max_lng)
    if diagonal_km > max_span_km:
        return max_decay_km

    scaled_decay = diagonal_km / span_ratio
    return max(min_decay_km, min(max_decay_km, round(scaled_decay, 2)))


def calculate_date_decay(
    pool: Sequence[AssetAnswer] | Mapping[str, AssetAnswer] | Iterable[AssetAnswer] | None,
    *,
    span_ratio: float = DATE_SPAN_RATIO,
    min_decay_days: float = DATE_MIN_DECAY_DAYS,
    max_decay_days: float = DATE_MAX_DECAY_DAYS,
) -> float:
    """Calculate dynamic temporal decay (days) adapted to the match pool's date span.

    Uses 5th-95th percentile trimming on capture dates to ignore isolated misdated scans
    or camera timestamp glitches.

    Formula:
        decay_days = clamp(date_span_days / span_ratio, min_decay_days, max_decay_days)

    The `span_ratio` controls temporal scale sensitivity:
        - Ratio 6.0 sets decay to 16.7% of the pool's timespan.
        - Exact month guess yields 100 points (0 days error).
        - Error of 16.7% timespan (1 decay unit) yields 37 points.
        - Error > 60% of total timespan drops score below 4 points.

    Args:
        pool: Collection or mapping of `AssetAnswer` candidate photos.
        span_ratio: Divisor ratio of pool date range to decay days. Defaults to 6.0.
        min_decay_days: Minimum allowable decay clamp in days. Defaults to 30.0 days.
        max_decay_days: Maximum allowable decay clamp in days. Defaults to 500.0 days.

    Returns:
        Date decay in days clamped to [min_decay_days, max_decay_days].

    """
    if not pool:
        return max_decay_days

    answers = pool.values() if isinstance(pool, Mapping) else pool
    dates = [ans.capture_date for ans in answers if ans.capture_date is not None]

    if len(dates) < 2:
        return max_decay_days

    min_date, max_date = _percentile_bounds(dates)
    delta_days = (max_date - min_date).days

    if delta_days <= 0:
        return min_decay_days

    scaled_decay = delta_days / span_ratio
    return max(min_decay_days, min(max_decay_days, round(scaled_decay, 2)))


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate the great-circle distance between two GPS coordinates in kilometers."""
    earth_radius_km = 6371.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)

    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    a = min(1.0, max(0.0, a))
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return earth_radius_km * c


def location_score(
    distance_km: float,
    *,
    decay_km: float = LOCATION_MAX_DECAY_KM,
    max_points: int = SCORE_MAX_POINTS,
) -> int:
    """Calculate location score using exponential distance decay."""
    return max(0, round(max_points * math.exp(-distance_km / decay_km)))


def month_index(year: int, month: int) -> int:
    """Absolute month number, used for the human-readable year/month error."""
    return year * 12 + (month - 1)


def date_diff_months(guessed_year: int, guessed_month: int, actual: date) -> int:
    """Calculate absolute difference in months between a guessed year/month and actual date."""
    return abs(month_index(guessed_year, guessed_month) - month_index(actual.year, actual.month))


def date_diff_days(guessed_year: int, guessed_month: int, actual: date) -> int:
    """Day error measured against the guessed month interval.

    The player only picks a year/month, so the guess covers the whole month.
    The error is the distance from the actual date to that interval: days from
    the first of the month when the actual date is earlier, days from the last
    of the month when it is later, and 0 when the actual date falls inside it.
    """
    first_day = date(guessed_year, guessed_month, 1)
    last_day = date(guessed_year, guessed_month, monthrange(guessed_year, guessed_month)[1])

    if actual < first_day:
        return (first_day - actual).days
    if actual > last_day:
        return (actual - last_day).days
    return 0


def date_diff_parts(guessed_year: int, guessed_month: int, actual: date) -> tuple[int, int, int]:
    """Break down the date difference into (years_part, months_part, days_part)."""
    first_day = date(guessed_year, guessed_month, 1)
    last_day = date(guessed_year, guessed_month, monthrange(guessed_year, guessed_month)[1])

    if first_day <= actual <= last_day:
        return 0, 0, 0

    if actual > last_day:
        ref = last_day
        years_part = 0
        while True:
            try:
                next_ref = date(ref.year + 1, ref.month, ref.day)
            except ValueError:
                next_ref = date(ref.year + 1, ref.month, ref.day - 1)
            if next_ref <= actual:
                years_part += 1
                ref = next_ref
            else:
                break

        months_part = 0
        while True:
            y = ref.year + (1 if ref.month == 12 else 0)
            m = 1 if ref.month == 12 else ref.month + 1
            max_d = monthrange(y, m)[1]
            d = min(ref.day, max_d)
            next_ref = date(y, m, d)
            if next_ref <= actual:
                months_part += 1
                ref = next_ref
            else:
                break

        days_part = (actual - ref).days
        return years_part, months_part, days_part

    ref = actual
    target = first_day

    years_part = 0
    while True:
        try:
            next_ref = date(ref.year + 1, ref.month, ref.day)
        except ValueError:
            next_ref = date(ref.year + 1, ref.month, ref.day - 1)
        if next_ref <= target:
            years_part += 1
            ref = next_ref
        else:
            break

    months_part = 0
    while True:
        y = ref.year + (1 if ref.month == 12 else 0)
        m = 1 if ref.month == 12 else ref.month + 1
        max_d = monthrange(y, m)[1]
        d = min(ref.day, max_d)
        next_ref = date(y, m, d)
        if next_ref <= target:
            months_part += 1
            ref = next_ref
        else:
            break

    days_part = (target - ref).days
    return years_part, months_part, days_part


def date_score(
    delta_days: int,
    *,
    decay_days: float = DATE_MAX_DECAY_DAYS,
    max_points: int = SCORE_MAX_POINTS,
) -> int:
    """Calculate date score using exponential day-difference decay."""
    return max(0, round(max_points * math.exp(-delta_days / decay_days)))


def max_possible_score(
    rounds_played: int,
    location_mode: bool,
    date_mode: bool,
    *,
    per_goal_max_points: int = SCORE_MAX_POINTS,
) -> int:
    """Compute maximum possible score achievable in a match given active modes and round count."""
    per_round = (per_goal_max_points if location_mode else 0) + (per_goal_max_points if date_mode else 0)
    return rounds_played * per_round


def accuracy_pct(total_score: int, max_score: int) -> float:
    """Calculate player accuracy percentage rounded to one decimal place."""
    if max_score <= 0:
        return 0.0
    value = Decimal(total_score) / Decimal(max_score) * Decimal(100)
    return float(value.quantize(Decimal('0.1'), rounding=ROUND_HALF_UP))


def batch_strict_location_score(correct_matches: int, total_photos: int, max_points: int = SCORE_MAX_POINTS) -> int:
    """Strict location score: each correctly paired photo earns max_points / total_photos."""
    if total_photos <= 0:
        return 0
    return max(0, round((correct_matches / total_photos) * max_points))


def batch_strict_date_score(correct_matches: int, total_photos: int, max_points: int = SCORE_MAX_POINTS) -> int:
    """Strict date score: each correctly sequence-placed photo earns max_points / total_photos."""
    if total_photos <= 0:
        return 0
    return max(0, round((correct_matches / total_photos) * max_points))

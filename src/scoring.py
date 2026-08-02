from __future__ import annotations

import math
from calendar import monthrange
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    earth_radius_km = 6371.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)

    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return earth_radius_km * c


def location_score(
    distance_km: float,
    *,
    decay_km: float = 500.0,
    max_points: int = 100,
) -> int:
    return max(0, round(max_points * math.exp(-distance_km / decay_km)))


def month_index(year: int, month: int) -> int:
    """Absolute month number, used for the human-readable year/month error."""
    return year * 12 + (month - 1)


def date_diff_months(guessed_year: int, guessed_month: int, actual: date) -> int:
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
        delta_months = (actual.year * 12 + actual.month) - (guessed_year * 12 + guessed_month)
        years_part, months_part = divmod(delta_months, 12)
        prev_month_end = date(actual.year, actual.month, 1) - timedelta(days=1)
        days_part = (actual - prev_month_end).days
        return years_part, months_part, days_part

    delta_months = (guessed_year * 12 + guessed_month) - (actual.year * 12 + actual.month)
    years_part, months_part = divmod(delta_months, 12)
    if actual.month == 12:
        next_month_start = date(actual.year + 1, 1, 1)
    else:
        next_month_start = date(actual.year, actual.month + 1, 1)
    days_part = (next_month_start - actual).days
    return years_part, months_part, days_part


def date_score(delta_days: int, *, decay_days: float = 500.0, max_points: int = 100) -> int:
    return max(0, round(max_points * math.exp(-delta_days / decay_days)))


def max_possible_score(
    rounds_played: int,
    location_mode: bool,
    date_mode: bool,
    *,
    per_goal_max_points: int = 100,
) -> int:
    per_round = (per_goal_max_points if location_mode else 0) + (per_goal_max_points if date_mode else 0)
    return rounds_played * per_round


def accuracy_pct(total_score: int, max_score: int) -> float:
    if max_score <= 0:
        return 0.0
    value = Decimal(total_score) / Decimal(max_score) * Decimal(100)
    return float(value.quantize(Decimal('0.1'), rounding=ROUND_HALF_UP))


def kendall_tau_inversion_score(guessed_order: list[int], max_points: int = 100) -> int:
    """Calculates chronological ordering score based on Kendall-Tau inversion count distance.

    guessed_order is a list of true rank indices (0..N-1) representing the player's guessed sequence.
    Example: [0, 1, 2, 3] is perfect (0 inversions -> max_points).
    [3, 2, 1, 0] is completely reversed (max inversions -> 0 points).
    """
    n = len(guessed_order)
    if n <= 1:
        return max_points

    max_inversions = n * (n - 1) // 2
    inversions = 0
    for i in range(n):
        for j in range(i + 1, n):
            if guessed_order[i] > guessed_order[j]:
                inversions += 1

    pct_correct = 1.0 - (inversions / max_inversions)
    return max(0, round(max_points * pct_correct))


def batch_strict_location_score(correct_matches: int, total_photos: int, max_points: int = 100) -> int:
    """Strict location score: each correctly paired photo earns max_points / total_photos."""
    if total_photos <= 0:
        return 0
    return max(0, round((correct_matches / total_photos) * max_points))


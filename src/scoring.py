from __future__ import annotations

import math
from calendar import monthrange
from datetime import date
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


def batch_strict_location_score(correct_matches: int, total_photos: int, max_points: int = 100) -> int:
    """Strict location score: each correctly paired photo earns max_points / total_photos."""
    if total_photos <= 0:
        return 0
    return max(0, round((correct_matches / total_photos) * max_points))


def batch_strict_date_score(correct_matches: int, total_photos: int, max_points: int = 100) -> int:
    """Strict date score: each correctly sequence-placed photo earns max_points / total_photos."""
    if total_photos <= 0:
        return 0
    return max(0, round((correct_matches / total_photos) * max_points))

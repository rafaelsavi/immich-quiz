from datetime import date

import pytest

from src.scoring import (
    accuracy_pct,
    batch_strict_date_score,
    batch_strict_location_score,
    date_diff_days,
    date_diff_months,
    date_diff_parts,
    date_score,
    haversine_km,
    kendall_tau_inversion_score,
    location_score,
    max_possible_score,
)


def test_haversine_zero_distance() -> None:
    assert haversine_km(0.0, 0.0, 0.0, 0.0) == 0.0


def test_haversine_one_degree_of_longitude_at_equator() -> None:
    assert haversine_km(0.0, 0.0, 0.0, 1.0) == pytest.approx(111.19, abs=0.01)


def test_location_score_formula() -> None:
    assert location_score(0.0, decay_km=500.0, max_points=100) == 100
    assert location_score(0.05, decay_km=500.0, max_points=100) == 100
    assert location_score(1.0, decay_km=500.0, max_points=100) == 100
    assert location_score(700, decay_km=500.0, max_points=100) == 25
    assert location_score(20000, decay_km=500.0, max_points=100) == 0


def test_location_score_supports_custom_parameters() -> None:
    assert location_score(0.0, decay_km=500, max_points=80) == 80
    assert location_score(500, decay_km=500, max_points=80) == 29


def test_date_score_formula() -> None:
    assert date_score(0, decay_days=500.0, max_points=100) == 100
    assert date_score(500, decay_days=500.0, max_points=100) == 37
    assert date_score(4500, decay_days=500.0, max_points=100) == 0


def test_date_score_supports_custom_parameters() -> None:
    assert date_score(0, decay_days=300, max_points=75) == 75
    assert date_score(300, decay_days=300, max_points=75) == 28


def test_date_difference_is_zero_anywhere_inside_the_guessed_month() -> None:
    assert date_diff_days(2024, 3, date(2024, 3, 1)) == 0
    assert date_diff_days(2024, 3, date(2024, 3, 17)) == 0
    assert date_diff_days(2024, 3, date(2024, 3, 31)) == 0


def test_date_difference_measures_from_the_facing_month_boundary() -> None:
    # Actual date is earlier, so the error runs from the 1st of the guessed month.
    assert date_diff_days(2024, 3, date(2024, 2, 20)) == 10
    # Actual date is later, so the error runs from the last day of the guessed month.
    assert date_diff_days(2024, 3, date(2024, 4, 10)) == 10


def test_date_difference_handles_leap_year_month_length() -> None:
    assert date_diff_days(2024, 2, date(2024, 3, 1)) == 1
    assert date_diff_days(2023, 2, date(2023, 3, 1)) == 1


def test_date_difference_months_is_display_only() -> None:
    assert date_diff_months(2024, 1, date(2024, 10, 20)) == 9
    assert date_diff_months(2023, 12, date(2024, 1, 15)) == 1


def test_date_diff_parts_breakdown() -> None:
    # Inside guessed month
    assert date_diff_parts(2024, 3, date(2024, 3, 15)) == (0, 0, 0)
    # Next month (5 days after March 31)
    assert date_diff_parts(2024, 3, date(2024, 4, 5)) == (0, 0, 5)
    # 2 months later (1 month and 15 days after Nov 30)
    assert date_diff_parts(2023, 11, date(2024, 1, 14)) == (0, 1, 15)
    # Earlier date (10 days before March 1 in leap year 2024)
    assert date_diff_parts(2024, 3, date(2024, 2, 20)) == (0, 0, 10)
    # 1 year or more (1 year, 1 month, 10 days)
    assert date_diff_parts(2024, 3, date(2025, 5, 10)) == (1, 1, 10)


def test_max_possible_score_respects_enabled_modes() -> None:
    assert max_possible_score(10, True, True, per_goal_max_points=100) == 2000
    assert max_possible_score(10, True, False, per_goal_max_points=100) == 1000
    assert max_possible_score(10, False, False, per_goal_max_points=100) == 0


def test_max_possible_score_supports_custom_per_goal_points() -> None:
    assert max_possible_score(10, True, True, per_goal_max_points=75) == 1500


def test_accuracy_rounding() -> None:
    assert accuracy_pct(199, 400) == 49.8
    assert accuracy_pct(0, 0) == 0.0


def test_accuracy_uses_half_up_rounding() -> None:
    # 6.25 rounds to 6.3 with ROUND_HALF_UP; banker's rounding would give 6.2.
    assert accuracy_pct(1, 16) == 6.3


def test_kendall_tau_inversion_score() -> None:
    assert kendall_tau_inversion_score([0, 1, 2, 3, 4], max_points=100) == 100
    assert kendall_tau_inversion_score([4, 3, 2, 1, 0], max_points=100) == 0
    assert kendall_tau_inversion_score([0, 1, 3, 2, 4], max_points=100) == 90

    # Incomplete or empty guesses when total_items is specified return 0
    assert kendall_tau_inversion_score([], max_points=100, total_items=5) == 0
    assert kendall_tau_inversion_score([0], max_points=100, total_items=5) == 0
    assert kendall_tau_inversion_score([0, 1, 2], max_points=100, total_items=5) == 0


def test_batch_strict_location_score() -> None:
    assert batch_strict_location_score(5, 5, max_points=100) == 100
    assert batch_strict_location_score(0, 5, max_points=100) == 0
    assert batch_strict_location_score(3, 5, max_points=100) == 60


def test_batch_strict_date_score() -> None:
    assert batch_strict_date_score(3, 3, max_points=100) == 100
    assert batch_strict_date_score(0, 3, max_points=100) == 0
    assert batch_strict_date_score(1, 3, max_points=100) == 33

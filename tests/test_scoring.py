from datetime import date

import pytest

from src.scoring import (
    SCORE_MAX_POINTS,
    accuracy_pct,
    batch_exponential_date_score,
    batch_exponential_location_score,
    date_diff_days,
    date_diff_months,
    date_diff_parts,
    date_score,
    haversine_km,
    location_score,
    max_possible_score,
)


def test_score_max_points_constant() -> None:
    assert SCORE_MAX_POINTS == 100


def test_haversine_zero_distance() -> None:
    assert haversine_km(0.0, 0.0, 0.0, 0.0) == 0.0


def test_haversine_one_degree_of_longitude_at_equator() -> None:
    assert haversine_km(0.0, 0.0, 0.0, 1.0) == pytest.approx(111.19, abs=0.01)


def test_location_score_formula() -> None:
    assert location_score(0.0, decay_km=500.0) == 100
    assert location_score(0.0, decay_km=500.0, max_points=100) == 100
    assert location_score(0.05, decay_km=500.0, max_points=100) == 100
    assert location_score(1.0, decay_km=500.0, max_points=100) == 100
    assert location_score(700, decay_km=500.0, max_points=100) == 25
    assert location_score(20000, decay_km=500.0, max_points=100) == 0


def test_location_score_supports_custom_parameters() -> None:
    assert location_score(0.0, decay_km=500, max_points=80) == 80
    assert location_score(500, decay_km=500, max_points=80) == 29


def test_date_score_formula() -> None:
    assert date_score(0, decay_days=500.0) == 100
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
    assert max_possible_score(10, True, True) == 2000
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


def test_batch_exponential_location_score_empty() -> None:
    assert batch_exponential_location_score({}, {}, {}, {}) == (0, 0, 0)


def test_batch_exponential_location_score_all_correct() -> None:
    true_pins = {'p1': 'pin1', 'p2': 'pin2', 'p3': 'pin3'}
    assigned = {'p1': 'pin1', 'p2': 'pin2', 'p3': 'pin3'}
    pin_coords = {
        'pin1': (48.8566, 2.3522),  # Paris
        'pin2': (41.9028, 12.4964),  # Rome
        'pin3': (35.6762, 139.6503),  # Tokyo
    }
    photo_coords = {
        'p1': (48.8566, 2.3522),
        'p2': (41.9028, 12.4964),
        'p3': (35.6762, 139.6503),
    }
    score, exact, total = batch_exponential_location_score(
        assigned, true_pins, pin_coords, photo_coords, decay_km=200.0
    )
    assert score == 100
    assert exact == 3
    assert total == 3


def test_batch_exponential_location_score_partial_near_miss() -> None:
    # Paris vs Versailles (~17 km) in a worldwide 200 km decay pool
    true_pins = {'p1': 'pin_paris', 'p2': 'pin_versailles', 'p3': 'pin_tokyo'}
    # Player swaps Paris and Versailles, gets Tokyo right
    assigned = {'p1': 'pin_versailles', 'p2': 'pin_paris', 'p3': 'pin_tokyo'}
    pin_coords = {
        'pin_paris': (48.8566, 2.3522),
        'pin_versailles': (48.8049, 2.1204),
        'pin_tokyo': (35.6762, 139.6503),
    }
    photo_coords = {
        'p1': (48.8566, 2.3522),
        'p2': (48.8049, 2.1204),
        'p3': (35.6762, 139.6503),
    }
    score, exact, total = batch_exponential_location_score(
        assigned, true_pins, pin_coords, photo_coords, decay_km=200.0
    )
    # Tokyo = 33.33 pts, Paris & Versailles each ~33.33 * exp(-17.3/200) ~= 30.56 pts -> total ~= 94 pts
    assert 93 <= score <= 96
    assert exact == 1
    assert total == 3


def test_batch_exponential_location_score_unassigned() -> None:
    true_pins = {'p1': 'pin1', 'p2': 'pin2'}
    assigned = {'p1': 'pin1', 'p2': None}
    pin_coords = {'pin1': (48.8566, 2.3522), 'pin2': (41.9028, 12.4964)}
    photo_coords = {'p1': (48.8566, 2.3522), 'p2': (41.9028, 12.4964)}
    score, exact, total = batch_exponential_location_score(
        assigned, true_pins, pin_coords, photo_coords, decay_km=200.0
    )
    assert score == 50
    assert exact == 1
    assert total == 2


def test_batch_exponential_date_score_empty() -> None:
    assert batch_exponential_date_score({}, {}) == (0, 0, 0)


def test_batch_exponential_date_score_all_correct() -> None:
    dates = {
        'p1': date(2020, 1, 1),
        'p2': date(2022, 6, 1),
        'p3': date(2024, 12, 1),
    }
    assigned = {'p1': 0, 'p2': 1, 'p3': 2}
    score, exact, total = batch_exponential_date_score(assigned, dates, decay_days=500.0)
    assert score == 100
    assert exact == 3
    assert total == 3


def test_batch_exponential_date_score_minor_swap_in_long_span() -> None:
    # 10-year span with 2 photos 2 days apart
    dates = {
        'p1': date(2014, 6, 1),
        'p2': date(2024, 7, 10),
        'p3': date(2024, 7, 12),
    }
    # Player swaps p2 and p3 (2 days diff)
    assigned = {'p1': 0, 'p2': 2, 'p3': 1}
    score, exact, total = batch_exponential_date_score(assigned, dates, decay_days=500.0)
    # p1 is exact (33.33 pts), p2 and p3 differ by 2 days in 500d decay:
    # 33.33 * exp(-2/500) = 33.20 pts -> total = 100
    assert score == 100
    assert exact == 1
    assert total == 3


def test_batch_exponential_date_score_distant_swap() -> None:
    dates = {
        'p1': date(2014, 6, 1),
        'p2': date(2024, 7, 10),
        'p3': date(2024, 7, 12),
    }
    # Player puts 2014 in slot 1 (swapping p1 and p2)
    assigned = {'p1': 1, 'p2': 0, 'p3': 2}
    score, exact, total = batch_exponential_date_score(assigned, dates, decay_days=500.0)
    # Only p3 in slot 2 is exact (33 pts), slots 0 and 1 are 10 years off (~0 pts)
    assert 33 <= score <= 35
    assert exact == 1
    assert total == 3


def test_batch_exponential_date_score_same_day_photos() -> None:
    dates = {
        'p1': date(2024, 8, 10),
        'p2': date(2024, 8, 10),
        'p3': date(2024, 8, 10),
    }
    # Any permutation is 100% since all share the same date
    assigned = {'p1': 2, 'p2': 0, 'p3': 1}
    score, exact, total = batch_exponential_date_score(assigned, dates, decay_days=30.0)
    assert score == 100
    assert exact == 3
    assert total == 3


def test_batch_exponential_scoring_handles_zero_decay_gracefully() -> None:
    # Verify zero decay does not cause ZeroDivisionError
    true_pins = {'p1': 'pin1', 'p2': 'pin2'}
    assigned = {'p1': 'pin1', 'p2': 'pin1'}
    pin_coords = {'pin1': (48.8566, 2.3522), 'pin2': (41.9028, 12.4964)}
    photo_coords = {'p1': (48.8566, 2.3522), 'p2': (41.9028, 12.4964)}
    score, exact, total = batch_exponential_location_score(assigned, true_pins, pin_coords, photo_coords, decay_km=0.0)
    assert score == 50
    assert exact == 1
    assert total == 2

    dates = {'p1': date(2020, 1, 1), 'p2': date(2024, 1, 1)}
    dt_score, dt_exact, dt_total = batch_exponential_date_score({'p1': 0, 'p2': 0}, dates, decay_days=0.0)
    assert dt_score == 50
    assert dt_exact == 1
    assert dt_total == 2

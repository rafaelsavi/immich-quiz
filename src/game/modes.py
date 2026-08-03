from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from src.config import AppSettings
from src.models import AnswerRequest
from src.scoring import (
    batch_strict_location_score,
    date_diff_days,
    date_diff_months,
    date_score,
    haversine_km,
    kendall_tau_inversion_score,
    location_score,
)
from src.storage.session import MatchState, QuestionState


@dataclass
class AnswerEvaluationResult:
    location_points: int
    date_points: int
    distance_km: float | None = None
    date_diff_days: int | None = None
    date_diff_months: int | None = None
    album_shuffle_guesses: list[dict[str, Any]] | None = None


def evaluate_pinpoint_answer(
    state: MatchState,
    question_state: QuestionState,
    payload: AnswerRequest,
    settings: AppSettings,
) -> AnswerEvaluationResult:
    """Evaluate submitted guess and calculate scores for Pinpoint mode."""
    location_points = 0
    date_points = 0
    distance: float | None = None
    delta_days: int | None = None
    delta_months: int | None = None

    if (
        state.setup.location_mode
        and payload.guessed_latitude is not None
        and payload.guessed_longitude is not None
        and question_state.actual_latitude is not None
        and question_state.actual_longitude is not None
    ):
        distance = haversine_km(
            question_state.actual_latitude,
            question_state.actual_longitude,
            payload.guessed_latitude,
            payload.guessed_longitude,
        )
        location_points = location_score(
            distance,
            decay_km=settings.location_score_decay_km,
            max_points=settings.score_max_points,
        )

    if (
        state.setup.date_mode
        and payload.guessed_year is not None
        and payload.guessed_month is not None
        and question_state.actual_date is not None
    ):
        delta_days = date_diff_days(payload.guessed_year, payload.guessed_month, question_state.actual_date)
        delta_months = date_diff_months(payload.guessed_year, payload.guessed_month, question_state.actual_date)
        date_points = date_score(
            delta_days,
            decay_days=settings.date_score_decay_days,
            max_points=settings.score_max_points,
        )

    return AnswerEvaluationResult(
        location_points=location_points,
        date_points=date_points,
        distance_km=distance,
        date_diff_days=delta_days,
        date_diff_months=delta_months,
    )


def evaluate_album_shuffle_answer(
    state: MatchState,
    question_state: QuestionState,
    payload: AnswerRequest,
    settings: AppSettings,
) -> AnswerEvaluationResult:
    """Evaluate submitted batch pin pairings and timeline rank ordering for Album Shuffle mode."""
    answers = payload.album_shuffle_answers or []
    batch_assets = question_state.batch_assets or []
    batch_pins = question_state.batch_pins or []

    true_pin_map = {str(bp['true_asset_id']): str(bp['pin_id']) for bp in batch_pins}

    correct_pins = 0
    album_shuffle_guesses: list[dict[str, Any]] = []
    for ans in answers:
        album_shuffle_guesses.append(
            {
                'photo_id': ans.photo_id,
                'assigned_pin_id': ans.assigned_pin_id,
                'assigned_timeline_index': ans.assigned_timeline_index,
            }
        )
        if ans.photo_id in true_pin_map and ans.assigned_pin_id == true_pin_map[ans.photo_id]:
            correct_pins += 1

    location_points = (
        batch_strict_location_score(
            correct_pins,
            total_photos=len(batch_assets),
            max_points=settings.score_max_points,
        )
        if state.setup.location_mode
        else 0
    )

    if state.setup.date_mode:
        if payload.timed_out or not answers:
            date_points = 0
        else:
            sorted_by_date = sorted(batch_assets, key=lambda a: a.answer.capture_date or date.min, reverse=True)
            true_rank_map = {a.asset_id: idx for idx, a in enumerate(sorted_by_date)}

            sorted_answers = sorted(
                answers,
                key=lambda ans: ans.assigned_timeline_index if ans.assigned_timeline_index is not None else 999,
            )
            guessed_ranks = [
                true_rank_map[ans.photo_id]
                for ans in sorted_answers
                if ans.photo_id in true_rank_map and ans.assigned_timeline_index is not None
            ]

            date_points = kendall_tau_inversion_score(
                guessed_ranks,
                max_points=settings.score_max_points,
                total_items=len(batch_assets),
            )
    else:
        date_points = 0

    return AnswerEvaluationResult(
        location_points=location_points,
        date_points=date_points,
        album_shuffle_guesses=album_shuffle_guesses,
    )

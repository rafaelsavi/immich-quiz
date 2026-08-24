"""Gameplay mode engine implementations for Pinpoint and Album Shuffle modes."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from datetime import date
from typing import Any, cast

from fastapi import HTTPException

from src.config import AppSettings
from src.game.selector import select_batch_round_assets, select_round_asset
from src.immich.client import ImmichClient, ImmichClientError
from src.models import (
    AlbumShuffleAnswerItem,
    AnswerRequest,
    BatchPhotoItem,
    BatchPinItem,
    BatchRevealItem,
    GameMode,
    PlayerRoundResult,
    QuestionResponse,
)
from src.scoring import (
    batch_strict_date_score,
    batch_strict_location_score,
    date_diff_days,
    date_diff_months,
    date_diff_parts,
    date_score,
    haversine_km,
    location_score,
)
from src.storage.metadata import MetadataStore
from src.storage.session import (
    MatchState,
    QuestionAlreadyAnsweredError,
    QuestionState,
    SessionStore,
)

logger = logging.getLogger(__name__)


def split_month_delta(delta_months: int | None) -> tuple[int | None, int | None]:
    """Split total month delta into (years, months) tuple."""
    if delta_months is None:
        return None, None
    return divmod(delta_months, 12)


def build_common_question_response(
    state: MatchState,
    question: QuestionState,
    batch_photos: list[BatchPhotoItem] | None = None,
    batch_pins: list[BatchPinItem] | None = None,
) -> QuestionResponse:
    """Construct standardized QuestionResponse payload with turn and player metadata."""
    players = state.setup.players
    player_index = players.index(question.player_name) if question.player_name in players else 0

    return QuestionResponse(
        question_id=question.question_id,
        asset_id=question.asset_id,
        media_url=f'/api/media/{question.asset_id}',
        player_name=question.player_name,
        player_number=player_index + 1,
        total_players=len(state.setup.players),
        player_round_number=state.current_player_round(),
        total_rounds_per_player=state.setup.round_count,
        turn_number=state.turn_index + 1,
        total_turns=state.total_turns,
        location_mode=state.setup.location_mode,
        date_mode=state.setup.date_mode,
        game_mode=state.setup.game_mode,
        round_length=state.setup.round_length,
        batch_photos=batch_photos,
        batch_pins=batch_pins,
    )


class BaseGameModeEngine(ABC):
    """Abstract base class defining gameplay mechanics for different game modes."""

    @abstractmethod
    async def select_question(
        self,
        state: MatchState,
        payload_played_asset_ids: list[str],
        settings: AppSettings,
        store: SessionStore,
        immich: ImmichClient,
        metadata_store: MetadataStore | None = None,
    ) -> QuestionState:
        """Select or retrieve question asset(s) for the current turn."""
        pass

    @abstractmethod
    def build_question_response(
        self,
        state: MatchState,
        question: QuestionState,
    ) -> QuestionResponse:
        """Construct turn payload tailored to the specific game mode."""
        pass

    @abstractmethod
    def evaluate_and_apply_answer(
        self,
        state: MatchState,
        question_state: QuestionState,
        payload: AnswerRequest,
        store: SessionStore,
    ) -> MatchState:
        """Score player submissions according to mode rules and update match state."""
        pass

    @abstractmethod
    def format_round_reveal(
        self,
        state: MatchState,
        reference: QuestionState,
        questions: list[QuestionState],
        round_index: int,
    ) -> tuple[list[BatchRevealItem] | None, list[PlayerRoundResult]]:
        """Format ground truth reveal and player score breakdowns for completed rounds."""
        pass


class PinpointEngine(BaseGameModeEngine):
    """Standard single-photo pinpoint game mode engine (map pinning and date guessing)."""

    async def select_question(
        self,
        state: MatchState,
        payload_played_asset_ids: list[str],
        settings: AppSettings,
        store: SessionStore,
        immich: ImmichClient,
        metadata_store: MetadataStore | None = None,
    ) -> QuestionState:
        round_index = state.current_round_index
        selection = state.round_assets.get(round_index)
        if selection is None:
            try:
                selection = await select_round_asset(
                    state,
                    immich,
                    set(payload_played_asset_ids),
                    settings.date_lower_bound,
                    settings.date_upper_bound,
                    metadata_store=metadata_store,
                    settings=settings,
                )
            except ImmichClientError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc

            if selection is None:
                raise HTTPException(status_code=404, detail='No eligible assets available')
            state.round_assets[round_index] = selection
            if metadata_store is not None:
                metadata_store.record_asset_played(selection.asset_id)

        return store.register_question(
            state.match_id,
            asset_id=selection.asset_id,
            actual_latitude=selection.answer.latitude,
            actual_longitude=selection.answer.longitude,
            actual_date=selection.answer.capture_date,
            actual_city=selection.answer.city,
            actual_country=selection.answer.country,
        )

    def build_question_response(
        self,
        state: MatchState,
        question: QuestionState,
    ) -> QuestionResponse:
        return build_common_question_response(state, question, batch_photos=None, batch_pins=None)

    def evaluate_and_apply_answer(
        self,
        state: MatchState,
        question_state: QuestionState,
        payload: AnswerRequest,
        store: SessionStore,
    ) -> MatchState:
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
                decay_km=state.location_decay_km,
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
                decay_days=state.date_decay_days,
            )

        try:
            return store.apply_score(
                payload.match_id,
                payload.question_id,
                location_points,
                date_points,
                guessed_latitude=payload.guessed_latitude,
                guessed_longitude=payload.guessed_longitude,
                guessed_year=payload.guessed_year,
                guessed_month=payload.guessed_month,
                distance_km=distance,
                diff_days=delta_days,
                diff_months=delta_months,
                timed_out=payload.timed_out,
                time_taken_seconds=payload.time_taken_seconds,
            )
        except QuestionAlreadyAnsweredError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    def format_round_reveal(
        self,
        state: MatchState,
        reference: QuestionState,
        questions: list[QuestionState],
        round_index: int,
    ) -> tuple[list[BatchRevealItem] | None, list[PlayerRoundResult]]:
        results: list[PlayerRoundResult] = []
        for question in questions:
            cumulative = sum(
                other.location_points + other.date_points
                for other in state.questions.values()
                if other.player_name == question.player_name and other.answered and other.round_index <= round_index
            )
            years_part, months_part, days_part = None, None, None
            if question.date_diff_months is not None and question.date_diff_days is not None:
                if reference.actual_date and question.guessed_year and question.guessed_month:
                    years_part, months_part, days_part = date_diff_parts(
                        question.guessed_year, question.guessed_month, reference.actual_date
                    )
                else:
                    years_part, months_part = split_month_delta(question.date_diff_months)
                    days_part = question.date_diff_days
            results.append(
                PlayerRoundResult(
                    player_name=question.player_name,
                    guessed_latitude=question.guessed_latitude,
                    guessed_longitude=question.guessed_longitude,
                    guessed_year=question.guessed_year,
                    guessed_month=question.guessed_month,
                    location_score=question.location_points if state.setup.location_mode else None,
                    date_score=question.date_points if state.setup.date_mode else None,
                    round_score=question.location_points + question.date_points,
                    total_score=cumulative,
                    distance_km=question.distance_km,
                    date_diff_days=question.date_diff_days,
                    date_diff_months=question.date_diff_months,
                    date_diff_years_part=years_part,
                    date_diff_months_part=months_part,
                    date_diff_days_part=days_part,
                    timed_out=question.timed_out,
                    album_shuffle_guesses=None,
                )
            )
        return None, results


class AlbumShuffleEngine(BaseGameModeEngine):
    """Album shuffle game mode engine (batch photo-to-pin mapping and timeline ordering)."""

    async def select_question(
        self,
        state: MatchState,
        payload_played_asset_ids: list[str],
        settings: AppSettings,
        store: SessionStore,
        immich: ImmichClient,
        metadata_store: MetadataStore | None = None,
    ) -> QuestionState:
        round_index = state.current_round_index
        batch_selection = state.batch_round_assets.get(round_index)
        batch_pins = state.batch_round_pins.get(round_index)

        if batch_selection is None or batch_pins is None:
            try:
                res = await select_batch_round_assets(
                    state,
                    immich,
                    3,
                    set(payload_played_asset_ids),
                    settings.date_lower_bound,
                    settings.date_upper_bound,
                    metadata_store=metadata_store,
                    settings=settings,
                )
            except ImmichClientError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc

            if res is None:
                raise HTTPException(status_code=404, detail='No eligible assets available')
            batch_selection, batch_pins = res
            state.batch_round_assets[round_index] = batch_selection
            state.batch_round_pins[round_index] = batch_pins
            if metadata_store is not None:
                metadata_store.record_assets_played([ra.asset_id for ra in batch_selection])

        return store.register_question(
            state.match_id,
            asset_id=batch_selection[0].asset_id,
            actual_latitude=batch_selection[0].answer.latitude,
            actual_longitude=batch_selection[0].answer.longitude,
            actual_date=batch_selection[0].answer.capture_date,
            actual_city=batch_selection[0].answer.city,
            actual_country=batch_selection[0].answer.country,
            batch_assets=batch_selection,
            batch_pins=batch_pins,
        )

    def build_question_response(
        self,
        state: MatchState,
        question: QuestionState,
    ) -> QuestionResponse:
        batch_photos = None
        batch_pins = None

        if question.batch_assets:
            batch_photos = [
                BatchPhotoItem(
                    photo_id=ba.asset_id,
                    media_url=f'/api/media/{ba.asset_id}',
                )
                for ba in question.batch_assets
            ]
            if state.setup.location_mode and question.batch_pins:
                batch_pins = [
                    BatchPinItem(
                        pin_id=str(bp['pin_id']),
                        latitude=float(cast(float | str, bp['latitude'])),
                        longitude=float(cast(float | str, bp['longitude'])),
                    )
                    for bp in question.batch_pins
                ]

        return build_common_question_response(state, question, batch_photos=batch_photos, batch_pins=batch_pins)

    def evaluate_and_apply_answer(
        self,
        state: MatchState,
        question_state: QuestionState,
        payload: AnswerRequest,
        store: SessionStore,
    ) -> MatchState:
        location_points = 0
        date_points = 0
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
            )
            if state.setup.location_mode
            else 0
        )

        if state.setup.date_mode:
            if not answers:
                date_points = 0
            else:
                sorted_by_date = sorted(batch_assets, key=lambda a: a.answer.capture_date or date.min, reverse=False)
                true_rank_map = {a.asset_id: idx for idx, a in enumerate(sorted_by_date)}

                correct_ranks = 0
                for ans in answers:
                    if (
                        ans.photo_id in true_rank_map
                        and ans.assigned_timeline_index is not None
                        and ans.assigned_timeline_index == true_rank_map[ans.photo_id]
                    ):
                        correct_ranks += 1

                date_points = batch_strict_date_score(correct_ranks, total_photos=len(batch_assets))
        else:
            date_points = 0

        try:
            return store.apply_score(
                payload.match_id,
                payload.question_id,
                location_points,
                date_points,
                timed_out=payload.timed_out,
                time_taken_seconds=payload.time_taken_seconds,
                album_shuffle_guesses=album_shuffle_guesses,
            )
        except QuestionAlreadyAnsweredError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    def format_round_reveal(
        self,
        state: MatchState,
        reference: QuestionState,
        questions: list[QuestionState],
        round_index: int,
    ) -> tuple[list[BatchRevealItem] | None, list[PlayerRoundResult]]:
        batch_reveal = None
        if reference.batch_assets:
            true_pin_map = {bp['true_asset_id']: bp['pin_id'] for bp in (reference.batch_pins or [])}
            batch_reveal = [
                BatchRevealItem(
                    photo_id=ba.asset_id,
                    true_pin_id=true_pin_map.get(ba.asset_id),
                    actual_latitude=ba.answer.latitude,
                    actual_longitude=ba.answer.longitude,
                    actual_date=ba.answer.capture_date,
                    actual_year=ba.answer.capture_date.year if ba.answer.capture_date else None,
                    actual_month=ba.answer.capture_date.month if ba.answer.capture_date else None,
                    actual_city=ba.answer.city,
                    actual_country=ba.answer.country,
                )
                for ba in reference.batch_assets
            ]

        results: list[PlayerRoundResult] = []
        for question in questions:
            cumulative = sum(
                other.location_points + other.date_points
                for other in state.questions.values()
                if other.player_name == question.player_name and other.answered and other.round_index <= round_index
            )
            years_part, months_part, days_part = None, None, None
            if question.date_diff_months is not None and question.date_diff_days is not None:
                if reference.actual_date and question.guessed_year and question.guessed_month:
                    years_part, months_part, days_part = date_diff_parts(
                        question.guessed_year, question.guessed_month, reference.actual_date
                    )
                else:
                    years_part, months_part = split_month_delta(question.date_diff_months)
                    days_part = question.date_diff_days
            shuffle_guesses = None
            if question.album_shuffle_guesses:
                shuffle_guesses = [
                    AlbumShuffleAnswerItem(
                        photo_id=str(g['photo_id']),
                        assigned_pin_id=str(g['assigned_pin_id']) if g.get('assigned_pin_id') else None,
                        assigned_timeline_index=int(cast(int | str, g['assigned_timeline_index']))
                        if g.get('assigned_timeline_index') is not None
                        else None,
                    )
                    for g in question.album_shuffle_guesses
                ]
            results.append(
                PlayerRoundResult(
                    player_name=question.player_name,
                    guessed_latitude=question.guessed_latitude,
                    guessed_longitude=question.guessed_longitude,
                    guessed_year=question.guessed_year,
                    guessed_month=question.guessed_month,
                    location_score=question.location_points if state.setup.location_mode else None,
                    date_score=question.date_points if state.setup.date_mode else None,
                    round_score=question.location_points + question.date_points,
                    total_score=cumulative,
                    distance_km=question.distance_km,
                    date_diff_days=question.date_diff_days,
                    date_diff_months=question.date_diff_months,
                    date_diff_years_part=years_part,
                    date_diff_months_part=months_part,
                    date_diff_days_part=days_part,
                    timed_out=question.timed_out,
                    album_shuffle_guesses=shuffle_guesses,
                )
            )

        return batch_reveal, results


class GameModeRegistry:
    """Registry mapping GameMode enum members to their execution engine instances."""

    def __init__(self) -> None:
        self._engines: dict[GameMode, BaseGameModeEngine] = {}

    def register(self, mode: GameMode, engine: BaseGameModeEngine) -> None:
        """Register an engine instance for a game mode."""
        self._engines[mode] = engine

    def get(self, mode: GameMode) -> BaseGameModeEngine:
        """Retrieve registered engine for a game mode or raise HTTPException."""
        if mode not in self._engines:
            raise HTTPException(status_code=400, detail=f'Unsupported game mode: {mode}')
        return self._engines[mode]


default_game_mode_registry = GameModeRegistry()
default_game_mode_registry.register(GameMode.pinpoint, PinpointEngine())
default_game_mode_registry.register(GameMode.album_shuffle, AlbumShuffleEngine())

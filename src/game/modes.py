"""Gameplay mode engine implementations for Pinpoint and Album Shuffle modes."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from fastapi import HTTPException

from src.app_logging import LOGGER_MATCH, get_logger
from src.config import AppSettings
from src.game.selector import select_batch_round_assets, select_pinpoint_round_asset
from src.immich.client import ImmichClient, ImmichClientError
from src.models import (
    AlbumShuffleAnswerItem,
    AnswerRequest,
    BatchPhotoItem,
    BatchPinItem,
    BatchRevealItem,
    GameMode,
    PinpointAnswerItem,
    PinpointDeviation,
    PinpointRoundResult,
    PlayerRoundResult,
    QuestionResponse,
)
from src.scoring import (
    batch_exponential_date_score,
    batch_exponential_location_score,
    calculate_date_decay,
    calculate_location_decay,
    date_diff_days,
    date_diff_months,
    date_diff_parts,
    haversine_km,
    pinpoint_date_score,
    pinpoint_location_score,
)
from src.storage.metadata import MetadataStore
from src.storage.session import (
    MatchState,
    QuestionAlreadyAnsweredError,
    QuestionState,
    RoundData,
    SessionStore,
)

logger = get_logger(LOGGER_MATCH)


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
    if not question.round_data.assets:
        raise ValueError(f'Question {question.question_id} has no assets in round_data')
    primary_asset_id = question.round_data.assets[0].asset_id

    return QuestionResponse(
        question_id=question.question_id,
        asset_id=primary_asset_id,
        media_url=f'/api/media/{primary_asset_id}',
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
        round_data = state.rounds.get(round_index)
        if round_data is None:
            try:
                selection = await select_pinpoint_round_asset(
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
            round_data = RoundData(assets=[selection])
            state.rounds[round_index] = round_data
            if metadata_store is not None:
                metadata_store.record_asset_played(selection.asset_id)

        return store.register_question(
            state.match_id,
            round_data=round_data,
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

        actual_asset = question_state.round_data.assets[0].answer
        guess = payload.pinpoint or PinpointAnswerItem()

        if (
            state.setup.location_mode
            and guess.guessed_latitude is not None
            and guess.guessed_longitude is not None
            and actual_asset.latitude is not None
            and actual_asset.longitude is not None
        ):
            distance = haversine_km(
                actual_asset.latitude,
                actual_asset.longitude,
                guess.guessed_latitude,
                guess.guessed_longitude,
            )
            location_points = pinpoint_location_score(
                distance,
                decay_km=state.location_decay_km,
            )

        if (
            state.setup.date_mode
            and guess.guessed_year is not None
            and guess.guessed_month is not None
            and actual_asset.capture_date is not None
        ):
            delta_days = date_diff_days(guess.guessed_year, guess.guessed_month, actual_asset.capture_date)
            delta_months = date_diff_months(guess.guessed_year, guess.guessed_month, actual_asset.capture_date)
            date_points = pinpoint_date_score(
                delta_days,
                decay_days=state.date_decay_days,
            )

        deviation = PinpointDeviation(
            distance_km=distance,
            date_diff_days=delta_days,
            date_diff_months=delta_months,
        )

        loc_desc = (
            f'{distance:.2f}km -> {location_points}pts (decay={state.location_decay_km:.1f}km)'
            if distance is not None
            else 'N/A'
        )
        date_desc = (
            f'{delta_days}d -> {date_points}pts (decay={state.date_decay_days:.1f}d)'
            if delta_days is not None
            else 'N/A'
        )
        logger.info(
            'Match %s (R%d) guess evaluated: location=[%s], date=[%s]',
            payload.match_id,
            state.current_round_index + 1,
            loc_desc,
            date_desc,
        )

        try:
            return store.apply_pinpoint_score(
                payload.match_id,
                payload.question_id,
                location_points,
                date_points,
                guess=guess,
                deviation=deviation,
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
        actual_date = reference.round_data.assets[0].answer.capture_date
        for question in questions:
            cumulative = sum(
                other.location_points + other.date_points
                for other in state.questions.values()
                if other.player_name == question.player_name and other.answered and other.round_index <= round_index
            )
            g = question.pinpoint_guess or PinpointAnswerItem()
            dev = question.pinpoint_deviation or PinpointDeviation()

            years_part, months_part, days_part = None, None, None
            if dev.date_diff_months is not None and dev.date_diff_days is not None:
                if actual_date and g.guessed_year and g.guessed_month:
                    years_part, months_part, days_part = date_diff_parts(g.guessed_year, g.guessed_month, actual_date)
                else:
                    years_part, months_part = split_month_delta(dev.date_diff_months)
                    days_part = dev.date_diff_days

            pinpoint_result = PinpointRoundResult(
                guessed_latitude=g.guessed_latitude,
                guessed_longitude=g.guessed_longitude,
                guessed_year=g.guessed_year,
                guessed_month=g.guessed_month,
                distance_km=dev.distance_km,
                date_diff_days=dev.date_diff_days,
                date_diff_months=dev.date_diff_months,
                date_diff_years_part=years_part,
                date_diff_months_part=months_part,
                date_diff_days_part=days_part,
            )
            results.append(
                PlayerRoundResult(
                    player_name=question.player_name,
                    location_score=question.location_points if state.setup.location_mode else None,
                    date_score=question.date_points if state.setup.date_mode else None,
                    round_score=question.location_points + question.date_points,
                    total_score=cumulative,
                    timed_out=question.timed_out,
                    pinpoint=pinpoint_result,
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
        round_data = state.rounds.get(round_index)

        if round_data is None:
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
            round_data = RoundData(assets=batch_selection, pins=batch_pins)
            state.rounds[round_index] = round_data
            if metadata_store is not None:
                metadata_store.record_assets_played([ra.asset_id for ra in batch_selection])

        return store.register_question(
            state.match_id,
            round_data=round_data,
        )

    def build_question_response(
        self,
        state: MatchState,
        question: QuestionState,
    ) -> QuestionResponse:
        batch_photos = None
        batch_pins = None

        if question.round_data.assets:
            batch_photos = [
                BatchPhotoItem(
                    photo_id=ba.asset_id,
                    media_url=f'/api/media/{ba.asset_id}',
                )
                for ba in question.round_data.assets
            ]
            if state.setup.location_mode and question.round_data.pins:
                batch_pins = [
                    BatchPinItem(
                        pin_id=str(bp['pin_id']),
                        latitude=float(bp['latitude']),
                        longitude=float(bp['longitude']),
                    )
                    for bp in question.round_data.pins
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
        answers = payload.album_shuffle or []
        batch_assets = question_state.round_data.assets
        batch_pins = question_state.round_data.pins

        true_pin_map = {str(bp['true_asset_id']): str(bp['pin_id']) for bp in batch_pins}
        pin_coords = {
            str(bp['pin_id']): (
                float(bp['latitude']) if bp.get('latitude') is not None else None,
                float(bp['longitude']) if bp.get('longitude') is not None else None,
            )
            for bp in batch_pins
        }
        photo_coords = {ba.asset_id: (ba.answer.latitude, ba.answer.longitude) for ba in batch_assets}
        photo_dates = {ba.asset_id: ba.answer.capture_date for ba in batch_assets}

        assigned_pins = {ans.photo_id: ans.assigned_pin_id for ans in answers}
        assigned_timeline = {ans.photo_id: ans.assigned_timeline_index for ans in answers}

        album_shuffle_guesses: list[dict[str, Any]] = [
            {
                'photo_id': ans.photo_id,
                'assigned_pin_id': ans.assigned_pin_id,
                'assigned_timeline_index': ans.assigned_timeline_index,
            }
            for ans in answers
        ]

        if state.setup.location_mode:
            decay_km = calculate_location_decay(batch_assets)
            location_points, correct_pins, _ = batch_exponential_location_score(
                assigned_pins=assigned_pins,
                true_pin_map=true_pin_map,
                pin_coords=pin_coords,
                photo_coords=photo_coords,
                decay_km=decay_km,
            )
        else:
            location_points = 0
            correct_pins = 0
            decay_km = None

        if state.setup.date_mode:
            decay_days = calculate_date_decay(batch_assets)
            date_points, correct_ranks, _ = batch_exponential_date_score(
                assigned_timeline=assigned_timeline,
                photo_dates=photo_dates,
                decay_days=decay_days,
            )
        else:
            date_points = 0
            correct_ranks = 0
            decay_days = None

        loc_desc = (
            f'{location_points}pts ({correct_pins}/{len(batch_assets)} exact, decay={decay_km:.1f}km)'
            if state.setup.location_mode and decay_km is not None
            else 'N/A'
        )
        date_desc = (
            f'{date_points}pts ({correct_ranks}/{len(batch_assets)} exact, decay={decay_days:.1f}d)'
            if state.setup.date_mode and decay_days is not None
            else 'N/A'
        )
        logger.info(
            'Match %s (R%d) Album Shuffle evaluated: location=[%s], date=[%s]',
            payload.match_id,
            state.current_round_index + 1,
            loc_desc,
            date_desc,
        )

        try:
            return store.apply_album_shuffle_score(
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
        if reference.round_data.assets:
            true_pin_map = {bp['true_asset_id']: bp['pin_id'] for bp in reference.round_data.pins}
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
                for ba in reference.round_data.assets
            ]

        results: list[PlayerRoundResult] = []
        for question in questions:
            cumulative = sum(
                other.location_points + other.date_points
                for other in state.questions.values()
                if other.player_name == question.player_name and other.answered and other.round_index <= round_index
            )
            shuffle_guesses = None
            if question.album_shuffle_guesses:
                shuffle_guesses = [
                    AlbumShuffleAnswerItem(
                        photo_id=str(g['photo_id']),
                        assigned_pin_id=str(g['assigned_pin_id']) if g.get('assigned_pin_id') else None,
                        assigned_timeline_index=int(g['assigned_timeline_index'])
                        if g.get('assigned_timeline_index') is not None
                        else None,
                    )
                    for g in question.album_shuffle_guesses
                ]
            results.append(
                PlayerRoundResult(
                    player_name=question.player_name,
                    location_score=question.location_points if state.setup.location_mode else None,
                    date_score=question.date_points if state.setup.date_mode else None,
                    round_score=question.location_points + question.date_points,
                    total_score=cumulative,
                    timed_out=question.timed_out,
                    pinpoint=None,
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

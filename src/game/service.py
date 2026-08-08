from __future__ import annotations

import logging
from typing import Any

from fastapi import HTTPException

from src.game.modes import GameModeRegistry, default_game_mode_registry
from src.immich.client import ImmichClient, ImmichClientError

logger = logging.getLogger(__name__)
from src.models import (
    AnswerRequest,
    AnswerResponse,
    GameMode,
    GameSetupRequest,
    GameSetupResponse,
    MatchSummaryPlayer,
    MatchSummaryResponse,
    PreflightRequest,
    PreflightResponse,
    QuestionRequest,
    QuestionResponse,
    RoundResultRequest,
    RoundResultResponse,
)
from src.scoring import accuracy_pct, max_possible_score
from src.storage.leaderboard import LeaderboardStore
from src.storage.session import SessionStore


class GameService:
    def __init__(self, registry: GameModeRegistry | None = None) -> None:
        self.registry = registry or default_game_mode_registry

    async def resolve_album_name(self, immich: ImmichClient, library_name: str, album_id: str | None) -> str:
        """Resolve the album label server-side so clients cannot spoof leaderboard metadata."""
        if not album_id:
            return '-'

        try:
            albums = await immich.list_albums(library_name, include_shared_albums=True)
        except ImmichClientError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        for album in albums:
            if album.get('id') == album_id:
                return album.get('name', '-')
        raise HTTPException(status_code=400, detail=f'Unknown album_id for library {library_name}')

    async def preflight(
        self,
        setup: PreflightRequest,
        settings: Any,
        immich: ImmichClient,
    ) -> PreflightResponse:
        try:
            raw_assets = await immich.search_random_assets(setup.library_name, setup.album_id)
        except ImmichClientError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        active_filters: list[str] = []
        if setup.location_mode:
            active_filters.append('location')
        if setup.date_mode:
            active_filters.append('date')
        if settings.fetch_photos_date_lower_bound or settings.fetch_photos_date_upper_bound:
            active_filters.append('date_range')

        eligible_count = sum(
            1
            for asset in raw_assets
            if ImmichClient.is_eligible_asset(
                asset,
                setup.location_mode,
                setup.date_mode,
                settings.fetch_photos_date_lower_bound,
                settings.fetch_photos_date_upper_bound,
            )
        )

        required = (
            5 * setup.round_count
            if getattr(setup, 'game_mode', GameMode.pinpoint) == GameMode.album_shuffle
            else setup.round_count
        )
        return PreflightResponse(
            eligible_count=eligible_count,
            required=required,
            ok=eligible_count >= required,
            active_filters=active_filters,
            min_date=settings.fetch_photos_date_lower_bound,
            max_date=settings.fetch_photos_date_upper_bound,
        )

    async def setup_game(
        self,
        setup: GameSetupRequest,
        store: SessionStore,
        immich: ImmichClient,
    ) -> GameSetupResponse:
        setup.album_name = await self.resolve_album_name(immich, setup.library_name, setup.album_id)
        state = store.create_match(setup)
        return GameSetupResponse(
            match_id=state.match_id,
            total_turns=state.total_turns,
            players=list(state.setup.players),
        )

    async def get_question(
        self,
        payload: QuestionRequest,
        settings: Any,
        store: SessionStore,
        immich: ImmichClient,
    ) -> QuestionResponse:
        try:
            state = store.get_match(payload.match_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

        if state.finished:
            raise HTTPException(status_code=409, detail='Match is already finished')

        if state.turn_index >= state.total_turns:
            raise HTTPException(status_code=409, detail='No remaining turns')

        engine = self.registry.get(state.setup.game_mode)

        active = store.active_question(payload.match_id)
        if active is not None:
            active_failed = False
            if active.asset_id in payload.played_asset_ids:
                active_failed = True
            elif active.batch_assets and any(ba.asset_id in payload.played_asset_ids for ba in active.batch_assets):
                active_failed = True

            if active_failed:
                logger.info(
                    "Active question %s asset was reported invalid/failed by client; invalidating active question and re-selecting for round %d.",
                    active.question_id,
                    state.current_round_index,
                )
                state.active_question_id = None
                state.round_assets.pop(state.current_round_index, None)
                state.batch_round_assets.pop(state.current_round_index, None)
                state.batch_round_pins.pop(state.current_round_index, None)
                if active.batch_assets:
                    for ba in active.batch_assets:
                        if ba.asset_id in payload.played_asset_ids:
                            state.played_asset_ids.add(ba.asset_id)
                else:
                    state.played_asset_ids.add(active.asset_id)
                active = None
            else:
                return engine.build_question_response(state, active)

        question_state = await engine.select_question(
            state,
            payload.played_asset_ids,
            settings,
            store,
            immich,
        )
        return engine.build_question_response(state, question_state)

    async def submit_answer(
        self,
        payload: AnswerRequest,
        settings: Any,
        store: SessionStore,
        leaderboard_store: LeaderboardStore,
    ) -> AnswerResponse:
        try:
            state = store.get_match(payload.match_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

        question_state = state.questions.get(payload.question_id)
        if question_state is None:
            raise HTTPException(status_code=404, detail='Unknown question_id')
        if question_state.answered:
            raise HTTPException(status_code=409, detail='Question already answered')

        engine = self.registry.get(state.setup.game_mode)
        updated_state = engine.evaluate_and_apply_answer(state, question_state, payload, settings, store)

        if updated_state.finished:
            leaderboard_store.append_match(
                match_id=updated_state.match_id,
                library_name=updated_state.setup.library_name,
                album_name=updated_state.setup.album_name or '-',
                rounds_played=updated_state.setup.round_count,
                round_length=updated_state.setup.round_length.value,
                location_mode=updated_state.setup.location_mode,
                date_mode=updated_state.setup.date_mode,
                game_mode=updated_state.setup.game_mode.value,
                player_scores=updated_state.scores,
            )

        return AnswerResponse(
            player_name=question_state.player_name,
            question_id=question_state.question_id,
            round_number=question_state.round_index + 1,
            turn_completed=updated_state.turn_index,
            total_turns=updated_state.total_turns,
            round_complete=updated_state.is_round_complete(question_state.round_index),
            waiting_for=updated_state.players_pending_in_round(question_state.round_index),
            match_finished=updated_state.finished,
        )

    async def get_round_result(
        self,
        payload: RoundResultRequest,
        settings: Any,
        store: SessionStore,
    ) -> RoundResultResponse:
        """Reveal a round only once every player in it has locked in an answer."""
        try:
            state = store.get_match(payload.match_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

        round_index = payload.round_number - 1
        total_rounds = state.setup.round_count
        if round_index < 0 or round_index >= total_rounds:
            raise HTTPException(status_code=404, detail='Unknown round_number')

        if not state.is_round_complete(round_index):
            raise HTTPException(status_code=409, detail='Round is not complete yet')

        questions = state.round_questions(round_index)
        reference = questions[0]

        engine = self.registry.get(state.setup.game_mode)
        batch_reveal, results = engine.format_round_reveal(state, reference, questions, round_index)

        return RoundResultResponse(
            round_number=round_index + 1,
            total_rounds=total_rounds,
            location_mode=state.setup.location_mode,
            date_mode=state.setup.date_mode,
            game_mode=state.setup.game_mode,
            library_name=state.setup.library_name,
            actual_latitude=reference.actual_latitude,
            actual_longitude=reference.actual_longitude,
            actual_date=reference.actual_date,
            actual_year=reference.actual_date.year if reference.actual_date else None,
            actual_month=reference.actual_date.month if reference.actual_date else None,
            actual_city=reference.actual_city,
            actual_country=reference.actual_country,
            batch_reveal=batch_reveal,
            results=results,
            match_finished=state.finished,
            score_max_points=settings.score_max_points,
        )

    async def get_match_summary(
        self,
        match_id: str,
        settings: Any,
        store: SessionStore,
    ) -> MatchSummaryResponse:
        try:
            state = store.get_match(match_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

        max_score = max_possible_score(
            state.setup.round_count,
            state.setup.location_mode,
            state.setup.date_mode,
            per_goal_max_points=settings.score_max_points,
        )

        ordered = sorted(
            state.setup.players,
            key=lambda player: (-state.scores[player]['total'], player.lower()),
        )
        best_total = state.scores[ordered[0]]['total'] if ordered else 0
        winners = [player for player in ordered if state.scores[player]['total'] == best_total]

        players: list[MatchSummaryPlayer] = []
        rank = 0
        previous_total: int | None = None
        for index, player in enumerate(ordered):
            bucket = state.scores[player]
            if previous_total is None or bucket['total'] != previous_total:
                rank = index + 1
                previous_total = bucket['total']
            players.append(
                MatchSummaryPlayer(
                    player_name=player,
                    location_score=bucket['location'] if state.setup.location_mode else None,
                    date_score=bucket['date'] if state.setup.date_mode else None,
                    total_score=bucket['total'],
                    max_possible_score=max_score,
                    accuracy_pct=accuracy_pct(bucket['total'], max_score),
                    rank=rank,
                    is_winner=player in winners,
                )
            )

        return MatchSummaryResponse(
            match_id=state.match_id,
            rounds_played=state.setup.round_count,
            location_mode=state.setup.location_mode,
            date_mode=state.setup.date_mode,
            game_mode=state.setup.game_mode,
            library_name=state.setup.library_name,
            album_name=state.setup.album_name or '-',
            finished=state.finished,
            winners=winners,
            players=players,
        )

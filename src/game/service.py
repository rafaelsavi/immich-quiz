from __future__ import annotations

from typing import cast

from src.config import AppSettings
from src.game.modes import evaluate_album_shuffle_answer, evaluate_pinpoint_answer
from src.game.selector import select_batch_round_assets, select_round_asset
from src.immich.client import ImmichClient
from src.models import (
    AlbumShuffleAnswerItem,
    AnswerRequest,
    AnswerResponse,
    BatchRevealItem,
    GameMode,
    GameSetupRequest,
    GameSetupResponse,
    MatchSummaryPlayer,
    MatchSummaryResponse,
    PlayerRoundResult,
    PreflightRequest,
    PreflightResponse,
    RoundResultResponse,
)
from src.scoring import (
    accuracy_pct,
    date_diff_parts,
    max_possible_score,
)
from src.storage.leaderboard import LeaderboardStore
from src.storage.session import MatchState, QuestionState, SessionStore


def _split_month_delta(delta_months: int | None) -> tuple[int | None, int | None]:
    if delta_months is None:
        return None, None
    return divmod(delta_months, 12)


class GameService:
    """Service layer orchestrating match state, question drawing, scoring evaluation, and leaderboard updates."""

    def __init__(
        self,
        store: SessionStore,
        immich: ImmichClient,
        leaderboard_store: LeaderboardStore,
        settings: AppSettings,
    ) -> None:
        self.store = store
        self.immich = immich
        self.leaderboard_store = leaderboard_store
        self.settings = settings

    async def preflight(self, setup: PreflightRequest) -> PreflightResponse:
        """Validate candidate asset count against requested round count."""
        raw_assets = await self.immich.search_random_assets(setup.library_name, setup.album_id)

        active_filters: list[str] = []
        if setup.location_mode:
            active_filters.append('location')
        if setup.date_mode:
            active_filters.append('date')
        if self.settings.fetch_photos_date_lower_bound or self.settings.fetch_photos_date_upper_bound:
            active_filters.append('date_range')

        eligible_count = sum(
            1
            for asset in raw_assets
            if ImmichClient.is_eligible_asset(
                asset,
                setup.location_mode,
                setup.date_mode,
                self.settings.fetch_photos_date_lower_bound,
                self.settings.fetch_photos_date_upper_bound,
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
            min_date=self.settings.fetch_photos_date_lower_bound,
            max_date=self.settings.fetch_photos_date_upper_bound,
        )

    async def setup_match(self, payload: GameSetupRequest) -> GameSetupResponse:
        """Initialize a new match state."""
        library_name = payload.library_name.strip()
        album_name: str | None = None
        if payload.album_id is not None:
            albums = await self.immich.list_albums(library_name, include_shared_albums=True)
            for album in albums:
                if str(album.get('id', '')).strip() == payload.album_id:
                    album_name = str(album.get('name', '')).strip() or None
                    break
        payload.album_name = album_name or '-'
        state = self.store.create_match(payload)
        return GameSetupResponse(
            match_id=state.match_id,
            total_turns=state.total_turns,
            players=list(state.setup.players),
        )

    async def get_or_create_question(
        self, match_id: str, played_asset_ids: list[str]
    ) -> tuple[MatchState, QuestionState]:
        """Fetch active question or sample a new asset for the current round turn."""
        state = self.store.get_match(match_id)
        if state.finished:
            raise ValueError('Match is already finished')
        if state.turn_index >= state.total_turns:
            raise ValueError('No remaining turns')

        active = self.store.active_question(match_id)
        if active is not None:
            return state, active

        round_index = state.current_round_index

        if state.setup.game_mode == GameMode.album_shuffle:
            batch_selection = state.batch_round_assets.get(round_index)
            batch_pins = state.batch_round_pins.get(round_index)

            if batch_selection is None or batch_pins is None:
                res = await select_batch_round_assets(
                    state,
                    self.immich,
                    5,
                    set(played_asset_ids),
                    self.settings.fetch_photos_date_lower_bound,
                    self.settings.fetch_photos_date_upper_bound,
                )
                if res is None:
                    raise KeyError('No eligible assets available')
                batch_selection, batch_pins = res
                state.batch_round_assets[round_index] = batch_selection
                state.batch_round_pins[round_index] = batch_pins

            question_state = self.store.register_question(
                match_id,
                asset_id=batch_selection[0].asset_id,
                actual_latitude=batch_selection[0].answer.latitude,
                actual_longitude=batch_selection[0].answer.longitude,
                actual_date=batch_selection[0].answer.capture_date,
                actual_city=batch_selection[0].answer.city,
                actual_country=batch_selection[0].answer.country,
                batch_assets=batch_selection,
                batch_pins=batch_pins,
            )
            return state, question_state

        selection = state.round_assets.get(round_index)
        if selection is None:
            selection = await select_round_asset(
                state,
                self.immich,
                set(played_asset_ids),
                self.settings.fetch_photos_date_lower_bound,
                self.settings.fetch_photos_date_upper_bound,
            )
            if selection is None:
                raise KeyError('No eligible assets available')
            state.round_assets[round_index] = selection

        question_state = self.store.register_question(
            match_id,
            asset_id=selection.asset_id,
            actual_latitude=selection.answer.latitude,
            actual_longitude=selection.answer.longitude,
            actual_date=selection.answer.capture_date,
            actual_city=selection.answer.city,
            actual_country=selection.answer.country,
        )
        return state, question_state

    def submit_answer(self, payload: AnswerRequest) -> AnswerResponse:
        """Evaluate submitted player answer and record score."""
        state = self.store.get_match(payload.match_id)
        question_state = state.questions.get(payload.question_id)
        if question_state is None:
            raise KeyError('Unknown question_id')
        if question_state.answered:
            raise ValueError('Question already answered')

        if state.setup.game_mode == GameMode.album_shuffle:
            eval_res = evaluate_album_shuffle_answer(state, question_state, payload, self.settings)
        else:
            eval_res = evaluate_pinpoint_answer(state, question_state, payload, self.settings)

        round_index = question_state.round_index
        updated_state = self.store.apply_score(
            payload.match_id,
            payload.question_id,
            eval_res.location_points,
            eval_res.date_points,
            guessed_latitude=payload.guessed_latitude,
            guessed_longitude=payload.guessed_longitude,
            guessed_year=payload.guessed_year,
            guessed_month=payload.guessed_month,
            distance_km=eval_res.distance_km,
            diff_days=eval_res.date_diff_days,
            diff_months=eval_res.date_diff_months,
            timed_out=payload.timed_out,
            album_shuffle_guesses=eval_res.album_shuffle_guesses,
        )

        if updated_state.finished:
            self.leaderboard_store.append_match(
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
            round_number=round_index + 1,
            turn_completed=updated_state.turn_index,
            total_turns=updated_state.total_turns,
            round_complete=updated_state.is_round_complete(round_index),
            waiting_for=updated_state.players_pending_in_round(round_index),
            match_finished=updated_state.finished,
        )

    def get_round_result(self, match_id: str, round_number: int) -> RoundResultResponse:
        """Assemble round reveal data once all players have answered."""
        state = self.store.get_match(match_id)
        round_index = round_number - 1
        total_rounds = state.setup.round_count
        if round_index < 0 or round_index >= total_rounds:
            raise ValueError('round_number is out of bounds')

        if not state.is_round_complete(round_index):
            raise ValueError('Round is not complete yet')

        questions = state.round_questions(round_index)
        reference = questions[0]

        batch_reveal: list[BatchRevealItem] | None = None
        if state.setup.game_mode == GameMode.album_shuffle and reference.batch_assets:
            true_pin_map = {bp['true_asset_id']: bp['pin_id'] for bp in (reference.batch_pins or [])}
            batch_reveal = [
                BatchRevealItem(
                    photo_id=ba.asset_id,
                    true_pin_id=str(true_pin_map.get(ba.asset_id, '')),
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
                    years_part, months_part = _split_month_delta(question.date_diff_months)
                    days_part = question.date_diff_days
            shuffle_guesses: list[AlbumShuffleAnswerItem] | None = None
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
            score_max_points=self.settings.score_max_points,
        )

    def get_match_summary(self, match_id: str) -> MatchSummaryResponse:
        """Assemble match summary details."""
        state = self.store.get_match(match_id)
        if not state.finished:
            raise ValueError('Match is not finished yet')

        max_score = max_possible_score(
            state.setup.round_count,
            state.setup.location_mode,
            state.setup.date_mode,
            per_goal_max_points=self.settings.score_max_points,
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

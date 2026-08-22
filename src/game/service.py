from __future__ import annotations

import logging
import time
from datetime import date, datetime, timezone
from typing import Any

from fastapi import HTTPException

from src.config import AppSettings
from src.game.modes import GameModeRegistry, default_game_mode_registry
from src.game.selector import calculate_match_bounds, load_asset_pool
from src.i18n import SupportedLanguage
from src.immich.client import ImmichClient
from src.models import (
    AnswerRequest,
    AnswerResponse,
    GameMode,
    GameSetupRequest,
    GameSetupResponse,
    MapBounds,
    MatchSummaryPlayer,
    MatchSummaryResponse,
    PeopleMode,
    PlayMode,
    PreflightRequest,
    PreflightResponse,
    QuestionRequest,
    QuestionResponse,
    RoundResultRequest,
    RoundResultResponse,
    SyncStatus,
)
from src.scoring import SCORE_MAX_POINTS, accuracy_pct, haversine_km, max_possible_score
from src.storage.leaderboard import LeaderboardStore
from src.storage.metadata import AssetFilterCriteria, MetadataStore
from src.storage.session import MatchState, SessionStore

logger = logging.getLogger(__name__)


def extract_round_guesses(state: MatchState) -> list[dict[str, Any]]:
    guesses: list[dict[str, Any]] = []
    ordered_questions = sorted(
        state.questions.values(),
        key=lambda q: (q.round_index, q.player_name),
    )
    for q in ordered_questions:
        if not q.answered:
            continue
        if state.setup.game_mode == GameMode.album_shuffle and q.batch_assets:
            guess_map = {g['photo_id']: g for g in (q.album_shuffle_guesses or [])}
            pin_by_id = {bp['pin_id']: bp for bp in (q.batch_pins or [])}
            true_pin_map = {str(bp['true_asset_id']): str(bp['pin_id']) for bp in (q.batch_pins or [])}
            sorted_by_date = sorted(q.batch_assets, key=lambda a: a.answer.capture_date or date.min, reverse=False)
            true_rank_map = {a.asset_id: idx for idx, a in enumerate(sorted_by_date)}
            total_photos = len(q.batch_assets)
            per_photo_max = (SCORE_MAX_POINTS // total_photos) if total_photos > 0 else 0

            for idx, ba in enumerate(q.batch_assets):
                guessed_item = guess_map.get(ba.asset_id, {})
                assigned_pin_id = guessed_item.get('assigned_pin_id')
                assigned_timeline_index = guessed_item.get('assigned_timeline_index')
                assigned_pin = pin_by_id.get(assigned_pin_id) if assigned_pin_id else None

                guess_lat = (
                    float(assigned_pin['latitude'])
                    if assigned_pin and assigned_pin.get('latitude') is not None
                    else None
                )
                guess_lng = (
                    float(assigned_pin['longitude'])
                    if assigned_pin and assigned_pin.get('longitude') is not None
                    else None
                )

                dist_km: float | None = None
                if (
                    guess_lat is not None
                    and guess_lng is not None
                    and ba.answer.latitude is not None
                    and ba.answer.longitude is not None
                ):
                    dist_km = haversine_km(ba.answer.latitude, ba.answer.longitude, guess_lat, guess_lng)

                if state.setup.location_mode:
                    is_correct_loc: int | None = 1 if (ba.asset_id in true_pin_map and assigned_pin_id == true_pin_map[ba.asset_id]) else 0
                    loc_points: int | None = per_photo_max if is_correct_loc == 1 else 0
                else:
                    is_correct_loc = None
                    loc_points = None

                if state.setup.date_mode:
                    is_correct_date: int | None = (
                        1
                        if (
                            ba.asset_id in true_rank_map
                            and assigned_timeline_index is not None
                            and assigned_timeline_index == true_rank_map[ba.asset_id]
                        )
                        else 0
                    )
                    dt_points: int | None = per_photo_max if is_correct_date == 1 else 0
                else:
                    is_correct_date = None
                    dt_points = None

                photo_score = (loc_points or 0) + (dt_points or 0)

                guesses.append(
                    {
                        'match_id': state.match_id,
                        'player_name': q.player_name,
                        'round_index': q.round_index,
                        'photo_index': idx,
                        'game_mode': state.setup.game_mode.value,
                        'asset_id': ba.asset_id,
                        'guess_latitude': guess_lat,
                        'guess_longitude': guess_lng,
                        'actual_latitude': ba.answer.latitude,
                        'actual_longitude': ba.answer.longitude,
                        'distance_km': dist_km,
                        'location_points': loc_points,
                        'guess_date': None,
                        'actual_date': ba.answer.capture_date.isoformat() if ba.answer.capture_date else None,
                        'date_diff_days': None,
                        'date_points': dt_points,
                        'round_score': photo_score,
                        'is_correct_location': is_correct_loc,
                        'is_correct_date_order': is_correct_date,
                        'time_taken_seconds': q.time_taken_seconds,
                        'submitted_at': q.submitted_at or datetime.now(timezone.utc).isoformat(),
                    }
                )
        else:
            guess_date_str = (
                f'{q.guessed_year:04d}-{q.guessed_month:02d}-01'
                if q.guessed_year is not None and q.guessed_month is not None
                else None
            )
            actual_date_str = q.actual_date.isoformat() if q.actual_date else None
            guesses.append(
                {
                    'match_id': state.match_id,
                    'player_name': q.player_name,
                    'round_index': q.round_index,
                    'photo_index': 0,
                    'game_mode': state.setup.game_mode.value,
                    'asset_id': q.asset_id,
                    'guess_latitude': q.guessed_latitude,
                    'guess_longitude': q.guessed_longitude,
                    'actual_latitude': q.actual_latitude,
                    'actual_longitude': q.actual_longitude,
                    'distance_km': q.distance_km,
                    'location_points': q.location_points if state.setup.location_mode else None,
                    'guess_date': guess_date_str,
                    'actual_date': actual_date_str,
                    'date_diff_days': q.date_diff_days,
                    'date_points': q.date_points if state.setup.date_mode else None,
                    'round_score': q.location_points + q.date_points,
                    'is_correct_location': None,
                    'is_correct_date_order': None,
                    'time_taken_seconds': q.time_taken_seconds,
                    'submitted_at': q.submitted_at or datetime.now(timezone.utc).isoformat(),
                }
            )
    return guesses


class GameService:
    def __init__(
        self,
        session_store: SessionStore,
        metadata_store: MetadataStore,
        immich_client: ImmichClient,
        leaderboard_store: LeaderboardStore,
        settings: AppSettings,
        registry: GameModeRegistry | None = None,
    ) -> None:
        self.store = session_store
        self.metadata_store = metadata_store
        self.immich = immich_client
        self.leaderboard_store = leaderboard_store
        self.settings = settings
        self.registry = registry or default_game_mode_registry

    async def resolve_album_names(
        self,
        libraries: list[str] | tuple[str, ...] | None,
        album_ids: list[str] | None = None,
    ) -> list[str]:
        """Resolve album IDs to human-readable names server-side from indexed metadata."""
        if not album_ids:
            return []

        albums = self.metadata_store.get_albums(libraries, include_shared=True)
        album_map = {
            str(album.get('id', '')).strip(): str(album.get('name', '-')).strip()
            for album in albums
            if isinstance(album, dict) and album.get('id')
        }
        names: list[str] = []
        for aid in album_ids:
            if aid not in album_map:
                raise HTTPException(status_code=400, detail=f'Unknown album_id: {aid}')
            names.append(album_map[aid])

        names.sort(key=lambda s: (s.lower(), s))
        return names

    def resolve_person_names(
        self,
        person_ids: list[str] | None = None,
        existing_names: list[str] | None = None,
    ) -> list[str]:
        """Resolve person IDs to names server-side from indexed metadata."""
        if not person_ids:
            return existing_names or []
        name_map = self.metadata_store.get_person_names(person_ids)
        if name_map:
            names = [name_map.get(pid, pid) for pid in person_ids if pid in name_map or pid]
            names.sort(key=lambda s: (s.lower(), s))
            return names
        return existing_names or person_ids

    async def preflight(self, setup: PreflightRequest) -> PreflightResponse:
        criteria = AssetFilterCriteria.from_setup(setup, self.settings)
        effective_min_date = criteria.min_date
        effective_max_date = criteria.max_date

        target_libs = setup.libraries or None
        is_synced = self.metadata_store.has_synced_assets(target_libs)
        sync_state = self.metadata_store.get_sync_state(target_libs[0]) if target_libs and len(target_libs) == 1 else {}
        raw_status = sync_state.get('sync_status', SyncStatus.idle.value)
        sync_status = SyncStatus(raw_status) if raw_status in SyncStatus._value2member_map_ else SyncStatus.idle

        counts = self.metadata_store.get_asset_counts(criteria)
        eligible_count = counts['eligible_count']
        total_count = counts['total_count']
        gps_count = counts['gps_count']
        date_count = counts['date_count']
        facet_counts = self.metadata_store.get_facet_counts(criteria)

        active_filters: list[str] = []
        if setup.location_mode:
            active_filters.append('location')
        if setup.date_mode:
            active_filters.append('date')
        if setup.libraries:
            active_filters.append('libraries')
        if setup.album_ids:
            active_filters.append('albums')
        if setup.person_ids:
            active_filters.append(
                'people_all' if setup.people_mode == PeopleMode.ALL and len(setup.person_ids) > 1 else 'people'
            )
        if setup.countries:
            active_filters.append('countries')
        if setup.cities:
            active_filters.append('cities')
        if effective_min_date or effective_max_date:
            active_filters.append('date_range')

        required = 3 * setup.round_count if setup.game_mode == GameMode.album_shuffle else setup.round_count

        return PreflightResponse(
            eligible_count=eligible_count,
            required=required,
            ok=eligible_count >= required,
            active_filters=active_filters,
            min_date=effective_min_date,
            max_date=effective_max_date,
            total_count=total_count,
            gps_count=gps_count,
            date_count=date_count,
            location_mode=setup.location_mode,
            date_mode=setup.date_mode,
            facet_counts=facet_counts,
            is_synced=is_synced,
            sync_status=sync_status,
        )

    async def setup_game(self, setup: GameSetupRequest) -> GameSetupResponse:
        target_libs = setup.libraries or None
        if not self.metadata_store.has_synced_assets(target_libs):
            raise HTTPException(
                status_code=400,
                detail='Selected libraries have not been synced yet. Please sync before starting a match.',
            )

        setup.album_names = await self.resolve_album_names(
            target_libs,
            album_ids=setup.album_ids,
        )
        setup.person_names = self.resolve_person_names(setup.person_ids, setup.person_names)
        state = self.store.create_match(setup)

        map_bounds: MapBounds | None = None
        if setup.location_mode and setup.game_mode == GameMode.pinpoint:
            try:
                load_asset_pool(
                    state,
                    self.metadata_store,
                    settings=self.settings,
                )
                map_bounds = calculate_match_bounds(state.asset_pool)
            except Exception as exc:
                logger.warning('Failed to pre-compute match bounds during setup: %s', exc)

        return GameSetupResponse(
            match_id=state.match_id,
            total_turns=state.total_turns,
            players=list(state.setup.players),
            map_bounds=map_bounds,
        )

    async def get_question(self, payload: QuestionRequest) -> QuestionResponse:
        try:
            state = self.store.get_match(payload.match_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

        if state.finished:
            raise HTTPException(status_code=409, detail='Match is already finished')

        if state.turn_index >= state.total_turns:
            raise HTTPException(status_code=409, detail='No remaining turns')

        engine = self.registry.get(state.setup.game_mode)

        active = self.store.active_question(payload.match_id)
        if active is not None:
            active_failed = False
            if (
                active.asset_id in payload.played_asset_ids
                or active.batch_assets
                and any(ba.asset_id in payload.played_asset_ids for ba in active.batch_assets)
            ):
                active_failed = True

            if active_failed:
                logger.info(
                    'Active question %s asset was reported invalid/failed by client; '
                    'invalidating active question and re-selecting for round %d.',
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
                            if self.metadata_store is not None:
                                self.metadata_store.mark_asset_invalid(ba.asset_id)
                else:
                    state.played_asset_ids.add(active.asset_id)
                    if self.metadata_store is not None:
                        self.metadata_store.mark_asset_invalid(active.asset_id)
                active = None
            else:
                return engine.build_question_response(state, active)

        question_state = await engine.select_question(
            state,
            payload.played_asset_ids,
            self.settings,
            self.store,
            self.immich,
            metadata_store=self.metadata_store,
        )
        return engine.build_question_response(state, question_state)

    async def submit_answer(self, payload: AnswerRequest) -> AnswerResponse:
        try:
            state = self.store.get_match(payload.match_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

        question_state = state.questions.get(payload.question_id)
        if question_state is None:
            raise HTTPException(status_code=404, detail='Unknown question_id')
        if question_state.answered:
            raise HTTPException(status_code=409, detail='Question already answered')

        engine = self.registry.get(state.setup.game_mode)
        updated_state = engine.evaluate_and_apply_answer(state, question_state, payload, self.settings, self.store)

        if updated_state.finished:
            duration_sec = max(0.0, time.time() - updated_state.created_at)
            player_times = {
                player: sum(
                    q.time_taken_seconds or 0.0
                    for q in updated_state.questions.values()
                    if q.player_name == player and q.answered
                )
                for player in updated_state.setup.players
            }
            round_guesses = extract_round_guesses(updated_state)

            self.leaderboard_store.append_match(
                match_id=updated_state.match_id,
                config=updated_state.setup,
                player_scores=updated_state.scores,
                play_mode=PlayMode.local,
                duration_seconds=duration_sec,
                player_times=player_times,
                round_guesses=round_guesses,
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

    async def get_round_result(self, payload: RoundResultRequest) -> RoundResultResponse:
        """Reveal a round only once every player in it has locked in an answer."""
        try:
            state = self.store.get_match(payload.match_id)
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
        )

    async def get_match_summary(
        self,
        match_id: str,
        language: str | None = None,
    ) -> MatchSummaryResponse:
        try:
            state = self.store.get_match(match_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

        max_score = max_possible_score(
            state.setup.round_count,
            state.setup.location_mode,
            state.setup.date_mode,
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

        lang = SupportedLanguage.from_str(language) if language else self.settings.language
        is_custom, filter_summary = state.setup.format_filter_summary(language=lang)
        filter_tooltip = state.setup.format_filter_tooltip(language=lang)

        return MatchSummaryResponse(
            match_id=state.match_id,
            rounds_played=state.setup.round_count,
            location_mode=state.setup.location_mode,
            date_mode=state.setup.date_mode,
            game_mode=state.setup.game_mode,
            libraries=state.setup.libraries,
            album_names=state.setup.album_names,
            finished=state.finished,
            winners=winners,
            players=players,
            filter_summary=filter_summary,
            filter_tooltip=filter_tooltip,
            is_custom_filtered=bool(is_custom),
        )

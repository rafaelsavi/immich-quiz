from __future__ import annotations

import logging

from fastapi import HTTPException

from src.config import AppSettings
from src.game.modes import GameModeRegistry, default_game_mode_registry
from src.game.selector import calculate_match_bounds, load_asset_pool
from src.immich.client import AssetAnswer, ImmichClient, ImmichClientError, SearchQuery
from src.models import (
    AnswerRequest,
    AnswerResponse,
    GameMode,
    GameSetupRequest,
    GameSetupResponse,
    MapBounds,
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
from src.storage.metadata import AssetFilterCriteria, MetadataStore
from src.storage.session import SessionStore

logger = logging.getLogger(__name__)


class GameService:
    def __init__(self, registry: GameModeRegistry | None = None) -> None:
        self.registry = registry or default_game_mode_registry

    async def resolve_album_name(
        self,
        immich: ImmichClient,
        library_name: str,
        album_ids: list[str] | None = None,
    ) -> str:
        """Resolve the album label server-side so clients cannot spoof leaderboard metadata."""
        if not album_ids:
            return '-'

        try:
            albums = await immich.list_albums(library_name, include_shared_albums=True)
        except ImmichClientError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        album_map = {
            str(album.get('id', '')).strip(): str(album.get('name', '-')).strip()
            for album in albums
            if isinstance(album, dict) and album.get('id')
        }
        names: list[str] = []
        for aid in album_ids:
            if aid not in album_map:
                raise HTTPException(status_code=400, detail=f'Unknown album_id for library {library_name}')
            names.append(album_map[aid])

        names.sort(key=lambda s: (s.lower(), s))
        return ', '.join(names) if names else '-'

    async def preflight(
        self,
        setup: PreflightRequest,
        settings: AppSettings,
        immich: ImmichClient,
        metadata_store: MetadataStore | None = None,
    ) -> PreflightResponse:
        # Determine effective date bounds (intersection of env bounds and GUI setup bounds)
        effective_min_date = max(filter(None, [settings.fetch_photos_date_lower_bound, setup.min_date]), default=None)
        effective_max_date = min(filter(None, [settings.fetch_photos_date_upper_bound, setup.max_date]), default=None)

        # 1. Fast indexed SQLite query if metadata store is populated for this library
        if metadata_store is not None and metadata_store.has_synced_assets(setup.library_name):
            criteria = AssetFilterCriteria(
                library_name=setup.library_name,
                location_mode=setup.location_mode,
                date_mode=setup.date_mode,
                min_date=effective_min_date,
                max_date=effective_max_date,
                countries=tuple(setup.countries),
                cities=tuple(setup.cities),
                person_ids=tuple(setup.person_ids),
                people_mode=setup.people_mode,
                album_ids=tuple(setup.album_ids),
                include_shared_albums=settings.include_shared_albums,
                include_partner_assets=settings.include_partner_assets,
            )
            eligible_count = metadata_store.count_eligible_assets(criteria)
        else:
            # Fallback to paginated HTTP sampling
            query = SearchQuery(
                album_ids=tuple(setup.album_ids),
                person_ids=tuple(setup.person_ids),
                people_mode=setup.people_mode,
                countries=tuple(setup.countries),
                cities=tuple(setup.cities),
                include_shared_albums=settings.include_shared_albums,
                include_partner_assets=settings.include_partner_assets,
                min_date=effective_min_date,
                max_date=effective_max_date,
            )

            # Sample candidate assets to verify availability for selected game mode and filters.
            target_eligible_count = 250
            max_sample_pages = 10
            seen_asset_ids: set[str] = set()
            eligible_answers: list[AssetAnswer] = []

            try:
                for page_num in range(1, max_sample_pages + 1):
                    raw_assets = await immich.search_assets(
                        setup.library_name,
                        query=query,
                        size=100,
                        page=page_num,
                    )
                    if not raw_assets:
                        break

                    for asset in raw_assets:
                        aid = str(asset.get('id', '') or asset.get('assetId', '')).strip()
                        if aid and aid not in seen_asset_ids:
                            seen_asset_ids.add(aid)
                            if ImmichClient.is_eligible_asset(
                                asset,
                                setup.location_mode,
                                setup.date_mode,
                                min_date=effective_min_date,
                                max_date=effective_max_date,
                                countries=tuple(setup.countries),
                                cities=tuple(setup.cities),
                            ):
                                eligible_answers.append(ImmichClient.extract_answer(asset))

                    if len(eligible_answers) >= target_eligible_count or len(raw_assets) == 0:
                        break
            except ImmichClientError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc

            eligible_count = len(eligible_answers)

        active_filters: list[str] = []
        if setup.location_mode:
            active_filters.append('location')
        if setup.date_mode:
            active_filters.append('date')
        if setup.album_ids:
            active_filters.append('albums')
        if setup.person_ids:
            active_filters.append(
                'people_all' if setup.people_mode == 'AND' and len(setup.person_ids) > 1 else 'people'
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
        )

    async def setup_game(
        self,
        setup: GameSetupRequest,
        settings: AppSettings,
        store: SessionStore,
        immich: ImmichClient,
        metadata_store: MetadataStore | None = None,
    ) -> GameSetupResponse:
        setup.album_name = await self.resolve_album_name(
            immich,
            setup.library_name,
            album_ids=setup.album_ids,
        )
        state = store.create_match(setup)

        map_bounds: MapBounds | None = None
        if setup.location_mode and setup.smart_map_zoom and setup.game_mode == GameMode.pinpoint:
            try:
                await load_asset_pool(
                    state,
                    immich,
                    min_capture_date=settings.fetch_photos_date_lower_bound,
                    max_capture_date=settings.fetch_photos_date_upper_bound,
                    include_shared_albums=settings.include_shared_albums,
                    include_partner_assets=settings.include_partner_assets,
                    metadata_store=metadata_store,
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

    async def get_question(
        self,
        payload: QuestionRequest,
        settings: AppSettings,
        store: SessionStore,
        immich: ImmichClient,
        metadata_store: MetadataStore | None = None,
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
                            if metadata_store is not None:
                                metadata_store.mark_asset_invalid(ba.asset_id)
                else:
                    state.played_asset_ids.add(active.asset_id)
                    if metadata_store is not None:
                        metadata_store.mark_asset_invalid(active.asset_id)
                active = None
            else:
                return engine.build_question_response(state, active)

        question_state = await engine.select_question(
            state,
            payload.played_asset_ids,
            settings,
            store,
            immich,
            metadata_store=metadata_store,
        )
        return engine.build_question_response(state, question_state)

    async def submit_answer(
        self,
        payload: AnswerRequest,
        settings: AppSettings,
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
        settings: AppSettings,
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
        settings: AppSettings,
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

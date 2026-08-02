from __future__ import annotations

import random
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response

from src.immich.client import ImmichClient, ImmichClientError
from src.models import (
    AlbumShuffleAnswerItem,
    AnswerRequest,
    AnswerResponse,
    BatchPhotoItem,
    BatchPinItem,
    BatchRevealItem,
    GameMode,
    GameSetupRequest,
    GameSetupResponse,
    MatchSummaryPlayer,
    MatchSummaryResponse,
    PlayerRoundResult,
    PreflightRequest,
    PreflightResponse,
    QuestionRequest,
    QuestionResponse,
    RoundResultRequest,
    RoundResultResponse,
)
from src.scoring import (
    accuracy_pct,
    batch_strict_location_score,
    date_diff_days,
    date_diff_months,
    date_score,
    haversine_km,
    kendall_tau_inversion_score,
    location_score,
    max_possible_score,
)
from src.storage.leaderboard import LeaderboardStore
from src.storage.session import (
    MatchState,
    QuestionAlreadyAnsweredError,
    QuestionState,
    RoundAsset,
    SessionStore,
)


router = APIRouter(prefix='/api')


def get_session_store(request: Request) -> SessionStore:
    return request.app.state.session_store


def get_immich_client(request: Request) -> ImmichClient:
    return request.app.state.immich_client


def get_leaderboard_store(request: Request) -> LeaderboardStore:
    return request.app.state.leaderboard_store


@router.get('/health')
async def health() -> dict[str, str]:
    return {'status': 'ok'}


@router.get('/ui-config')
async def ui_config(request: Request) -> dict[str, object]:
    settings = request.app.state.settings
    return {
        'quiz_image_max_height_px': int(settings.quiz_image_max_height_px),
        'language': settings.language,
        'score_max_points': settings.score_max_points,
    }


@router.get('/libraries')
async def libraries(request: Request, immich: ImmichClient = Depends(get_immich_client)) -> dict[str, object]:
    names = immich.list_libraries()
    available = getattr(request.app.state, 'available_libraries', None)
    unavailable = getattr(request.app.state, 'unavailable_libraries', {})
    return {
        'libraries': names if available is None else available,
        'unavailable': unavailable,
    }


@router.get('/albums')
async def albums(
    library_name: str,
    request: Request,
    include_shared_albums: bool | None = Query(default=None),
    immich: ImmichClient = Depends(get_immich_client),
) -> dict[str, list[dict[str, str]]]:
    try:
        configured_default = bool(getattr(request.app.state.settings, 'include_shared_albums', False))
        effective_include_shared = configured_default if include_shared_albums is None else include_shared_albums
        result = await immich.list_albums(library_name, include_shared_albums=effective_include_shared)
        return {'albums': result}
    except ImmichClientError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get('/leaderboard')
async def leaderboard(
    store: LeaderboardStore = Depends(get_leaderboard_store),
    rounds: int | None = Query(default=None),
    round_length: str | None = Query(default=None),
    location_mode: bool | None = Query(default=None),
    date_mode: bool | None = Query(default=None),
    game_mode: str | None = Query(default=None),
    library: str | None = Query(default=None),
    album: str | None = Query(default=None),
) -> list[dict[str, object]]:
    entries = store.list_entries(
        rounds=rounds,
        round_length=round_length,
        location_mode=location_mode,
        date_mode=date_mode,
        game_mode=game_mode,
        library=library,
        album=album,
    )
    return [entry.model_dump(mode='json') for entry in entries]


@router.post('/game/preflight', response_model=PreflightResponse)
async def game_preflight(
    setup: PreflightRequest,
    request: Request,
    immich: ImmichClient = Depends(get_immich_client),
) -> PreflightResponse:
    settings = request.app.state.settings
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

    required = 5 * setup.round_count if getattr(setup, "game_mode", GameMode.pinpoint) == GameMode.album_shuffle else setup.round_count
    return PreflightResponse(
        eligible_count=eligible_count,
        required=required,
        ok=eligible_count >= required,
        active_filters=active_filters,
        min_date=settings.fetch_photos_date_lower_bound,
        max_date=settings.fetch_photos_date_upper_bound,
    )


@router.post('/game/setup', response_model=GameSetupResponse)
async def game_setup(
    setup: GameSetupRequest,
    store: SessionStore = Depends(get_session_store),
    immich: ImmichClient = Depends(get_immich_client),
) -> GameSetupResponse:
    setup.album_name = await _resolve_album_name(immich, setup.library_name, setup.album_id)
    state = store.create_match(setup)
    return GameSetupResponse(
        match_id=state.match_id,
        total_turns=state.total_turns,
        players=list(state.setup.players),
    )


async def _resolve_album_name(immich: ImmichClient, library_name: str, album_id: str | None) -> str:
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


def _build_question_response(state: MatchState, question: QuestionState) -> QuestionResponse:
    players = state.setup.players
    player_index = players.index(question.player_name) if question.player_name in players else 0
    batch_photos = None
    batch_pins = None
    if state.setup.game_mode == GameMode.album_shuffle and question.batch_assets and question.batch_pins:
        batch_photos = [
            BatchPhotoItem(
                photo_id=ba.asset_id,
                media_url=f'/api/media/{ba.asset_id}?library_name={state.setup.library_name}',
            )
            for ba in question.batch_assets
        ]
        batch_pins = [
            BatchPinItem(
                pin_id=str(bp['pin_id']),
                latitude=float(bp['latitude']),
                longitude=float(bp['longitude']),
            )
            for bp in question.batch_pins
        ]

    return QuestionResponse(
        question_id=question.question_id,
        asset_id=question.asset_id,
        media_url=f'/api/media/{question.asset_id}?library_name={state.setup.library_name}',
        library_name=state.setup.library_name,
        album_name=state.setup.album_name,
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


async def _load_asset_pool(
    state: MatchState,
    immich: ImmichClient,
    min_capture_date: date | None,
    max_capture_date: date | None,
) -> None:
    """Populate the per-match candidate pool once instead of searching every round."""
    raw_assets = await immich.search_random_assets(state.setup.library_name, state.setup.album_id)
    pool = {}
    for asset in raw_assets:
        if not ImmichClient.is_eligible_asset(
            asset,
            state.setup.location_mode,
            state.setup.date_mode,
            min_capture_date,
            max_capture_date,
        ):
            continue
        asset_id = str(asset.get('id', '')).strip()
        if asset_id:
            pool[asset_id] = ImmichClient.extract_answer(asset)
    state.asset_pool = pool


async def _select_round_asset(
    state: MatchState,
    immich: ImmichClient,
    client_excluded: set[str],
    min_capture_date: date | None,
    max_capture_date: date | None,
) -> RoundAsset | None:
    """Draw an unplayed asset, refreshing the pool once if it is exhausted."""
    excluded = state.played_asset_ids | client_excluded

    if not state.asset_pool:
        await _load_asset_pool(state, immich, min_capture_date, max_capture_date)
    candidates = [asset_id for asset_id in state.asset_pool if asset_id not in excluded]

    if not candidates:
        await _load_asset_pool(state, immich, min_capture_date, max_capture_date)
        candidates = [asset_id for asset_id in state.asset_pool if asset_id not in excluded]

    if not candidates:
        return None

    asset_id = random.choice(candidates)
    return RoundAsset(asset_id=asset_id, answer=state.asset_pool[asset_id])


async def _select_batch_round_assets(
    state: MatchState,
    immich: ImmichClient,
    count: int,
    client_excluded: set[str],
    min_capture_date: date | None,
    max_capture_date: date | None,
) -> tuple[list[RoundAsset], list[dict[str, object]]] | None:
    excluded = state.played_asset_ids | client_excluded

    if not state.asset_pool:
        await _load_asset_pool(state, immich, min_capture_date, max_capture_date)
    candidates = [asset_id for asset_id in state.asset_pool if asset_id not in excluded]

    if len(candidates) < count:
        await _load_asset_pool(state, immich, min_capture_date, max_capture_date)
        candidates = [asset_id for asset_id in state.asset_pool if asset_id not in excluded]

    if not candidates:
        return None

    if len(candidates) < count:
        selected_ids = candidates
    else:
        selected_ids = random.sample(candidates, count)

    assets = [RoundAsset(asset_id=aid, answer=state.asset_pool[aid]) for aid in selected_ids]

    letters = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
    raw_pins = []
    for ra in assets:
        lat = ra.answer.latitude or 0.0
        lon = ra.answer.longitude or 0.0
        raw_pins.append({'true_asset_id': ra.asset_id, 'latitude': lat, 'longitude': lon})

    random.shuffle(raw_pins)
    pins_data = []
    for idx, p in enumerate(raw_pins):
        letter = letters[idx % len(letters)]
        if idx >= len(letters):
            letter = f'{letter}{idx // len(letters)}'
        pins_data.append({
            'pin_id': letter,
            'true_asset_id': p['true_asset_id'],
            'latitude': p['latitude'],
            'longitude': p['longitude'],
        })

    return assets, pins_data


@router.post('/question', response_model=QuestionResponse)
async def question(
    payload: QuestionRequest,
    request: Request,
    store: SessionStore = Depends(get_session_store),
    immich: ImmichClient = Depends(get_immich_client),
) -> QuestionResponse:
    try:
        state = store.get_match(payload.match_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    if state.finished:
        raise HTTPException(status_code=409, detail='Match is already finished')

    if state.turn_index >= state.total_turns:
        raise HTTPException(status_code=409, detail='No remaining turns')

    active = store.active_question(payload.match_id)
    if active is not None:
        return _build_question_response(state, active)

    round_index = state.current_round_index

    if state.setup.game_mode == GameMode.album_shuffle:
        batch_selection = state.batch_round_assets.get(round_index)
        batch_pins = state.batch_round_pins.get(round_index)

        if batch_selection is None or batch_pins is None:
            try:
                settings = request.app.state.settings
                res = await _select_batch_round_assets(
                    state,
                    immich,
                    5,
                    set(payload.played_asset_ids),
                    settings.fetch_photos_date_lower_bound,
                    settings.fetch_photos_date_upper_bound,
                )
            except ImmichClientError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc

            if res is None:
                raise HTTPException(status_code=404, detail='No eligible assets available')
            batch_selection, batch_pins = res
            state.batch_round_assets[round_index] = batch_selection
            state.batch_round_pins[round_index] = batch_pins

        question_state = store.register_question(
            payload.match_id,
            asset_id=batch_selection[0].asset_id,
            actual_latitude=batch_selection[0].answer.latitude,
            actual_longitude=batch_selection[0].answer.longitude,
            actual_date=batch_selection[0].answer.capture_date,
            actual_city=batch_selection[0].answer.city,
            actual_country=batch_selection[0].answer.country,
            batch_assets=batch_selection,
            batch_pins=batch_pins,
        )
        return _build_question_response(state, question_state)

    selection = state.round_assets.get(round_index)
    if selection is None:
        try:
            settings = request.app.state.settings
            selection = await _select_round_asset(
                state,
                immich,
                set(payload.played_asset_ids),
                settings.fetch_photos_date_lower_bound,
                settings.fetch_photos_date_upper_bound,
            )
        except ImmichClientError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        if selection is None:
            raise HTTPException(status_code=404, detail='No eligible assets available')
        state.round_assets[round_index] = selection

    question_state = store.register_question(
        payload.match_id,
        asset_id=selection.asset_id,
        actual_latitude=selection.answer.latitude,
        actual_longitude=selection.answer.longitude,
        actual_date=selection.answer.capture_date,
        actual_city=selection.answer.city,
        actual_country=selection.answer.country,
    )

    return _build_question_response(state, question_state)


@router.get('/media/{asset_id}')
async def media(
    asset_id: str,
    library_name: str | None = Query(default=None),
    library: str | None = Query(default=None),
    store: SessionStore = Depends(get_session_store),
    immich: ImmichClient = Depends(get_immich_client),
) -> Response:
    selected_library = library_name or library
    if not selected_library:
        raise HTTPException(status_code=400, detail='library_name or library query parameter is required')

    if not store.is_asset_registered(asset_id):
        raise HTTPException(status_code=404, detail='Unknown asset for any active match')

    try:
        content, content_type = await immich.get_asset_bytes(selected_library, asset_id)
    except ImmichClientError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return Response(content=content, media_type=content_type)


@router.post('/answer', response_model=AnswerResponse)
async def answer(
    payload: AnswerRequest,
    request: Request,
    store: SessionStore = Depends(get_session_store),
    leaderboard_store: LeaderboardStore = Depends(get_leaderboard_store),
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

    location_points = 0
    date_points = 0
    distance: float | None = None
    delta_days: int | None = None
    delta_months: int | None = None
    settings = request.app.state.settings

    if state.setup.game_mode == GameMode.album_shuffle:
        answers = payload.album_shuffle_answers or []
        batch_assets = question_state.batch_assets or []
        batch_pins = question_state.batch_pins or []

        true_pin_map = {str(bp['true_asset_id']): str(bp['pin_id']) for bp in batch_pins}

        correct_pins = 0
        album_shuffle_guesses = []
        for ans in answers:
            album_shuffle_guesses.append({
                'photo_id': ans.photo_id,
                'assigned_pin_id': ans.assigned_pin_id,
                'assigned_timeline_index': ans.assigned_timeline_index,
            })
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
            sorted_by_date = sorted(batch_assets, key=lambda a: a.answer.capture_date or date.min, reverse=True)
            true_rank_map = {a.asset_id: idx for idx, a in enumerate(sorted_by_date)}

            sorted_answers = sorted(
                answers,
                key=lambda ans: ans.assigned_timeline_index if ans.assigned_timeline_index is not None else 999,
            )
            guessed_ranks = [true_rank_map[ans.photo_id] for ans in sorted_answers if ans.photo_id in true_rank_map]

            date_points = kendall_tau_inversion_score(guessed_ranks, max_points=settings.score_max_points)
        else:
            date_points = 0

        round_index = question_state.round_index
        try:
            state = store.apply_score(
                payload.match_id,
                payload.question_id,
                location_points,
                date_points,
                timed_out=payload.timed_out,
                album_shuffle_guesses=album_shuffle_guesses,
            )
        except QuestionAlreadyAnsweredError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

        if state.finished:
            leaderboard_store.append_match(
                match_id=state.match_id,
                library_name=state.setup.library_name,
                album_name=state.setup.album_name or '-',
                rounds_played=state.setup.round_count,
                round_length=state.setup.round_length.value,
                location_mode=state.setup.location_mode,
                date_mode=state.setup.date_mode,
                game_mode=state.setup.game_mode.value,
                player_scores=state.scores,
            )

        return AnswerResponse(
            player_name=question_state.player_name,
            question_id=question_state.question_id,
            round_number=round_index + 1,
            turn_completed=state.turn_index,
            total_turns=state.total_turns,
            round_complete=state.is_round_complete(round_index),
            waiting_for=state.players_pending_in_round(round_index),
            match_finished=state.finished,
        )


    round_index = question_state.round_index

    try:
        state = store.apply_score(
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
        )
    except QuestionAlreadyAnsweredError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    if state.finished:
        leaderboard_store.append_match(
            match_id=state.match_id,
            library_name=state.setup.library_name,
            album_name=state.setup.album_name or '-',
            rounds_played=state.setup.round_count,
            round_length=state.setup.round_length.value,
            location_mode=state.setup.location_mode,
            date_mode=state.setup.date_mode,
            game_mode=state.setup.game_mode.value,
            player_scores=state.scores,
        )

    return AnswerResponse(
        player_name=question_state.player_name,
        question_id=question_state.question_id,
        round_number=round_index + 1,
        turn_completed=state.turn_index,
        total_turns=state.total_turns,
        round_complete=state.is_round_complete(round_index),
        waiting_for=state.players_pending_in_round(round_index),
        match_finished=state.finished,
    )


def _split_month_delta(delta_months: int | None) -> tuple[int | None, int | None]:
    if delta_months is None:
        return None, None
    return divmod(delta_months, 12)


@router.post('/round/result', response_model=RoundResultResponse)
async def round_result(
    payload: RoundResultRequest,
    request: Request,
    store: SessionStore = Depends(get_session_store),
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

    batch_reveal = None
    if state.setup.game_mode == GameMode.album_shuffle and reference.batch_assets and reference.batch_pins:
        true_pin_map = {bp['true_asset_id']: bp['pin_id'] for bp in reference.batch_pins}
        batch_reveal = [
            BatchRevealItem(
                photo_id=ba.asset_id,
                true_pin_id=str(true_pin_map.get(ba.asset_id, '')),
                actual_latitude=ba.answer.latitude,
                actual_longitude=ba.answer.longitude,
                actual_date=ba.answer.capture_date,
                actual_year=ba.answer.capture_date.year if ba.answer.capture_date else None,
                actual_month=ba.answer.capture_date.month if ba.answer.capture_date else None,
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
        years_part, months_part = _split_month_delta(question.date_diff_months)
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
        score_max_points=request.app.state.settings.score_max_points,
    )


@router.get('/match/{match_id}/summary', response_model=MatchSummaryResponse)
async def match_summary(
    match_id: str,
    request: Request,
    store: SessionStore = Depends(get_session_store),
) -> MatchSummaryResponse:
    try:
        state = store.get_match(match_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    max_score = max_possible_score(
        state.setup.round_count,
        state.setup.location_mode,
        state.setup.date_mode,
        per_goal_max_points=request.app.state.settings.score_max_points,
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


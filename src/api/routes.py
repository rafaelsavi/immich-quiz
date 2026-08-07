from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response

from src.game.service import GameService
from src.immich.client import ImmichClient, ImmichClientError
from src.models import (
    AnswerRequest,
    AnswerResponse,
    GameSetupRequest,
    GameSetupResponse,
    MatchSummaryResponse,
    PreflightRequest,
    PreflightResponse,
    QuestionRequest,
    QuestionResponse,
    RoundResultRequest,
    RoundResultResponse,
)
from src.storage.leaderboard import LeaderboardStore
from src.storage.session import SessionStore

router = APIRouter(prefix='/api')


def get_session_store(request: Request) -> SessionStore:
    return request.app.state.session_store


def get_immich_client(request: Request) -> ImmichClient:
    return request.app.state.immich_client


def get_leaderboard_store(request: Request) -> LeaderboardStore:
    return request.app.state.leaderboard_store


def get_game_service(request: Request) -> GameService:
    if not hasattr(request.app.state, 'game_service'):
        request.app.state.game_service = GameService()
    return request.app.state.game_service


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
    game_service: GameService = Depends(get_game_service),
) -> PreflightResponse:
    return await game_service.preflight(setup, request.app.state.settings, immich)


@router.post('/game/setup', response_model=GameSetupResponse)
async def game_setup(
    setup: GameSetupRequest,
    store: SessionStore = Depends(get_session_store),
    immich: ImmichClient = Depends(get_immich_client),
    game_service: GameService = Depends(get_game_service),
) -> GameSetupResponse:
    return await game_service.setup_game(setup, store, immich)


@router.post('/question', response_model=QuestionResponse)
async def question(
    payload: QuestionRequest,
    request: Request,
    store: SessionStore = Depends(get_session_store),
    immich: ImmichClient = Depends(get_immich_client),
    game_service: GameService = Depends(get_game_service),
) -> QuestionResponse:
    return await game_service.get_question(payload, request.app.state.settings, store, immich)


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
    game_service: GameService = Depends(get_game_service),
) -> AnswerResponse:
    return await game_service.submit_answer(payload, request.app.state.settings, store, leaderboard_store)


@router.post('/round/result', response_model=RoundResultResponse)
async def round_result(
    payload: RoundResultRequest,
    request: Request,
    store: SessionStore = Depends(get_session_store),
    game_service: GameService = Depends(get_game_service),
) -> RoundResultResponse:
    return await game_service.get_round_result(payload, request.app.state.settings, store)


@router.get('/match/{match_id}/summary', response_model=MatchSummaryResponse)
async def match_summary(
    match_id: str,
    request: Request,
    store: SessionStore = Depends(get_session_store),
    game_service: GameService = Depends(get_game_service),
) -> MatchSummaryResponse:
    return await game_service.get_match_summary(match_id, request.app.state.settings, store)

from typing import Any

from cachetools import TTLCache
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response

from src.config import AppSettings
from src.game.service import GameService
from src.immich.client import ImmichClient, ImmichClientError
from src.models import (
    AnswerRequest,
    AnswerResponse,
    GameMode,
    GameSetupRequest,
    GameSetupResponse,
    LeaderboardEntry,
    LibraryFiltersResponse,
    MatchSummaryResponse,
    PreflightRequest,
    PreflightResponse,
    QuestionRequest,
    QuestionResponse,
    RoundLength,
    RoundResultRequest,
    RoundResultResponse,
    SyncStateResponse,
)
from src.scoring import SCORE_MAX_POINTS
from src.storage.leaderboard import LeaderboardStore
from src.storage.metadata import MetadataStore
from src.storage.session import SessionStore
from src.storage.sync import SyncEngine
from src.version import APP_VERSION

# 5-minute TTL for filter metadata cache. Change this constant to tune cache lifetime.
FILTERS_CACHE_TTL_SECONDS: int = 300

# Module-level cache shared across all requests: library_name -> LibraryFiltersResponse
_filters_cache: TTLCache = TTLCache(maxsize=64, ttl=FILTERS_CACHE_TTL_SECONDS)


def invalidate_filters_cache(library_name: str | None = None) -> None:
    """Invalidate cached library filter responses (e.g. after sync completion)."""
    if library_name is not None:
        _filters_cache.pop(library_name, None)
    else:
        _filters_cache.clear()


router = APIRouter(prefix='/api')


def get_session_store(request: Request) -> SessionStore:
    return request.app.state.session_store


def get_immich_client(request: Request) -> ImmichClient:
    return request.app.state.immich_client


def get_leaderboard_store(request: Request) -> LeaderboardStore:
    return request.app.state.leaderboard_store


def get_metadata_store(request: Request) -> MetadataStore:
    return request.app.state.metadata_store


def get_sync_engine(request: Request) -> SyncEngine:
    return request.app.state.sync_engine


def get_game_service(request: Request) -> GameService:
    return GameService(
        session_store=request.app.state.session_store,
        metadata_store=request.app.state.metadata_store,
        immich_client=request.app.state.immich_client,
        leaderboard_store=request.app.state.leaderboard_store,
        settings=request.app.state.settings,
    )


@router.get('/health')
async def health() -> dict[str, str]:
    return {'status': 'ok', 'version': APP_VERSION}


@router.get('/ui-config')
async def ui_config(request: Request) -> dict[str, object]:
    settings = request.app.state.settings
    return {
        'language': settings.language,
        'score_max_points': SCORE_MAX_POINTS,
        'version': APP_VERSION,
    }


@router.get('/libraries')
async def libraries(request: Request, immich: ImmichClient = Depends(get_immich_client)) -> dict[str, object]:
    names = immich.list_libraries()
    available = request.app.state.available_libraries
    unavailable = request.app.state.unavailable_libraries
    return {
        'libraries': names if available is None else available,
        'unavailable': unavailable,
    }


@router.get('/albums')
async def albums(
    library_name: str,
    metadata_store: MetadataStore = Depends(get_metadata_store),
) -> dict[str, list[dict[str, str]]]:
    return {'albums': metadata_store.get_albums(library_name, include_shared=True)}


@router.get('/filters', response_model=LibraryFiltersResponse)
async def library_filters(
    library_name: str,
    request: Request,
    metadata_store: MetadataStore = Depends(get_metadata_store),
) -> LibraryFiltersResponse:
    settings: AppSettings = request.app.state.settings

    # Check TTL cache first (evicts automatically after FILTERS_CACHE_TTL_SECONDS)
    cached = _filters_cache.get(library_name)
    if cached is not None:
        return cached

    response = metadata_store.get_filter_options(library_name, settings)
    _filters_cache[library_name] = response
    return response


@router.get('/sync/status', response_model=SyncStateResponse)
async def sync_status(
    library_name: str,
    sync_engine: SyncEngine = Depends(get_sync_engine),
) -> dict[str, Any]:
    return sync_engine.get_sync_status(library_name)


@router.post('/sync', response_model=SyncStateResponse)
async def trigger_sync(
    library_name: str,
    force_full: bool = Query(default=False),
    sync_engine: SyncEngine = Depends(get_sync_engine),
) -> dict[str, Any]:
    invalidate_filters_cache(library_name)
    sync_engine.trigger_sync(library_name, force_full=force_full)
    return sync_engine.get_sync_status(library_name)


@router.get('/leaderboard', response_model=list[LeaderboardEntry])
async def leaderboard(
    store: LeaderboardStore = Depends(get_leaderboard_store),
    rounds: int | None = Query(default=None),
    round_length: RoundLength | None = Query(default=None),
    location_mode: bool | None = Query(default=None),
    date_mode: bool | None = Query(default=None),
    game_mode: GameMode | None = Query(default=None),
    library: str | None = Query(default=None),
    albums: str | None = Query(default=None),
    player_name: str | None = Query(default=None),
    is_custom_filtered: bool | None = Query(default=None),
    limit: int | None = Query(default=None),
) -> list[LeaderboardEntry]:
    return store.list_entries(
        rounds=rounds,
        round_length=round_length,
        location_mode=location_mode,
        date_mode=date_mode,
        game_mode=game_mode,
        library=library,
        albums=albums,
        player_name=player_name,
        is_custom_filtered=is_custom_filtered,
        limit=limit,
    )


@router.post('/game/preflight', response_model=PreflightResponse)
async def game_preflight(
    setup: PreflightRequest,
    game_service: GameService = Depends(get_game_service),
) -> PreflightResponse:
    return await game_service.preflight(setup)


@router.post('/game/setup', response_model=GameSetupResponse)
async def game_setup(
    setup: GameSetupRequest,
    game_service: GameService = Depends(get_game_service),
) -> GameSetupResponse:
    return await game_service.setup_game(setup)


@router.post('/question', response_model=QuestionResponse)
async def question(
    payload: QuestionRequest,
    game_service: GameService = Depends(get_game_service),
) -> QuestionResponse:
    return await game_service.get_question(payload)


@router.get('/media/{asset_id}')
async def media(
    asset_id: str,
    library_name: str,
    store: SessionStore = Depends(get_session_store),
    immich: ImmichClient = Depends(get_immich_client),
    metadata_store: MetadataStore = Depends(get_metadata_store),
) -> Response:
    if not store.is_asset_registered(asset_id):
        raise HTTPException(status_code=404, detail='Unknown asset for any active match')

    try:
        content, content_type = await immich.get_asset_bytes(library_name, asset_id)
    except ImmichClientError as exc:
        metadata_store.mark_asset_invalid(asset_id)
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return Response(content=content, media_type=content_type)


@router.post('/answer', response_model=AnswerResponse)
async def answer(
    payload: AnswerRequest,
    game_service: GameService = Depends(get_game_service),
) -> AnswerResponse:
    return await game_service.submit_answer(payload)


@router.post('/round/result', response_model=RoundResultResponse)
async def round_result(
    payload: RoundResultRequest,
    game_service: GameService = Depends(get_game_service),
) -> RoundResultResponse:
    return await game_service.get_round_result(payload)


@router.get('/match/{match_id}/summary', response_model=MatchSummaryResponse)
async def match_summary(
    match_id: str,
    game_service: GameService = Depends(get_game_service),
) -> MatchSummaryResponse:
    return await game_service.get_match_summary(match_id)

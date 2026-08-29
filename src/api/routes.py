import asyncio
from typing import Annotated, Any

from cachetools import TTLCache
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response

from src.config import AppSettings
from src.game.service import GameService
from src.i18n import SupportedLanguage, parse_accept_language
from src.immich.client import ImmichClient, ImmichClientError
from src.models import (
    AnswerRequest,
    AnswerResponse,
    FlagAssetRequest,
    FlagAssetResponse,
    FlaggedAssetItem,
    GameSetupRequest,
    GameSetupResponse,
    LeaderboardEntry,
    LeaderboardQuery,
    LibraryFiltersResponse,
    MatchSummaryResponse,
    PreflightRequest,
    PreflightResponse,
    QuestionRequest,
    QuestionResponse,
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
        _filters_cache.pop((), None)
        to_remove = [k for k in _filters_cache if isinstance(k, tuple) and library_name in k]
        for k in to_remove:
            _filters_cache.pop(k, None)
    else:
        _filters_cache.clear()


router = APIRouter(prefix='/api')


def get_session_store(request: Request) -> SessionStore:
    """FastAPI dependency yielding the in-memory session store."""
    return request.app.state.session_store


def get_immich_client(request: Request) -> ImmichClient:
    """FastAPI dependency yielding the configured Immich HTTP client."""
    return request.app.state.immich_client


def get_leaderboard_store(request: Request) -> LeaderboardStore:
    """FastAPI dependency yielding the SQLite leaderboard store."""
    return request.app.state.leaderboard_store


def get_metadata_store(request: Request) -> MetadataStore:
    """FastAPI dependency yielding the SQLite metadata store."""
    return request.app.state.metadata_store


def get_sync_engine(request: Request) -> SyncEngine:
    """FastAPI dependency yielding the background metadata sync engine."""
    return request.app.state.sync_engine


def get_game_service(request: Request) -> GameService:
    """FastAPI dependency yielding a configured GameService instance."""
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
    immich_web_url = settings.immich_server_url.removesuffix('/api')
    return {
        'language': settings.language,
        'score_max_points': SCORE_MAX_POINTS,
        'version': APP_VERSION,
        'immich_web_url': immich_web_url,
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
    libraries: list[str] | None = Query(default=None),
    metadata_store: MetadataStore = Depends(get_metadata_store),
) -> dict[str, list[dict[str, str]]]:
    res = await asyncio.to_thread(metadata_store.get_albums, libraries, True)
    return {'albums': res}


@router.get('/filters', response_model=LibraryFiltersResponse)
async def library_filters(
    request: Request,
    libraries: list[str] | None = Query(default=None),
    metadata_store: MetadataStore = Depends(get_metadata_store),
) -> LibraryFiltersResponse:
    settings: AppSettings = request.app.state.settings
    cache_key = tuple(sorted(libraries)) if libraries else ()

    # Check TTL cache first (evicts automatically after FILTERS_CACHE_TTL_SECONDS)
    cached = _filters_cache.get(cache_key)
    if cached is not None:
        return cached

    response = await asyncio.to_thread(metadata_store.get_filter_options, libraries, settings)
    _filters_cache[cache_key] = response
    return response


@router.get('/sync/status', response_model=SyncStateResponse)
async def sync_status(
    request: Request,
    sync_engine: SyncEngine = Depends(get_sync_engine),
) -> dict[str, Any]:
    available = request.app.state.available_libraries
    return sync_engine.get_sync_status(available_libraries=available)


@router.post('/sync', response_model=SyncStateResponse)
async def trigger_sync(
    request: Request,
    force_full: bool = Query(default=False),
    sync_engine: SyncEngine = Depends(get_sync_engine),
) -> dict[str, Any]:
    invalidate_filters_cache()
    available = request.app.state.available_libraries
    sync_engine.trigger_sync_all(force_full=force_full, available_libraries=available)
    return sync_engine.get_sync_status(available_libraries=available)


@router.get('/leaderboard', response_model=list[LeaderboardEntry])
async def leaderboard(
    query: Annotated[LeaderboardQuery, Query()],
    store: LeaderboardStore = Depends(get_leaderboard_store),
) -> list[LeaderboardEntry]:
    return store.list_entries(query)


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
    store: SessionStore = Depends(get_session_store),
    immich: ImmichClient = Depends(get_immich_client),
    metadata_store: MetadataStore = Depends(get_metadata_store),
    leaderboard_store: LeaderboardStore = Depends(get_leaderboard_store),
) -> Response:
    if not store.is_asset_registered(asset_id) and not leaderboard_store.is_asset_recorded(asset_id):
        raise HTTPException(status_code=404, detail='Unknown asset for any match')

    target_library = metadata_store.get_asset_library(asset_id)
    if not target_library:
        raise HTTPException(status_code=404, detail='Cannot resolve library for asset')

    try:
        content, content_type = await immich.get_asset_bytes(target_library, asset_id)
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
    request: Request,
    response: Response,
    lang: str | None = None,
    game_service: GameService = Depends(get_game_service),
) -> MatchSummaryResponse:
    if not lang:
        accept_lang = request.headers.get('accept-language')
        if accept_lang:
            lang = parse_accept_language(accept_lang, default=request.app.state.settings.language).value
    res_lang = SupportedLanguage.from_str(lang, default=request.app.state.settings.language)
    lang_code = res_lang.value if hasattr(res_lang, 'value') else str(res_lang)
    response.headers['Content-Language'] = lang_code
    return await game_service.get_match_summary(match_id, language=lang_code)


@router.post('/assets/flag', response_model=FlagAssetResponse)
async def flag_asset(
    payload: FlagAssetRequest,
    request: Request,
    metadata_store: MetadataStore = Depends(get_metadata_store),
) -> FlagAssetResponse:
    res = await asyncio.to_thread(
        metadata_store.flag_asset,
        payload.asset_id,
        flag_coordinates=payload.flag_coordinates,
        flag_date=payload.flag_date,
        other=payload.other,
        reported_by=payload.reported_by,
    )
    immich_web_url = request.app.state.settings.immich_server_url.removesuffix('/api')
    immich_url = f'{immich_web_url}/photos/{payload.asset_id}'
    return FlagAssetResponse(
        success=True,
        asset_id=res['asset_id'],
        flag_coordinates=res['flag_coordinates'],
        flag_date=res['flag_date'],
        other=res['other'],
        reported_by=res['reported_by'],
        reported_at=res['reported_at'],
        immich_url=immich_url,
    )


@router.get('/assets/flagged', response_model=list[FlaggedAssetItem])
async def list_flagged_assets(
    request: Request,
    limit: int = Query(default=100, ge=1, le=1000),
    metadata_store: MetadataStore = Depends(get_metadata_store),
) -> list[FlaggedAssetItem]:
    immich_web_url = request.app.state.settings.immich_server_url.removesuffix('/api')
    records = await asyncio.to_thread(metadata_store.list_flagged_assets, limit)
    return [
        FlaggedAssetItem(
            id=r['id'],
            asset_id=r['asset_id'],
            flag_coordinates=r['flag_coordinates'],
            flag_date=r['flag_date'],
            other=r['other'],
            reported_by=r['reported_by'],
            reported_at=r['reported_at'],
            immich_url=f"{immich_web_url}/photos/{r['asset_id']}",
        )
        for r in records
    ]


@router.delete('/assets/flagged/{asset_id}')
async def unflag_asset(
    asset_id: str,
    metadata_store: MetadataStore = Depends(get_metadata_store),
) -> dict[str, object]:
    removed = await asyncio.to_thread(metadata_store.unflag_asset, asset_id)
    if not removed:
        raise HTTPException(status_code=404, detail='Flagged asset not found')
    return {'success': True, 'asset_id': asset_id}

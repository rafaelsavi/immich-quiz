from cachetools import TTLCache
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response

from src.config import AppSettings
from src.game.service import GameService
from src.immich.client import ImmichClient, ImmichClientError
from src.models import (
    AnswerRequest,
    AnswerResponse,
    CityOption,
    DateRangeOption,
    GameSetupRequest,
    GameSetupResponse,
    LibraryFiltersResponse,
    MatchSummaryResponse,
    PersonOption,
    PreflightRequest,
    PreflightResponse,
    QuestionRequest,
    QuestionResponse,
    RoundResultRequest,
    RoundResultResponse,
)
from src.storage.leaderboard import LeaderboardStore
from src.storage.session import SessionStore
from src.version import APP_VERSION

# 5-minute TTL for filter metadata cache. Change this constant to tune cache lifetime.
FILTERS_CACHE_TTL_SECONDS: int = 300

# Module-level cache shared across all requests: library_name -> LibraryFiltersResponse
_filters_cache: TTLCache = TTLCache(maxsize=64, ttl=FILTERS_CACHE_TTL_SECONDS)

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
    return {'status': 'ok', 'version': APP_VERSION}


@router.get('/ui-config')
async def ui_config(request: Request) -> dict[str, object]:
    settings = request.app.state.settings
    return {
        'language': settings.language,
        'score_max_points': settings.score_max_points,
        'version': APP_VERSION,
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
    immich: ImmichClient = Depends(get_immich_client),
) -> dict[str, list[dict[str, str]]]:
    try:
        settings = request.app.state.settings
        result = await immich.list_albums(library_name, include_shared_albums=settings.include_shared_albums)
        return {'albums': result}
    except ImmichClientError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get('/filters', response_model=LibraryFiltersResponse)
async def library_filters(
    library_name: str,
    request: Request,
    immich: ImmichClient = Depends(get_immich_client),
) -> LibraryFiltersResponse:
    settings: AppSettings = request.app.state.settings

    # Check TTL cache first (evicts automatically after FILTERS_CACHE_TTL_SECONDS)
    cached = _filters_cache.get(library_name)
    if cached is not None:
        return cached

    try:
        # 1. Fetch people from Immich
        people_raw = await immich.list_people(
            library_name,
            whitelist=settings.people_whitelist,
            blacklist=settings.people_blacklist,
        )
        people = [PersonOption(id=p.id, name=p.name) for p in people_raw]

        # 2. Fetch timeline bounds
        bounds = await immich.get_timeline_bounds(library_name)
        min_d = settings.fetch_photos_date_lower_bound or bounds.min_date
        max_d = settings.fetch_photos_date_upper_bound or bounds.max_date

        date_range = DateRangeOption(
            min_month=min_d.strftime('%Y-%m') if min_d else None,
            max_month=max_d.strftime('%Y-%m') if max_d else None,
        )

        # 3. Fetch countries & cities (with country association)
        countries = await immich.list_countries(
            library_name,
            whitelist=settings.country_whitelist,
            blacklist=settings.country_blacklist,
        )
        cities_raw = await immich.list_cities(
            library_name,
            whitelist=settings.city_whitelist,
            blacklist=settings.city_blacklist,
        )
        cities = [CityOption(name=c.name, country=c.country) for c in cities_raw]

        response = LibraryFiltersResponse(
            date_range=date_range,
            countries=countries,
            cities=cities,
            people=people,
        )

        # Store in TTL cache — automatically expires after FILTERS_CACHE_TTL_SECONDS
        _filters_cache[library_name] = response
        return response

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
    albums: str | None = Query(default=None),
) -> list[dict[str, object]]:
    entries = store.list_entries(
        rounds=rounds,
        round_length=round_length,
        location_mode=location_mode,
        date_mode=date_mode,
        game_mode=game_mode,
        library=library,
        albums=albums,
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
    request: Request,
    store: SessionStore = Depends(get_session_store),
    immich: ImmichClient = Depends(get_immich_client),
    game_service: GameService = Depends(get_game_service),
) -> GameSetupResponse:
    return await game_service.setup_game(setup, request.app.state.settings, store, immich)


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
    library_name: str,
    store: SessionStore = Depends(get_session_store),
    immich: ImmichClient = Depends(get_immich_client),
) -> Response:
    if not store.is_asset_registered(asset_id):
        raise HTTPException(status_code=404, detail='Unknown asset for any active match')

    try:
        content, content_type = await immich.get_asset_bytes(library_name, asset_id)
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

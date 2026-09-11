"""REST API routes for Challenge Mode (async & hybrid multiplayer).

Separated into:
- challenge_router (/api/challenge): Protected host management endpoints (create, list, deactivate).
- play_router (/play): Public player endpoints (/play/api/...) and scoped media proxy (/play/media/...).
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status

from src.game.challenge_service import ChallengeService, get_challenge_total_rounds
from src.immich.client import ImmichClient, ImmichClientError
from src.models import (
    ChallengeAnswerRequest,
    ChallengeAnswerResponse,
    ChallengeCreateRequest,
    ChallengeCreateResponse,
    ChallengeDeactivateResponse,
    ChallengeDetailResponse,
    ChallengeLeaderboardResponse,
    ChallengeListItem,
    ChallengeListResponse,
    ChallengeQuestionResponse,
    ChallengeStartRequest,
    ChallengeStartResponse,
    FlagAssetRequest,
    FlagAssetResponse,
    GameMode,
    MapBounds,
    RoundLength,
)
from src.storage.challenge import ChallengeStore
from src.storage.leaderboard import LeaderboardStore
from src.storage.metadata import MetadataStore

challenge_router = APIRouter(prefix='/api/challenge', tags=['challenge'])
play_router = APIRouter(prefix='/play', tags=['play'])


# --- Dependency Helpers ---


def get_challenge_service(request: Request) -> ChallengeService:
    """FastAPI dependency yielding the configured ChallengeService."""
    return request.app.state.challenge_service


def get_challenge_store(request: Request) -> ChallengeStore:
    """FastAPI dependency yielding the SQLite ChallengeStore."""
    return request.app.state.challenge_store


def get_leaderboard_store(request: Request) -> LeaderboardStore:
    """FastAPI dependency yielding the SQLite LeaderboardStore."""
    return request.app.state.leaderboard_store


def get_immich_client(request: Request) -> ImmichClient:
    """FastAPI dependency yielding the Immich client."""
    return request.app.state.immich_client


def get_metadata_store(request: Request) -> MetadataStore:
    """FastAPI dependency yielding the MetadataStore."""
    return request.app.state.metadata_store


# =====================================================================
# Host / Management Routes (/api/challenge)
# =====================================================================


@challenge_router.post('/create', response_model=ChallengeCreateResponse)
async def create_challenge(
    payload: ChallengeCreateRequest,
    request: Request,
    service: ChallengeService = Depends(get_challenge_service),
) -> ChallengeCreateResponse:
    """Create a deterministic challenge match seed with a capability URL.

    Pre-computes scoring decay constants and map bounds from the selected asset pool.
    These frozen values guarantee scoring fairness for all participants.
    """
    base_url = str(request.base_url).rstrip('/')
    record = await asyncio.to_thread(service.create_challenge, payload, base_url)

    return ChallengeCreateResponse(
        challenge_id=record['challenge_id'],
        capability_token=record['capability_token'],
        play_url=record['play_url'],
        title=record.get('title'),
        creator_name=record['creator_name'],
        libraries=record.get('libraries', []),
        rounds=record['rounds'],
        game_mode=GameMode(record.get('game_mode', 'pinpoint')),
        created_at=record.get('created_at'),
        expires_at=record.get('expires_at'),
    )


@challenge_router.get('/list', response_model=ChallengeListResponse)
async def list_challenges(
    request: Request,
    limit: int = 50,
    include_inactive: bool = True,
    challenge_store: ChallengeStore = Depends(get_challenge_store),
    leaderboard_store: LeaderboardStore = Depends(get_leaderboard_store),
) -> ChallengeListResponse:
    """List created challenges with metadata and participant counts for host management."""
    base_url = str(request.base_url).rstrip('/')
    records = await asyncio.to_thread(
        challenge_store.list_challenges,
        limit=limit,
        include_inactive=include_inactive,
    )

    challenge_ids = [rec['challenge_id'] for rec in records]
    participant_counts = await asyncio.to_thread(leaderboard_store.get_challenge_participant_counts, challenge_ids)
    now_utc = datetime.now(UTC)

    items: list[ChallengeListItem] = []
    for rec in records:
        config = rec.get('config', {})
        game_mode = GameMode(config.get('game_mode', 'pinpoint'))
        rounds = get_challenge_total_rounds(rec)

        total_participants = participant_counts.get(rec['challenge_id'], 0)
        play_url = f'{base_url}/play/{rec["capability_token"]}'

        is_active = bool(rec.get('is_active', True))
        if is_active and rec.get('expires_at'):
            exp = datetime.fromisoformat(rec['expires_at'])
            if now_utc > exp:
                is_active = False

        items.append(
            ChallengeListItem(
                challenge_id=rec['challenge_id'],
                capability_token=rec['capability_token'],
                play_url=play_url,
                title=rec.get('title'),
                creator_name=rec['creator_name'],
                game_mode=game_mode,
                rounds=rounds,
                round_length=RoundLength(config.get('round_length', '1m')),
                created_at=rec['created_at'],
                expires_at=rec.get('expires_at'),
                is_active=is_active,
                total_participants=total_participants,
                filter_summary=config.get('filter_summary'),
                filter_tooltip=config.get('filter_tooltip'),
                libraries=rec.get('libraries', []),
                location_mode=bool(config.get('location_mode', True)),
                date_mode=bool(config.get('date_mode', True)),
                config=config,
            )
        )

    return ChallengeListResponse(challenges=items)


@challenge_router.post('/{challenge_id}/deactivate', response_model=ChallengeDeactivateResponse)
async def deactivate_challenge(
    challenge_id: str,
    challenge_store: ChallengeStore = Depends(get_challenge_store),
) -> ChallengeDeactivateResponse:
    """Deactivate a challenge by its ID (host revocation)."""
    success = await asyncio.to_thread(challenge_store.deactivate_challenge, challenge_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f'Challenge {challenge_id} not found or already inactive.',
        )
    return ChallengeDeactivateResponse(success=True, challenge_id=challenge_id)


# =====================================================================
# Public Player & Game Routes (/play/api & /play/media)
# =====================================================================


@play_router.get('/api/{capability_token}', response_model=ChallengeDetailResponse)
async def get_challenge_detail(
    capability_token: str,
    challenge_store: ChallengeStore = Depends(get_challenge_store),
) -> ChallengeDetailResponse:
    """Public challenge info (metadata, round count, filters, participant count)."""
    challenge = await asyncio.to_thread(challenge_store.get_challenge_by_token, capability_token, include_inactive=True)
    if not challenge:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Challenge not found.')

    config = challenge['config']
    game_mode = GameMode(config.get('game_mode', 'pinpoint'))

    rounds = get_challenge_total_rounds(challenge)

    is_active = bool(challenge.get('is_active', True))
    if is_active and challenge.get('expires_at'):
        exp = datetime.fromisoformat(challenge['expires_at'])
        if datetime.now(UTC) > exp:
            is_active = False

    participants = await asyncio.to_thread(challenge_store.get_challenge_participants, challenge['challenge_id'])
    total_participants = len(participants)

    return ChallengeDetailResponse(
        challenge_id=challenge['challenge_id'],
        capability_token=challenge['capability_token'],
        title=challenge.get('title'),
        creator_name=challenge['creator_name'],
        libraries=challenge.get('libraries', []),
        rounds=rounds,
        round_length=RoundLength(config.get('round_length', '1m')),
        location_mode=bool(config.get('location_mode', True)),
        date_mode=bool(config.get('date_mode', True)),
        game_mode=game_mode,
        filter_summary=config.get('filter_summary'),
        filter_tooltip=config.get('filter_tooltip'),
        map_bounds=MapBounds(**config['map_bounds']) if config.get('map_bounds') else None,
        created_at=challenge['created_at'],
        expires_at=challenge['expires_at'],
        total_participants=total_participants,
        participants=participants,
        is_active=is_active,
    )


@play_router.post('/api/{capability_token}/start', response_model=ChallengeStartResponse)
async def start_challenge(
    capability_token: str,
    body: ChallengeStartRequest,
    challenge_store: ChallengeStore = Depends(get_challenge_store),
) -> ChallengeStartResponse:
    """Start or resume a player attempt for a challenge.

    If the player already has a session (same name), their existing
    progress is resumed instead of creating a duplicate entry.
    """
    challenge = await asyncio.to_thread(challenge_store.get_challenge_by_token, capability_token)
    if not challenge:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Challenge not found or expired.')

    session = await asyncio.to_thread(
        challenge_store.get_or_resume_player_session,
        challenge_id=challenge['challenge_id'],
        player_name=body.player_name.strip(),
        player_color=body.player_color,
    )
    total_rounds = get_challenge_total_rounds(challenge)

    is_resumed = session['current_round'] > 0
    participants = await asyncio.to_thread(challenge_store.get_challenge_participants, challenge['challenge_id'])
    participant_index = session.get('participant_index', 0)
    if 'participant_index' not in session:
        try:
            participant_index = participants.index(session['player_name'])
        except ValueError:
            participant_index = 0

    return ChallengeStartResponse(
        session_token=session['session_token'],
        match_id=session['match_id'],
        player_name=session['player_name'],
        total_rounds=total_rounds,
        current_round=session['current_round'],
        is_resumed=is_resumed,
        player_color=session.get('player_color'),
        participant_index=participant_index,
        participants=participants,
    )


@play_router.get(
    '/api/{capability_token}/question/{round_index}',
    response_model=ChallengeQuestionResponse,
)
async def get_challenge_question(
    capability_token: str,
    round_index: int,
    x_player_token: str = Header(...),
    challenge_store: ChallengeStore = Depends(get_challenge_store),
    service: ChallengeService = Depends(get_challenge_service),
) -> ChallengeQuestionResponse:
    """Get the question payload for round N.

    Server enforces security: no answer coordinates or dates are exposed.
    Validates that the player has completed all previous rounds.
    """
    challenge = await asyncio.to_thread(challenge_store.get_challenge_by_token, capability_token)
    if not challenge:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Challenge not found or expired.')

    session = await asyncio.to_thread(challenge_store.get_player_session, x_player_token)
    if not session or session['challenge_id'] != challenge['challenge_id']:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Invalid session token.')

    total_rounds = get_challenge_total_rounds(challenge)

    # Prevent accessing questions after challenge completion
    if session.get('completed_at') or session.get('current_round', 0) >= total_rounds:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='Challenge already completed.')

    # Enforce sequential round access (no skipping ahead)
    if round_index > session['current_round']:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f'Must complete round {session["current_round"]} first.',
        )

    if round_index >= total_rounds:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='Challenge already completed.')

    return await asyncio.to_thread(service.get_question, challenge, round_index)


@play_router.post(
    '/api/{capability_token}/answer',
    response_model=ChallengeAnswerResponse,
)
async def submit_challenge_answer(
    capability_token: str,
    body: ChallengeAnswerRequest,
    x_player_token: str = Header(...),
    challenge_store: ChallengeStore = Depends(get_challenge_store),
    service: ChallengeService = Depends(get_challenge_service),
) -> ChallengeAnswerResponse:
    """Score a round answer, persist to match_round_guesses, and return the personal reveal.

    The personal reveal includes the true answer (location, date, city, country)
    so the player sees their own result immediately — Fog of War only restricts
    visibility of OTHER players' answers until they also complete that round.
    """
    challenge = await asyncio.to_thread(challenge_store.get_challenge_by_token, capability_token)
    if not challenge:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Challenge not found or expired.')

    session = await asyncio.to_thread(challenge_store.get_player_session, x_player_token)
    if not session or session['challenge_id'] != challenge['challenge_id']:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Invalid session token.')

    # Validate round sequencing
    if body.round_index != session['current_round']:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f'Expected round {session["current_round"]}, got {body.round_index}.',
        )

    total_rounds = get_challenge_total_rounds(challenge)
    if session.get('completed_at') or session.get('current_round', 0) >= total_rounds:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='Challenge already completed.')

    return await asyncio.to_thread(
        service.score_and_persist_answer,
        challenge,
        session,
        body,
    )


@play_router.get(
    '/api/{capability_token}/leaderboard',
    response_model=ChallengeLeaderboardResponse,
)
async def get_challenge_leaderboard(
    capability_token: str,
    x_player_token: str | None = Header(default=None),
    challenge_store: ChallengeStore = Depends(get_challenge_store),
    leaderboard_store: LeaderboardStore = Depends(get_leaderboard_store),
) -> ChallengeLeaderboardResponse:
    """Fog of War Leaderboard Endpoint.

    Returns standings and round guesses up to the requesting player's completed round.
    If the player has finished all rounds (or has no active token), the full summary
    is accessible. Players CANNOT see other players' answers for rounds they haven't
    completed yet.
    """
    challenge = await asyncio.to_thread(challenge_store.get_challenge_by_token, capability_token, include_inactive=True)
    if not challenge:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Challenge not found.')

    config = challenge['config']
    game_mode = GameMode(config.get('game_mode', 'pinpoint'))

    total_rounds = get_challenge_total_rounds(challenge)

    caller_completed_round = -1
    is_game_over = False
    session = None
    if x_player_token:
        session = await asyncio.to_thread(challenge_store.get_player_session, x_player_token)
        if session:
            caller_completed_round = session['current_round'] - 1
            is_game_over = session['current_round'] >= total_rounds

    is_expired = False
    if challenge.get('expires_at'):
        exp = datetime.fromisoformat(challenge['expires_at'])
        if datetime.now(UTC) > exp:
            is_expired = True
    is_stopped = not challenge.get('is_active', True)
    is_concluded = bool(is_stopped or is_expired)

    if is_concluded:
        history_max_round: int | None = None
        standings_max_round: int | None = None
        is_game_over = True
    elif x_player_token and session:
        if is_game_over:
            history_max_round = None
            standings_max_round = None
        else:
            history_max_round = caller_completed_round
            standings_max_round = caller_completed_round
    else:
        # Anonymous / unauthenticated caller on an active challenge:
        # Standings show overall participant progress (for the Challenges Hub drawer),
        # but Fog of War strictly conceals round guesses and round history (true locations/dates).
        history_max_round = -1
        standings_max_round = None

    location_mode = bool(config.get('location_mode', True))
    date_mode = bool(config.get('date_mode', True))

    standings = await asyncio.to_thread(
        leaderboard_store.get_challenge_standings,
        challenge_id=challenge['challenge_id'],
        max_round=standings_max_round,
    )
    guesses = await asyncio.to_thread(
        leaderboard_store.get_challenge_round_guesses,
        challenge_id=challenge['challenge_id'],
        max_round=history_max_round,
    )
    round_history = await asyncio.to_thread(
        leaderboard_store.get_challenge_round_history,
        challenge_id=challenge['challenge_id'],
        max_round=history_max_round,
        game_mode=game_mode.value,
        location_mode=location_mode,
        capability_token=capability_token,
    )

    return ChallengeLeaderboardResponse(
        challenge_id=challenge['challenge_id'],
        title=challenge.get('title'),
        game_mode=game_mode,
        up_to_round=caller_completed_round,
        total_rounds=total_rounds,
        is_game_over=is_game_over,
        is_concluded=is_concluded,
        leaderboard=standings,
        round_guesses=guesses,
        location_mode=location_mode,
        date_mode=date_mode,
        round_history=round_history,
    )


@play_router.post('/api/{capability_token}/flag', response_model=FlagAssetResponse)
async def flag_challenge_asset(
    capability_token: str,
    payload: FlagAssetRequest,
    request: Request,
    challenge_store: ChallengeStore = Depends(get_challenge_store),
    metadata_store: MetadataStore = Depends(get_metadata_store),
) -> FlagAssetResponse:
    """Allow challenge participants to flag photo inconsistencies directly from challenge gameplay."""
    is_valid = await asyncio.to_thread(challenge_store.is_asset_in_challenge, capability_token, payload.asset_id)
    if not is_valid:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Unknown asset for this challenge')

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


@play_router.get('/media/{capability_token}/{asset_id}')
async def play_media(
    capability_token: str,
    asset_id: str,
    request: Request,
    challenge_store: ChallengeStore = Depends(get_challenge_store),
    immich: ImmichClient = Depends(get_immich_client),
    metadata_store: MetadataStore = Depends(get_metadata_store),
) -> Response:
    """Scoped media proxy for challenge players.

    Verifies the asset is registered to this specific active capability token,
    and strips all EXIF/GPS metadata in-memory before streaming image bytes.
    """
    is_valid = await asyncio.to_thread(challenge_store.is_asset_in_challenge, capability_token, asset_id)
    if not is_valid:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Unknown asset for this challenge')

    target_library = await asyncio.to_thread(metadata_store.get_asset_library, asset_id)
    if not target_library:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Cannot resolve library for asset')

    etag = f'"{asset_id}"'
    if_none_match = request.headers.get('if-none-match')
    if if_none_match and if_none_match.strip() == etag:
        return Response(
            status_code=status.HTTP_304_NOT_MODIFIED,
            headers={
                'ETag': etag,
                'Cache-Control': 'public, max-age=86400, immutable',
            },
        )

    try:
        content, content_type = await immich.get_asset_bytes(target_library, asset_id)
    except ImmichClientError as exc:
        await asyncio.to_thread(metadata_store.mark_asset_invalid, asset_id)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return Response(
        content=content,
        media_type=content_type,
        headers={
            'ETag': etag,
            'Cache-Control': 'public, max-age=86400, immutable',
        },
    )

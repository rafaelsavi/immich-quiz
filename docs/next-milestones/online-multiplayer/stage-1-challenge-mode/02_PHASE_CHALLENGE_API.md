# Phase 2: Challenge REST API & Fog-of-War Engine

> **Prerequisites**: Phase 1 must be complete (`src/storage/challenge.py` and models in `src/models.py` must exist).

## Goal

1. Create `src/api/challenge_routes.py` with complete endpoints for creating, starting, querying questions, submitting answers, and scoring challenge links.
2. Implement **Server-Side Fog of War** in `/api/challenge/{token}/leaderboard` so players cannot inspect opponent guesses for rounds they have not personally completed.
3. Update `src/api/routes.py` `/media/{asset_id}` endpoint to authorize challenge assets with automatic library resolution.
4. Mount the challenge router in `src/main.py`.

---

## 1. File: `src/api/challenge_routes.py`

Create this file with the complete router implementation:

```python
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status

from src.config import AppSettings
from src.game.selector import AssetSelector
from src.immich.client import ImmichClient
from src.models import (
    ChallengeAnswerRequest,
    ChallengeCreateRequest,
    ChallengeCreateResponse,
    ChallengeDetailResponse,
    ChallengeLeaderboardEntry,
    ChallengeLeaderboardResponse,
    ChallengeQuestionResponse,
    ChallengeRoundGuessData,
    ChallengeStartRequest,
    ChallengeStartResponse,
    RoundResultResponse,
)
from src.scoring import accuracy_pct, calculate_score, max_possible_score
from src.storage.challenge import ChallengeStore
from src.storage.leaderboard import LeaderboardStore
from src.storage.metadata import MetadataStore

logger = logging.getLogger(__name__)

challenge_router = APIRouter(prefix='/api/challenge', tags=['challenge'])


# Dependency helpers
def get_challenge_store(request: Request) -> ChallengeStore:
    return request.app.state.challenge_store


def get_metadata_store(request: Request) -> MetadataStore:
    return request.app.state.metadata_store


def get_immich_client(request: Request) -> ImmichClient:
    return request.app.state.immich_client


def get_leaderboard_store(request: Request) -> LeaderboardStore:
    return request.app.state.leaderboard_store


def get_settings(request: Request) -> AppSettings:
    return request.app.state.settings


@challenge_router.post('/create', response_model=ChallengeCreateResponse)
async def create_challenge(
    payload: ChallengeCreateRequest,
    request: Request,
    challenge_store: ChallengeStore = Depends(get_challenge_store),
    metadata_store: MetadataStore = Depends(get_metadata_store),
) -> ChallengeCreateResponse:
    """Create a deterministic challenge match seed with a capability URL."""
    candidates = metadata_store.fetch_candidate_assets(payload, limit=500)
    if len(candidates) < payload.rounds:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f'Insufficient eligible photos for challenge. Found {len(candidates)}, needed {payload.rounds}.',
        )

    selector = AssetSelector(metadata_store=metadata_store)
    selected_assets = selector.select_diverse_assets(
        candidates=candidates,
        count=payload.rounds,
        min_spatial_km=0.1,
        min_temporal_seconds=60,
    )
    asset_ids = [a.id for a in selected_assets]

    record = challenge_store.create_challenge(
        creator_name=payload.creator_name,
        library_name=payload.library_name,
        config=payload.model_dump(),
        asset_ids=asset_ids,
        expires_in_hours=payload.expires_in_hours,
    )

    base_url = str(request.base_url).rstrip('/')
    play_url = f'{base_url}/play/{record["capability_token"]}'

    return ChallengeCreateResponse(
        challenge_id=record['challenge_id'],
        capability_token=record['capability_token'],
        play_url=play_url,
        creator_name=record['creator_name'],
        library_name=record['library_name'],
        rounds=len(asset_ids),
        expires_at=record['expires_at'],
    )


@challenge_router.get('/{capability_token}', response_model=ChallengeDetailResponse)
async def get_challenge_detail(
    capability_token: str,
    challenge_store: ChallengeStore = Depends(get_challenge_store),
    leaderboard_store: LeaderboardStore = Depends(get_leaderboard_store),
) -> ChallengeDetailResponse:
    """Public challenge info (metadata, round count, and filter summary)."""
    challenge = challenge_store.get_challenge_by_token(capability_token)
    if not challenge:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Challenge not found or expired.')

    config = challenge['config']
    total_participants = leaderboard_store.get_challenge_participant_count(challenge['challenge_id'])

    return ChallengeDetailResponse(
        challenge_id=challenge['challenge_id'],
        capability_token=challenge['capability_token'],
        creator_name=challenge['creator_name'],
        library_name=challenge['library_name'],
        rounds=len(challenge['asset_ids']),
        round_length=config.get('round_length', 'medium'),
        location_mode=bool(config.get('location_mode', True)),
        date_mode=bool(config.get('date_mode', True)),
        game_mode=config.get('game_mode', 'pinpoint'),
        filter_summary=config.get('filter_summary', 'Standard'),
        created_at=challenge['created_at'],
        expires_at=challenge['expires_at'],
        total_participants=total_participants,
    )


@challenge_router.post('/{capability_token}/start', response_model=ChallengeStartResponse)
async def start_challenge(
    capability_token: str,
    body: ChallengeStartRequest,
    challenge_store: ChallengeStore = Depends(get_challenge_store),
) -> ChallengeStartResponse:
    """Start an active player attempt for a challenge."""
    challenge = challenge_store.get_challenge_by_token(capability_token)
    if not challenge:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Challenge not found or expired.')

    session_data = challenge_store.create_player_session(
        challenge_id=challenge['challenge_id'],
        capability_token=capability_token,
        player_name=body.player_name.strip(),
    )

    return ChallengeStartResponse(
        session_token=session_data['session_token'],
        match_id=session_data['match_id'],
        player_name=session_data['player_name'],
        total_rounds=len(challenge['asset_ids']),
        current_round=0,
    )


@challenge_router.get('/{capability_token}/question/{round_index}', response_model=ChallengeQuestionResponse)
async def get_challenge_question(
    capability_token: str,
    round_index: int,
    x_player_token: str = Header(...),
    challenge_store: ChallengeStore = Depends(get_challenge_store),
) -> ChallengeQuestionResponse:
    """Get the question payload for round N without exposing answer coordinates or dates."""
    challenge = challenge_store.get_challenge_by_token(capability_token)
    if not challenge:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Challenge not found or expired.')

    session = challenge_store.get_player_session(x_player_token)
    if not session or session['capability_token'] != capability_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Invalid session token.')

    asset_ids = challenge['asset_ids']
    if round_index < 0 or round_index >= len(asset_ids):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Invalid round index.')

    config = challenge['config']
    return ChallengeQuestionResponse(
        round_index=round_index,
        total_rounds=len(asset_ids),
        asset_id=asset_ids[round_index],
        game_mode=config.get('game_mode', 'pinpoint'),
        location_mode=bool(config.get('location_mode', True)),
        date_mode=bool(config.get('date_mode', True)),
        round_length=config.get('round_length', 'medium'),
    )


@challenge_router.post('/{capability_token}/answer')
async def submit_challenge_answer(
    capability_token: str,
    body: ChallengeAnswerRequest,
    x_player_token: str = Header(...),
    challenge_store: ChallengeStore = Depends(get_challenge_store),
    metadata_store: MetadataStore = Depends(get_metadata_store),
    leaderboard_store: LeaderboardStore = Depends(get_leaderboard_store),
    settings: AppSettings = Depends(get_settings),
) -> dict[str, Any]:
    """Score a round answer, persist to match_round_guesses, and return the reveal result."""
    challenge = challenge_store.get_challenge_by_token(capability_token)
    if not challenge:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Challenge not found or expired.')

    session = challenge_store.get_player_session(x_player_token)
    if not session or session['capability_token'] != capability_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Invalid session token.')

    asset_ids = challenge['asset_ids']
    if body.round_index < 0 or body.round_index >= len(asset_ids):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Invalid round index.')

    target_asset_id = asset_ids[body.round_index]
    asset = metadata_store.get_asset(target_asset_id)
    if not asset:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Photo asset not found.')

    # Calculate scores
    result = calculate_score(
        guess_lat=body.guess_latitude,
        guess_lng=body.guess_longitude,
        actual_lat=asset.latitude,
        actual_lng=asset.longitude,
        guess_date=body.guess_date,
        actual_date=asset.file_created_at.strftime('%Y-%m-%d') if asset.file_created_at else None,
        scoring_config=settings.scoring,
    )

    # Persist round guess
    leaderboard_store.record_challenge_round_guess(
        match_id=session['match_id'],
        challenge_id=challenge['challenge_id'],
        player_name=session['player_name'],
        round_index=body.round_index,
        asset_id=target_asset_id,
        guess_lat=body.guess_latitude,
        guess_lng=body.guess_longitude,
        actual_lat=asset.latitude,
        actual_lng=asset.longitude,
        distance_km=result.get('distance_km'),
        location_points=result.get('location_score'),
        guess_date=body.guess_date,
        actual_date=asset.file_created_at.strftime('%Y-%m-%d') if asset.file_created_at else None,
        date_diff_days=result.get('date_diff_days'),
        date_points=result.get('date_score'),
        round_score=result.get('total_score', 0),
        time_taken_seconds=body.time_taken_seconds,
    )

    session['completed_rounds'] = max(session['completed_rounds'], body.round_index + 1)
    session['total_score'] += result.get('total_score', 0)
    session['total_time_seconds'] += body.time_taken_seconds

    is_final_round = body.round_index >= len(asset_ids) - 1
    if is_final_round:
        # Finalize player match entry in match_entries
        leaderboard_store.finalize_challenge_player_match(
            match_id=session['match_id'],
            challenge_id=challenge['challenge_id'],
            player_name=session['player_name'],
            total_score=session['total_score'],
            total_rounds=len(asset_ids),
            total_time_seconds=session['total_time_seconds'],
        )

    return {
        'round_index': body.round_index,
        'round_score': result.get('total_score', 0),
        'location_score': result.get('location_score'),
        'date_score': result.get('date_score'),
        'distance_km': result.get('distance_km'),
        'actual_latitude': asset.latitude,
        'actual_longitude': asset.longitude,
        'actual_date': asset.file_created_at.strftime('%Y-%m-%d') if asset.file_created_at else None,
        'is_game_over': is_final_round,
    }


@challenge_router.get('/{capability_token}/leaderboard', response_model=ChallengeLeaderboardResponse)
async def get_challenge_leaderboard(
    capability_token: str,
    x_player_token: str | None = Header(default=None),
    challenge_store: ChallengeStore = Depends(get_challenge_store),
    leaderboard_store: LeaderboardStore = Depends(get_leaderboard_store),
) -> ChallengeLeaderboardResponse:
    """
    Fog of War Leaderboard Endpoint:
    Returns standings and round guesses up to the requesting player's completed round.
    If the player has finished all rounds (or has no active token), the full summary is accessible.
    """
    challenge = challenge_store.get_challenge_by_token(capability_token)
    if not challenge:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Challenge not found or expired.')

    caller_completed_round = -1
    is_game_over = False
    if x_player_token:
        session = challenge_store.get_player_session(x_player_token)
        if session:
            caller_completed_round = session['completed_rounds'] - 1
            is_game_over = session['completed_rounds'] >= len(challenge['asset_ids'])

    standings = leaderboard_store.get_challenge_standings(
        challenge_id=challenge['challenge_id'],
        max_round=caller_completed_round if not is_game_over else None,
    )
    guesses = leaderboard_store.get_challenge_round_guesses(
        challenge_id=challenge['challenge_id'],
        max_round=caller_completed_round if not is_game_over else None,
    )

    return ChallengeLeaderboardResponse(
        challenge_id=challenge['challenge_id'],
        up_to_round=caller_completed_round,
        is_game_over=is_game_over,
        leaderboard=standings,
        round_guesses=guesses,
    )
```

---

## 2. File: `src/api/routes.py` (Media Proxying Update)

Update the `/media/{asset_id}` endpoint to authorize challenge assets and resolve `library_name` automatically if omitted:

```python
@router.get('/media/{asset_id}')
async def media(
    asset_id: str,
    library_name: str | None = None,
    store: SessionStore = Depends(get_session_store),
    challenge_store: ChallengeStore = Depends(get_challenge_store),
    immich: ImmichClient = Depends(get_immich_client),
    metadata_store: MetadataStore = Depends(get_metadata_store),
) -> Response:
    # Authorize if asset is in an active local match OR in an active challenge
    is_local = store.is_asset_registered(asset_id)
    is_challenge = challenge_store.is_asset_in_active_challenge(asset_id)

    if not is_local and not is_challenge:
        raise HTTPException(status_code=404, detail='Unknown asset for any active game or challenge')

    # Resolve library_name from MetadataStore if omitted in query params
    if not library_name:
        cached_asset = metadata_store.get_asset(asset_id)
        if cached_asset and cached_asset.library_name:
            library_name = cached_asset.library_name
        else:
            raise HTTPException(status_code=400, detail='library_name required for asset')

    try:
        content, content_type = await immich.get_asset_bytes(library_name, asset_id)
    except ImmichClientError as exc:
        metadata_store.mark_asset_invalid(asset_id)
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return Response(content=content, media_type=content_type)
```

---

## 3. File: `src/main.py` (Wire Challenge Store and Router)

Add `ChallengeStore` initialization and mount the `challenge_router`:

```python
# In src/main.py:
from src.api.challenge_routes import challenge_router
from src.storage.challenge import ChallengeStore

# Inside create_app() after leaderboard_store:
challenge_store = ChallengeStore(leaderboard_db_manager)
app.state.challenge_store = challenge_store

# Mount challenge routes:
app.include_router(challenge_router)
```

---

## Acceptance Criteria

1. `POST /api/challenge/create` creates an unguessable capability URL and stores the selected assets deterministically.
2. `POST /api/challenge/{token}/start` issues a player session token.
3. `GET /api/challenge/{token}/question/{round_index}` serves round photo metadata without answer coordinates or dates.
4. `POST /api/challenge/{token}/answer` validates score calculations and writes guesses to `match_round_guesses`.
5. `GET /api/challenge/{token}/leaderboard` strictly enforces **Fog of War**: Player A with 1 completed round cannot see Player B's Round 2 guess or score.
6. `/media/{asset_id}` resolves `library_name` automatically for challenge participants.

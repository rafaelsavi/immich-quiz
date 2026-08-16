# Phase 2: Challenge REST API & Fog-of-War Engine

> **Prerequisites**: Phase 1 must be complete (`src/storage/challenge.py` and models in `src/models.py` must exist).

## Goal

1. Create `src/api/challenge_routes.py` with endpoints for creating, playing, and scoring challenge links.
2. Implement **Server-Side Fog of War** in `/api/challenge/{token}/leaderboard` so players cannot inspect opponent guesses for rounds they have not personally completed.
3. Update `src/api/routes.py` `/media/{asset_id}` endpoint to authorize challenge assets.
4. Mount the challenge router in `src/main.py`.

---

## 1. File: `src/api/challenge_routes.py`

Create this file with the complete router implementation:

```python
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Header, Request, status

from src.config import AppSettings
from src.game.modes import GameModeRegistry
from src.game.selector import AssetSelector
from src.immich.client import ImmichClient
from src.models import (
    AnswerResponse,
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
from src.scoring import accuracy_pct, max_possible_score
from src.storage.challenge import ChallengeStore
from src.storage.leaderboard import LeaderboardStore
from src.storage.metadata import MetadataStore
from src.storage.session import SessionStore

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
    immich_client: ImmichClient = Depends(get_immich_client),
) -> ChallengeCreateResponse:
    """Create a deterministic challenge match seed with a capability URL."""
    # 1. Fetch eligible candidate assets matching criteria
    candidates = metadata_store.fetch_candidate_assets(payload, limit=500)
    if len(candidates) < payload.rounds:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f'Insufficient eligible photos for challenge. Found {len(candidates)}, needed {payload.rounds}.',
        )

    # 2. Select deterministic sequence using AssetSelector
    selector = AssetSelector(metadata_store=metadata_store)
    selected_assets = selector.select_diverse_assets(
        candidates=candidates,
        count=payload.rounds,
        min_spatial_km=0.1,
        min_temporal_seconds=60,
    )
    asset_ids = [a.id for a in selected_assets]

    # 3. Store challenge seed
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

    # Determine caller's current completed round index
    caller_completed_round = -1
    is_game_over = False
    if x_player_token:
        caller_completed_round = leaderboard_store.get_player_completed_round(x_player_token)
        is_game_over = caller_completed_round >= len(challenge['asset_ids']) - 1

    # Fetch standings and guesses up to caller_completed_round
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

Update the `/media/{asset_id}` endpoint to authorize challenge assets:

```python
@router.get('/media/{asset_id}')
async def media(
    asset_id: str,
    library_name: str,
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
from src.api.challenge_routes import router as challenge_router
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
2. `GET /api/challenge/{token}` returns public metadata without exposing answers or future asset IDs.
3. `GET /api/challenge/{token}/leaderboard` strictly enforces **Fog of War**: Player A with 1 completed round cannot see Player B's Round 2 guess or score.
4. `/media/{asset_id}` allows loading challenge photos while rejecting unassociated assets.

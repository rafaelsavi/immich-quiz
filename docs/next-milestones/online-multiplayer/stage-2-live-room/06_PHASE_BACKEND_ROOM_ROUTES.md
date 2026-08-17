# Phase 6: Backend Room API Routes (Milestone 2)

> **Prerequisites**: Phase 5 must be complete. `src/room/manager.py` and `src/room/websocket.py` must exist.

## Goal

1. Create `src/api/room_routes.py` with REST + WebSocket endpoints for room operations
2. Add room-related Pydantic models to `src/models.py`
3. Wire everything into `src/main.py`

---

## File 1: Add Models to `src/models.py`

Add these new models at the **end** of the existing `src/models.py` file. Do NOT modify any existing models.

```python
# --- Online Room Models (append to end of file) ---


class PlayerMode(str, Enum):
    local = 'local'
    online = 'online'


class RoomCreateRequest(BaseModel):
    host_name: str = Field(min_length=1)
    settings: dict = Field(default_factory=dict)


class RoomCreateResponse(BaseModel):
    room_id: str
    join_code: str
    host_token: str
    players: list[dict]


class RoomJoinRequest(BaseModel):
    join_code: str = Field(min_length=4, max_length=4)
    player_name: str = Field(min_length=1)


class RoomJoinResponse(BaseModel):
    room_id: str
    player_token: str
    join_code: str
    players: list[dict]
    settings: dict
    phase: str


class RoomPlayerInfo(BaseModel):
    name: str
    is_host: bool
    is_ready: bool
    connected: bool


class RoomStateResponse(BaseModel):
    room_id: str
    join_code: str
    players: list[RoomPlayerInfo]
    settings: dict
    phase: str
    current_match_id: str | None
    match_history: list[str]


class RoomSettingsUpdateRequest(BaseModel):
    settings: dict
```

---

## File 2: Create `src/api/room_routes.py`

This is a NEW file. Here is the existing `src/api/routes.py` pattern for reference (dependency injection style):

```python
# EXISTING PATTERN (from src/api/routes.py) — just for reference, do NOT modify:
# def get_session_store(request: Request) -> SessionStore:
#     return request.app.state.session_store
# @router.post('/game/setup', response_model=GameSetupResponse)
# async def game_setup(setup: GameSetupRequest, store: SessionStore = Depends(get_session_store)) -> GameSetupResponse:
#     ...
```

Create `src/api/room_routes.py`:

```python
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Header, HTTPException, Request, WebSocket, WebSocketDisconnect

from src.models import (
    RoomCreateRequest,
    RoomCreateResponse,
    RoomJoinRequest,
    RoomJoinResponse,
    RoomPlayerInfo,
    RoomSettingsUpdateRequest,
    RoomStateResponse,
)
from src.room.manager import RoomError, RoomManager
from src.room.websocket import RoomEvent, RoomEventType, WebSocketManager

logger = logging.getLogger(__name__)

room_router = APIRouter(prefix='/api/room')


def get_room_manager(request: Request) -> RoomManager:
    return request.app.state.room_manager


def get_ws_manager(request: Request) -> WebSocketManager:
    return request.app.state.ws_manager


def _serialize_players(room) -> list[dict]:
    return [
        RoomPlayerInfo(
            name=p.name,
            is_host=p.is_host,
            is_ready=p.is_ready,
            connected=p.connected,
        ).model_dump()
        for p in room.players
    ]


@room_router.post('/create', response_model=RoomCreateResponse)
async def create_room(
    body: RoomCreateRequest,
    mgr: RoomManager = Depends(get_room_manager),
) -> RoomCreateResponse:
    try:
        room, host_token = mgr.create_room(body.host_name, body.settings)
    except RoomError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return RoomCreateResponse(
        room_id=room.room_id,
        join_code=room.join_code,
        host_token=host_token,
        players=_serialize_players(room),
    )


@room_router.post('/join', response_model=RoomJoinResponse)
async def join_room(
    body: RoomJoinRequest,
    mgr: RoomManager = Depends(get_room_manager),
    ws_mgr: WebSocketManager = Depends(get_ws_manager),
) -> RoomJoinResponse:
    try:
        room, player_token = mgr.join_room(body.join_code, body.player_name)
    except RoomError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    # Notify existing players
    await ws_mgr.broadcast(
        room.room_id,
        RoomEvent(
            type=RoomEventType.PLAYER_JOINED,
            data={'player_name': body.player_name, 'players': _serialize_players(room)},
        ),
    )

    return RoomJoinResponse(
        room_id=room.room_id,
        player_token=player_token,
        join_code=room.join_code,
        players=_serialize_players(room),
        settings=room.settings,
        phase=room.phase.value,
    )


@room_router.post('/{room_id}/ready')
async def toggle_ready(
    room_id: str,
    x_player_token: str = Header(...),
    mgr: RoomManager = Depends(get_room_manager),
    ws_mgr: WebSocketManager = Depends(get_ws_manager),
) -> dict:
    try:
        room = mgr.toggle_ready(room_id, x_player_token)
    except RoomError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    player = room.get_player_by_token(x_player_token)
    await ws_mgr.broadcast(
        room_id,
        RoomEvent(
            type=RoomEventType.PLAYER_READY,
            data={
                'player_name': player.name if player else '',
                'is_ready': player.is_ready if player else False,
                'players': _serialize_players(room),
            },
        ),
    )
    return {'ok': True, 'players': _serialize_players(room)}


@room_router.get('/{room_id}/state', response_model=RoomStateResponse)
async def room_state(
    room_id: str,
    x_player_token: str = Header(...),
    mgr: RoomManager = Depends(get_room_manager),
) -> RoomStateResponse:
    try:
        room = mgr.get_room(room_id)
    except RoomError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    player = room.get_player_by_token(x_player_token)
    if player is None:
        raise HTTPException(status_code=403, detail='Not a member of this room')

    return RoomStateResponse(
        room_id=room.room_id,
        join_code=room.join_code,
        players=[
            RoomPlayerInfo(name=p.name, is_host=p.is_host, is_ready=p.is_ready, connected=p.connected)
            for p in room.players
        ],
        settings=room.settings,
        phase=room.phase.value,
        current_match_id=room.current_match_id,
        match_history=room.match_history,
    )


@room_router.post('/{room_id}/settings')
async def update_settings(
    room_id: str,
    body: RoomSettingsUpdateRequest,
    x_player_token: str = Header(...),
    mgr: RoomManager = Depends(get_room_manager),
    ws_mgr: WebSocketManager = Depends(get_ws_manager),
) -> dict:
    try:
        room = mgr.update_settings(room_id, x_player_token, body.settings)
    except RoomError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    await ws_mgr.broadcast(
        room_id,
        RoomEvent(
            type=RoomEventType.SETTINGS_CHANGED,
            data={'settings': room.settings, 'players': _serialize_players(room)},
        ),
    )
    return {'ok': True}


@room_router.post('/{room_id}/start')
async def start_match(
    room_id: str,
    x_player_token: str = Header(...),
    request: Request = None,
    mgr: RoomManager = Depends(get_room_manager),
    ws_mgr: WebSocketManager = Depends(get_ws_manager),
) -> dict:
    """Host starts a match. Creates a MatchState via existing GameService."""
    from src.game.service import GameService
    from src.models import GameSetupRequest
    from src.storage.session import SessionStore

    try:
        room = mgr.start_match(room_id, x_player_token)
    except RoomError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    # Build GameSetupRequest from room settings + room players
    settings_dict = dict(room.settings)
    settings_dict['players'] = room.player_names()

    try:
        setup = GameSetupRequest(**settings_dict)
    except Exception as exc:
        # Revert room phase if setup fails
        room.phase = room.phase.LOBBY
        raise HTTPException(status_code=400, detail=f'Invalid game settings: {exc}') from exc

    store: SessionStore = request.app.state.session_store
    immich = request.app.state.immich_client
    game_service: GameService = getattr(request.app.state, 'game_service', None) or GameService()

    response = await game_service.setup_game(setup, store, immich)
    room.current_match_id = response.match_id

    await ws_mgr.broadcast(
        room_id,
        RoomEvent(
            type=RoomEventType.MATCH_STARTING,
            data={
                'match_id': response.match_id,
                'total_turns': response.total_turns,
                'players': response.players,
            },
        ),
    )
    return {
        'ok': True,
        'match_id': response.match_id,
        'total_turns': response.total_turns,
        'players': response.players,
    }


@room_router.post('/{room_id}/kick/{player_name}')
async def kick_player(
    room_id: str,
    player_name: str,
    x_player_token: str = Header(...),
    mgr: RoomManager = Depends(get_room_manager),
    ws_mgr: WebSocketManager = Depends(get_ws_manager),
) -> dict:
    try:
        room = mgr.kick_player(room_id, x_player_token, player_name)
    except RoomError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    await ws_mgr.broadcast(
        room_id,
        RoomEvent(
            type=RoomEventType.PLAYER_LEFT,
            data={'player_name': player_name, 'kicked': True, 'players': _serialize_players(room)},
        ),
    )
    return {'ok': True}


@room_router.post('/{room_id}/leave')
async def leave_room(
    room_id: str,
    x_player_token: str = Header(...),
    mgr: RoomManager = Depends(get_room_manager),
    ws_mgr: WebSocketManager = Depends(get_ws_manager),
) -> dict:
    try:
        room_before = mgr.get_room(room_id)
        player = room_before.get_player_by_token(x_player_token)
        player_name = player.name if player else 'Unknown'
        room = mgr.leave_room(room_id, x_player_token)
    except RoomError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    await ws_mgr.broadcast(
        room_id,
        RoomEvent(
            type=RoomEventType.PLAYER_LEFT,
            data={'player_name': player_name, 'kicked': False, 'players': _serialize_players(room)},
        ),
    )
    return {'ok': True}


@room_router.post('/{room_id}/close')
async def close_room(
    room_id: str,
    x_player_token: str = Header(...),
    mgr: RoomManager = Depends(get_room_manager),
    ws_mgr: WebSocketManager = Depends(get_ws_manager),
) -> dict:
    try:
        await ws_mgr.broadcast(
            room_id,
            RoomEvent(type=RoomEventType.ROOM_CLOSED, data={}),
        )
        mgr.close_room(room_id, x_player_token)
        ws_mgr.close_room(room_id)
    except RoomError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {'ok': True}
```

### WebSocket Endpoint (add at the bottom of room_routes.py)

```python
# Add this to src/api/room_routes.py — this is a standalone router for the WS endpoint

ws_router = APIRouter()


@ws_router.websocket('/ws/room/{room_id}')
async def room_websocket(
    websocket: WebSocket,
    room_id: str,
    token: str,
) -> None:
    """WebSocket endpoint for real-time room events."""
    app = websocket.app
    mgr: RoomManager = app.state.room_manager
    ws_mgr: WebSocketManager = app.state.ws_manager

    # Validate token belongs to this room
    try:
        room = mgr.get_room(room_id)
    except RoomError:
        await websocket.close(code=4004, reason='Room not found')
        return

    player = room.get_player_by_token(token)
    if player is None:
        await websocket.close(code=4003, reason='Invalid token')
        return

    await ws_mgr.connect(room_id, token, websocket)
    mgr.reconnect_player(room_id, token)

    # Notify others of reconnection
    await ws_mgr.broadcast(
        room_id,
        RoomEvent(
            type=RoomEventType.PLAYER_RECONNECTED,
            data={'player_name': player.name, 'players': _serialize_players(room)},
        ),
        exclude_token=token,
    )

    # Send current room state to the connecting client
    await ws_mgr.send_to(
        room_id,
        token,
        RoomEvent(
            type=RoomEventType.ROOM_STATE,
            data={
                'room_id': room.room_id,
                'join_code': room.join_code,
                'players': _serialize_players(room),
                'settings': room.settings,
                'phase': room.phase.value,
                'current_match_id': room.current_match_id,
            },
        ),
    )

    try:
        while True:
            # Listen for client messages (ready toggle, etc.)
            data = await websocket.receive_text()
            # For now, we handle ready toggle via REST. WS is receive-only for clients.
            # Future: parse JSON and handle lightweight signals here.
            logger.debug('WS received from %s: %s', player.name, data[:100])
    except WebSocketDisconnect:
        ws_mgr.disconnect(room_id, token)
        mgr.disconnect_player(room_id, token)
        await ws_mgr.broadcast(
            room_id,
            RoomEvent(
                type=RoomEventType.PLAYER_DISCONNECTED,
                data={'player_name': player.name, 'players': _serialize_players(room)},
            ),
        )
```

---

## File 3: Modify `src/main.py`

Make these specific changes to `src/main.py`:

### Change 1: Add imports (at the top, after existing imports)

```python
# ADD after the line: from src.storage.session import SessionStore
from src.room.manager import RoomManager
from src.room.websocket import WebSocketManager
```

### Change 2: Initialize room state (in `create_app`, after `app.state.leaderboard_store = ...`)

```python
    # ADD after: app.state.leaderboard_store = LeaderboardStore(...)
    app.state.room_manager = RoomManager()
    app.state.ws_manager = WebSocketManager()
```

### Change 3: Mount room routes (after `app.include_router(router)`)

```python
# ADD after: app.include_router(router)
from src.api.room_routes import room_router, ws_router

app.include_router(room_router)
app.include_router(ws_router)
```

### Change 4: Add room cleanup to periodic task (in `_periodic_cleanup`)

```python
    # MODIFY the _periodic_cleanup function to also clean rooms:
    async def _periodic_cleanup() -> None:
        while True:
            await asyncio.sleep(900)
            cleaned = app.state.session_store.cleanup_expired_matches(ttl_seconds=7200)
            if cleaned > 0:
                logger.info('Cleaned up %d expired match session(s)', cleaned)
            room_cleaned = app.state.room_manager.cleanup_stale_rooms(ttl_seconds=7200)
            if room_cleaned > 0:
                logger.info('Cleaned up %d expired room(s)', room_cleaned)
```

---

## Acceptance Criteria

1. Server starts without errors: `uv run -m src.main`
2. `POST /api/room/create` returns a room with join code
3. `POST /api/room/join` adds a player to the room
4. `GET /api/room/{id}/state` returns room state
5. `WS /ws/room/{id}?token=...` connects and receives ROOM_STATE event
6. `POST /api/room/{id}/start` creates a MatchState and broadcasts MATCH_STARTING
7. All existing endpoints (`/api/game/setup`, `/api/question`, etc.) still work unchanged
8. Code passes linting: `uv run ruff check src/api/room_routes.py src/room/`

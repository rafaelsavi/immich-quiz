# Phase 1: Backend Room Infrastructure

> **Prerequisites**: Read `00_OVERVIEW.md` first. Do NOT modify any existing files in this phase.

## Goal

Create the `src/room/` package with two modules:
1. `manager.py` — Room lifecycle, player management, join codes
2. `websocket.py` — Per-room WebSocket connection tracking and event broadcast

---

## File 1: `src/room/__init__.py`

Create this file:

```python
"""Game room package for online multiplayer coordination."""

from src.room.manager import GameRoom, RoomManager, RoomPhase, RoomPlayer
from src.room.websocket import RoomEvent, RoomEventType, WebSocketManager

__all__ = [
    'GameRoom',
    'RoomManager',
    'RoomPhase',
    'RoomPlayer',
    'RoomEvent',
    'RoomEventType',
    'WebSocketManager',
]
```

---

## File 2: `src/room/manager.py`

Create this file with the following structure.

### Data Models

```python
from __future__ import annotations

import secrets
import string
import time
from dataclasses import dataclass, field
from enum import Enum
from uuid import uuid4


class RoomPhase(str, Enum):
    LOBBY = 'lobby'
    IN_MATCH = 'in_match'
    BETWEEN_MATCHES = 'between_matches'
    CLOSED = 'closed'


@dataclass
class RoomPlayer:
    name: str
    is_host: bool
    is_ready: bool = False
    connected: bool = True
    session_token: str = field(default_factory=lambda: secrets.token_urlsafe(32))


@dataclass
class GameRoom:
    room_id: str
    join_code: str
    players: list[RoomPlayer] = field(default_factory=list)
    current_match_id: str | None = None
    match_history: list[str] = field(default_factory=list)
    settings: dict = field(default_factory=dict)
    phase: RoomPhase = RoomPhase.LOBBY
    created_at: float = field(default_factory=time.time)
    last_activity_at: float = field(default_factory=time.time)

    def touch(self) -> None:
        self.last_activity_at = time.time()

    def get_host(self) -> RoomPlayer | None:
        for p in self.players:
            if p.is_host:
                return p
        return None

    def get_player_by_token(self, token: str) -> RoomPlayer | None:
        for p in self.players:
            if p.session_token == token:
                return p
        return None

    def get_player_by_name(self, name: str) -> RoomPlayer | None:
        for p in self.players:
            if p.name.lower() == name.lower():
                return p
        return None

    def player_names(self) -> list[str]:
        return [p.name for p in self.players]

    def all_guests_ready(self) -> bool:
        """Return True when every non-host player is ready."""
        guests = [p for p in self.players if not p.is_host]
        return len(guests) > 0 and all(p.is_ready for p in guests)

    def reset_ready_states(self) -> None:
        """Clear all ready flags (called when a new match starts or settings change)."""
        for p in self.players:
            p.is_ready = False
```

### RoomManager Class

```python
class RoomError(ValueError):
    """Raised for room operation failures."""


class RoomManager:
    """In-memory room lifecycle manager."""

    MAX_PLAYERS_PER_ROOM = 8

    def __init__(self) -> None:
        self._rooms: dict[str, GameRoom] = {}  # room_id -> GameRoom
        self._code_to_room: dict[str, str] = {}  # join_code -> room_id
        self._token_to_room: dict[str, str] = {}  # player_token -> room_id

    def _generate_join_code(self) -> str:
        """Generate a 4-char alphanumeric code, excluding ambiguous chars (O/0/I/1/L)."""
        alphabet = 'ABCDEFGHJKMNPQRSTUVWXYZ23456789'
        while True:
            code = ''.join(secrets.choice(alphabet) for _ in range(4))
            if code not in self._code_to_room:
                return code

    def create_room(self, host_name: str, settings: dict | None = None) -> tuple[GameRoom, str]:
        """Create a new room. Returns (room, host_token)."""
        host_name = host_name.strip()
        if not host_name:
            raise RoomError('Host name cannot be empty')

        room_id = str(uuid4())
        join_code = self._generate_join_code()
        host = RoomPlayer(name=host_name, is_host=True)

        room = GameRoom(
            room_id=room_id,
            join_code=join_code,
            players=[host],
            settings=settings or {},
        )

        self._rooms[room_id] = room
        self._code_to_room[join_code] = room_id
        self._token_to_room[host.session_token] = room_id

        return room, host.session_token

    def join_room(self, join_code: str, player_name: str) -> tuple[GameRoom, str]:
        """Add a player to an existing room. Returns (room, player_token)."""
        join_code = join_code.strip().upper()
        player_name = player_name.strip()

        if not player_name:
            raise RoomError('Player name cannot be empty')

        room_id = self._code_to_room.get(join_code)
        if room_id is None:
            raise RoomError(f'No room found with code: {join_code}')

        room = self._rooms[room_id]

        if room.phase == RoomPhase.CLOSED:
            raise RoomError('This room has been closed')

        if room.phase == RoomPhase.IN_MATCH:
            raise RoomError('A match is currently in progress. Please wait for it to finish.')

        if len(room.players) >= self.MAX_PLAYERS_PER_ROOM:
            raise RoomError(f'Room is full (max {self.MAX_PLAYERS_PER_ROOM} players)')

        if room.get_player_by_name(player_name) is not None:
            raise RoomError(f"Name '{player_name}' is already taken in this room")

        player = RoomPlayer(name=player_name, is_host=False)
        room.players.append(player)
        room.touch()
        self._token_to_room[player.session_token] = room_id

        return room, player.session_token

    def leave_room(self, room_id: str, player_token: str) -> GameRoom:
        """Remove a player from the room."""
        room = self.get_room(room_id)
        player = room.get_player_by_token(player_token)
        if player is None:
            raise RoomError('Player not found in room')

        room.players.remove(player)
        self._token_to_room.pop(player_token, None)
        room.touch()

        # If host left, promote the next player or close
        if player.is_host and room.players:
            room.players[0].is_host = True
        elif not room.players:
            self._close_room_internal(room)

        return room

    def kick_player(self, room_id: str, host_token: str, player_name: str) -> GameRoom:
        """Host removes a player by name."""
        room = self.get_room(room_id)
        host = room.get_player_by_token(host_token)
        if host is None or not host.is_host:
            raise RoomError('Only the host can kick players')

        target = room.get_player_by_name(player_name)
        if target is None:
            raise RoomError(f"Player '{player_name}' not found")
        if target.is_host:
            raise RoomError('Cannot kick the host')

        room.players.remove(target)
        self._token_to_room.pop(target.session_token, None)
        room.touch()
        return room

    def toggle_ready(self, room_id: str, player_token: str) -> GameRoom:
        """Toggle a player's ready state."""
        room = self.get_room(room_id)
        player = room.get_player_by_token(player_token)
        if player is None:
            raise RoomError('Player not found in room')
        player.is_ready = not player.is_ready
        room.touch()
        return room

    def update_settings(self, room_id: str, host_token: str, settings: dict) -> GameRoom:
        """Host updates room game settings. Resets all ready states."""
        room = self.get_room(room_id)
        host = room.get_player_by_token(host_token)
        if host is None or not host.is_host:
            raise RoomError('Only the host can change settings')
        if room.phase == RoomPhase.IN_MATCH:
            raise RoomError('Cannot change settings during a match')

        room.settings.update(settings)
        room.reset_ready_states()
        room.touch()
        return room

    def start_match(self, room_id: str, host_token: str) -> GameRoom:
        """Mark room as IN_MATCH. Returns room for the caller to create the actual MatchState."""
        room = self.get_room(room_id)
        host = room.get_player_by_token(host_token)
        if host is None or not host.is_host:
            raise RoomError('Only the host can start a match')
        if len(room.players) < 2:
            raise RoomError('Need at least 2 players to start')
        if room.phase == RoomPhase.IN_MATCH:
            raise RoomError('A match is already in progress')

        room.phase = RoomPhase.IN_MATCH
        room.reset_ready_states()
        room.touch()
        return room

    def finish_match(self, room_id: str, match_id: str) -> GameRoom:
        """Transition room from IN_MATCH to BETWEEN_MATCHES."""
        room = self.get_room(room_id)
        if room.current_match_id == match_id:
            room.match_history.append(match_id)
            room.current_match_id = None
        room.phase = RoomPhase.BETWEEN_MATCHES
        room.reset_ready_states()
        room.touch()
        return room

    def close_room(self, room_id: str, host_token: str) -> None:
        """Host closes the room."""
        room = self.get_room(room_id)
        host = room.get_player_by_token(host_token)
        if host is None or not host.is_host:
            raise RoomError('Only the host can close the room')
        self._close_room_internal(room)

    def get_room(self, room_id: str) -> GameRoom:
        room = self._rooms.get(room_id)
        if room is None:
            raise RoomError(f'Room not found: {room_id}')
        return room

    def get_room_by_code(self, join_code: str) -> GameRoom:
        room_id = self._code_to_room.get(join_code.strip().upper())
        if room_id is None:
            raise RoomError(f'No room with code: {join_code}')
        return self.get_room(room_id)

    def get_room_for_token(self, player_token: str) -> GameRoom | None:
        room_id = self._token_to_room.get(player_token)
        if room_id is None:
            return None
        return self._rooms.get(room_id)

    def reconnect_player(self, room_id: str, player_token: str) -> GameRoom:
        """Mark a returning player as connected."""
        room = self.get_room(room_id)
        player = room.get_player_by_token(player_token)
        if player is None:
            raise RoomError('Player token not recognized for this room')
        player.connected = True
        room.touch()
        return room

    def disconnect_player(self, room_id: str, player_token: str) -> GameRoom:
        """Mark a player as disconnected (WS dropped)."""
        room = self.get_room(room_id)
        player = room.get_player_by_token(player_token)
        if player is not None:
            player.connected = False
        room.touch()
        return room

    def cleanup_stale_rooms(self, ttl_seconds: int = 7200) -> int:
        """Remove rooms inactive for longer than ttl_seconds."""
        now = time.time()
        stale = [room_id for room_id, room in self._rooms.items() if (now - room.last_activity_at) > ttl_seconds]
        for room_id in stale:
            room = self._rooms.get(room_id)
            if room:
                self._close_room_internal(room)
        return len(stale)

    def _close_room_internal(self, room: GameRoom) -> None:
        room.phase = RoomPhase.CLOSED
        self._code_to_room.pop(room.join_code, None)
        for p in room.players:
            self._token_to_room.pop(p.session_token, None)
        self._rooms.pop(room.room_id, None)
```

---

## File 3: `src/room/websocket.py`

Create this file:

```python
from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from starlette.websockets import WebSocket, WebSocketDisconnect, WebSocketState

logger = logging.getLogger(__name__)


class RoomEventType(str, Enum):
    PLAYER_JOINED = 'player_joined'
    PLAYER_LEFT = 'player_left'
    PLAYER_READY = 'player_ready'
    PLAYER_RECONNECTED = 'player_reconnected'
    PLAYER_DISCONNECTED = 'player_disconnected'
    SETTINGS_CHANGED = 'settings_changed'
    MATCH_STARTING = 'match_starting'
    QUESTION_READY = 'question_ready'
    PLAYER_ANSWERED = 'player_answered'
    ROUND_COMPLETE = 'round_complete'
    MATCH_FINISHED = 'match_finished'
    ROOM_CLOSED = 'room_closed'
    TIMER_SYNC = 'timer_sync'
    KICKED = 'kicked'
    HOST_CHANGED = 'host_changed'
    ROOM_STATE = 'room_state'
    ERROR = 'error'


@dataclass
class RoomEvent:
    type: RoomEventType
    data: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> str:
        return json.dumps({'type': self.type.value, 'data': self.data})


class WebSocketManager:
    """Manages per-room WebSocket connections and broadcasts events."""

    def __init__(self) -> None:
        # room_id -> {player_token -> WebSocket}
        self._connections: dict[str, dict[str, WebSocket]] = {}

    async def connect(self, room_id: str, player_token: str, websocket: WebSocket) -> None:
        """Accept and register a WebSocket connection."""
        await websocket.accept()
        if room_id not in self._connections:
            self._connections[room_id] = {}
        # Close any existing connection for this token (reconnect scenario)
        old_ws = self._connections[room_id].get(player_token)
        if old_ws is not None:
            try:
                await old_ws.close()
            except Exception:
                pass
        self._connections[room_id][player_token] = websocket
        logger.info('WS connected: room=%s token=%s...', room_id[:8], player_token[:8])

    def disconnect(self, room_id: str, player_token: str) -> None:
        """Remove a WebSocket connection."""
        room_conns = self._connections.get(room_id, {})
        room_conns.pop(player_token, None)
        if not room_conns:
            self._connections.pop(room_id, None)
        logger.info('WS disconnected: room=%s token=%s...', room_id[:8], player_token[:8])

    async def broadcast(self, room_id: str, event: RoomEvent, exclude_token: str | None = None) -> None:
        """Send an event to all connected clients in a room."""
        room_conns = self._connections.get(room_id, {})
        payload = event.to_json()
        dead: list[str] = []

        for token, ws in room_conns.items():
            if token == exclude_token:
                continue
            try:
                if ws.client_state == WebSocketState.CONNECTED:
                    await ws.send_text(payload)
            except Exception:
                dead.append(token)

        for token in dead:
            room_conns.pop(token, None)

    async def send_to(self, room_id: str, player_token: str, event: RoomEvent) -> None:
        """Send an event to a specific player."""
        room_conns = self._connections.get(room_id, {})
        ws = room_conns.get(player_token)
        if ws is None:
            return
        try:
            if ws.client_state == WebSocketState.CONNECTED:
                await ws.send_text(event.to_json())
        except Exception:
            room_conns.pop(player_token, None)

    def close_room(self, room_id: str) -> None:
        """Remove all connections for a room."""
        self._connections.pop(room_id, None)
```

---

## Acceptance Criteria

After completing this phase:

1. `from src.room import RoomManager, WebSocketManager` imports without error
2. `RoomManager` can create rooms, join players, toggle ready, start/finish matches, kick, leave, close, cleanup
3. `WebSocketManager` can connect/disconnect/broadcast/send_to
4. No existing files were modified
5. All code passes `uv run ruff check src/room/` and `uv run ruff format src/room/`

## How to Verify

Write and run a simple test:

```python
# tests/test_room_manager.py
from src.room.manager import RoomManager, RoomError
import pytest


def test_create_and_join():
    mgr = RoomManager()
    room, host_token = mgr.create_room('Alice', {'game_mode': 'pinpoint'})
    assert len(room.join_code) == 4
    assert len(room.players) == 1
    assert room.players[0].is_host

    room2, guest_token = mgr.join_room(room.join_code, 'Bob')
    assert len(room2.players) == 2
    assert not room2.players[1].is_host


def test_duplicate_name_rejected():
    mgr = RoomManager()
    room, _ = mgr.create_room('Alice')
    with pytest.raises(RoomError):
        mgr.join_room(room.join_code, 'Alice')


def test_ready_and_start():
    mgr = RoomManager()
    room, host_token = mgr.create_room('Alice')
    _, guest_token = mgr.join_room(room.join_code, 'Bob')
    mgr.toggle_ready(room.room_id, guest_token)
    assert room.all_guests_ready()
    mgr.start_match(room.room_id, host_token)
    assert room.phase.value == 'in_match'
```

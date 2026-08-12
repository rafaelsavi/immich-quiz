# Phase 5: Reconnection, Edge Cases, Polish

> **Prerequisites**: Phases 1-4 must be complete and working. End-to-end online gameplay must function.

## Goal

Handle edge cases, add reconnection support, add WS event broadcasting from the existing answer/result flow, and polish the experience.

---

## Task 1: Broadcast WS Events from Answer and Round Result Endpoints

The existing `/api/answer` and `/api/round/result` endpoints don't know about rooms. We need to broadcast WebSocket events when answers are submitted and rounds complete.

### Approach: Add a thin middleware/hook in `room_routes.py`

Add these helper functions to `src/api/room_routes.py`:

```python
async def notify_player_answered(app, room_id: str, player_name: str) -> None:
    """Called after a player submits an answer in online mode."""
    ws_mgr: WebSocketManager = app.state.ws_manager
    await ws_mgr.broadcast(
        room_id,
        RoomEvent(
            type=RoomEventType.PLAYER_ANSWERED,
            data={'player_name': player_name},
        ),
    )


async def notify_round_complete(app, room_id: str, round_number: int) -> None:
    """Called when all players in a round have answered."""
    ws_mgr: WebSocketManager = app.state.ws_manager
    await ws_mgr.broadcast(
        room_id,
        RoomEvent(
            type=RoomEventType.ROUND_COMPLETE,
            data={'round_number': round_number},
        ),
    )


async def notify_match_finished(app, room_id: str, match_id: str) -> None:
    """Called when the match is complete."""
    ws_mgr: WebSocketManager = app.state.ws_manager
    mgr: RoomManager = app.state.room_manager
    try:
        mgr.finish_match(room_id, match_id)
    except RoomError:
        pass
    await ws_mgr.broadcast(
        room_id,
        RoomEvent(
            type=RoomEventType.MATCH_FINISHED,
            data={'match_id': match_id},
        ),
    )
```

### Modify the existing `/api/answer` endpoint in `src/api/routes.py`

At the **end** of the `answer` function, after `return await game_service.submit_answer(...)`, we need to call the room notifications. The cleanest way is to make the answer endpoint aware of room context:

**Option A (recommended — minimal change to routes.py):**

Add room_id as an optional header/query param to the answer call:

```python
# In src/api/routes.py, modify the answer endpoint:


@router.post('/answer', response_model=AnswerResponse)
async def answer(
    payload: AnswerRequest,
    request: Request,
    store: SessionStore = Depends(get_session_store),
    leaderboard_store: LeaderboardStore = Depends(get_leaderboard_store),
    game_service: GameService = Depends(get_game_service),
    x_room_id: str | None = Header(default=None),
) -> AnswerResponse:
    result = await game_service.submit_answer(payload, request.app.state.settings, store, leaderboard_store)

    # Online mode: broadcast WS events
    if x_room_id and hasattr(request.app.state, 'ws_manager'):
        from src.api.room_routes import notify_player_answered, notify_round_complete, notify_match_finished

        await notify_player_answered(request.app, x_room_id, result.player_name)
        if result.round_complete:
            await notify_round_complete(request.app, x_room_id, result.round_number)
        if result.match_finished:
            await notify_match_finished(request.app, x_room_id, payload.match_id)

    return result
```

### Frontend change: Send room_id header with answer requests

In `static/js/modules/api.js` or wherever the answer API call is made, add the room header when in online mode:

```javascript
// In app.js, in the submitAnswer function, when calling /api/answer:
const headers = {};
if (state.playerMode === "online" && state.roomId) {
  headers["X-Room-Id"] = state.roomId;
}

const result = await api("/api/answer", {
  method: "POST",
  body: JSON.stringify(payload),
  headers,
});
```

---

## Task 2: Auto-Reconnect on Page Refresh

In `app.js`, during `DOMContentLoaded` initialization, add:

```javascript
  // --- Auto-reconnect to room ---
  const savedClient = new RoomClient();
  if (savedClient.restoreFromStorage()) {
    try {
      const roomState = await savedClient.getRoomState();
      state.roomClient = savedClient;
      state.roomId = savedClient.roomId;
      state.joinCode = savedClient.joinCode;
      state.isHost = savedClient.isHost;
      state.playerMode = "online";
      state.roomPlayers = roomState.players.map((p) => ({
        name: p.name,
        is_host: p.is_host,
        is_ready: p.is_ready,
        connected: p.connected,
      }));

      setupRoomEventHandlers(savedClient);
      savedClient.connectWs();

      if (roomState.phase === "in_match" && roomState.current_match_id) {
        // Rejoin active match
        state.matchId = roomState.current_match_id;
        showCard(el.gameCard);
        const activeMode = getActiveMode();
        activeMode.mount(el.guessingUi, {});
        await loadQuestion();
      } else {
        showLobby();
      }
    } catch (err) {
      console.warn("[Reconnect] Failed to restore room:", err.message);
      savedClient.reset();
    }
  }
```

---

## Task 3: Handle Disconnected Player Timeout

When a player disconnects during a match, their turn should auto-submit after a timeout.

### Backend: Add to room WebSocket disconnect handler

In `src/api/room_routes.py`, in the `room_websocket` function's `except WebSocketDisconnect` block, add a delayed auto-submit task:

```python
    except WebSocketDisconnect:
        ws_mgr.disconnect(room_id, token)
        mgr.disconnect_player(room_id, token)
        await ws_mgr.broadcast(
            room_id,
            RoomEvent(
                type=RoomEventType.PLAYER_DISCONNECTED,
                data={"player_name": player.name, "players": _serialize_players(room)},
            ),
        )

        # If in a match, schedule auto-submit after 60 seconds if player doesn't reconnect
        if room.phase == RoomPhase.IN_MATCH and room.current_match_id:
            async def auto_submit_if_disconnected():
                await asyncio.sleep(60)
                room_now = mgr.get_room(room_id)
                p = room_now.get_player_by_token(token)
                if p and not p.connected:
                    # Auto-submit for this player (with timed_out=true)
                    logger.info("Auto-submitting for disconnected player: %s", p.name)
                    # Find their active question and submit
                    # This requires access to the SessionStore and GameService
                    # Implementation depends on how questions map to players in online mode

            asyncio.create_task(auto_submit_if_disconnected())
```

> **Note**: The auto-submit implementation is complex because it requires mapping which question belongs to the disconnected player. This can be deferred to a later iteration. For MVP, just mark the player as disconnected and let the host decide to wait or close the room.

---

## Task 4: "Between Matches" Flow

When a match finishes in online mode and the host clicks "New Match":

1. Room transitions to `BETWEEN_MATCHES` phase
2. Lobby shows again with all players
3. Host can modify settings (game mode, rounds, timer, library, album)
4. Host clicks "Start Match" again → new MatchState is created with same room players

### Frontend: Settings editor for host in lobby

When `room.phase === "between_matches"`, the lobby should show a settings panel for the host:

```javascript
function renderLobby() {
  // ... existing lobby rendering ...

  // If between matches and host, show settings editor
  if (state.isHost && state.roomClient) {
    // Add settings controls (simplified: just show current settings)
    // Full settings editor can reuse the setup form fields
    // For MVP, host can use the existing setup form dropdowns
  }
}
```

### Backend: The `start_match` endpoint already handles this

The `/api/room/{room_id}/start` endpoint creates a new MatchState each time. Since the room keeps its player list, this works for subsequent matches automatically.

---

## Task 5: Server-Authoritative Timer (Optional Enhancement)

For tighter sync, the server can broadcast timer corrections:

```python
# In room_routes.py, after MATCH_STARTING is broadcast:
async def broadcast_timer_sync(room_id, total_seconds):
    """Periodically sync the timer to prevent client drift."""
    ws_mgr = app.state.ws_manager
    remaining = total_seconds
    while remaining > 0:
        await asyncio.sleep(5)
        remaining -= 5
        await ws_mgr.broadcast(
            room_id,
            RoomEvent(type=RoomEventType.TIMER_SYNC, data={'remaining': remaining}),
        )
```

> **Note**: This is a polish item. For MVP, the client-side timer is sufficient since the server already enforces answer windows.

---

## Task 6: Update Documentation

### Modify `docs/ARCHITECTURE.md`

Add a new section:

```markdown
## Online Multiplayer (Player Mode: Online)

When "Online" player mode is selected, a **Game Room** coordination layer sits
on top of the existing game engine:

- `src/room/manager.py` — `RoomManager` manages rooms, join codes, player connections
- `src/room/websocket.py` — `WebSocketManager` handles per-room WebSocket broadcast
- `src/api/room_routes.py` — REST + WebSocket endpoints for room operations

The existing REST API (`/api/game/setup`, `/api/question`, `/api/answer`,
`/api/round/result`) is reused identically. WebSocket is only used for
real-time notifications (player joined, round complete, etc.).

All anti-cheat guarantees are preserved: WebSocket never carries answer data.
```

### Modify `docs/GAMEPLAY.md`

Add a new section:

```markdown
## Online Play

### Creating a Room

1. On the setup screen, select **Online** under Player Mode
2. Configure game settings as usual (game mode, guess mode, rounds, etc.)
3. Click **Create Room**
4. Share the 4-character room code with other players

### Joining a Room

1. Click **Join a Room** on the home screen
2. Enter the room code and your name
3. Click **Join Room**
4. Wait in the lobby for the host to start

### Lobby

The lobby shows all connected players with ready indicators. Guests must
toggle "Ready" before the host can start. The host can override and start
at any time with 2+ players.

### Online Gameplay

All players answer simultaneously. There is no pass-device overlay.
After everyone submits, the reveal screen appears for all players at once.

### Between Matches

After a match ends, the room returns to the lobby. The host can change
settings and start a new match without players needing to rejoin.
```

### Modify `docs/TODO.md`

Mark the multiplayer item as done or in-progress.

---

## Acceptance Criteria

1. WS events fire when answers are submitted (PLAYER_ANSWERED, ROUND_COMPLETE, MATCH_FINISHED)
2. Page refresh auto-reconnects to an active room
3. Disconnected players are shown as disconnected in the lobby
4. After match ends, host can start a new match in the same room
5. Documentation is updated
6. All existing tests pass
7. New tests pass for room lifecycle

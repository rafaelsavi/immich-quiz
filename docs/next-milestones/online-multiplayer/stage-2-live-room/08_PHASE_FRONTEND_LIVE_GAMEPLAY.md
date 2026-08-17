# Phase 8: Frontend Live Gameplay Integration (Milestone 2)

> **Prerequisites**: Phases 5–7 must be complete. Room UI must be visible and RoomClient must be functional.

## Goal

Wire the room system into the existing game cycle in `app.js` so that:
1. Host flow: setup → create room → lobby → start match → game plays simultaneously → summary → back to lobby
2. Guest flow: join card → lobby → wait for start → game plays → summary → back to lobby
3. Online mode replaces pass-device overlay with simultaneous play
4. Between matches, the host can reconfigure settings and start a new match

---

## Key Behavioral Differences from Local Mode

| Aspect | Local Mode (unchanged) | Online Mode (new) |
|--------|----------------------|-------------------|
| Players input | Comma-separated text field | Players join room dynamically |
| Turn order | Sequential pass-and-play | **Simultaneous** — all answer the same round at once |
| Pass-device overlay | Shown between turns | **NOT shown** — replaced by "waiting for players" chips |
| Round advance | After last sequential player submits | After ALL players submit in parallel |
| After match ends | Back to setup screen | Back to lobby (same room, host can start new match) |

---

## File 1: Modify `static/js/app.js`

This is the largest change. Here is the **exact approach** — modify the existing `app.js`, don't rewrite it.

### Change 1: Import RoomClient

At the top of `app.js`, after the existing imports, add:

```javascript
import { RoomClient } from "./modules/room.js";
```

### Change 2: Add Player Mode selector logic

In the `document.addEventListener("DOMContentLoaded", ...)` block, add this initialization:

```javascript
  // --- Player Mode selector ---
  const playerModeSelector = document.getElementById("player-mode-selector");
  if (playerModeSelector) {
    playerModeSelector.addEventListener("click", (e) => {
      const btn = e.target.closest(".mode-btn");
      if (!btn) return;
      playerModeSelector.querySelectorAll(".mode-btn").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      state.playerMode = btn.dataset.mode;
      updatePlayerModeUi();
    });
  }

  function updatePlayerModeUi() {
    const isOnline = state.playerMode === "online";
    // Hide player names input in online mode (players come from room)
    const playersRow = el.players?.closest("div") || el.players?.parentElement;
    if (playersRow && el.players) {
      // Only hide the players input wrapper, not the label
      el.players.closest("label")?.parentElement?.classList.toggle("hidden", isOnline);
      // Or simply hide the input
      if (el.players.parentElement) {
        const label = el.players.previousElementSibling;
        if (label) label.classList.toggle("hidden", isOnline);
        el.players.classList.toggle("hidden", isOnline);
        el.players.required = !isOnline;
      }
    }
    // Change submit button text
    const submitBtn = el.setupForm?.querySelector('button[type="submit"]');
    if (submitBtn) {
      submitBtn.textContent = isOnline ? t("room.create_btn") : t("setup.start_btn");
    }
  }
```

### Change 3: Add "Join Room" button handler

```javascript
  // --- Join Room flow ---
  if (el.joinRoomShowBtn) {
    el.joinRoomShowBtn.addEventListener("click", () => {
      showCard(el.joinCard);
    });
  }

  if (el.joinBackBtn) {
    el.joinBackBtn.addEventListener("click", () => {
      showCard(el.setupCard);
    });
  }

  if (el.joinRoomBtn) {
    el.joinRoomBtn.addEventListener("click", async () => {
      const code = el.joinCodeInput.value.trim().toUpperCase();
      const name = el.joinNameInput.value.trim();
      if (!code || code.length !== 4) {
        showAlert(t("room.code_label") + " is required (4 characters)");
        return;
      }
      if (!name) {
        showAlert(t("room.name_label") + " is required");
        return;
      }
      try {
        const client = new RoomClient();
        const data = await client.joinRoom(code, name);
        state.roomClient = client;
        state.roomId = data.room_id;
        state.joinCode = data.join_code;
        state.isHost = false;
        state.roomPlayers = data.players;
        setupRoomEventHandlers(client);
        client.connectWs();
        showLobby();
      } catch (err) {
        showAlert(err.message || "Failed to join room");
      }
    });
  }
```

### Change 4: Override `startMatch` for online mode

Modify the existing `startMatch` function. Wrap the existing logic in an `if (state.playerMode === "local")` check, and add the online path:

```javascript
async function startMatch(event) {
  event.preventDefault();

  if (state.playerMode === "online") {
    // Online mode: create room instead of starting match directly
    await createOnlineRoom();
    return;
  }

  // ... existing local mode code (keep ALL of it exactly as-is) ...
}

async function createOnlineRoom() {
  const activeMode = getActiveMode();
  const modePayload = activeMode.getModePayload();
  const albumId = el.album.value || null;

  const settings = {
    round_count: Number(el.roundCount.value),
    round_length: el.roundLength.value,
    library_name: el.library.value,
    album_id: albumId,
    album_name: albumId ? el.album.options[el.album.selectedIndex].text : "-",
    ...modePayload,
  };

  // Prompt for host name
  const hostName = prompt(t("room.name_label") || "Your name:");
  if (!hostName || !hostName.trim()) return;

  try {
    const client = new RoomClient();
    const data = await client.createRoom(hostName.trim(), settings);
    state.roomClient = client;
    state.roomId = data.room_id;
    state.joinCode = data.join_code;
    state.isHost = true;
    state.roomPlayers = data.players;
    setupRoomEventHandlers(client);
    client.connectWs();
    showLobby();
  } catch (err) {
    showAlert(err.message || "Failed to create room");
  }
}
```

### Change 5: Lobby rendering functions

```javascript
function showCard(cardEl) {
  clearRevealAnimation();
  // Add join-card and lobby-card to the list of cards to hide
  [el.setupCard, el.gameCard, el.summaryCard, el.joinCard, el.lobbyCard].forEach((c) => {
    if (c) c.classList.add("hidden");
  });
  cardEl.classList.remove("hidden");
}

function showLobby() {
  showCard(el.lobbyCard);
  el.leaderboardCard.classList.add("hidden");
  renderLobby();
}

function renderLobby() {
  if (!el.lobbyJoinCode || !el.lobbyPlayers || !el.lobbyActions) return;

  // Join code
  el.lobbyJoinCode.textContent = state.joinCode || "";

  // Copy button
  if (el.lobbyCopyCode) {
    el.lobbyCopyCode.onclick = () => {
      navigator.clipboard.writeText(state.joinCode || "").then(() => {
        el.lobbyCopyCode.textContent = "✅";
        setTimeout(() => (el.lobbyCopyCode.textContent = "📋"), 2000);
      });
    };
  }

  // Player list
  el.lobbyPlayers.replaceChildren();
  for (const player of state.roomPlayers) {
    const row = document.createElement("div");
    row.className = "lobby-player-row";
    if (player.is_ready) row.classList.add("is-ready");
    if (!player.connected) row.classList.add("is-disconnected");

    const name = document.createElement("span");
    name.className = "lobby-player-name";
    name.textContent = player.name;
    row.appendChild(name);

    if (player.is_host) {
      const badge = document.createElement("span");
      badge.className = "lobby-player-badge host";
      badge.textContent = "Host";
      row.appendChild(badge);
    }

    const status = document.createElement("span");
    status.className = "lobby-player-status";
    status.textContent = !player.connected ? "⚫" : player.is_ready ? "✅" : "⏳";
    row.appendChild(status);

    // Kick button (host only, not self)
    if (state.isHost && !player.is_host) {
      const kick = document.createElement("button");
      kick.className = "lobby-player-kick";
      kick.textContent = "✕";
      kick.title = "Kick player";
      kick.onclick = async () => {
        if (confirm(`Kick ${player.name}?`)) {
          try {
            await state.roomClient.kickPlayer(player.name);
          } catch (err) {
            showAlert(err.message);
          }
        }
      };
      row.appendChild(kick);
    }

    el.lobbyPlayers.appendChild(row);
  }

  // Actions
  el.lobbyActions.replaceChildren();

  if (state.isHost) {
    const startBtn = document.createElement("button");
    startBtn.className = "btn-primary";
    startBtn.textContent = t("room.start_btn");
    startBtn.disabled = state.roomPlayers.length < 2;
    startBtn.onclick = async () => {
      try {
        const result = await state.roomClient.startMatch();
        // Match will start via WS MATCH_STARTING event
      } catch (err) {
        showAlert(err.message);
      }
    };
    el.lobbyActions.appendChild(startBtn);

    const closeBtn = document.createElement("button");
    closeBtn.className = "btn-secondary";
    closeBtn.textContent = t("room.close_btn");
    closeBtn.onclick = async () => {
      if (confirm("Close room for everyone?")) {
        await state.roomClient.closeRoom();
        state.roomClient = null;
        showCard(el.setupCard);
      }
    };
    el.lobbyActions.appendChild(closeBtn);
  } else {
    // Guest: ready toggle
    const player = state.roomPlayers.find(
      (p) => state.roomClient && p.name && state.roomClient.playerToken
    );
    // Simpler: just show a ready button
    const readyBtn = document.createElement("button");
    readyBtn.className = "btn-primary";
    readyBtn.textContent = t("room.ready_btn");
    readyBtn.onclick = async () => {
      try {
        await state.roomClient.toggleReady();
      } catch (err) {
        showAlert(err.message);
      }
    };
    el.lobbyActions.appendChild(readyBtn);

    const leaveBtn = document.createElement("button");
    leaveBtn.className = "btn-secondary";
    leaveBtn.textContent = t("room.leave_btn");
    leaveBtn.onclick = async () => {
      await state.roomClient.leaveRoom();
      state.roomClient = null;
      showCard(el.setupCard);
    };
    el.lobbyActions.appendChild(leaveBtn);

    // Waiting message
    const msg = document.createElement("p");
    msg.className = "lobby-settings-summary";
    msg.textContent = t("room.waiting_host");
    el.lobbyActions.appendChild(msg);
  }
}
```

### Change 6: WebSocket event handlers

```javascript
function setupRoomEventHandlers(client) {
  client.on("player_joined", (data) => {
    state.roomPlayers = data.players;
    renderLobby();
  });

  client.on("player_left", (data) => {
    state.roomPlayers = data.players;
    renderLobby();
  });

  client.on("player_ready", (data) => {
    state.roomPlayers = data.players;
    renderLobby();
  });

  client.on("player_reconnected", (data) => {
    state.roomPlayers = data.players;
    renderLobby();
  });

  client.on("player_disconnected", (data) => {
    state.roomPlayers = data.players;
    renderLobby();
  });

  client.on("settings_changed", (data) => {
    state.roomPlayers = data.players;
    renderLobby();
  });

  client.on("match_starting", async (data) => {
    // A match is starting! Transition from lobby to game.
    state.matchId = data.match_id;
    state.players = data.players;
    state.playedAssetIds = [];
    state.matchFinished = false;
    state.perfectCounts = {};
    state.playerStats = {};
    state.roundHistory = [];
    state.gameMode = state.roomClient?.isHost
      ? (el.setupForm ? document.querySelector("#game-mode-selector .mode-btn.active")?.dataset?.mode : "pinpoint")
      : "pinpoint"; // Will be overridden by question response

    el.leaderboardCard.classList.add("hidden");
    showCard(el.gameCard);

    const activeMode = getActiveMode();
    // For online mode, we need to mount the game mode UI
    // Use stored settings or defaults
    activeMode.mount(el.guessingUi, {});
    applyLanguage();

    await loadQuestion();
  });

  client.on("player_answered", (data) => {
    // Show who has answered (update a waiting indicator if visible)
    // This is a notification only — no score data
    console.log(`[Room] ${data.player_name} has answered`);
  });

  client.on("round_complete", async (data) => {
    // All players answered — reveal is available
    // The existing reveal flow will handle this via the normal loadQuestion/submitAnswer cycle
    console.log("[Room] Round complete, reveal available");
  });

  client.on("match_finished", (data) => {
    console.log("[Room] Match finished");
    // The existing summary flow handles this
  });

  client.on("room_closed", () => {
    showAlert("The room has been closed by the host.");
    if (state.roomClient) {
      state.roomClient.reset();
      state.roomClient = null;
    }
    showCard(el.setupCard);
  });

  client.on("kicked", () => {
    showAlert("You have been kicked from the room.");
    if (state.roomClient) {
      state.roomClient.reset();
      state.roomClient = null;
    }
    showCard(el.setupCard);
  });

  client.on("room_state", (data) => {
    // Full state sync on reconnect
    state.roomPlayers = data.players;
    state.joinCode = data.join_code;
    if (data.phase === "lobby" || data.phase === "between_matches") {
      renderLobby();
    }
  });

  client.on("connection_lost", () => {
    showAlert("Connection to room lost. Please refresh to reconnect.");
  });
}
```

### Change 7: Modify pass-device overlay for online mode

In the `loadQuestion` function, find the block that shows the pass-device overlay (around the `if (data.total_players > 1)` check). Wrap it:

```javascript
  // In online mode, skip the pass-device overlay entirely
  if (state.playerMode === "online") {
    el.passOverlay.classList.add("hidden");
    activeMode.onReady(data);
    startTimer(data.round_length);
  } else if (data.total_players > 1) {
    // Existing local mode pass-device overlay logic (keep as-is)
    el.overlayTitle.textContent = t("game.pass_device_title", ...);
    el.overlaySubtitle.textContent = t("game.pass_device_subtitle", ...);
    el.passOverlay.classList.remove("hidden");
  } else {
    el.passOverlay.classList.add("hidden");
    activeMode.onReady(data);
    startTimer(data.round_length);
  }
```

### Change 8: After match ends in online mode, return to lobby

In the summary rendering code, modify the "New Match" button behavior:

```javascript
  // When match is finished and in online mode:
  if (state.playerMode === "online" && state.roomClient) {
    // "New Match" button returns to lobby, not setup
    el.newMatch.textContent = state.isHost ? t("room.start_btn") : t("room.lobby_heading");
    el.newMatch.onclick = () => {
      showLobby();
    };
  }
```

---

## Acceptance Criteria

1. **Host flow works end-to-end**: Setup → Player Mode "Online" → "Create Room" → lobby shows with code → guest joins → host starts → game plays (no pass-device overlay) → summary → "New Match" returns to lobby
2. **Guest flow works**: "Join a Room" → enter code + name → lobby → wait → game plays → summary → back to lobby
3. **Simultaneous play**: In online mode, all players answer at the same time (no sequential turns, no pass-device overlay)
4. **Local mode unchanged**: Switching to "Local" mode works exactly as before — all existing behavior intact
5. **WebSocket events**: Player join/leave/ready updates are reflected in real-time in the lobby

---

## How to Test

1. Open the app in **two separate browser windows** (or tabs)
2. Window 1: Select "Online" player mode → fill settings → "Create Room"
3. Window 1: Note the 4-character join code in the lobby
4. Window 2: Click "Join a Room" → enter the code + a name → "Join Room"
5. Window 1 should show the new player appear in real-time
6. Window 2: Click "Ready"
7. Window 1: Click "Start Match"
8. Both windows should enter the game simultaneously
9. Both players answer → round reveals → continue → match summary
10. From summary, both return to lobby → host can start a new match

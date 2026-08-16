# Phase 3: Frontend Room UI

> **Prerequisites**: Phases 1-2 must be complete. Backend room endpoints must be working.

## Goal

1. Add "Player Mode" selector to the setup form
2. Add "Join Room" card for guests
3. Add "Lobby" card showing connected players
4. Create `room.js` client module for REST + WebSocket communication
5. Style the room UI

---

## File 1: Create `static/js/modules/room.js`

This module handles all room communication (REST + WebSocket).

```javascript
/**
 * Room client for online multiplayer.
 * Manages REST calls to /api/room/* and a WebSocket connection for real-time events.
 */

export class RoomClient {
  constructor() {
    this.roomId = null;
    this.playerToken = null;
    this.joinCode = null;
    this.isHost = false;
    this.ws = null;
    this._eventHandlers = {};
    this._reconnectAttempts = 0;
    this._maxReconnectAttempts = 5;
    this._reconnectTimer = null;
  }

  /** Register an event handler. type = RoomEventType string. */
  on(type, callback) {
    if (!this._eventHandlers[type]) this._eventHandlers[type] = [];
    this._eventHandlers[type].push(callback);
  }

  /** Remove an event handler. */
  off(type, callback) {
    if (!this._eventHandlers[type]) return;
    this._eventHandlers[type] = this._eventHandlers[type].filter((cb) => cb !== callback);
  }

  _emit(type, data) {
    const handlers = this._eventHandlers[type] || [];
    for (const handler of handlers) {
      try {
        handler(data);
      } catch (err) {
        console.error(`[RoomClient] Error in handler for ${type}:`, err);
      }
    }
  }

  // --- REST API calls ---

  async _fetch(path, options = {}) {
    const headers = { "Content-Type": "application/json", ...options.headers };
    if (this.playerToken) {
      headers["X-Player-Token"] = this.playerToken;
    }
    const response = await fetch(path, { ...options, headers });
    if (!response.ok) {
      const text = await response.text();
      let message = text;
      try {
        const data = JSON.parse(text);
        message = data.detail || data.message || text;
      } catch (_) {}
      throw new Error(message);
    }
    return response.json();
  }

  async createRoom(hostName, settings) {
    const data = await this._fetch("/api/room/create", {
      method: "POST",
      body: JSON.stringify({ host_name: hostName, settings }),
    });
    this.roomId = data.room_id;
    this.joinCode = data.join_code;
    this.playerToken = data.host_token;
    this.isHost = true;
    this._saveToStorage();
    return data;
  }

  async joinRoom(joinCode, playerName) {
    const data = await this._fetch("/api/room/join", {
      method: "POST",
      body: JSON.stringify({ join_code: joinCode, player_name: playerName }),
    });
    this.roomId = data.room_id;
    this.joinCode = data.join_code;
    this.playerToken = data.player_token;
    this.isHost = false;
    this._saveToStorage();
    return data;
  }

  async toggleReady() {
    return this._fetch(`/api/room/${this.roomId}/ready`, { method: "POST" });
  }

  async startMatch() {
    return this._fetch(`/api/room/${this.roomId}/start`, { method: "POST" });
  }

  async updateSettings(settings) {
    return this._fetch(`/api/room/${this.roomId}/settings`, {
      method: "POST",
      body: JSON.stringify({ settings }),
    });
  }

  async kickPlayer(playerName) {
    return this._fetch(`/api/room/${this.roomId}/kick/${encodeURIComponent(playerName)}`, {
      method: "POST",
    });
  }

  async leaveRoom() {
    const result = await this._fetch(`/api/room/${this.roomId}/leave`, { method: "POST" });
    this._clearStorage();
    this.disconnectWs();
    return result;
  }

  async closeRoom() {
    const result = await this._fetch(`/api/room/${this.roomId}/close`, { method: "POST" });
    this._clearStorage();
    this.disconnectWs();
    return result;
  }

  async getRoomState() {
    return this._fetch(`/api/room/${this.roomId}/state`);
  }

  // --- WebSocket ---

  connectWs() {
    if (this.ws && this.ws.readyState <= WebSocket.OPEN) {
      return; // Already connected or connecting
    }

    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const url = `${protocol}//${window.location.host}/ws/room/${this.roomId}?token=${this.playerToken}`;

    this.ws = new WebSocket(url);

    this.ws.onopen = () => {
      console.log("[RoomClient] WebSocket connected");
      this._reconnectAttempts = 0;
    };

    this.ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        this._emit(msg.type, msg.data);
      } catch (err) {
        console.error("[RoomClient] Failed to parse WS message:", err);
      }
    };

    this.ws.onclose = (event) => {
      console.log("[RoomClient] WebSocket closed:", event.code, event.reason);
      if (event.code !== 1000 && event.code < 4000) {
        this._attemptReconnect();
      }
    };

    this.ws.onerror = (err) => {
      console.error("[RoomClient] WebSocket error:", err);
    };
  }

  disconnectWs() {
    if (this._reconnectTimer) {
      clearTimeout(this._reconnectTimer);
      this._reconnectTimer = null;
    }
    if (this.ws) {
      this.ws.onclose = null; // Prevent reconnect on intentional close
      this.ws.close();
      this.ws = null;
    }
  }

  _attemptReconnect() {
    if (this._reconnectAttempts >= this._maxReconnectAttempts) {
      console.error("[RoomClient] Max reconnect attempts reached");
      this._emit("connection_lost", {});
      return;
    }
    this._reconnectAttempts++;
    const delay = Math.min(1000 * Math.pow(2, this._reconnectAttempts - 1), 10000);
    console.log(`[RoomClient] Reconnecting in ${delay}ms (attempt ${this._reconnectAttempts})`);
    this._reconnectTimer = setTimeout(() => this.connectWs(), delay);
  }

  // --- LocalStorage persistence for reconnection ---

  _saveToStorage() {
    try {
      localStorage.setItem(
        "immich_quiz_room",
        JSON.stringify({
          roomId: this.roomId,
          playerToken: this.playerToken,
          joinCode: this.joinCode,
          isHost: this.isHost,
        })
      );
    } catch (_) {}
  }

  _clearStorage() {
    try {
      localStorage.removeItem("immich_quiz_room");
    } catch (_) {}
  }

  /** Try to restore a previous room session from localStorage. Returns true if found. */
  restoreFromStorage() {
    try {
      const raw = localStorage.getItem("immich_quiz_room");
      if (!raw) return false;
      const data = JSON.parse(raw);
      if (data.roomId && data.playerToken) {
        this.roomId = data.roomId;
        this.playerToken = data.playerToken;
        this.joinCode = data.joinCode;
        this.isHost = data.isHost;
        return true;
      }
    } catch (_) {}
    return false;
  }

  /** Reset all state. */
  reset() {
    this.disconnectWs();
    this._clearStorage();
    this.roomId = null;
    this.playerToken = null;
    this.joinCode = null;
    this.isHost = false;
    this._eventHandlers = {};
    this._reconnectAttempts = 0;
  }
}
```

---

## File 2: Modify `static/index.html`

### Change 1: Add Player Mode selector

Insert this block BEFORE the existing Game Mode selector (`<div class="form-group mode-selection-group">` that contains `game-mode-selector`):

```html
        <div class="form-group mode-selection-group">
          <label data-i18n="setup.player_mode_label">Player Mode</label>
          <div class="mode-buttons" id="player-mode-selector">
            <button type="button" class="mode-btn active" data-mode="local" id="mode-local-btn">
              <span class="mode-title" data-i18n="mode.local">🖥️ Local</span>
              <span class="mode-desc" data-i18n="mode.local_desc">Pass-and-play on one device</span>
            </button>
            <button type="button" class="mode-btn" data-mode="online" id="mode-online-btn">
              <span class="mode-title" data-i18n="mode.online">🌐 Online</span>
              <span class="mode-desc" data-i18n="mode.online_desc">Each player on their own device</span>
            </button>
          </div>
        </div>
```

### Change 2: Add Join Room card

Insert this section AFTER the `setup-card` section and BEFORE the `game-card` section:

```html
    <section id="join-card" class="card hidden">
      <h2 data-i18n="room.join_heading">Join Game Room</h2>
      <div class="join-form">
        <label data-i18n="room.code_label">Room Code</label>
        <input id="join-code-input" class="join-code-input" placeholder="XXXX" maxlength="4"
          autocomplete="off" spellcheck="false" style="text-transform: uppercase; letter-spacing: 0.3em; font-size: 1.5rem; text-align: center;" />
        <label data-i18n="room.name_label">Your Name</label>
        <input id="join-name-input" placeholder="" required />
        <button id="join-room-btn" class="btn-primary" data-i18n="room.join_btn">Join Room</button>
        <button id="join-back-btn" class="btn-secondary" data-i18n="room.back_btn">Back</button>
      </div>
    </section>

    <section id="lobby-card" class="card hidden">
      <h2 data-i18n="room.lobby_heading">Game Lobby</h2>
      <div class="lobby-code-display">
        <span data-i18n="room.code_prefix">Room Code:</span>
        <span id="lobby-join-code" class="lobby-join-code"></span>
        <button id="lobby-copy-code" class="btn-icon" title="Copy code" aria-label="Copy code">📋</button>
      </div>
      <div id="lobby-players" class="lobby-players"></div>
      <div id="lobby-settings-summary" class="lobby-settings-summary"></div>
      <div id="lobby-actions" class="lobby-actions">
        <!-- Dynamically populated: Ready button (guest), Start button (host), Leave/Close button -->
      </div>
    </section>
```

### Change 3: Add a "Join Room" button on setup screen

Below the Start Match submit button (line `<button type="submit" class="btn-primary" data-i18n="setup.start_btn">Start Match</button>`), add:

```html
        <button type="button" id="join-room-show-btn" class="btn-secondary" data-i18n="setup.join_room_btn">Join a Room</button>
```

---

## File 3: Create `static/css/components/room.css`

```css
/* ===== Room / Lobby Styles ===== */

/* Join code display */
.lobby-code-display {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.75rem;
  padding: 1rem;
  margin-bottom: 1.25rem;
  background: rgba(255, 255, 255, 0.06);
  border-radius: 12px;
  border: 1px solid rgba(255, 255, 255, 0.1);
}

.lobby-join-code {
  font-family: 'Space Grotesk', monospace;
  font-size: 2rem;
  font-weight: 700;
  letter-spacing: 0.35em;
  color: var(--accent, #a78bfa);
  user-select: all;
}

.lobby-code-display .btn-icon {
  background: none;
  border: none;
  font-size: 1.25rem;
  cursor: pointer;
  padding: 0.25rem;
  opacity: 0.7;
  transition: opacity 0.2s;
}
.lobby-code-display .btn-icon:hover {
  opacity: 1;
}

/* Player list */
.lobby-players {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  margin-bottom: 1.25rem;
}

.lobby-player-row {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.625rem 1rem;
  background: rgba(255, 255, 255, 0.04);
  border-radius: 8px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  transition: border-color 0.3s, background 0.3s;
}

.lobby-player-row.is-ready {
  border-color: rgba(52, 211, 153, 0.4);
  background: rgba(52, 211, 153, 0.08);
}

.lobby-player-row.is-disconnected {
  opacity: 0.4;
}

.lobby-player-name {
  flex: 1;
  font-weight: 500;
}

.lobby-player-badge {
  font-size: 0.75rem;
  padding: 0.15rem 0.5rem;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.1);
}
.lobby-player-badge.host {
  background: rgba(251, 191, 36, 0.2);
  color: #fbbf24;
}

.lobby-player-status {
  font-size: 1.1rem;
}

.lobby-player-kick {
  background: none;
  border: none;
  color: rgba(239, 68, 68, 0.7);
  cursor: pointer;
  font-size: 0.85rem;
  padding: 0.2rem 0.4rem;
  border-radius: 4px;
  transition: color 0.2s, background 0.2s;
}
.lobby-player-kick:hover {
  color: #ef4444;
  background: rgba(239, 68, 68, 0.1);
}

/* Lobby actions */
.lobby-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem;
  justify-content: center;
  margin-top: 1rem;
}

/* Settings summary */
.lobby-settings-summary {
  font-size: 0.85rem;
  opacity: 0.7;
  text-align: center;
  margin-bottom: 0.75rem;
  line-height: 1.6;
}

/* Join form */
.join-form {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.join-code-input {
  text-transform: uppercase;
  letter-spacing: 0.3em;
  font-size: 1.5rem;
  text-align: center;
  font-family: 'Space Grotesk', monospace;
}

/* Waiting indicator (used during gameplay) */
.waiting-indicator {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.5rem;
  padding: 1.5rem;
  text-align: center;
}

.waiting-players {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  justify-content: center;
}

.waiting-player-chip {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  padding: 0.3rem 0.7rem;
  border-radius: 999px;
  font-size: 0.85rem;
  background: rgba(255, 255, 255, 0.08);
  border: 1px solid rgba(255, 255, 255, 0.1);
}
.waiting-player-chip.done {
  background: rgba(52, 211, 153, 0.15);
  border-color: rgba(52, 211, 153, 0.3);
}
```

### Change: Add import to `static/css/style.css`

Add this line to the existing imports in `static/css/style.css`:

```css
@import "components/room.css";
```

---

## File 4: Modify `static/js/modules/state.js`

Add these fields to the `state` object (after the existing `gameMode` field):

```javascript
  playerMode: "local", // "local" | "online"
  roomId: null,
  joinCode: null,
  playerToken: null,
  isHost: false,
  roomPlayers: [],
  roomClient: null,
```

Add these element references to the `el` object:

```javascript
  joinCard: document.getElementById("join-card"),
  lobbyCard: document.getElementById("lobby-card"),
  joinCodeInput: document.getElementById("join-code-input"),
  joinNameInput: document.getElementById("join-name-input"),
  joinRoomBtn: document.getElementById("join-room-btn"),
  joinBackBtn: document.getElementById("join-back-btn"),
  joinRoomShowBtn: document.getElementById("join-room-show-btn"),
  lobbyJoinCode: document.getElementById("lobby-join-code"),
  lobbyCopyCode: document.getElementById("lobby-copy-code"),
  lobbyPlayers: document.getElementById("lobby-players"),
  lobbySettingsSummary: document.getElementById("lobby-settings-summary"),
  lobbyActions: document.getElementById("lobby-actions"),
```

---

## File 5: Modify `static/js/modules/i18n.js`

Add these translation keys to BOTH the `en` and `pt` sections:

### English:
```javascript
"setup.player_mode_label": "Player Mode",
"setup.join_room_btn": "Join a Room",
"mode.local": "🖥️ Local",
"mode.local_desc": "Pass-and-play on one device",
"mode.online": "🌐 Online",
"mode.online_desc": "Each player on their own device",
"room.join_heading": "Join Game Room",
"room.code_label": "Room Code",
"room.name_label": "Your Name",
"room.join_btn": "Join Room",
"room.back_btn": "Back",
"room.lobby_heading": "Game Lobby",
"room.code_prefix": "Room Code:",
"room.ready_btn": "Ready",
"room.not_ready_btn": "Not Ready",
"room.start_btn": "Start Match",
"room.leave_btn": "Leave Room",
"room.close_btn": "Close Room",
"room.waiting_host": "Waiting for host to start...",
"room.all_ready": "All players ready!",
"room.player_joined": "{0} joined the room",
"room.player_left": "{0} left the room",
"room.player_kicked": "{0} was kicked from the room",
"room.copied": "Copied!",
"room.create_btn": "Create Room",
```

### Portuguese:
```javascript
"setup.player_mode_label": "Modo de Jogo",
"setup.join_room_btn": "Entrar em uma Sala",
"mode.local": "🖥️ Local",
"mode.local_desc": "Passar e jogar em um dispositivo",
"mode.online": "🌐 Online",
"mode.online_desc": "Cada jogador em seu próprio dispositivo",
"room.join_heading": "Entrar na Sala",
"room.code_label": "Código da Sala",
"room.name_label": "Seu Nome",
"room.join_btn": "Entrar",
"room.back_btn": "Voltar",
"room.lobby_heading": "Saguão do Jogo",
"room.code_prefix": "Código da Sala:",
"room.ready_btn": "Pronto",
"room.not_ready_btn": "Não Pronto",
"room.start_btn": "Iniciar Partida",
"room.leave_btn": "Sair da Sala",
"room.close_btn": "Fechar Sala",
"room.waiting_host": "Esperando o anfitrião iniciar...",
"room.all_ready": "Todos os jogadores prontos!",
"room.player_joined": "{0} entrou na sala",
"room.player_left": "{0} saiu da sala",
"room.player_kicked": "{0} foi removido da sala",
"room.copied": "Copiado!",
"room.create_btn": "Criar Sala",
```

---

## Acceptance Criteria

1. Setup screen shows Player Mode selector (Local/Online toggle buttons)
2. "Join a Room" button is visible on setup screen
3. Clicking "Join a Room" shows the join card with code + name inputs
4. Lobby card renders correctly with player list
5. `RoomClient` can create/join rooms and connect WebSocket
6. All CSS is properly imported and renders
7. Translations work in both EN and PT
8. Existing local mode game flow is completely unaffected

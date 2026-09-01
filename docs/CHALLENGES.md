# Multiplayer Challenges (Async & Hybrid)

Immich Quiz features **Multiplayer Challenge Mode**, enabling multi-device trivia matches across your Immich library. A host creates a match seed that generates an unguessable capability URL, allowing friends to play asynchronously at their own pace or socially in a hybrid group call.

---

## 1. Core Concepts

### Asynchronous vs. Hybrid Multiplayer
- **Asynchronous Play**: Friends can open the capability link anytime within the configurable expiration window on their mobile phone or desktop, playing through rounds at their own convenience.
- **Hybrid "Socially Synced" Play**: Friends jump on a Discord, Google Meet, or living room call and open the same link together. While each player interacts with their own device, the **Round Reveal Screen** polls the server every 3 seconds, dropping friends' pins onto the map with animated pulses as they finish each round.

### Capability URLs & Unguessable Tokens
Challenges do not require player login accounts or complex authentication. Instead, each challenge is protected by a **128-bit unguessable capability token** (e.g. `ch_9f8e2a...` generated via `secrets.token_urlsafe(16)`).
Anyone with the link can participate or view results, while unauthorized users cannot guess or brute-force active match tokens.

### Deterministic Scoring Fairness (Frozen Decay Constants)
In local matches, exponential decay constants adapt dynamically to the geographic and temporal spread of selected photos. For challenges, the decay formulas:
- **Location**: $\text{score} = 100 \times e^{-\text{distance\_km} / \text{location\_decay\_km}}$
- **Date**: $\text{score} = 100 \times e^{-\text{date\_diff\_days} / \text{date\_decay\_days}}$

are computed **once** at challenge creation time from the selected photo pool and frozen into `config_json`. Every participant faces identical mathematical scoring curves and map bounding boxes regardless of when they play.

---

## 2. Host Creation & Management

### Creating a Challenge
1. Open the game setup screen and configure game settings (Mode: **Pinpoint** or **Album Shuffle**, Targets: **Location**, **Date**, or **Both**, Rounds, Round Length, and Library Filters).
2. Click **🎮 Prepare Game** to open the match preparation modal.
3. Switch to the **Challenge Link** tab:
   - **Challenge Title**: Auto-generated from active filter criteria (e.g. *"Summer Vacation 2024 (10 Rounds)"*) or custom-edited.
   - **Expiration Window**: Choose when the challenge closes:
     - `1h` — Quick party match
     - `6h` — Evening game night
     - `24h` — Daily challenge (default)
     - `48h` — Weekend match
     - `7d` — Week-long competition
     - `Never` — Permanent link
   - **Host Name**: Enter your player name.
4. Click **Create Challenge**. The server pre-selects the photo pool, computes frozen decay constants, stores the challenge, and returns the capability link and an instant SVG QR code.
5. Click **📋 Copy Link** or scan the QR code to share with friends.

### The Challenges Hub (`/challenges`)
The **Challenges Hub** provides an administrative overview of all challenges:
- **Toolbar & Filtering**:
  - **Search**: Live filter by challenge title, host name, album, or tagged person.
  - **Status Pills**: Filter by **All**, **Active**, or **Expired**.
  - **Game Mode Filter**: Filter by **Pinpoint** or **Album Shuffle**.
  - **Sorting**: Sort by *Newest First*, *Most Players*, *Ending Soonest*, or *Title (A–Z)*.
- **Card Actions**:
  - **Share Drawer**: Click the share icon (`🔗`) in the header to expand a drawer with the full URL, 1-click clipboard copy, and high-resolution SVG QR code.
  - **Standings Drawer**: Toggle **View Standings** to inspect live participant progress, accuracy percentages, completed rounds (e.g. `5/5` vs `2/5`), and current rankings.
  - **Play / Results Button**: Active challenges display a **Play Challenge** button; expired challenges display a **Results** deep link navigating to the Grand Reveal summary.
  - **Deactivation**: Hosts can immediately stop an active challenge using the deactivation button.

---

## 3. Participant Gameplay Lifecycle

```
Landing Screen (/play/:token)
       │
       ▼
In-Game Round (#game-card)
       │ (submit guess or timer expires)
       ▼
Personal Reveal & Social Polling (#reveal-ui)
       │ (repeat for rounds 1..N-1)
       ▼
Round N Submitted
       │
       ▼
Post-Game Intermission (.challenge-invite)
       │ (click "See Results")
       ▼
Grand Reveal Summary (/play/:token/summary)
```

### 1. Landing & Session Resume (`/play/:token`)
- **New Players**: Enter a player name. An avatar circle dynamically previews the participant's initial and assigned color palette in real-time.
- **Returning Players**: If a player has an active session on the device, a two-path card appears:
  1. *Resume Active Session*: Shows player avatar, name, and a one-click resume button to continue where they left off.
  2. *Play as Someone Else*: Form to start a fresh attempt under a different name (ideal for shared family tablets or computers).
- **Expired Challenges**: Displays a status notice and a direct **🏆 See Results** button so past matches remain viewable.

### 2. In-Game Round Gameplay
- Single-player experience matching local game rules (Pinpoint map pin & date picker, or Album Shuffle card reordering and pin matching).
- Local restart buttons are hidden to prevent accidental session abandonment.
- Turn timer features smooth 60 FPS transitions with audible ticks under 10s. If the timer expires, inputs freeze and zero points are scored cleanly.

### 3. Personal Reveal & Live Social Polling
- Immediately shows personal performance: distance error in kilometers, date error, points awarded, and true location/date.
- The reveal map displays the actual star location and the player's guess connected by a dashed polyline.
- **3-Second Background Polling**: While reviewing the round, the client polls the server. As friends complete that round, their colored pins drop into the map with pulse animations and their scores append to the round score table live.
- Tab background throttling: Polling pauses when the browser tab is hidden to conserve bandwidth and battery.

### 4. Post-Game "Invite Friends" Intermission
- Shown to **all players** upon completing the final round.
- Features celebratory header, direct challenge URL copy button, collapsible SVG QR code, and a live finisher tally:
  > *"You + 2 friends have finished"*
- Players click **🏆 See Results** when ready to view the podium.

### 5. Grand Reveal / Final Summary (`/play/:token/summary`)
- Gold confetti and fanfare audio play upon entry.
- **Provisional vs. Settled Podium**:
  - If only 1 player has completed the match: A *Provisional Standings* notice explains that rankings may shift as friends finish.
  - If $\ge 2$ players have finished: Displays a full 3D podium with medals (`🥇 1`, `🥈 2`, `🥉 3`).
- **Awards Section**: Awards such as *Sharpshooter*, *Speed Demon*, and *Globetrotter*.
- **Visual Match Review**:
  - **Pinpoint Mode**: An interactive **Round Carousel** with photo preview, fullscreen SVG lightbox, scatter map of all players' guesses and connector lines, and date comparison chips.
  - **Album Shuffle Mode**: A **World Journey Map** with spiderfy pin clustering and a **Polaroid Gallery** of all round photos.
- **Navigation Actions**: 1-click buttons to *Copy Invite Link*, *Copy Summary Link*, visit the *Challenges Hub*, or return *Home*.

---

## 4. Anti-Cheat & Security Model

Immich Quiz implements defense-in-depth protections for challenge matches:

### 1. Server-Enforced Fog of War
- When querying `GET /api/challenge/{token}/leaderboard`, the server strictly withholds round answers and player guesses for future rounds:
  - If a player is on Round $k$, they can only see round history and guesses for rounds $\le k - 1$.
  - Unauthenticated requests on active matches receive empty `round_history: []` and `round_guesses: []`.
  - True photo coordinates, dates, and other players' guesses are only exposed after the player completes the round, or when the challenge concludes.

### 2. EXIF & GPS Metadata Stripping
- Image thumbnails are proxied through FastAPI (`GET /api/media/{asset_id}`).
- All EXIF metadata, GPS latitude/longitude tags, and camera timestamps are stripped in-memory before streaming image bytes to the client. Inspecting images in browser DevTools or Network tabs reveals no location or date data.

### 3. Asset Authorization via Capability Tokens
- Media proxy endpoints require proof of authorization:
  - Local matches require an active in-memory `match_id`.
  - Challenge matches verify that the requested `asset_id` belongs to an active or valid challenge seed. Arbitrary asset probing is blocked with HTTP 404.

### 4. Server-Side Timer Grace Window
- Active answer duration (`time_taken_seconds`) is tracked client-side and validated on the backend.
- Submissions exceeding `round_length_seconds + 5.0s` (network latency grace window) are flagged or rejected to prevent client-side timer tampering.

---

## 5. Reverse Proxy & Zero Trust Deployment

When hosting Immich Quiz behind Cloudflare Zero Trust, Traefik, Nginx, or Caddy, public challenge paths must be allowed while protecting administrative interfaces.

### Path Protection Rules
| Path | Access Level | Description |
|:---|:---|:---|
| `/play/*` | **Public** | Challenge landing, participant join, and match summary |
| `/api/challenge/*` | **Public** | Capability-token authenticated challenge endpoints |
| `/media/*` | **Public** | Metadata-scrubbed thumbnail proxy (authorized by asset ID) |
| `/static/*` | **Public** | Frontend assets (JS, CSS, audio, icons) |
| `/api/challenge/create` | **Protected / Host** | Challenge creation (protect with Zero Trust / HTTP Basic Auth) |
| `/api/challenge/*/stop` | **Protected / Host** | Challenge termination |
| `/challenges` | **Protected / Host** | Challenges Hub management page |
| `/api/sync*` | **Protected / Admin** | Metadata synchronization triggers |

### Example Nginx Configuration
```nginx
server {
    listen 443 ssl http2;
    server_name quiz.example.com;

    # Public Challenge Paths
    location /play/ {
        proxy_pass http://127.0.0.1:8010;
    }
    location /api/challenge/ {
        proxy_pass http://127.0.0.1:8010;
    }
    location /media/ {
        proxy_pass http://127.0.0.1:8010;
    }
    location /static/ {
        proxy_pass http://127.0.0.1:8010;
    }

    # Protected Admin & Creation Routes
    location /api/challenge/create {
        auth_basic "Host Authorization";
        auth_basic_user_file /etc/nginx/.htpasswd;
        proxy_pass http://127.0.0.1:8010;
    }
    location /challenges {
        auth_basic "Host Authorization";
        auth_basic_user_file /etc/nginx/.htpasswd;
        proxy_pass http://127.0.0.1:8010;
    }
}
```

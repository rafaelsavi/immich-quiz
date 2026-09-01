# How to Play Immich Quiz

Immich Quiz turns your personal Immich photo collection into an engaging trivia game. Test how well you and your friends remember where photos were taken, when they were captured, or both!

The game supports two distinct play modes:

1. **👥 Local Match (Pass & Play)**: Gather around a single computer, tablet, or living room TV and take turns passing the device between rounds.
2. **🌐 Multiplayer Challenges (Async & Hybrid)**: Generate a capability link or QR code so friends can play from their own phones or computers—either asynchronously at their own pace or socially in a group voice call.

---

## Setting Up a Match

All games begin on the main setup screen. Once configured, clicking **🎮 Prepare Game** opens a dialog allowing you to choose between launching a **Local Match** or creating a **Challenge Link**.

### 1. Game Mode

- **🎯 Pinpoint**: 1 photo per round. Players place a pin on an interactive Leaflet map and/or guess the month and year of capture.
- **🔀 Album Shuffle**: 3 photos per round. Players match photos to lettered map pins (**A**, **B**, **C**) and/or arrange the photos in chronological sequence along a timeline.

### 2. What to Guess (Targets)

- **Location only**: Guess where the photo was taken on the world map.
- **Date only**: Guess the month and year the photo was captured.
- **Location & Date**: Score points for both geographical proximity and temporal accuracy.

### 3. Match Parameters

- **Rounds**: Choose **5**, **10**, or **20** rounds per match.
- **Round Length**: Set a turn timer: **30s**, **1 min**, **2 min**, **5 min**, or **Unlimited**.
  - Timers feature silky-smooth 60 FPS transitions, adaptive formatting (`2:00` → `1:15` → `59s` → `5s`), and shifting color gradients (teal → amber → crimson).
  - Subtle audio ticks play at 10s and accelerate smoothly as time expires.
  - On timeout, inputs freeze, a yellow time-up banner appears, and zero points are scored cleanly.

### 4. Library & Photo Filters (Optional)

Expand the **Library & Photo Filters** accordion to tailor your photo candidate pool:

- **Libraries**: Select one or more Immich media libraries, or select all.
- **Albums**: Search and select specific albums (e.g. *"Summer Vacation 2024"*).
- **Date Range**: Use the dual-handle interactive timeline slider to restrict photos to a specific year/month span.
- **Countries & Cities**: Searchable multi-select dropdowns. Selecting a country dynamically narrows the available cities to that country.
- **People / Faces**: Filter by recognized people:
  - **Any (ANY)**: Photos containing at least one of the selected individuals.
  - **All (ALL)**: Photos where all selected individuals appear together.
- **Shared & Partner Media**: Toggles to include or exclude shared albums and partner photos.

### 5. Live Preflight Validation

As you adjust filters, a live preflight indicator validates your library in real-time, verifying that enough diverse, geotagged, and dated photos exist to satisfy your match requirements.

---

## Play Mode 1: 👥 Local Match (Pass & Play)

Designed for parties, family gatherings, or solo play on a single screen.

### 1. Setup & Player Roster

- In the **Local Match** tab of the Prepare Game modal, add players using the tag input (type a name and press **Enter** or **,**).
- Each player receives an assigned avatar badge color and distinct marker style.
- Click **Start Match** to launch the game.

### 2. Pass the Device

- Before each turn, a privacy curtain hides the upcoming photo (`Pass device to [Player]`).
- Hand the device to the active player and click **I'm Ready** to reveal the photo and start the timer.

### 3. Making Your Guess

- **Inspect Photo**: Click the photo or the fullscreen expand icon (`⛶`) to inspect details in high resolution with the modal lightbox.
- **Pinpoint Location**: Click or drag your pin on the world map. Use the **Focus region** button to snap back to the album's auto-framed bounding box.
- **Pinpoint Date**: Pick the month and year using the scroll-wheel-enabled date selectors.
- **Album Shuffle Matching**: Tap a photo card to select it, then tap its matching pin on the map.
- **Album Shuffle Timeline**: Reorder photo cards chronologically using the ▲ and ▼ buttons.
- Click **Submit Guess** when finished.

### 4. Round Reveal

- Once all players finish the round, the reveal screen compares each player's guess to reality:
  - True photo location marked with a gold star, connected to player pins with colored dashed lines indicating distance error in kilometers.
  - Actual capture date compared to guessed dates, with day differences.
  - Point breakdown and celebratory badges for spot-on guesses.
- Click **Next Round** to continue to the next turn.

### 5. Match Summary & Podium

- When all rounds conclude, celebrate with confetti, fanfare audio, and the 3D winner's podium.
- Review the match summary table, performance awards (e.g. 🎯 *Sniper*, ⏳ *Time Traveler*, ⚡ *Speed Demon*), interactive **World Journey Map**, and the **Match Memory Cards** polaroid gallery.

---

## Play Mode 2: 🌐 Multiplayer Challenges (Async & Hybrid)

Allows anyone with a browser to join a shared game on their own device.

### 1. Generating a Challenge

- In the **Challenge Link** tab of the Prepare Game modal, choose an expiration window (`1h`, `6h`, `24h`, `48h`, `7d`, or `Never`) and enter the host name.
- Click **Create Challenge** to generate an unguessable capability URL and an instant SVG QR code.
- Share the link or QR code via chat, messaging, or email.

### 2. Joining a Challenge (`/play/:token`)

- Friends open the link on mobile or desktop without needing an account.
- **New Players**: Type a name; a live preview circle displays their assigned avatar color and initials in real-time.
- **Returning Players**: If a player has played on the device before, a two-path layout offers:
  1. *Resume Active Session*: One-click button to resume their exact round.
  2. *Play as Someone Else*: Form to start a fresh attempt under a different name.

### 3. Gameplay Rounds

- Players play through rounds on their own devices with the full interactive map, date pickers, photo lightbox, and turn timer.
- Restart buttons are hidden to prevent accidental session abandonment.

### 4. Round Reveal & Live Opponent Polling

- After submitting a guess, players immediately see their personal distance error, date difference, points, and map polyline.
- **Social Polling (3s)**: While reviewing the reveal screen, the app polls the server. As friends complete the round, their colored pins drop into the map with animated pulses and sound cues, and the score table updates live!

### 5. Post-Game "Invite Friends" Intermission

- Shown to **all players** upon completing the final round.
- Provides a direct link copy button, expandable SVG QR code for friends nearby, and a live tally:
  > *"You + 2 friends have finished"*
- Players click **🏆 See Results** when ready to view the podium.

### 6. Grand Reveal Summary (`/play/:token/summary`)

- Features gold confetti, fanfare audio, and a 3D podium:
  - **Provisional Standings**: Displayed if only 1 player has completed the match.
  - **Settled Podium**: Displays ranks, crowns, medals, and completed round counts (`5/5`).
- **Mode-Specific Review**:
  - *Pinpoint*: Interactive **Round Carousel** with photo preview, lightbox zoom, multi-player scatter map with connector lines, and date comparison chips.
  - *Album Shuffle*: Full **World Journey Map** with spiderfy clustering and **Match Memory Cards** polaroid gallery.
- **Quick Actions**: Buttons to *Copy Invite Link*, *Copy Summary Link*, open the *Challenges Hub*, or return *Home*.

---

## The Challenges Hub (`/challenges`)

Navigate to the **Challenges Hub** via the header navbar to track and manage all multiplayer matches:

- **Search & Filter**: Search by title, host, album, or tagged person. Filter by status (**All**, **Active**, **Expired**) or game mode (**Pinpoint**, **Album Shuffle**).
- **Share Drawer**: Expand any challenge card's header share button (`🔗`) to view the direct URL and scan the SVG QR code.
- **Standings Drawer**: Click **View Standings** to inspect real-time participant progress, completed round counts, and scores without leaving the hub.
- **Play / Results**: Direct action button to play active challenges or jump directly to the Grand Reveal summary for concluded matches.

---

## Scoring & Awards

- **Exponential Decay**: Points are awarded on a 0–100 scale using pool-adaptive exponential decay formulas. See [SCORING.md](SCORING.md) for full mathematical specifications.
- **Performance Awards**: Earned at the end of matches for exceptional play:
  - 🎯 **Sniper**: Most perfect location guesses (<100m).
  - ⏳ **Time Traveler**: Most perfect date guesses (exact month & year).
  - ⚡ **Speed Demon**: Fastest average response time with zero timeouts.
  - Full award criteria are detailed in [AWARDS.md](AWARDS.md).
- **Persistent Leaderboard**: All matches are recorded in SQLite (`data/leaderboard.db`) and displayed on the home page leaderboard with dedicated badges for `👥 Local` and `🌐 Challenge` play modes.

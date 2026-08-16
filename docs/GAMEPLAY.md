# How to Play Immich Quiz

Immich Quiz is a pass-and-play trivia game that tests how well you know your photos. Gather your friends on the same device and take turns guessing where each photo was taken, when it was captured, or both!

---

## Setting Up a Game

Customize your match on the setup screen:

### 1. Player Settings
- **Players**: Add players using the interactive tag input. Type a name and press **Enter** or **,** (comma), or paste comma-separated lists. Each player gets a distinctive avatar color.
- **Rounds**: Choose the number of rounds per player: **5**, **10**, or **20** rounds.
- **Round Length**: Set a turn timer: **30s**, **1 min**, **2 min**, **5 min**, or **Unlimited**.

### 2. Library & Photo Filters (Optional)
Expand the **Library & Photo Filters** accordion to customize your photo pool. An active filter count badge reflects your selections:
- **Library**: Select which Immich media library to pull photos from.
- **Albums**: Search and select one or more albums, or leave empty for the full library.
- **Date Range**: Use the dual-handle interactive timeline slider to restrict photos to a specific year/month span.
- **Countries & Cities**: Searchable multi-select dropdowns for geographic filtering. Selecting a country dynamically narrows the available cities to that country.
- **People / Faces**: Filter by recognized people. When selecting multiple people, choose between:
  - **Any (OR)**: Photos containing at least one of the selected individuals.
  - **All (AND)**: Photos where all selected individuals appear together in the same photo.
- **Shared & Partner Media**: Checkbox toggles to dynamically include or exclude shared albums and partner photos.

### 3. Game & Guessing Mode
- **Game Mode**:
  - **🎯 Pinpoint**: One photo per turn. Players guess location on a world map and/or capture date.
  - **🔀 Album Shuffle**: 3 photos at once. Match photos to lettered map pins and/or arrange them chronologically.
- **Guess Mode**: Choose to guess **Location**, **Date**, or **Both**.

### 4. Live Preflight Validation
As you adjust filters, a live preflight indicator validates your library to ensure enough diverse, eligible photos exist. The **Start Match** button activates once requirements are met.

---

## Game Modes

### 🎯 Pinpoint

In **Pinpoint**, players take turns guessing photos individually.

#### 1. Pass the Device
Before each turn, a privacy screen hides the upcoming photo. Hand the device to the active player and press **I'm Ready** to start the turn.

#### 2. Make Your Guess
- **Photo**: Tap the photo to inspect it in high-resolution fullscreen.
- **Location**: Drag and drop your pin on the interactive world map. You can zoom freely or open the map in fullscreen.
- **Date**: Pick the month and year you think the photo was taken (scroll wheel enabled).
- **Smart Auto-Framing**: When playing regional or vacation albums, the guess map automatically opens framed to that region. Tap the **Focus region** button anytime to snap back.
- Tap **Submit** when you are done. If the turn timer expires, your current pin and date are submitted automatically.

#### 3. The Reveal
Once all players have taken their turn, the reveal screen shows:
- **Location**: Your pin compared to the true photo coordinates, connected by a dashed line showing distance error in kilometers.
- **Date**: Your guessed date compared to the real month, year, and day error.
- **Points & Badges**: Points awarded based on proximity. Spot-on guesses earn celebratory badges!

---

### 🔀 Album Shuffle

In **Album Shuffle**, players receive a set of 3 photos to solve together.

#### 1. Your Turn
- **Location**: Three lettered pins (**A**, **B**, **C**) appear on the map. Tap a photo card to select it, then tap its matching pin on the map.
- **Date (Timeline)**: Sort the 3 photos chronologically from earliest (top) to latest (bottom) using the ▲ and ▼ reordering buttons.
- Tap **Submit** when you are finished.

#### 2. The Reveal
See true locations and chronology side-by-side with per-player score breakdowns.

---

## Scoring & Achievements

- **Accuracy Matters**: The closer your pin or date is to reality, the higher your score.
- **Performance Awards**: Outstanding performances (e.g., pinpoint accuracy, exact date matching, lightning-fast round submissions) earn end-of-match awards:
  - 🎯 **Sniper**: Player with the most perfect location guesses.
  - ⏳ **Time Traveler**: Player with the most perfect date guesses.
  - ⚡ **Speed Demon**: Fastest player with zero timeouts.
- Full scoring formulas are detailed in [SCORING.md](SCORING.md), and award criteria in [AWARDS.md](AWARDS.md).

---

## Leaderboard

View all-time high scores and match summaries directly from the home screen or at the end of each game. The leaderboard tracks match configurations, player rankings, accuracy percentages, and performance awards stored persistently in SQLite.

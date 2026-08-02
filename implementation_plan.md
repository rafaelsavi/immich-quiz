# Implementation Plan - Game Mode Expansion: "Pinpoint" & "Album Shuffle"

This document outlines the architecture, UI/UX design, scoring algorithms, API contracts, awards rules, and documentation updates for introducing the new **Album Shuffle** (*Álbum Embaralhado*) hybrid game mode alongside the classic **Pinpoint** (*Mira Certa*) game mode in **Immich Quiz**.

---

## 🎯 Game Mode Overview & Naming

| Language | Classic Mode (Single Photo) | New Hybrid Batch Mode |
| :--- | :--- | :--- |
| 🇬🇧 **English** | **Pinpoint** | **Album Shuffle** |
| 🇵🇹 **Português** | **Mira Certa** | **Álbum Embaralhado** |

### **1. Pinpoint (*Mira Certa*)**
* **Gameplay**: One photo per turn. Players guess the map coordinates, the capture month/year, or both.
* **Round Lengths**: `30s`, `1m`, `2m`, `5m`, `unlimited`.
* **Awards**: 🎯 **Sniper** (Location), ⏳ **Time Traveler** (Date), ⚡ **Speed Demon** (Fast turns).

### **2. Album Shuffle (*Álbum Embaralhado*)**
* **Gameplay**: A batch of $N$ photos (e.g. 5, 10, or 20) is presented at once.
  * **Task A (Location Mapping)**: Match each photo to a shuffled map pin (`A`, `B`, `C`, `D`, `E`...).
  * **Task B (Timeline Sorting)**: Arrange the photos into exact chronological order from oldest to newest (`1st`, `2nd`, `3rd`...).
* **Round Lengths**: `30s`, `1m`, `2m`, `5m`, `unlimited` (specifically optimized for `2m` and `5m` batch sessions).
* **Awards**: ⚡ **Speed Demon ONLY** (Fast submission $\le 50\%$ time limit, 0 timeouts). *Sniper* and *Time Traveler* are disabled for Album Shuffle mode.

---

## 📱 Responsive UI/UX Design (Desktop & Mobile)

To provide a premium experience across all screen sizes without drag-and-drop complexity:

1. **Desktop / Wide Layout ($\ge 1024\text{px}$)**:
   * **Side-by-Side Dashboard**: The Leaflet map occupies the main section (65–70% width), while a vertical **Photo & Timeline Control Column** sits on the right side (30–35% width).
   * No vertical scrolling required on desktop; players can see the entire map and the vertical list of photo cards simultaneously.
2. **Mobile / Narrow Layout ($< 1024\text{px}$)**:
   * **Vertical Stack**: Map on top, timeline slots and horizontal photo carousel below.
3. **Photo Cards & Dynamic Live Auto-Sorting**:
   * **Live Auto-Sort**: As the player assigns timeline ranks (`1st`, `2nd`, `3rd`...), photo cards automatically re-order themselves dynamically in real-time to reflect the assigned chronological sequence! Unassigned photos remain grouped at the end.
4. **Two-Tap Assignment**:
   * Tap a Photo Card $\rightarrow$ Tap a Map Pin or Timeline Slot.
   * Visual badge updates on the photo tile (e.g. `[📍 Pin C | ⏱️ 2nd]`).
   * Tapping two photos in sequence swaps their timeline positions.

---

## 🧮 Scoring & Anti-Cheat Rules

### **Album Shuffle Scoring**
1. **Location Match Score (Strict)**:
   * **Strict Pin Match**: Each photo assigned to its exact true map pin earns 100 points ($100 / N$ per photo). Any photo assigned to the wrong pin receives 0 points.
2. **Chronological Timeline Score (No Bonus Points)**:
   * Evaluated strictly using Kendall-Tau inversion count distance:
     $$\text{Score} = \text{SCORE\_MAX\_POINTS} \times \left(1 - \frac{\text{Inversions}}{\text{Max Inversions}}\right)$$
   * No arbitrary extra bonus points.

### **Anti-Cheat Boundary**
* Response from `POST /api/question` contains $N$ media URLs and $N$ shuffled map pin coordinates without linking metadata.
* Answers are validated server-side upon `POST /api/answer`.
* Answers remain hidden until all players submit their reconstructions.

---

## ⚙️ Proposed Code & Documentation Changes

### Backend & API
#### [MODIFY] [models.py](file:///d:/Rafael/Projects/immich-quiz/src/models.py)
* Update `RoundLength` enum to add `minute_2 = '2m'` and `minute_5 = '5m'`.
* Update `GameSetupRequest` to accept `game_mode: str = 'pinpoint'` (`'pinpoint'` vs `'album_shuffle'`).

#### [MODIFY] [routes.py](file:///d:/Rafael/Projects/immich-quiz/src/api/routes.py)
* Handle multi-asset batch questions for `album_shuffle` mode.
* Compute Kendall-Tau timeline scores and distance-weighted pin assignment scores for `album_shuffle` answers.

#### [MODIFY] [scoring.py](file:///d:/Rafael/Projects/immich-quiz/src/scoring.py)
* Add `timeline_inversion_score` and `batch_location_match_score` pure helper functions.

---

### Frontend & UI
#### [MODIFY] [i18n.js](file:///d:/Rafael/Projects/immich-quiz/static/js/modules/i18n.js)
* Add mode titles & descriptions:
  * `"mode.pinpoint"`: `"Pinpoint"` / `"Mira Certa"`
  * `"mode.album_shuffle"`: `"Album Shuffle"` / `"Álbum Embaralhado"`
* Rename `"setup.rounds"`: `"Photos"` / `"Fotos"` (works generically across all game modes).
* Add round timer labels (`2m`, `5m`).

#### [MODIFY] [index.html](file:///d:/Rafael/Projects/immich-quiz/static/index.html)
* Rename label "Rounds" $\rightarrow$ **"Photos"** (**"Fotos"** in PT).
* Re-order setup options so **Game Mode** selector is positioned at the **very bottom** (after Players, Photos, Round length, Library, and Album).
* Extend round length select options to include `2m` and `5m`.

#### [MODIFY] [app.js](file:///d:/Rafael/Projects/immich-quiz/static/js/app.js)
* Update `renderAwards(summary)`: Limit award evaluation in Album Shuffle mode exclusively to ⚡ **Speed Demon**.
* Integrate two-tap selection for Album Shuffle mode interface.

---

### Documentation
#### [MODIFY] [GAMEPLAY.md](file:///d:/Rafael/Projects/immich-quiz/docs/GAMEPLAY.md)
* Document both **Pinpoint** and **Album Shuffle** modes, setup options, timer choices (`2m`, `5m`), and two-tap mobile mechanics.

#### [MODIFY] [AWARDS.md](file:///d:/Rafael/Projects/immich-quiz/docs/AWARDS.md)
* Document that **Album Shuffle** mode awards only **Speed Demon** ⚡ under the 50% time threshold rule.

#### [MODIFY] [SCORING.md](file:///d:/Rafael/Projects/immich-quiz/docs/SCORING.md)
* Add Kendall-Tau inversion formulas and batch pin matching scoring details.

#### [MODIFY] [API.md](file:///d:/Rafael/Projects/immich-quiz/docs/API.md)
* Document `game_mode` field (`pinpoint` vs `album_shuffle`) and `2m`/`5m` round length options.

---

## 🧪 Verification Plan

### Automated Tests
* Run `pytest` to verify all existing and new scoring models.
```powershell
uv run pytest
```
* Verify backend linting and type checking:
```powershell
uv run ruff check .
uv run mypy src
```

### Manual Verification
1. Launch app with `uv run -m src.main`.
2. Test **Pinpoint** mode: Verify round timer options (`30s`, `1m`, `2m`, `5m`, `unlimited`) and end-of-game awards.
3. Test **Album Shuffle** mode: Verify batch photo delivery, two-tap pin and timeline assignments, reveal results, and verify that **only Speed Demon** award is evaluated at match summary.


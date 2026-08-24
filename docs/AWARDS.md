# Performance Awards Guide & Customization

This guide documents all end-of-match performance awards in **Immich Quiz**, their evaluation criteria, default thresholds, and instructions on how to customize them.

---

## 🏆 Summary of Available Awards

| Award             | Icon | Requirement                                  | Description                                                                                                            | Tie-breaker           |
|:------------------|:-----|:---------------------------------------------|:-----------------------------------------------------------------------------------------------------------------------|:----------------------|
| **Sniper**        | 🎯   | `≥ 1 perfect location guess`                 | Awarded to the player with the most **perfect location guesses** (100% score). *Disabled in Album Shuffle mode.*       | Higher location score |
| **Time Traveler** | ⏳    | `≥ 1 perfect date guess`                     | Awarded to the player with the most **perfect date guesses** (100% score). *Disabled in Album Shuffle mode.*           | Higher date score     |
| **Speed Demon**   | ⚡    | `≥ 1 fast round`; `Timed game`; `0 timeouts` | Awarded to the player with the maximum number of fast rounds (submitted within **≤ 50% of the max round time limit**). | Lower total duration  |

> [!NOTE]
> In **Album Shuffle** mode (`game_mode == 'album_shuffle'`), only the **⚡ Speed Demon** award is active.
> If a tie cannot be broken, the award is not given to any player.

---

## 💾 Presentation & Data Architecture

When a match concludes:

1. Performance awards are dynamically evaluated and rendered on the match summary screen via `renderAwards(summary, playerStats)` in `static/js/modules/summary/awards.js`.
2. Raw invariant physical metrics (`distance_km`, `date_diff_days`, `time_taken_seconds`) and total player response times (`total_time_seconds`) are persisted in SQLite (`data/leaderboard.db`).
3. Awards are rendered client-side on-the-fly, allowing award criteria and thresholds to evolve without requiring database schema changes or data migrations.

---

## 🛠️ How to Customize Award Conditions & Thresholds

All award presentation logic is located in `static/js/modules/summary/awards.js` inside the `renderAwards(summary, playerStats)` function, and internationalized in `static/js/modules/i18n.js`.

### 1. Adjusting Award Criteria

Open `static/js/modules/summary/awards.js` and locate `function renderAwards(summary, playerStats)`:

- **Speed Demon time fraction**:
  `elapsedSec <= totalSec / 2` checks for guesses within 50% of the time limit. Change `totalSec / 2` to `totalSec * 0.3` for a stricter 30% speed requirement.

- **Sniper / Time Traveler requirements**:
  Require at least 1 perfect location or date guess (`stats.perfectLocationCount >= 1` and `stats.perfectDateCount >= 1`).

---

### 2. Adding a New Custom Award

To add a new award (e.g. "Clutch Finisher" or "Comeback King"):

1. **Add translation strings** in `static/js/modules/i18n.js` under both `"en"` and `"pt"` sections:

   ```javascript
   "award.my_award": "🚀 Clutch Finisher",
   "award.my_award_desc": "Highest score in the final round",
   ```

2. **Add condition logic** in `static/js/modules/summary/awards.js` inside `renderAwards(summary, playerStats)`:

   ```javascript
   awards.push({
     titleKey: "award.my_award",
     descKey: "award.my_award_desc",
     player: playerName,
   });
   ```

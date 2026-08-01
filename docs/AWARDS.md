# Performance Awards Guide & Customization

This guide documents all end-of-match performance awards in **Immich Quiz**, their evaluation criteria, default thresholds, and instructions on how to customize them.

---

## 🏆 Summary of Available Awards

| Award             | Icon | Description / Criteria                                                                                                                                                                                                                                |
|-------------------|------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| **Sniper**        | 🎯   | Awarded to the player with the most **perfect location guesses** (100% score).<br>**Requirement**: `≥ 1 perfect location guess`.                                                                                       |
| **Time Traveler** | ⏳    | Awarded to the player with the most **perfect date guesses** (100% score).<br>**Requirement**: `≥ 1 perfect date guess`.                                                                                                     |
| **Speed Demon**   | ⚡    | Awarded to the player with the maximum number of fast rounds (submitted within **≤ 50% of the max round time limit**), provided they had **0 timeouts** in the match.<br>**Requirement**: Timed game (`30s` or `1m`), `0 timeouts`, `≥ 1 fast round`. |

---

## 🛠️ How to Customize Award Conditions & Thresholds

All award logic is executed client-side in [`static/js/app.js`](../static/js/app.js) inside the `renderAwards(summary)` function, and internationalized in [`static/js/modules/i18n.js`](../static/js/modules/i18n.js).

### 1. Adjusting Award Criteria

Open [`static/js/app.js`](../static/js/app.js) and locate `function renderAwards(summary)`:

- **Speed Demon time fraction**:
  Currently, `elapsedSec <= totalSec / 2` checks for guesses within 50% of the time limit. Change `totalSec / 2` to `totalSec * 0.3` if you want a stricter 30% speed requirement.

- **Sniper / Time Traveler requirements**:
  Currently require at least 1 perfect location or date guess (`maxLocationPerfect > 0` and `maxDatePerfect > 0`).

---

### 2. Adding a New Custom Award

To add a new award (e.g. "Clutch Finisher" or "Comeback King"):

1. **Add translation strings** in [`static/js/modules/i18n.js`](../static/js/modules/i18n.js) under both `"en"` and `"pt"` sections:

   ```javascript
   "award.my_award": "🚀 Clutch Finisher",
   "award.my_award_desc": "Highest score in the final round",
   ```

2. **Add condition logic** in [`static/js/app.js`](../static/js/app.js) inside `renderAwards(summary)`:

   ```javascript
   awards.push({
     titleKey: "award.my_award",
     descKey: "award.my_award_desc",
     player: playerName,
   });
   ```

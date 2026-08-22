# Scoring System

Immich Quiz awards up to **100 points** for each enabled objective in a round (Location and/or Date). The scoring style depends on the game mode:

- **Pinpoint**: Uses exponential decay—the closer your guess, the more points you get.
- **Album Shuffle**: Uses strict matching—points are split evenly among correctly matched or sequenced photos in the batch.

---

## Pinpoint Game

In Pinpoint mode, you guess where and when an individual photo was taken. Each guess is scored independently from 0 to 100 points based on how close you got.

### 📍 Location Scoring

Points drop off exponentially with distance ($d$) using the Haversine formula (great-circle distance on Earth):

$$\text{Score} = \max\left(0, \text{round}\left(100 \times \exp\left(-\frac{d}{\text{LOCATION\_SCORE\_DECAY\_KM}}\right)\right)\right)$$

- **Default decay**: `LOCATION_SCORE_DECAY_KM = 500` km (configurable in `.env`).
- **How it feels**: Guesses within a few kilometers award almost full points (~99–100). As distance grows into hundreds of kilometers, points taper off smoothly until reaching 0 on the other side of the world.

### 📅 Date Scoring

Because players select a **year and month** rather than a specific calendar day, your guess gives you credit for the entire month!

Error is measured in **days** ($\Delta D$) from the closest boundary of your guessed month:
- **Right on target**: If the photo was taken inside your guessed month, your error is **0 days** $\rightarrow$ **100 points**.
- **Earlier than guess**: Measured in days from the 1st of your guessed month back to the capture date.
- **Later than guess**: Measured in days from the last day of your guessed month to the capture date (accounting for month lengths and leap years).

$$\text{Score} = \max\left(0, \text{round}\left(100 \times \exp\left(-\frac{\Delta D}{\text{DATE\_SCORE\_DECAY\_DAYS}}\right)\right)\right)$$

- **Default decay**: `DATE_SCORE_DECAY_DAYS = 500` days (~16 months, configurable in `.env`).
- **How it feels**: Nailing the month or being off by just a few weeks yields 95–100 points. Being off by several years quickly reduces your score towards 0.

---

## Album Shuffle Game

In **Album Shuffle** mode, 3 photos are shown simultaneously. Points are divided equally across the batch ($N = 3$).

### 📍 Location Scoring

- Each photo matched to its correct map pin earns a proportional share of the 100 points:

$$\text{Location Score} = \max\left(0, \text{round}\left(\frac{\text{correct\_pins}}{N} \times 100\right)\right)$$

*(e.g., 3/3 = 100 pts, 2/3 = 67 pts, 1/3 = 33 pts, 0/3 = 0 pts)*

### 📅 Date Scoring

- Each photo placed in its correct chronological order on the timeline earns a proportional share of the 100 points:

$$\text{Date Score} = \max\left(0, \text{round}\left(\frac{\text{correct\_ranks}}{N} \times 100\right)\right)$$

---

## Exponential Decay Quick Reference

Here is how scores translate for common distance/time errors across different decay settings:

| Error (Distance / Time) | Decay = 100 | Decay = 200 | Decay = 300 | Decay = 500 *(default)* | Decay = 750 | Decay = 1000 |
|:---|:---|:---|:---|:---|:---|:---|
| **1 (1 km / 1 day)**    | 99          | 100         | 100         | **100**                 | 100         | 100          |
| **5 (5 km / 5 days)**   | 95          | 98          | 98          | **99**                  | 99          | 100          |
| **10 (10 km / 10 days)**| 90          | 95          | 97          | **98**                  | 99          | 99           |
| **100 (~3 months)**     | 37          | 61          | 72          | **82**                  | 88          | 90           |
| **500 (~1.5 years)**    | 1           | 8           | 19          | **37**                  | 51          | 61           |
| **1000 (~3 years)**     | 0           | 1           | 4           | **14**                  | 26          | 37           |

---

## Match Totals & Accuracy

- **Max Possible Score**: Each round contributes up to 100 points per enabled objective (100 if location-only or date-only, 200 if both are enabled).
  $$\text{MaxPossibleScore} = \text{roundsPlayed} \times \left((\text{100 if location\_mode}) + (\text{100 if date\_mode})\right)$$

- **Accuracy (%)**: Your overall performance across the match expressed as a percentage:
  $$\text{Accuracy (\%)} = \text{round}\left(\frac{\text{TotalScore}}{\text{MaxPossibleScore}} \times 100, 1\right)$$

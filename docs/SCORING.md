# Scoring

Each enabled goal is scored using exponential decay (for Pinpoint) or proportional strict matching (for Album Shuffle), configured via environment variables. Defaults:

- `SCORE_MAX_POINTS = 100`

---

## Pinpoint Game

In **Pinpoint** mode, scores are calculated based on the error of the individual guesses.

### Location Score

The location score uses the following parameter:

- `LOCATION_SCORE_DECAY_KM = 500`

Distance $d$ is computed in km using the Haversine formula.

$$\text{Score} = \max\left(0, \text{round}\left(\text{SCORE\_MAX\_POINTS} \times \exp\left(-\frac{d}{\text{LOCATION\_SCORE\_DECAY\_KM}}\right)\right)\right)$$

### Date Score

The date score uses the following parameter:

- `DATE_SCORE_DECAY_DAYS = 500`

The player only guesses a **year and a month**, so the guess covers that whole month. Scoring is measured in **days** ($\Delta D$), using whichever month boundary faces the actual capture date:

- Actual date is inside the guessed month $\rightarrow \Delta D = 0$
- Actual date is earlier $\rightarrow \Delta D = \text{days from the 1st of the guessed month}$
- Actual date is later $\rightarrow \Delta D = \text{days from the last day of the guessed month}$

(The last day calculation accounts for variable month lengths and leap years.)

$$\text{Score} = \max\left(0, \text{round}\left(\text{SCORE\_MAX\_POINTS} \times \exp\left(-\frac{\Delta D}{\text{DATE\_SCORE\_DECAY\_DAYS}}\right)\right)\right)$$

---

## Album Shuffle Game

In **Album Shuffle** mode, the score of a round is computed across the batch of $N=3$ photos.

### Location Score

- Each photo correctly matched to its corresponding map pin earns proportional points:

$$\text{Location Score} = \max\left(0, \text{round}\left(\frac{\text{correct\_pins}}{N} \times \text{SCORE\_MAX\_POINTS}\right)\right)$$

### Date Score

- Each photo placed in its exact sequence position (timeline index matching true chronological order rank) earns proportional points:

$$\text{Date Score} = \max\left(0, \text{round}\left(\frac{\text{correct\_ranks}}{N} \times \text{SCORE\_MAX\_POINTS}\right)\right)$$

---

## Exponential Decay Scoring Reference Table

Common score outputs for exponential decay with $\text{SCORE\_MAX\_POINTS} = 100$:

| Error Value (km / days) | Decay = 100 | Decay = 200 | Decay = 300 | Decay = 500 | Decay = 750 | Decay = 1000 |
|:---|:---|:---|:---|:---|:---|:---|
| **1 (1 day)**           | 99          | 100         | 100         | 100         | 100         | 100          |
| **5 (1 week)**          | 95          | 98          | 98          | 99          | 99          | 100          |
| **10 (2 weeks)**        | 90          | 95          | 97          | 98          | 99          | 99           |
| **100 (3 months)**      | 37          | 61          | 72          | 82          | 88          | 90           |
| **500 (1.5 years)**     | 1           | 8           | 19          | 37          | 51          | 61           |
| **1000 (3 years)**      | 0           | 1           | 4           | 14          | 26          | 37           |

---

## Match Totals

$$\text{MaxPossibleScore} = \text{roundsPlayed} \times \left((\text{SCORE\_MAX\_POINTS if location\_mode}) + (\text{SCORE\_MAX\_POINTS if date\_mode})\right)$$

$$\text{Accuracy (\%)} = \text{round}\left(\frac{\text{TotalScore}}{\text{MaxPossibleScore}} \times 100, 1\right)$$

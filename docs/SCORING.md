# Scoring

Each enabled goal is scored using exponential decay, with parameters from
environment variables. Defaults:

- `SCORE_MAX_POINTS = 100`

## Pinpoint Game

For Pinpoint game mode, score is calculated based on the error of the gueeses.

### Location Score

The location score uses the following environment variables:

- `LOCATION_SCORE_DECAY_KM = 500`

Distance d is computed in km using Haversine.

- score = round(SCORE_MAX_POINTS * exp(-d / `LOCATION_SCORE_DECAY_KM`)), clamped to 0

### Date Score

The date score uses the following environment variables:

- `DATE_SCORE_DECAY_DAYS = 500`

The player only guesses a **year and a month**, so the guess covers that whole
month. Scoring is still measured in **days**, using whichever month boundary
faces the actual capture date:

- Actual date is inside the guessed month -> DeltaD = 0
- Actual date is earlier -> DeltaD = days from the **1st** of the guessed month
- Actual date is later -> DeltaD = days from the **last day** of the guessed month

(The last day accounts for month length and leap years.)

- score = round(SCORE_MAX_POINTS * exp(-DeltaD / `DATE_SCORE_DECAY_DAYS`)), clamped to 0

## Album Shuffle Game

In **Album Shuffle** mode, the score of a round is computed over the entire batch of $N=3$ photos.

### Location Score

- Each photo correctly matched to its corresponding map pin earns $round($`SCORE_MAX_POINTS`$)/N$ points. If all photos are correctly matched, `SCORE_MAX_POINTS` is awarded to the location guess.

#### Date Score

- Each photo placed in its exact sequence position (timeline index matching true chronological order rank) earns $round($`SCORE_MAX_POINTS`$)/N$ points. If all photos are placed in their exact sequence position, `SCORE_MAX_POINTS` is awarded to the date guess.

## Common values for scoring exponential function

Common values for inverse exponential decay scoring with `SCORE_MAX_POINTS`:

| Error value (km/~days) | Decay | Score |
|------------------------|-------|-------|
| 1 (1d)                 | 100   | 99.0  |
| 5 (1w)                 | 100   | 95.1  |
| 10 (2w)                | 100   | 90.5  |
| 100 (3m)               | 100   | 36.8  |
| 1000 (3y)              | 100   | 0.0   |
| 1 (1d)                 | 200   | 99.5  |
| 5 (1w)                 | 200   | 97.5  |
| 10 (2w)                | 200   | 95.1  |
| 100 (3m)               | 200   | 60.7  |
| 1000 (3y)              | 200   | 0.7   |
| 1 (1d)                 | 300   | 99.7  |
| 5 (1w)                 | 300   | 98.3  |
| 10 (2w)                | 300   | 96.7  |
| 100 (3m)               | 300   | 71.7  |
| 1000 (3y)              | 300   | 3.6   |
| 1 (1d)                 | 500   | 99.8  |
| 5 (1w)                 | 500   | 99.0  |
| 10 (2w)                | 500   | 98.0  |
| 100 (3m)               | 500   | 81.9  |
| 1000 (3y)              | 500   | 13.5  |
| 1 (1d)                 | 750   | 99.9  |
| 5 (1w)                 | 750   | 99.3  |
| 10 (2w)                | 750   | 98.7  |
| 100 (3m)               | 750   | 87.5  |
| 1000 (3y)              | 750   | 26.4  |
| 1 (1d)                 | 1000  | 99.9  |
| 5 (1w)                 | 1000  | 99.5  |
| 10 (2w)                | 1000  | 99.0  |
| 100 (3m)               | 1000  | 90.5  |
| 1000 (3y)              | 1000  | 36.8  |

## Match Totals

- $ MaxPossibleScore = roundsPlayed * ($`SCORE_MAX_POINTS` if location mode $) + ($`SCORE_MAX_POINTS` if date mode $)$

# Scoring

Each enabled goal is scored using exponential decay, with parameters from
environment variables. Defaults:

- `SCORE_MAX_POINTS = 100`
- `LOCATION_SCORE_DECAY_KM = 700`
- `DATE_SCORE_DECAY_DAYS = 500`

With defaults, a very close location guess is near 100 and the score decays
gently with distance (100 km away scores ~86; 700 km away scores ~36).
Date scoring rewards guessing the right month and decays with day distance from
the guessed-month interval boundary.

## Location Score

Distance d is computed in km using Haversine.

- score = floor(SCORE_MAX_POINTS * exp(-d / LOCATION_SCORE_DECAY_KM)), clamped to 0

## Date Score

The player only guesses a **year and a month**, so the guess covers that whole
month. Scoring is still measured in **days**, using whichever month boundary
faces the actual capture date:

- Actual date is inside the guessed month -> DeltaD = 0
- Actual date is earlier -> DeltaD = days from the **1st** of the guessed month
- Actual date is later -> DeltaD = days from the **last day** of the guessed month

(The last day accounts for month length and leap years.)

- score = floor(SCORE_MAX_POINTS * exp(-DeltaD / DATE_SCORE_DECAY_DAYS)), clamped to 0

Reference points with defaults: 0 days -> 100, 500 days -> 36, 4500 days -> 0.

The reveal additionally shows a whole-month distance split into a years part
and a months part (`divmod(DeltaM, 12)`) purely for readability.

## Match Totals

- max_possible_score = rounds_played * ((SCORE_MAX_POINTS if location mode) + (SCORE_MAX_POINTS if date mode))
- accuracy_pct = round((total_score / max_possible_score) * 100, 1)

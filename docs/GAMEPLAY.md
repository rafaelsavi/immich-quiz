# How to Play Immich Quiz

Immich Quiz is a pass-and-play trivia game where every question is a photo from
your own Immich library. Players take turns on the same device; for each photo
they try to guess where it was taken, when it was taken, or both.

## Setting Up a Game

When you open the app you land on the setup screen. Fill in:

| Option           | What it does                                                                                     |
|------------------|--------------------------------------------------------------------------------------------------|
| **Players**      | One or more names. Add as many players as you like.                                              |
| **Rounds**       | How many photos the game will use: 5, 10, or 20. Every player answers the same photo each round. |
| **Round length** | Time limit per turn: 30 s, 60 s, or unlimited. Unlimited is recommended for relaxed play.        |
| **Goals**        | What you are scored on: **Location**, **Date**, or both. At least one must be enabled.           |
| **Library**      | Which Immich library to pull photos from.                                                        |
| **Album**        | Optional. Narrow the photo pool to a specific album; leave blank for the whole library.          |

Press **Start** when ready.

## Playing a Round

Each round has one photo that all players answer in turn.

### Pass-device overlay

Before your turn a screen appears that covers the photo. This is the pass-device
overlay — hand the device to the active player and press **Ready** to reveal the
photo.

### Active turn

Once the photo is revealed:

- **Location mode**: a map appears. Drag and drop a pin where you think the
  photo was taken. You can zoom in and out. Place the pin anywhere on the globe.
- **Date mode**: a month/year picker appears. Select the month and year you
  think the photo was taken. You do not need to guess the exact day.
- Press **Submit** when done. If a countdown is running, the turn auto-submits
  when it reaches zero.

### Reveal

After every player in the round has submitted, the reveal screen appears:

- **Location**: your pin and the actual location are shown on the map, connected
  by a dashed line. Your distance error is shown in kilometres.
- **Date**: the actual month/year is shown next to your guess. Your error is
  shown as a years and months difference.
- Your score for the round and your running total are shown.

The next round starts with the pass-device overlay for the first player again.

## Scoring

Each goal is scored from 0 to `SCORE_MAX_POINTS` per turn (default: 100).

- **Location**: score decreases exponentially with map distance.
- **Date**: score decreases exponentially with day distance from the guessed
  month interval.

Defaults are tuned to be forgiving. You can adjust scoring behavior with
`SCORE_MAX_POINTS`, `LOCATION_SCORE_DECAY_KM`, and `DATE_SCORE_DECAY_DAYS`.

See [SCORING.md](SCORING.md) for the exact formulas.

## Leaderboard

After the final round the leaderboard shows all historical matches, sorted by
most recent. Each row shows the player's total score and accuracy percentage
(score as a fraction of the maximum possible). Use the column headers to sort.

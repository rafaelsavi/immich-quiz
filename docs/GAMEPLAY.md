# How to Play Immich Quiz

Immich Quiz is a pass-and-play trivia game where every question is a photo from
your own Immich library. Players take turns on the same device; for each photo
they try to guess where it was taken, when it was taken, or both.

## Setting Up a Game

When you open the app you land on the setup screen. Fill in:

| Option           | What it does                                                                                   |
|------------------|------------------------------------------------------------------------------------------------|
| **Players**      | One or more names. Add as many players as you like.                                            |
| **Rounds**       | How many rounds the game will run.                                                             |
| **Round Length** | Time limit per turn: 30 s, 1 min, 2 min, 5 min, or unlimited.                                  |
| **Library**      | Which Immich library to pull photos from.                                                      |
| **Album**        | Optional. Narrow the photo pool to a specific album; leave blank for the whole library.        |
| **Game Mode**    | **Pinpoint** (classic single photo per turn) or **Album Shuffle** (batch matching & timeline). |
| **Guess Mode**   | **Location**, **date**, or both                                                                |

Press **Start** when ready. Before launching, a preflight check automatically validates that the selected library or album contains enough eligible photos meeting your active game parameters.

## Game Modes

### 🎯 Pinpoint

In **Pinpoint**, players guess photo locations and capture dates one photo at a time. Each round presents a single photo to all players.

#### Pass-device overlay

Before your turn a screen appears that covers the photo. This is the pass-device overlay — hand the device to the active player and press **Ready** to reveal the photo.

#### Active turn

A single photo is presented to each player in turn.

- **Location mode**: a map appears. Drag and drop a pin where you think the
  photo was taken. You can zoom in and out or open the map in fullscreen. Place the pin anywhere on the globe.
- **Date mode**: a month/year picker appears. Select the month and year you think the photo was taken.
- Press **Submit** when done. If a countdown is running, the turn auto-submits when it reaches zero.

#### Reveal

After every player in the round has submitted, the reveal screen appears:

- **Location**: your pin and the actual location are shown on the map, connected by a dashed line. Your distance error is shown in kilometres.
- **Date**: the actual month/year is shown next to your guess.

A score is calculated based on the error of the two gueeses. See [SCORING.md](SCORING.md) for more details. Depending on the performance, a player may receive a badge. See [AWARDS.md](AWARDS.md) for more details.

The next round starts with the pass-device overlay for the first player again.

### 🔀 Album Shuffle

In **Album Shuffle**, players receive a full batch of 5 photos alongside shuffled map pins (`A`, `B`, `C`...) and timeline slots (`1st`, `2nd`, `3rd`...).

#### Active turn

5 images are shown in a list to each player in turn.

- **Location mode**: a map appears with pins A, B, C, D, E. Players must select each photo from the list and click on the corresponding pin on the map.
- **Date mode**: The 5 images must be sorted chronologically in the list by clicking on their arrows.

- Press **Submit** when done. If a countdown is running, the turn auto-submits when it reaches zero.

#### Reveal

A score is calculated based on the error of the two gueeses. See [SCORING.md](SCORING.md) for more details. Depending on the performance, a player may receive a badge. See [AWARDS.md](AWARDS.md) for more details.

## Leaderboard

After the final round (or from the setup screen navigation), the leaderboard shows all historical games that used the same settings.

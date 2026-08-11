# How to Play Immich Quiz

Immich Quiz is a pass-and-play trivia game that uses photos from your Immich library. You and your friends take turns on the same device and try to guess where each photo was taken, when it was taken, or both.

## Setting Up a Game

When you open the app, you start on the setup screen. Fill in your game options:

| Option           | What it does                                                                                   |
|------------------|------------------------------------------------------------------------------------------------|
| **Players**      | Add one or more player names. You can add as many players as you like.                         |
| **Rounds**       | Choose how many rounds the game will run.                                                      |
| **Round Length** | Pick a time limit per turn: 30 s, 1 min, 2 min, 5 min, or unlimited.                           |
| **Library**      | Pick which Immich library to use for photos.                                                    |
| **Album**        | Optional. Pick an album to narrow the photo pool, or leave blank to use the whole library.     |
| **Game Mode**    | Choose **Pinpoint** (single photo per turn) or **Album Shuffle** (batch matching & timeline).  |
| **Guess Mode**   | Choose **Location**, **Date**, or **Both**.                                                     |

Press **Start** when you're ready. The game checks that the selected library or album has enough eligible photos for your settings before it begins. You can also switch the UI language between **English** and **Portuguese** at any time using the header language toggle button.

## Game Modes

### 🎯 Pinpoint

In **Pinpoint**, everyone takes turns guessing one photo at a time.

#### Pass-device overlay

Before your turn, a screen appears that hides the photo. Hand the device to the active player and press **Ready** to reveal the photo.

#### Your turn

A single photo is shown to the active player.

- **Location mode**: a map appears. Drag and drop a pin where you think the photo was taken. You can zoom or open the map in fullscreen. Place the pin anywhere on the globe.
- **Date mode**: a month/year picker appears. Choose the month and year you think the photo was taken. You can also scroll your mouse wheel over the month and year boxes to quickly adjust dates.
- Press **Submit** when you are done. If a countdown is running, the turn auto-submits when time runs out.

#### Reveal

Once every player in the round has submitted, the reveal screen appears:

- **Location**: your pin and the real location are shown on the map, linked by a dashed line. Your distance error is shown in kilometres.
- **Date**: the real month and year are shown next to your guess.

Your score is calculated from how close your guesses were. See [SCORING.md](SCORING.md) for more details. Great performance can earn a badge; see [AWARDS.md](AWARDS.md) for badge details.

The next round begins with the pass-device overlay for the first player again.

### 🔀 Album Shuffle

In **Album Shuffle**, you get a batch of 3 photos and must match them to map pins or sort them in chronological order.

#### Your turn

Each player sees 3 photo cards in a list.

- **Location mode**: a map appears with pins labeled A, B, and C. Click a photo card to select it, then click the map pin where you think that photo was taken to assign it.
- **Date mode**: sort the 3 images into chronological order (from earliest to latest, top to bottom) using the ▲ and ▼ rank buttons next to each photo card. Photos automatically reorder in real time as ranks are shifted.
- Press **Submit** when you are finished. If a countdown is running, the turn auto-submits when time runs out.

#### Reveal

After everyone submits, the game calculates your score based on how accurate your location and date assignments were. See [SCORING.md](SCORING.md) for more details and [AWARDS.md](AWARDS.md) for badge information.

## Photo Variety & Quality

To ensure every match is engaging and fair:

- Photos without valid location data (or Null Island `0,0` coordinates) are automatically filtered out when location guessing is enabled.
- Photo locations are chosen to be at least 100 metres apart from each other, and photo capture times are chosen at least 1 minute apart, giving you distinct photos to guess every round.

## Leaderboard

After the final round—or from the setup screen—you can view the leaderboard. It shows past games played with the same settings.

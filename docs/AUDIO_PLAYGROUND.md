# Sound & Audio Testing Playground

Immich Quiz features a zero-dependency, local-first sound engine built directly on the browser **Web Audio API** in [`static/js/modules/audio.js`](../static/js/modules/audio.js).

To facilitate testing, tuning, and designing sound effects without having to play through full game rounds, an interactive **Audio Testing Playground** is included in the project.

---

## Accessing the Playground

When the app server is running (e.g., via `uv run -m src.main` or Docker):

- **Direct Route**: [`http://localhost:8010/audio-playground`](http://localhost:8010/audio-playground)
- **Static File Route**: [`http://localhost:8010/static/audio-playground.html`](http://localhost:8010/static/audio-playground.html)

---

## Sound Engine Architecture (`audio.js`)

All sound effects in Immich Quiz are synthesized dynamically at runtime using browser Web Audio oscillators (`OscillatorNode` + `GainNode`). No external audio file assets (such as MP3 or WAV files) are required.

### Core Exported Functions

| Function               | Parameters                              | Waveform                                       | Frequency / Notes                                                    | Duration            | Description                                                                                                                           |
|------------------------|-----------------------------------------|------------------------------------------------|----------------------------------------------------------------------|---------------------|---------------------------------------------------------------------------------------------------------------------------------------|
| `playSubmitTone()`    | —                                       | `sine`                                         | 480 Hz                                                               | 0.08 s              | Short confirmation cue played when a player submits an answer.                                                                      |
| `playTick()`           | `clampedSec`                            | `sine`                                         | 520 Hz ➔ 720 Hz (rises as time gets shorter)                        | 0.09 s              | Short feedback used for countdown warnings, quick UI interactions, and other light alert cues.                                     |
| `playPinDropSound()`   | —                                       | `sine`                                         | 440 Hz ➔ 180 Hz                                                      | 0.08 s              | Tactile pop/thump sound triggered when placing or moving a pin on the guess map.                                                     |
| `playScoreRollupTick()`| `progress`                              | `triangle`                                     | 580 Hz ➔ 1100 Hz (ascending)                                         | 0.035 s per tick    | Ticker sound played during the round points count-up animation, with duration proportional to points scored in the round.           |
| `playBuzzer()`         | —                                       | `sawtooth`                                     | 140 Hz + 210 Hz double pulse                                         | 0.18 s per pulse    | Low-pitch alert sound for wrong guesses, low accuracy scores, or timeouts.                                                            |
| `playChime()`          | —                                       | `triangle`                                     | C5 (523.25 Hz)<br>E5 (659.25 Hz)<br>G5 (783.99 Hz)<br>C6 (1046.5 Hz) | 0.35 s per note     | Multi-note ascending chord arpeggio for correct guesses and high accuracy scores.                                                     |
| `playVictoryFanfare()` | —                                       | `triangle`                                     | F4 (349.23 Hz)<br>A4 (440.00 Hz)<br>C5 (523.25 Hz)<br>F5 (698.46 Hz) | 0.65 s final note   | Celebratory fanfare played when a match finishes and final scores are displayed.                                                      |
| `playTone()`           | `freq`, `type`, `duration`, `gainValue` | `sine`<br>`triangle`<br>`sawtooth`<br>`square` | Custom (50–4000 Hz)                                                  | Custom (0.01–5.0 s) | Low-level dynamic tone synthesizer helper function.                                                                                   |
| `toggleAudio()`        | —                                       | —                                              | —                                                                    | —                   | Toggles global audio state on/off, persists setting to `localStorage` (`immich_quiz_audio`), updates UI icons, and plays a test tone. |
| `unlockAudioContext()` | —                                       | —                                              | —                                                                    | —                   | Unlocks/resumes suspended `AudioContext` on first user interaction (`pointerdown` or `keydown`).                                      |

---

## Playground Features

The interactive testing playground (`static/audio-playground.html`) provides five dedicated toolsets:

### 1. Audio System Status Auditor

- Displays live status of `state.audioEnabled` (Enabled vs Muted).
- Shows live state of `AudioContext` (`suspended`, `running`, `closed`) along with sample rate (e.g. 48000 Hz).
- Includes an explicit **Unlock / Resume AudioContext** action button.

### 2. Built-in Sound Presets

- Dedicated trigger cards for `playTick()`, `playBuzzer()`, `playChime()`, and `playVictoryFanfare()`.
- Provides instant acoustic feedback and lists frequency/waveform parameters for each preset.

### 3. Custom Tone Synthesizer

- Test arbitrary audio parameters live:
  - **Frequency Slider & Input**: 50 Hz to 4000 Hz.
  - **Quick Pitch Shortcuts**: A3 (220Hz), C4 (261Hz), A4 (440Hz), C5 (523Hz), A5 (880Hz), C6 (1046Hz).
  - **Waveform Selector**: `sine` (pure), `triangle` (flute/soft), `square` (retro 8-bit), `sawtooth` (harsh buzzer).
  - **Duration & Volume (Gain)**: Precision sliders with numerical feedback.

### 4. Game Sequence Simulator

- Allows developers to test real-time audio transition timing across simulated game phases:
  - *Option Selection* (`playTick`)
  - *Incorrect Guess* (`playBuzzer`)
  - *Perfect Guess* (`playChime`)
  - *Match Victory* (`playVictoryFanfare`)
  - *Mute Toggle* (`toggleAudio`)

### 5. Oscilloscope Waveform Visualizer & Event Inspector

- Real-time HTML5 canvas rendering live animated oscilloscope waveforms corresponding to played frequencies and oscillator types.
- Live scrolling event log table detailing timestamps, event names, frequencies, duration, gain levels, and audio state.

### 6. Game-submit confirmation cue

- The main game flow now uses `playSubmitTone()` from the audio module when a player submits an answer. The playground exposes the same tone through the dedicated “Submit Confirmation” preset so it can be tested independently of a full round.

### 7. Countdown timer simulator

- A dedicated countdown demo mirrors the in-game timer cadence with a fluid 60 FPS countdown bar, adaptive `M:SS` formatting, per-second rising-pitch tick cues, and a final buzzer when the timer expires.

---

## Developer Guide: Adding New Sound Effects

To add a new sound effect to `static/js/modules/audio.js`:

1. Export a new function using `getAudioContext()` and `playTone()`:

```javascript
export function playBonusSound() {
  if (!state || !state.audioEnabled) return;
  try {
    const ctx = getAudioContext();
    if (!ctx) return;
    // Synthesize custom oscillator sequence...
    playTone(1200, "sine", 0.1, 0.15);
  } catch (_) {}
}
```

1. Open [`http://localhost:8010/audio-playground`](http://localhost:8010/audio-playground) in your browser.
2. Use the **Custom Tone Synthesizer** controls to fine-tune frequencies, durations, and waveforms before locking them into code.

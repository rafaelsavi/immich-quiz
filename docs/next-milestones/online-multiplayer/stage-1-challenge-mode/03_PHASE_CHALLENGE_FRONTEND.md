# Phase 3: Frontend Challenge Experience & Intermission Polling

> **Prerequisites**: Phases 1 and 2 must be complete.

## Goal

1. Implement the frontend router for capability URLs (`/play/{capability_token}` or `#challenge={capability_token}`).
2. Create `static/js/modules/challenge.js` to manage the challenge lifecycle:
   - Challenge landing & player entry screen
   - Active question response timer (`time_taken_seconds`)
   - **Intermission Screen with 3-Second Polling** and animated Leaflet pin drops
   - **Grand Reveal Summary Screen** (Podium, interactive multi-pin map scatter plot, horizontal date timeline)
3. Add modular styles in `static/css/components/challenge.css`.

---

## 1. File: `static/js/modules/challenge.js`

Create this module with the complete challenge flow:

```javascript
/**
 * Challenge Mode Controller for Immich Quiz.
 * Handles async/hybrid multiplayer, 3s polling intermission, and grand reveal map/timeline.
 */
import { api } from './api.js';
import { state } from './state.js';
import { maps } from './maps.js';
import { audio } from './audio.js';
import { effects } from './effects.js';
import { formatters } from './formatters.js';

let challengeData = null;
let currentSessionToken = null;
let pollingInterval = null;
let questionStartTime = null;

export const challenge = {
  /**
   * Initialize a challenge from a capability token in the URL.
   */
  async init(capabilityToken) {
    try {
      challengeData = await api.get(`/api/challenge/${capabilityToken}`);
      this.renderLandingScreen(challengeData);
    } catch (err) {
      console.error('Failed to load challenge:', err);
      this.renderErrorScreen('This challenge link is invalid or has expired.');
    }
  },

  /**
   * Render the player entry screen.
   */
  renderLandingScreen(data) {
    const appEl = document.getElementById('app');
    appEl.innerHTML = `
      <div class="challenge-landing card">
        <div class="challenge-header">
          <span class="badge badge-primary">Photo Challenge</span>
          <h2>${data.creator_name}'s Challenge</h2>
          <p class="challenge-meta">${data.rounds} Rounds • ${data.filter_summary}</p>
        </div>

        <div class="challenge-participants">
          <span class="icon">👥</span> ${data.total_participants} players have completed this challenge
        </div>

        <form id="challenge-join-form" class="challenge-form">
          <label for="player-name-input">Your Name</label>
          <input type="text" id="player-name-input" class="input" placeholder="Enter your name" maxlength="30" required autofocus />
          <button type="submit" class="btn btn-primary btn-large">Start Challenge</button>
        </form>
      </div>
    `;

    document.getElementById('challenge-join-form').addEventListener('submit', (e) => {
      e.preventDefault();
      const name = document.getElementById('player-name-input').value.trim();
      if (name) this.start(name);
    });
  },

  /**
   * Start the challenge attempt for this player.
   */
  async start(playerName) {
    try {
      const res = await api.post(`/api/challenge/${challengeData.capability_token}/start`, {
        player_name: playerName,
      });
      currentSessionToken = res.session_token;
      state.set('challengeSession', {
        token: currentSessionToken,
        matchId: res.match_id,
        playerName: playerName,
      });

      this.loadRound(0);
    } catch (err) {
      alert('Failed to start challenge: ' + err.message);
    }
  },

  /**
   * Load and render question for round N.
   */
  async loadRound(roundIndex) {
    this.stopPolling();
    questionStartTime = performance.now();

    // Standard quiz question layout rendered with challenge-specific submission handler
    // ...
  },

  /**
   * Submit answer and transition to the Intermission screen.
   */
  async submitAnswer(guessData) {
    const elapsedSeconds = Math.max(0.1, (performance.now() - questionStartTime) / 1000);

    const payload = {
      round_index: state.get('currentRoundIndex'),
      guess_latitude: guessData.latitude,
      guess_longitude: guessData.longitude,
      guess_date: guessData.date,
      time_taken_seconds: elapsedSeconds,
    };

    const result = await api.post(
      `/api/challenge/${challengeData.capability_token}/answer`,
      payload,
      { headers: { 'X-Player-Token': currentSessionToken } }
    );

    this.renderIntermissionScreen(result);
  },

  /**
   * Intermission Screen with 3s Polling ("Live Illusion").
   */
  renderIntermissionScreen(roundResult) {
    // 1. Render Map with True Location
    // 2. Start 3-second polling to fetch friends' submissions
    this.startPolling(roundResult.round_index);
  },

  startPolling(roundIndex) {
    this.stopPolling();
    const poll = async () => {
      try {
        const data = await api.get(
          `/api/challenge/${challengeData.capability_token}/leaderboard`,
          { headers: { 'X-Player-Token': currentSessionToken } }
        );
        this.updateIntermissionView(data, roundIndex);
      } catch (e) {
        console.warn('Polling error:', e);
      }
    };

    poll();
    pollingInterval = setInterval(poll, 3000);
  },

  stopPolling() {
    if (pollingInterval) {
      clearInterval(pollingInterval);
      pollingInterval = null;
    }
  },

  /**
   * Update Intermission View with animated friend pins dropping on Leaflet map.
   */
  updateIntermissionView(leaderboardData, roundIndex) {
    const guesses = leaderboardData.round_guesses.filter((g) => g.round_index === roundIndex);

    // Drop pins on Leaflet map dynamically
    guesses.forEach((g) => {
      if (g.guess_latitude && g.guess_longitude) {
        maps.addPlayerPin({
          lat: g.guess_latitude,
          lng: g.guess_longitude,
          name: g.player_name,
          score: g.round_score,
          animate: true,
        });
      }
    });

    // Update real-time standings list
    // ...
  },

  /**
   * Grand Reveal Summary Screen at the end of the challenge.
   */
  renderGrandReveal(finalLeaderboardData) {
    this.stopPolling();
    effects.fireConfetti();

    // Renders:
    // 1. Gold/Silver/Bronze Podium
    // 2. Interactive Round Carousel with Leaflet Multi-Pin Scatter Plot
    // 3. Horizontal Date Timeline plotting each player's guessed date vs True Date
  },
};
```

---

## 2. Capability URL Routing in `static/js/app.js`

Add capability URL detection in the main app router:

```javascript
// Check for capability path /play/{token} or query/hash #play={token}
const pathMatch = window.location.pathname.match(/^\/play\/([a-zA-Z0-9_-]+)/);
const hashMatch = window.location.hash.match(/#play=([a-zA-Z0-9_-]+)/);
const capabilityToken = pathMatch ? pathMatch[1] : (hashMatch ? hashMatch[1] : null);

if (capabilityToken) {
  challenge.init(capabilityToken);
} else {
  // Standard single-player / local setup screen
  initLocalApp();
}
```

---

## Acceptance Criteria

1. Navigating to `/play/{token}` loads the challenge and displays the creator's name, round count, and filter summary.
2. Active response time is recorded per round and sent with answer submissions.
3. The **Intermission Screen** polls every 3 seconds, rendering animated pins for friends who complete the round.
4. The **Grand Reveal Screen** allows toggling between rounds, displaying all player pins on the map and all player dates on the timeline.

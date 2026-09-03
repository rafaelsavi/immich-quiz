/**
 * Challenge Grand Reveal Summary & Scatter-Map Carousel Controller.
 *
 * Renders the multiplayer summary with 3D podium, performance awards,
 * standings table with live player highlights, and interactive round-by-round
 * Leaflet scatter-map carousel with player connector lines.
 */

import { api } from "../api.js";
import { state, el } from "../state.js";
import {
  createStandardMap,
  createPinIcon,
  fitMapToBounds,
  unregisterActiveMap,
  renderJourneyMap,
} from "../maps.js";
import { renderPolaroidGallery } from "../summary/polaroids.js";
import { openPhotoLightbox } from "../components/lightbox.js";
import { playVictoryFanfare } from "../audio.js";
import { launchGoldConfetti, animateScoreRollup } from "../effects.js";
import {
  ACTUAL_COLOR,
  playerColor,
  playerInitial,
  registerPlayerColor,
  formatDistance,
  formatMonth,
  formatMonthError,
  formatRankBadge,
  formatRoundsBadge,
  formatPlayerCellHtml,
  formatPlace,
} from "../formatters.js";
import { t, formatDate } from "../i18n.js";
import { renderPodium } from "../summary/podium.js";
import { renderAwards } from "../summary/awards.js";
import { showCard } from "../screens/common.js";
import { navigate } from "../router.js";
import { copyToClipboard } from "../summary/share.js";
import { challengeSession, POLL_INTERVAL_MS } from "./session.js";
import { renderErrorScreen } from "./landing.js";
import { showActivityToast } from "../components/activity_toast.js";

export const challengeSummary = {
  /**
   * Grand Reveal Summary Screen at the end of the challenge.
   * @param {object} [options]
   * @param {boolean} [options.updateUrl=true]
   */
  async showGrandReveal({ updateUrl = true } = {}) {
    challengeSession.stopPolling();
    challengeSession.cleanupMaps();
    state.currentScreen = null;
    state.currentQuestion = null;
    challengeSession.lastRoundResult = null;

    if (!el.challengeCard) return;
    showCard(el.challengeCard);
    window.scrollTo({ top: 0, behavior: "smooth" });

    try {
      const data = await api(
        `/api/challenge/${encodeURIComponent(challengeSession.challengeData.capability_token)}/leaderboard`,
        {
          headers: {
            "X-Player-Token": challengeSession.sessionToken,
          },
        }
      );
      challengeSession.cachedLeaderboardData = data;

      if (data.leaderboard) {
        const participantNames = data.leaderboard.map((p) => p.player_name);
        if (participantNames.length > 0) {
          state.players = participantNames;
        }
        data.leaderboard.forEach((p) => {
          if (p.player_color) {
            registerPlayerColor(p.player_name, p.player_color);
          }
        });
      }

      if (updateUrl && challengeSession.challengeData?.capability_token) {
        navigate(`/play/${encodeURIComponent(challengeSession.challengeData.capability_token)}/summary`, { replace: true });
      }

      launchGoldConfetti();
      playVictoryFanfare();

      const playUrl = `${window.location.origin}/play/${challengeSession.challengeData.capability_token}`;
      const summaryUrl = `${window.location.origin}/play/${challengeSession.challengeData.capability_token}/summary`;
      const totalRoundsCount = data.total_rounds || challengeSession.totalRounds;

      const finishedPlayers = data.leaderboard.filter((p) => p.is_finished || p.completed_rounds >= totalRoundsCount);
      const hasUnfinishedPlayers = data.leaderboard.some((p) => !p.is_finished && p.completed_rounds < totalRoundsCount);
      const isSettled = finishedPlayers.length >= 2;
      const isConcluded = Boolean(
        data.is_concluded ||
        challengeSession.challengeData.is_active === false ||
        (challengeSession.challengeData.expires_at && new Date() > new Date(challengeSession.challengeData.expires_at))
      );

      const podiumNoteHtml = (isSettled && hasUnfinishedPlayers)
        ? `
            <div class="podium-finished-note" id="grand-reveal-podium-finished-note">
              <span class="note-icon" aria-hidden="true">🏁</span>
              <span data-i18n="challenge.podium_finished_notice">${t("challenge.podium_finished_notice")}</span>
            </div>
          `
        : "";

      const podiumHtml = isSettled
        ? `
          <div class="grand-reveal-podium-wrap">
            <div id="grand-reveal-podium" class="summary-winner"></div>
            ${podiumNoteHtml}
          </div>
        `
        : `
          <div class="challenge-provisional-card" id="grand-reveal-provisional">
            <div class="provisional-header">
              <span class="pulse-dot"></span>
              <h3 class="provisional-title">${t("challenge.provisional_title")}</h3>
            </div>
            <p class="provisional-desc">${t("challenge.provisional_desc")}</p>
            <div class="provisional-hint">
              <span aria-hidden="true">🏆</span>
              <span>${t("challenge.single_player_podium_hint")}</span>
            </div>
          </div>
        `;

      const isAlbumShuffle = data.game_mode === "album_shuffle";
      const isLocationEnabled = challengeSession.challengeData.location_mode !== false && data.location_mode !== false;

      const standingsTableHtml = `
        <div class="table-scroll">
          <table id="grand-reveal-table" class="summary-table standings-table">
            <thead>
              <tr>
                <th class="col-rank">${t("summary.col_rank")}</th>
                <th class="col-player">${t("summary.col_player")}</th>
                <th class="col-rounds text-center">${t("summary.col_rounds")}</th>
                ${challengeSession.challengeData.location_mode !== false ? `<th class="col-score text-right">${t("summary.col_location")}</th>` : ""}
                ${challengeSession.challengeData.date_mode !== false ? `<th class="col-score text-right">${t("summary.col_date")}</th>` : ""}
                <th class="col-score text-right">${t("summary.col_total")}</th>
                <th class="col-accuracy text-right hide-on-mobile">${t("summary.col_accuracy")}</th>
              </tr>
            </thead>
            <tbody>
              ${this.renderStandingsRows(data.leaderboard, totalRoundsCount, isSettled)}
            </tbody>
          </table>
        </div>
      `;

      const middleContentHtml = isAlbumShuffle
        ? `
          ${standingsTableHtml}

          <!-- World Journey Map (if location mode is active) -->
          ${
            isLocationEnabled
              ? `
            <div class="field-head" id="challenge-journey-map-head">
              <label>${t("summary.journey_map_heading")}</label>
            </div>
            <div id="challenge-journey-map-shell" class="map-shell" style="height: 450px;">
              <div id="challenge-journey-map"></div>
            </div>
          `
              : ""
          }

          <!-- Match Memory Cards (Polaroids) -->
          <div class="polaroids-section" id="challenge-polaroids-section">
            <div class="field-head">
              <label>${t("summary.polaroids_heading")}</label>
            </div>
            <div id="challenge-polaroid-gallery" class="polaroid-grid"></div>
          </div>
        `
        : `
          <!-- Interactive Round Carousel Section -->
          <div class="challenge-carousel-card">
            <div class="carousel-nav-header">
              <h3 class="carousel-nav-title" id="carousel-title">${t("challenge.round_carousel_title")}</h3>
              <div class="carousel-nav-controls">
                <button type="button" class="carousel-nav-btn" id="carousel-prev-btn">◀ ${t("challenge.carousel_prev")}</button>
                <span id="carousel-indicator" style="font-weight:700;font-size:0.9rem;color:var(--ink);"></span>
                <button type="button" class="carousel-nav-btn" id="carousel-next-btn">${t("challenge.carousel_next")} ▶</button>
              </div>
            </div>

            <div class="carousel-round-content" id="carousel-round-content">
              <div class="carousel-media-row" id="carousel-media-row">
                <div class="media-frame carousel-photo-shell hidden" id="carousel-photo-shell">
                  <img id="carousel-photo-img" class="carousel-photo-img" alt="${t("game.photo_alt")}" />
                  <button type="button" class="map-fullscreen-btn carousel-photo-zoom-btn" id="carousel-photo-zoom-btn"
                    title="${t("game.fullscreen_image_title")}" data-i18n-title="game.fullscreen_image_title" aria-pressed="false">
                    <svg class="fs-icon" viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor"
                      stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round">
                      <polyline points="15 3 21 3 21 9"></polyline>
                      <polyline points="9 21 3 21 3 15"></polyline>
                      <line x1="21" y1="3" x2="14" y2="10"></line>
                      <line x1="3" y1="21" x2="10" y2="14"></line>
                    </svg>
                  </button>
                </div>
                <div class="map-shell scatter-map-shell" id="scatter-map-shell">
                  <div id="scatter-map"></div>
                </div>
              </div>
              <div id="carousel-round-extra"></div>
            </div>
          </div>

          ${standingsTableHtml}
        `;

      el.challengeCard.innerHTML = `
        <div class="challenge-grand-reveal">
          <div class="grand-reveal-header">
            <span class="badge badge-challenge">${t("challenge.badge")}</span>
            <h2>${data.title || `${challengeSession.challengeData.creator_name}'s Challenge`}</h2>
            <p class="grand-reveal-meta">
              <span id="grand-reveal-meta-tally">${totalRoundsCount} ${t("challenge.rounds")} • ${t("challenge.participants", data.leaderboard.length)}</span>
              <span id="grand-reveal-live-pill" class="challenge-live-pill">
                <span class="live-poll-dot" aria-hidden="true"></span>
                <span id="grand-reveal-live-status">${t("challenge.live_finished_tally", finishedPlayers.length, data.leaderboard.length)}</span>
              </span>
            </p>
          </div>

          ${podiumHtml}

          ${middleContentHtml}

          <div class="summary-actions">
            <button type="button" class="btn btn-primary" id="grand-reveal-share-btn">
              📋 ${t("challenge.copy_invite_link")}
            </button>
            <button type="button" class="btn btn-secondary" id="grand-reveal-share-summary-btn">
              🏆 ${t("challenge.copy_summary_link")}
            </button>
            <button type="button" class="btn btn-secondary" id="grand-reveal-hub-btn">
              🌐 ${t("challenge.challenges_hub")}
            </button>
            <button type="button" class="btn btn-secondary" id="grand-reveal-home-btn">
              🏠 ${t("challenge.back_home")}
            </button>
          </div>
        </div>
      `;

      if (isSettled) {
        // 1. Render Podium
        const podiumEl = document.getElementById("grand-reveal-podium");
        const winners = finishedPlayers.filter((p) => p.is_winner).map((p) => p.player_name);
        renderPodium(
          {
            players: finishedPlayers,
            winners: winners.length > 0 ? winners : [finishedPlayers[0]?.player_name].filter(Boolean),
            is_concluded: isConcluded,
          },
          podiumEl
        );

        // 2. Render Performance Awards
        const playerStats = this.buildPlayerStats(data);
        const grandRevealEl = el.challengeCard.querySelector(".challenge-grand-reveal");
        renderAwards(
          {
            game_mode: data.game_mode,
            location_mode: challengeSession.challengeData.location_mode !== false,
            date_mode: challengeSession.challengeData.date_mode !== false,
            players: data.leaderboard,
          },
          playerStats,
          grandRevealEl,
          podiumEl
        );
      }

      if (isAlbumShuffle) {
        // 3. Render Journey Map & Polaroids for Album Shuffle
        const mapShell = document.getElementById("challenge-journey-map-shell");
        const mapHead = document.getElementById("challenge-journey-map-head");
        const mapContainer = document.getElementById("challenge-journey-map");
        if (isLocationEnabled && mapShell && mapHead && mapContainer) {
          challengeSession.challengeJourneyMap = renderJourneyMap(data.round_history, true, {
            mapShell,
            mapHead,
            container: mapContainer,
            existingMap: challengeSession.challengeJourneyMap,
          });
        }

        const polaroidGallery = document.getElementById("challenge-polaroid-gallery");
        if (polaroidGallery) {
          renderPolaroidGallery(data.round_history, polaroidGallery);
        }
      } else {
        // 3. Render Round Carousel for Pinpoint
        challengeSession.carouselRoundIndex = 0;
        this.renderCarouselRound(data, challengeSession.carouselRoundIndex);

        document.getElementById("carousel-prev-btn")?.addEventListener("click", () => {
          if (challengeSession.carouselRoundIndex > 0) {
            challengeSession.carouselRoundIndex--;
            this.renderCarouselRound(data, challengeSession.carouselRoundIndex);
          }
        });

        document.getElementById("carousel-next-btn")?.addEventListener("click", () => {
          if (challengeSession.carouselRoundIndex < totalRoundsCount - 1) {
            challengeSession.carouselRoundIndex++;
            this.renderCarouselRound(data, challengeSession.carouselRoundIndex);
          }
        });
      }

      // Share button (Invite link)
      document.getElementById("grand-reveal-share-btn")?.addEventListener("click", async () => {
        const btn = document.getElementById("grand-reveal-share-btn");
        await copyToClipboard(playUrl, {
          button: btn,
          copiedText: `✅ ${t("challenge.link_copied")}`,
        });
      });

      // Share button (Summary link)
      document.getElementById("grand-reveal-share-summary-btn")?.addEventListener("click", async () => {
        const btn = document.getElementById("grand-reveal-share-summary-btn");
        await copyToClipboard(summaryUrl, {
          button: btn,
          copiedText: `🏆 ${t("challenge.summary_link_copied")}`,
        });
      });

      // Challenges Hub button
      document.getElementById("grand-reveal-hub-btn")?.addEventListener("click", () => {
        navigate("/challenges");
      });

      // Home button
      document.getElementById("grand-reveal-home-btn")?.addEventListener("click", () => {
        navigate("/");
      });

      // Start background polling if the challenge is active and unsettled or has unfinished players
      if ((!isSettled || hasUnfinishedPlayers) && !isConcluded) {
        this.startSummaryPolling();
      }
    } catch (err) {
      console.error("Failed to load grand reveal:", err);
      renderErrorScreen(err.message || "Failed to load summary");
    }
  },

  /**
   * Render a specific round inside the Grand Reveal Carousel with scatter map and date comparisons.
   * @param {object} data
   * @param {number} roundIdx
   */
  renderCarouselRound(data, roundIdx) {
    const totalRoundsCount = data.total_rounds || challengeSession.totalRounds;
    const indicatorEl = document.getElementById("carousel-indicator");
    if (indicatorEl) {
      indicatorEl.textContent = t("challenge.round_n_of_total", roundIdx + 1, totalRoundsCount);
    }

    const prevBtn = document.getElementById("carousel-prev-btn");
    const nextBtn = document.getElementById("carousel-next-btn");
    if (prevBtn) prevBtn.disabled = roundIdx === 0;
    if (nextBtn) nextBtn.disabled = roundIdx >= totalRoundsCount - 1;

    const roundGuesses = (data.round_guesses || []).filter((g) => g.round_index === roundIdx);
    const extraEl = document.getElementById("carousel-round-extra");

    const isLocationEnabled = challengeSession.challengeData?.location_mode !== false && data?.location_mode !== false;
    const isDateEnabled = challengeSession.challengeData?.date_mode !== false && data?.date_mode !== false;

    // 1. Photo preview
    const roundHistoryItem = (data.round_history || []).find((r) => r.round_number === roundIdx + 1);
    const mediaUrl = roundHistoryItem?.media_url;
    const mediaRow = document.getElementById("carousel-media-row");
    const photoShell = document.getElementById("carousel-photo-shell");
    const photoImg = document.getElementById("carousel-photo-img");
    const photoZoomBtn = document.getElementById("carousel-photo-zoom-btn");

    if (photoShell && photoImg) {
      if (mediaUrl) {
        photoImg.src = mediaUrl;
        photoShell.classList.remove("hidden");
        photoImg.onclick = () => openPhotoLightbox(mediaUrl);
        if (photoZoomBtn) {
          photoZoomBtn.onclick = () => openPhotoLightbox(mediaUrl);
        }
      } else {
        photoShell.classList.add("hidden");
      }
    }

    if (mediaRow) {
      if (!isLocationEnabled) {
        mediaRow.classList.add("single-col");
      } else {
        mediaRow.classList.remove("single-col");
      }
    }

    // 2. Initialize scatter map (only if location_mode is enabled)
    const mapShell = document.getElementById("scatter-map-shell");
    if (!isLocationEnabled) {
      if (mapShell) {
        mapShell.classList.add("hidden");
      }
      if (challengeSession.carouselMap) {
        try {
          unregisterActiveMap(challengeSession.carouselMap);
          challengeSession.carouselMap.remove();
        } catch (_) {}
        challengeSession.carouselMap = null;
      }
    } else {
      if (mapShell) {
        mapShell.classList.remove("hidden");
      }
      if (mapShell && window.L) {
        challengeSession.carouselMarkers = {};
        challengeSession.carouselSpiderLines = {};
        challengeSession.carouselTrueCoords = {};

        challengeSession.carouselMap = createStandardMap("scatter-map", {
          existingMap: challengeSession.carouselMap,
          titleKey: "game.fullscreen_map_title",
        });

        const bounds = L.latLngBounds();

        // Find first guess with actual coordinates
        const sampleGuess = roundGuesses.find((g) => g.actual_latitude !== null && g.actual_longitude !== null);
        if (sampleGuess) {
          const trueLatLng = L.latLng(sampleGuess.actual_latitude, sampleGuess.actual_longitude);
          bounds.extend(trueLatLng);
          challengeSession.carouselTrueCoords["__true__"] = { lat: sampleGuess.actual_latitude, lng: sampleGuess.actual_longitude };

          const trueMarker = L.marker(trueLatLng, {
            icon: createPinIcon("\u2605", ACTUAL_COLOR),
            zIndexOffset: 1000,
          })
            .bindPopup(`<b>${t("challenge.true_location")}</b><br>${formatPlace(sampleGuess)}`)
            .addTo(challengeSession.carouselMap);
          challengeSession.carouselMarkers["__true__"] = trueMarker;

          // Add all player pins and connect dashed lines to true location
          roundGuesses.forEach((g) => {
            if (g.guessed_latitude !== null && g.guessed_longitude !== null) {
              const latlng = L.latLng(g.guessed_latitude, g.guessed_longitude);
              bounds.extend(latlng);
              const pKey = `player_${g.player_name}`;
              challengeSession.carouselTrueCoords[pKey] = { lat: g.guessed_latitude, lng: g.guessed_longitude };

              const color = playerColor(g.player_name);
              const initial = playerInitial(g.player_name);
              const icon = createPinIcon(initial, color);

              // Dashed connector polyline
              L.polyline([trueLatLng, latlng], {
                color,
                weight: 3,
                dashArray: "8, 8",
                opacity: 0.85,
              }).addTo(challengeSession.carouselMap);

              const distStr = g.distance_km !== null ? ` (${formatDistance(g.distance_km)})` : "";
              const marker = L.marker(latlng, { icon })
                .bindPopup(`<b>${g.player_name}</b><br>${g.round_score} pts${distStr}`)
                .addTo(challengeSession.carouselMap);
              challengeSession.carouselMarkers[pKey] = marker;
            }
          });
        }

        if (bounds.isValid()) {
          fitMapToBounds(challengeSession.carouselMap, bounds, { padding: [50, 50], maxZoom: 15 });
        }
      }
    }

    // 3. Render Date Comparison Table (only if date_mode is enabled)
    if (extraEl) {
      if (!isDateEnabled) {
        extraEl.innerHTML = "";
        extraEl.classList.add("hidden");
      } else {
        extraEl.classList.remove("hidden");
        const sampleWithDate = roundGuesses.find((g) => g.actual_date || g.actual_year);
        if (sampleWithDate) {
          const actualDateStr = sampleWithDate.actual_date
            ? formatDate(sampleWithDate.actual_date, { year: "numeric", month: "short", day: "numeric" })
            : formatMonth(sampleWithDate.actual_year, sampleWithDate.actual_month);

          const validGuesses = roundGuesses
            .filter((g) => g.guessed_year && g.guessed_month)
            .sort((a, b) => (b.date_points || 0) - (a.date_points || 0) || (a.date_diff_days ?? 999999) - (b.date_diff_days ?? 999999));

          const topScore = validGuesses.length > 0 ? (validGuesses[0].date_points || 0) : 0;

          extraEl.innerHTML = `
            <div class="round-date-comparison">
              <div class="date-comp-head">
                <div class="date-comp-title">
                  <span>📅 ${t("game.date_guess_label")}</span>
                </div>
                <div class="date-comp-truth">
                  <span class="date-comp-truth-icon">✓</span>
                  <strong>${t("challenge.true_date")}:</strong>
                  <span>${actualDateStr}</span>
                </div>
              </div>
              <div class="table-scroll date-table-scroll">
                <table class="summary-table round-date-table">
                  <thead>
                    <tr>
                      <th class="col-player">${t("reveal.col_player")}</th>
                      <th class="col-guess text-center">${t("reveal.col_guessed")}</th>
                      <th class="col-error text-center">${t("reveal.col_date_error")}</th>
                      <th class="col-score text-right">${t("reveal.col_points")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    ${
                      validGuesses.length === 0
                        ? `<tr><td colspan="4" class="text-center text-muted py-2">${t("fmt.no_guess")}</td></tr>`
                        : validGuesses
                            .map((g, idx) => {
                              const pDateStr = formatMonth(g.guessed_year, g.guessed_month);
                              const guessWithActual = {
                                ...g,
                                actual_year: g.actual_year ?? sampleWithDate.actual_year,
                                actual_month: g.actual_month ?? sampleWithDate.actual_month,
                              };
                              const errStr = formatMonthError(guessWithActual);
                              const isCurrent = g.player_name === challengeSession.sessionPlayerName;
                              const isWinner = idx === 0 && topScore > 0 && validGuesses.length > 1;
                              return `
                                <tr class="${isCurrent ? "highlight-player-row" : ""} ${isWinner ? "winner-row" : ""}">
                                  <td class="col-player">
                                    ${formatPlayerCellHtml(g.player_name, { isWinner, isCurrent })}
                                  </td>
                                  <td class="col-guess text-center">${pDateStr}</td>
                                  <td class="col-error text-center text-muted">${errStr}</td>
                                  <td class="col-score text-right font-bold">+${g.date_points || 0} pts</td>
                                </tr>
                              `;
                            })
                            .join("")
                    }
                  </tbody>
                </table>
              </div>
            </div>
          `;
        } else {
          extraEl.innerHTML = "";
        }
      }
    }
  },

  /**
   * Build aggregated player statistics from round guesses for awards calculation.
   * @param {object} leaderboardData
   * @returns {Record<string, object>}
   */
  buildPlayerStats(leaderboardData) {
    const stats = {};

    // Initialize stats for each player
    (leaderboardData.leaderboard || []).forEach((p) => {
      stats[p.player_name] = {
        totalDistanceKm: 0,
        distanceCount: 0,
        totalDateDiffDays: 0,
        dateCount: 0,
        perfectLocationCount: 0,
        perfectDateCount: 0,
        perfectRounds: 0,
        timedOutCount: 0,
        fastRoundCount: 0,
        totalDurationSec: p.total_time_seconds || 0,
      };
    });

    const isLocationEnabled = challengeSession.challengeData?.location_mode !== false && leaderboardData?.location_mode !== false;
    const isDateEnabled = challengeSession.challengeData?.date_mode !== false && leaderboardData?.date_mode !== false;

    // Aggregate individual photo guesses and group by round
    const playerRoundGuesses = new Map();
    const seenPlayerRounds = new Set();

    (leaderboardData.round_guesses || []).forEach((g) => {
      const pStats = stats[g.player_name];
      if (!pStats) return;

      const isLocPerfect = Boolean(
        g.is_correct_location ||
        (g.distance_km !== null && (g.distance_km < 1 || g.location_points === 100))
      );
      const isDatePerfect = Boolean(
        g.is_correct_date_order ||
        (g.date_diff_days !== null && (g.date_diff_days === 0 || g.date_points === 100))
      );

      if (g.distance_km !== null) {
        pStats.totalDistanceKm += g.distance_km;
        pStats.distanceCount++;
        if (isLocPerfect) {
          pStats.perfectLocationCount++;
        }
      }

      if (g.date_diff_days !== null) {
        pStats.totalDateDiffDays += g.date_diff_days;
        pStats.dateCount++;
        if (isDatePerfect) {
          pStats.perfectDateCount++;
        }
      }

      const roundKey = `${g.player_name}_${g.round_index}`;
      if (!playerRoundGuesses.has(roundKey)) {
        playerRoundGuesses.set(roundKey, []);
      }
      playerRoundGuesses.get(roundKey).push({ g, isLocPerfect, isDatePerfect });

      if (!seenPlayerRounds.has(roundKey)) {
        seenPlayerRounds.add(roundKey);
        if (g.time_taken_seconds > 0 && g.time_taken_seconds <= 30) {
          pStats.fastRoundCount++;
        }
      }
    });

    // Evaluate perfect rounds across all items in each round
    playerRoundGuesses.forEach((items, roundKey) => {
      const playerName = items[0].g.player_name;
      const pStats = stats[playerName];
      if (!pStats) return;

      const allLocPerfect = !isLocationEnabled || items.every((i) => i.isLocPerfect);
      const allDatePerfect = !isDateEnabled || items.every((i) => i.isDatePerfect);

      if (allLocPerfect && allDatePerfect && (isLocationEnabled || isDateEnabled)) {
        pStats.perfectRounds++;
      }
    });

    return stats;
  },

  /**
   * Render HTML for standings table rows with data attributes for live updates and animations.
   * @param {Array} leaderboard
   * @param {number} totalRoundsCount
   * @param {boolean} isSettled
   * @returns {string}
   */
  renderStandingsRows(leaderboard, totalRoundsCount, isSettled) {
    return (leaderboard || [])
      .map((p) => {
        const isFin = p.is_finished || p.completed_rounds >= totalRoundsCount;
        const roundsBadge = formatRoundsBadge(p.completed_rounds, totalRoundsCount, isFin);
        const isCurrent = p.player_name === challengeSession.sessionPlayerName;
        const isWinner = p.is_winner && isSettled;
        return `
          <tr data-player-name="${p.player_name}" data-total-score="${p.total_score}" class="${isCurrent ? "highlight-player-row" : ""} ${isWinner ? "winner-row" : ""}">
            <td class="col-rank">${formatRankBadge(p.rank, { showNumber: true })}</td>
            <td class="col-player">
              ${formatPlayerCellHtml(p.player_name, { isWinner, isCurrent })}
            </td>
            <td class="col-rounds text-center">
              ${roundsBadge}
            </td>
            ${challengeSession.challengeData?.location_mode !== false ? `<td class="col-score text-right">${p.location_score !== null && p.location_score !== undefined ? `${p.location_score}` : "—"}</td>` : ""}
            ${challengeSession.challengeData?.date_mode !== false ? `<td class="col-score text-right">${p.date_score !== null && p.date_score !== undefined ? `${p.date_score}` : "—"}</td>` : ""}
            <td class="col-score col-total-score text-right font-bold">${p.total_score}</td>
            <td class="col-accuracy text-right hide-on-mobile">${p.accuracy_pct}%</td>
          </tr>
        `;
      })
      .join("");
  },

  /**
   * Start 3-second social polling on Grand Reveal screen while challenge is in progress.
   */
  startSummaryPolling() {
    challengeSession.stopPolling();
    let isInitial = true;

    const poll = async () => {
      if (!challengeSession.challengeData) return;
      try {
        const data = await api(
          `/api/challenge/${encodeURIComponent(challengeSession.challengeData.capability_token)}/leaderboard`,
          {
            headers: {
              "X-Player-Token": challengeSession.sessionToken,
            },
          }
        );
        this.updateSummaryLive(data, { isInitial });
        isInitial = false;
      } catch (err) {
        console.warn("Summary polling error:", err);
      }
    };

    challengeSession.pollingInterval = setInterval(poll, POLL_INTERVAL_MS);
  },

  /**
   * Dynamically update Grand Reveal UI when polling detects new submissions or player completions.
   * @param {object} data
   * @param {object} [options]
   * @param {boolean} [options.isInitial=false]
   */
  updateSummaryLive(data, { isInitial = false } = {}) {
    if (!el.challengeCard || el.challengeCard.classList.contains("hidden") || !data || !data.leaderboard) {
      return;
    }

    const prevData = challengeSession.cachedLeaderboardData;
    const oldLeaderboard = prevData?.leaderboard || [];
    const oldMap = new Map(oldLeaderboard.map((p) => [p.player_name, p]));
    const totalRoundsCount = data.total_rounds || challengeSession.totalRounds;

    const finishedPlayers = data.leaderboard.filter((p) => p.is_finished || p.completed_rounds >= totalRoundsCount);
    const hasUnfinishedPlayers = data.leaderboard.some((p) => !p.is_finished && p.completed_rounds < totalRoundsCount);
    const wasSettled = oldLeaderboard.filter((p) => p.is_finished || p.completed_rounds >= totalRoundsCount).length >= 2;
    const isSettled = finishedPlayers.length >= 2;

    const updatedPlayers = [];

    // 1. Detect diffs for Activity Toasts (Option 1)
    if (!isInitial) {
      data.leaderboard.forEach((newP) => {
        const oldP = oldMap.get(newP.player_name);
        if (!oldP) {
          updatedPlayers.push(newP);
          showActivityToast({
            icon: "👥",
            playerName: newP.player_name,
            title: `${newP.player_name} joined the challenge!`,
          });
        } else {
          const wasFin = oldP.is_finished || oldP.completed_rounds >= totalRoundsCount;
          const nowFin = newP.is_finished || newP.completed_rounds >= totalRoundsCount;
          if (!wasFin && nowFin) {
            updatedPlayers.push(newP);
            showActivityToast({
              icon: "🏆",
              playerName: newP.player_name,
              score: newP.total_score,
              title: t("challenge.player_finished_challenge", newP.player_name, newP.rank),
            });
          } else if (newP.completed_rounds > oldP.completed_rounds) {
            updatedPlayers.push(newP);
            const diff = newP.total_score - oldP.total_score;
            showActivityToast({
              icon: "🎯",
              playerName: newP.player_name,
              score: diff > 0 ? diff : null,
              title: t("challenge.player_submitted_round", newP.player_name, newP.completed_rounds, diff > 0 ? diff : 0),
            });
          }
        }
      });
    } else {
      data.leaderboard.forEach((newP) => {
        const oldP = oldMap.get(newP.player_name);
        if (!oldP || newP.completed_rounds > oldP.completed_rounds || newP.total_score !== oldP.total_score) {
          updatedPlayers.push(newP);
        }
      });
    }

    // Register colors for any newly appeared players
    data.leaderboard.forEach((p) => {
      if (p.player_color) {
        registerPlayerColor(p.player_name, p.player_color);
      }
    });

    // 2. Update Live Status Pill and Header Meta (Option 3)
    const metaTallyEl = document.getElementById("grand-reveal-meta-tally");
    if (metaTallyEl) {
      metaTallyEl.textContent = `${totalRoundsCount} ${t("challenge.rounds")} • ${t("challenge.participants", data.leaderboard.length)}`;
    }

    const statusEl = document.getElementById("grand-reveal-live-status");
    const pillEl = document.getElementById("grand-reveal-live-pill");
    if (statusEl && pillEl) {
      const prevTally = statusEl.textContent;
      const newTally = t("challenge.live_finished_tally", finishedPlayers.length, data.leaderboard.length);
      statusEl.textContent = newTally;
      if (!isInitial && prevTally && prevTally !== newTally) {
        pillEl.classList.remove("bump");
        void pillEl.offsetWidth;
        pillEl.classList.add("bump");
      }
    }

    // 3. Dynamic Provisional-to-Podium Transition (Option 4)
    if (!wasSettled && isSettled) {
      const provisionalCard = document.getElementById("grand-reveal-provisional");
      if (provisionalCard) {
        const podiumWrap = document.createElement("div");
        podiumWrap.className = "grand-reveal-podium-wrap";
        podiumWrap.id = "grand-reveal-podium-section";
        podiumWrap.innerHTML = `
          <div id="grand-reveal-podium" class="summary-winner"></div>
          ${(isSettled && hasUnfinishedPlayers) ? `
            <div class="podium-finished-note" id="grand-reveal-podium-finished-note">
              <span class="note-icon" aria-hidden="true">🏁</span>
              <span data-i18n="challenge.podium_finished_notice">${t("challenge.podium_finished_notice")}</span>
            </div>
          ` : ""}
        `;
        provisionalCard.replaceWith(podiumWrap);

        const podiumEl = document.getElementById("grand-reveal-podium");
        const winners = finishedPlayers.filter((p) => p.is_winner).map((p) => p.player_name);
        renderPodium(
          {
            players: finishedPlayers,
            winners: winners.length > 0 ? winners : [finishedPlayers[0]?.player_name].filter(Boolean),
            is_concluded: Boolean(data.is_concluded),
          },
          podiumEl
        );

        // Render Performance Awards
        const playerStats = this.buildPlayerStats(data);
        const grandRevealEl = el.challengeCard.querySelector(".challenge-grand-reveal");
        renderAwards(
          {
            game_mode: data.game_mode,
            location_mode: challengeSession.challengeData.location_mode !== false,
            date_mode: challengeSession.challengeData.date_mode !== false,
            players: data.leaderboard,
          },
          playerStats,
          grandRevealEl,
          podiumEl
        );

        launchGoldConfetti();
        playVictoryFanfare();
      }
    } else if (isSettled) {
      // Refresh podium if any winner/ranking state updated
      const podiumEl = document.getElementById("grand-reveal-podium");
      if (podiumEl && updatedPlayers.length > 0) {
        const winners = finishedPlayers.filter((p) => p.is_winner).map((p) => p.player_name);
        renderPodium(
          {
            players: finishedPlayers,
            winners: winners.length > 0 ? winners : [finishedPlayers[0]?.player_name].filter(Boolean),
            is_concluded: Boolean(data.is_concluded),
          },
          podiumEl
        );
      }
    }

    // 4. Update Standings Table Rows & Flash (Option 2)
    const tableBody = document.querySelector("#grand-reveal-table tbody");
    if (tableBody && updatedPlayers.length > 0) {
      tableBody.innerHTML = this.renderStandingsRows(data.leaderboard, totalRoundsCount, isSettled);

      if (!isInitial) {
        const updatedNames = new Set(updatedPlayers.map((p) => p.player_name));
        Array.from(tableBody.querySelectorAll("tr[data-player-name]")).forEach((tr) => {
          const name = tr.getAttribute("data-player-name");
          if (updatedNames.has(name)) {
            const color = playerColor(name);
            tr.classList.remove("row-arrival-flash");
            tr.style.setProperty("--player-accent", color);
            tr.style.setProperty("--player-accent-alpha", `${color}33`);
            void tr.offsetWidth;
            tr.classList.add("row-arrival-flash");

            // Score rollup animation
            const totalScoreCell = tr.querySelector(".col-total-score");
            const targetScore = Number(tr.getAttribute("data-total-score") || 0);
            if (totalScoreCell && !isNaN(targetScore)) {
              animateScoreRollup(totalScoreCell, targetScore, targetScore * 1.5, "", false, 0);
            }
          }
        });
      }
    }

    // 5. Update cached data and carousel scatter map
    challengeSession.cachedLeaderboardData = data;
    if (data.game_mode !== "album_shuffle" && challengeSession.carouselRoundIndex !== undefined) {
      this.renderCarouselRound(data, challengeSession.carouselRoundIndex);
    }

    // 6. Stop polling if all players have completed and match is settled
    if (!hasUnfinishedPlayers && isSettled) {
      challengeSession.stopPolling();
    }
  },
};

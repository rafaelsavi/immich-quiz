/**
 * Challenge Grand Reveal Summary Controller.
 *
 * Coordinates challenge results with the unified match review screen,
 * managing real-time multiplayer background polling, activity toast notifications,
 * dynamic provisional-to-podium transitions, and animated score updates.
 */

import { api } from "../api.js";
import { state, el } from "../state.js";
import {
  registerPlayerColor,
  playerColor,
  escapeHtml,
  formatRankBadge,
  formatRoundsBadge,
  formatPlayerCellHtml,
  formatMonth,
  formatMonthError,
  formatDistance,
  playerInitial,
} from "../formatters.js";
import { t, formatDate } from "../i18n.js";
import { renderPodium } from "../summary/podium.js";
import { renderAwards } from "../summary/awards.js";
import { renderSummaryTable, flashUpdatedSummaryRows } from "../summary/table.js";
import { showMatchSummaryByMatchId } from "../screens/summary.js";
import { navigate } from "../router.js";
import { challengeSession, POLL_INTERVAL_MS } from "./session.js";
import { renderErrorScreen } from "./landing.js";
import { showActivityToast } from "../components/activity_toast.js";
import { launchGoldConfetti, animateScoreRollup } from "../effects.js";
import { playVictoryFanfare } from "../audio.js";
import { createPinIcon, fitMapToBounds, createStandardMap, unregisterActiveMap } from "../maps.js";
import { openPhotoLightbox } from "../components/lightbox.js";

export const challengeSummary = {
  /**
   * Grand Reveal Summary Screen at the end of the challenge.
   * Delegates view layout to the unified match review screen (#summary-card).
   * @param {object} [options]
   * @param {boolean} [options.updateUrl=true]
   */
  async showGrandReveal({ updateUrl = true } = {}) {
    challengeSession.stopPolling();
    challengeSession.cleanupMaps();
    state.currentScreen = null;
    state.currentQuestion = null;
    challengeSession.lastRoundResult = null;

    try {
      const capToken = challengeSession.challengeData?.capability_token;
      const data = await api(
        `/play/api/${encodeURIComponent(capToken)}/leaderboard`,
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

      if (updateUrl && capToken) {
        navigate(`/play/${encodeURIComponent(capToken)}/summary`, { replace: true, silent: true });
      }

      launchGoldConfetti();
      playVictoryFanfare();

      const totalRoundsCount = data.total_rounds || challengeSession.totalRounds || 1;
      const finishedPlayers = (data.leaderboard || []).filter(
        (p) => p.is_finished || p.completed_rounds >= totalRoundsCount
      );
      const hasUnfinishedPlayers = (data.leaderboard || []).some(
        (p) => !p.is_finished && p.completed_rounds < totalRoundsCount
      );
      const isSettled = finishedPlayers.length >= 2;
      const isConcluded = Boolean(
        data.is_concluded ||
        challengeSession.challengeData?.is_active === false ||
        (challengeSession.challengeData?.expires_at && new Date() > new Date(challengeSession.challengeData.expires_at))
      );

      const callerCompletedRound =
        typeof data.up_to_round === "number"
          ? data.up_to_round
          : (challengeSession.currentRoundIndex - 1);
      const canReplay = Boolean(
        isConcluded ||
        data.is_game_over ||
        (callerCompletedRound >= 0 && callerCompletedRound >= totalRoundsCount - 1)
      );

      const replayMatchId =
        data.challenge_id ||
        data.match_id ||
        (capToken ? challengeSession.loadSession(capToken)?.matchId : null) ||
        capToken;

      // Delegate rendering to the unified review controller inside #summary-card
      await showMatchSummaryByMatchId(replayMatchId, {
        mode: "summary",
        playFanfare: false,
        isChallenge: true,
        challengeData: data,
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
   * Render standings table html markup.
   * @param {Array<object>} leaderboard
   * @param {number} totalRoundsCount
   * @param {boolean} isSettled
   * @returns {string}
   */
  renderStandingsTableHtml(leaderboard, totalRoundsCount, isSettled) {
    return `
      <div class="table-scroll">
        <table id="grand-reveal-table" class="summary-table standings-table">
          <thead>
            <tr>
              <th class="col-rank">${t("summary.col_rank")}</th>
              <th class="col-player">${t("summary.col_player")}</th>
              <th class="col-rounds text-center">${t("summary.col_rounds")}</th>
              ${challengeSession.challengeData?.location_mode !== false ? `<th class="col-score text-right">${t("summary.col_location")}</th>` : ""}
              ${challengeSession.challengeData?.date_mode !== false ? `<th class="col-score text-right">${t("summary.col_date")}</th>` : ""}
              <th class="col-score text-right">${t("summary.col_total")}</th>
              <th class="col-acc text-right hide-on-mobile">${t("summary.col_accuracy")}</th>
            </tr>
          </thead>
          <tbody>
            ${this.renderStandingsRows(leaderboard, totalRoundsCount, isSettled)}
          </tbody>
        </table>
      </div>
    `;
  },

  /**
   * Render standings table rows.
   * @param {Array<object>} leaderboard
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
          <tr data-player-name="${escapeHtml(p.player_name)}" data-total-score="${escapeHtml(p.total_score)}" class="${isCurrent ? "highlight-player-row" : ""} ${isWinner ? "winner-row" : ""}">
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
            <td class="col-acc text-right hide-on-mobile">${p.accuracy_pct}%</td>
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
          `/play/api/${encodeURIComponent(challengeSession.challengeData.capability_token)}/leaderboard`,
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
    if (!el.summaryCard || el.summaryCard.classList.contains("hidden") || !data || !data.leaderboard) {
      return;
    }

    const prevData = challengeSession.cachedLeaderboardData;
    const oldLeaderboard = prevData?.leaderboard || [];
    const oldMap = new Map(oldLeaderboard.map((p) => [p.player_name, p]));
    const totalRoundsCount = data.total_rounds || challengeSession.totalRounds || 1;

    const finishedPlayers = data.leaderboard.filter(
      (p) => p.is_finished || p.completed_rounds >= totalRoundsCount
    );
    const hasUnfinishedPlayers = data.leaderboard.some(
      (p) => !p.is_finished && p.completed_rounds < totalRoundsCount
    );
    const wasSettled = oldLeaderboard.filter(
      (p) => p.is_finished || p.completed_rounds >= totalRoundsCount
    ).length >= 2;
    const isSettled = finishedPlayers.length >= 2;

    const updatedPlayers = [];

    // 1. Detect diffs for Activity Toasts
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
              title: t(
                "challenge.player_submitted_round",
                newP.player_name,
                newP.completed_rounds,
                diff > 0 ? diff : 0
              ),
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

    // 2. Update Live Status Pill
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

    // 3. Dynamic Provisional-to-Podium Transition
    if (!wasSettled && isSettled) {
      const provisionalCard = document.getElementById("grand-reveal-provisional");
      const summaryWinner = document.getElementById("summary-winner");
      if (provisionalCard && summaryWinner) {
        summaryWinner.innerHTML = `
          <div class="grand-reveal-podium-wrap" id="grand-reveal-podium-section">
            <div id="grand-reveal-podium" class="summary-winner"></div>
          </div>
        `;
        const podiumEl = document.getElementById("grand-reveal-podium") || summaryWinner;
        const winners = finishedPlayers.filter((p) => p.is_winner).map((p) => p.player_name);
        renderPodium(
          {
            players: finishedPlayers,
            winners: winners.length > 0 ? winners : [finishedPlayers[0]?.player_name].filter(Boolean),
            is_concluded: Boolean(data.is_concluded),
          },
          podiumEl
        );

        const playerStats = this.buildPlayerStats(data);
        renderAwards(
          {
            game_mode: data.game_mode,
            location_mode: challengeSession.challengeData?.location_mode !== false,
            date_mode: challengeSession.challengeData?.date_mode !== false,
            players: data.leaderboard,
          },
          playerStats,
          summaryWinner,
          podiumEl
        );

        launchGoldConfetti();
        playVictoryFanfare();
      }
    } else if (isSettled) {
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

    // 4. Update Unified Standings Table Rows & Flash
    if (updatedPlayers.length > 0) {
      const summaryObj = {
        is_challenge: true,
        play_mode: "challenge",
        location_mode: challengeSession.challengeData?.location_mode !== false && data.location_mode !== false,
        date_mode: challengeSession.challengeData?.date_mode !== false && data.date_mode !== false,
        rounds_played: totalRoundsCount,
        total_rounds: totalRoundsCount,
        max_possible_score: totalRoundsCount * 10000,
        players: data.leaderboard,
        is_settled: isSettled,
      };
      renderSummaryTable(summaryObj, state.perfectCounts, {
        currentSessionPlayerName: challengeSession.sessionPlayerName,
      });

      if (!isInitial) {
        const updatedNames = new Set(updatedPlayers.map((p) => p.player_name));
        Array.from(document.querySelectorAll("#summary-table tr[data-player-name], #grand-reveal-table tr[data-player-name]")).forEach((tr) => {
          const name = tr.getAttribute("data-player-name");
          if (updatedNames.has(name)) {
            const color = playerColor(name);
            tr.classList.remove("row-arrival-flash");
            tr.style.setProperty("--player-accent", color);
            tr.style.setProperty("--player-accent-alpha", `${color}33`);
            void tr.offsetWidth;
            tr.classList.add("row-arrival-flash");

            const totalScoreCell = tr.querySelector(".col-total-score");
            const targetScore = Number(tr.getAttribute("data-total-score") || 0);
            if (totalScoreCell && !isNaN(targetScore)) {
              animateScoreRollup(totalScoreCell, targetScore, targetScore * 1.5, "", false, 0);
            }
          }
        });
        flashUpdatedSummaryRows(updatedPlayers);
      }
    }

    // 5. Update cached data and carousel scatter map if active round data changed
    const activeRoundIdx = challengeSession.carouselRoundIndex;
    const prevGuesses = (prevData?.round_guesses || []).filter((g) => g.round_index === activeRoundIdx);
    const newGuesses = (data.round_guesses || []).filter((g) => g.round_index === activeRoundIdx);

    challengeSession.cachedLeaderboardData = data;

    if (document.getElementById("carousel-round-content") && data.game_mode !== "unshuffle" && activeRoundIdx !== undefined) {
      const hasRoundGuessesChanged =
        prevGuesses.length !== newGuesses.length ||
        newGuesses.some((ng) => {
          const pg = prevGuesses.find((g) => g.player_name === ng.player_name);
          if (!pg) return true;
          return (
            pg.round_score !== ng.round_score ||
            pg.location_points !== ng.location_points ||
            pg.date_points !== ng.date_points
          );
        });

      if (hasRoundGuessesChanged) {
        this.renderCarouselRound(data, activeRoundIdx, { preserveView: true });
      }
    }

    // 6. Stop polling if all players have completed and match is settled
    if (!hasUnfinishedPlayers && isSettled) {
      challengeSession.stopPolling();
    }
  },

  /**
   * Render a specific round inside the Grand Reveal Carousel with scatter map and date comparisons.
   * @param {object} data
   * @param {number} roundIdx
   * @param {object} [options]
   * @param {boolean} [options.preserveView=false]
   */
  renderCarouselRound(data, roundIdx, { preserveView = false } = {}) {
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
        if (photoImg.src !== mediaUrl) {
          photoImg.src = mediaUrl;
        }
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
        } catch (_) { }
        challengeSession.carouselMap = null;
      }
      challengeSession.carouselLayers = [];
      challengeSession.carouselMarkers = {};
    } else {
      if (mapShell) {
        mapShell.classList.remove("hidden");
      }
      const mapContainer = document.getElementById("scatter-map");
      if (mapShell && mapContainer && window.L) {
        const needsNewMap =
          !challengeSession.carouselMap ||
          !challengeSession.carouselMap.getContainer ||
          challengeSession.carouselMap.getContainer() !== mapContainer;

        if (needsNewMap) {
          challengeSession.carouselMap = createStandardMap("scatter-map", {
            existingMap: challengeSession.carouselMap,
            titleKey: "game.fullscreen_map_title",
          });
          challengeSession.carouselLayers = [];
        } else {
          (challengeSession.carouselLayers || []).forEach((layer) => {
            try {
              challengeSession.carouselMap.removeLayer(layer);
            } catch (_) { }
          });
          challengeSession.carouselLayers = [];
        }

        const bounds = L.latLngBounds();
        const sampleWithLoc = roundGuesses.find((g) => {
          const p = g.pinpoint || g;
          return p.actual_latitude != null && p.actual_longitude != null;
        });

        if (sampleWithLoc) {
          const sampleP = sampleWithLoc.pinpoint || sampleWithLoc;
          const trueLat = Number(sampleP.actual_latitude);
          const trueLng = Number(sampleP.actual_longitude);
          const trueLatLng = L.latLng(trueLat, trueLng);
          bounds.extend(trueLatLng);

          const trueIcon = createPinIcon("★", "#22c55e");
          const trueMarker = L.marker(trueLatLng, { icon: trueIcon })
            .bindPopup(`<b>${t("game.actual_location")}</b>`)
            .addTo(challengeSession.carouselMap);
          challengeSession.carouselLayers.push(trueMarker);

          roundGuesses.forEach((g) => {
            const gp = g.pinpoint || g;
            const gLat = Number(gp.guessed_latitude);
            const gLng = Number(gp.guessed_longitude);
            if (!isNaN(gLat) && !isNaN(gLng) && (gLat !== 0 || gLng !== 0)) {
              const latlng = L.latLng(gLat, gLng);
              bounds.extend(latlng);
              const color = playerColor(g.player_name);
              const initial = playerInitial(g.player_name);
              const icon = createPinIcon(initial, color);

              const line = L.polyline([trueLatLng, latlng], {
                color,
                weight: 3,
                dashArray: "8, 8",
                opacity: 0.85,
              }).addTo(challengeSession.carouselMap);
              challengeSession.carouselLayers.push(line);

              const distStr = gp.distance_km !== null && gp.distance_km !== undefined ? ` (${formatDistance(gp.distance_km)})` : "";
              const marker = L.marker(latlng, { icon })
                .bindPopup(`<b>${g.player_name}</b><br>${g.round_score} pts${distStr}`)
                .addTo(challengeSession.carouselMap);
              challengeSession.carouselLayers.push(marker);
            }
          });
        }

        if (bounds.isValid() && !preserveView) {
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
        const sampleWithDate = roundGuesses.find((g) => {
          const p = g.pinpoint || g;
          return p.actual_date || p.actual_year;
        });
        if (sampleWithDate) {
          const sampleP = sampleWithDate.pinpoint || sampleWithDate;
          const actualDateStr = sampleP.actual_date
            ? formatDate(sampleP.actual_date, { year: "numeric", month: "short", day: "numeric" })
            : formatMonth(sampleP.actual_year, sampleP.actual_month);

          const validGuesses = roundGuesses
            .filter((g) => {
              const p = g.pinpoint || g;
              return p.guessed_year && p.guessed_month;
            })
            .sort((a, b) => {
              const ap = a.pinpoint || a;
              const bp = b.pinpoint || b;
              return (b.date_points || 0) - (a.date_points || 0) || (ap.date_diff_days ?? 999999) - (bp.date_diff_days ?? 999999);
            });

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
                    ${validGuesses.length === 0
                      ? `<tr><td colspan="4" class="text-center text-muted py-2">${t("fmt.no_guess")}</td></tr>`
                      : validGuesses
                        .map((g, idx) => {
                          const pp = g.pinpoint || g;
                          const pDateStr = formatMonth(pp.guessed_year, pp.guessed_month);
                          const guessWithActual = {
                            ...pp,
                            player_name: g.player_name,
                            actual_year: pp.actual_year ?? sampleP.actual_year,
                            actual_month: pp.actual_month ?? sampleP.actual_month,
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

    const isLocationEnabled =
      challengeSession.challengeData?.location_mode !== false && leaderboardData?.location_mode !== false;
    const isDateEnabled =
      challengeSession.challengeData?.date_mode !== false && leaderboardData?.date_mode !== false;

    const playerRoundGuesses = new Map();
    const seenPlayerRounds = new Set();

    (leaderboardData.round_guesses || []).forEach((g) => {
      const pStats = stats[g.player_name];
      if (!pStats) return;

      const pp = g.pinpoint;
      const ash = g.unshuffle;

      const isLocPerfect = Boolean(
        ash?.is_correct_location ||
        (pp?.distance_km !== null && pp?.distance_km !== undefined && (pp.distance_km < 1 || g.location_points === 100))
      );
      const isDatePerfect = Boolean(
        ash?.is_correct_date_order ||
        (pp?.date_diff_days !== null && pp?.date_diff_days !== undefined && (pp.date_diff_days === 0 || g.date_points === 100))
      );

      if (pp?.distance_km != null) {
        pStats.totalDistanceKm += pp.distance_km;
        pStats.distanceCount++;
        if (isLocPerfect) {
          pStats.perfectLocationCount++;
        }
      } else if (ash && isLocPerfect) {
        pStats.perfectLocationCount++;
      }

      if (pp?.date_diff_days != null) {
        pStats.totalDateDiffDays += pp.date_diff_days;
        pStats.dateCount++;
        if (isDatePerfect) {
          pStats.perfectDateCount++;
        }
      } else if (ash && isDatePerfect) {
        pStats.perfectDateCount++;
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

    playerRoundGuesses.forEach((items) => {
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
};

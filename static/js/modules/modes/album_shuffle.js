import { t } from "../i18n.js";
import { state, el } from "../state.js";
import { updateSubmitState } from "../maps.js";
import { renderGuessingModeSettings } from "./common.js";

let shuffleMap = null;
let revealShuffleMap = null;
let shuffleMarkers = {}; // pinId -> Leaflet marker

export const albumShuffleMode = {
  name: "album_shuffle",

  renderSettings(containerEl) {
    renderGuessingModeSettings(containerEl);
  },

  getModePayload() {
    const locCheckbox = document.getElementById("goal-location");
    const dateCheckbox = document.getElementById("goal-date");
    return {
      game_mode: "album_shuffle",
      location_mode: locCheckbox ? locCheckbox.checked : true,
      date_mode: dateCheckbox ? dateCheckbox.checked : true,
    };
  },

  renderQuestion(guessingUi, questionData) {
    const pinpointUi = document.getElementById("pinpoint-ui");
    if (pinpointUi) pinpointUi.classList.add("hidden");

    let uiContainer = document.getElementById("album-shuffle-ui");
    if (!uiContainer) {
      uiContainer = document.createElement("div");
      uiContainer.id = "album-shuffle-ui";
      guessingUi.appendChild(uiContainer);
    }
    uiContainer.classList.remove("hidden");
    uiContainer.replaceChildren();

    // Initialize photo order & pin assignments
    const photos = questionData.batch_photos || [];
    state.albumShuffleState = {
      orderedPhotoIds: photos.map((p) => p.photo_id),
      selectedPhotoId: photos[0]?.photo_id || null,
      pinAssignments: {}, // photoId -> pinId
    };

    photos.forEach((p) => {
      state.albumShuffleState.pinAssignments[p.photo_id] = null;
    });

    const boardEl = document.createElement("div");
    boardEl.className = "shuffle-board";

    // Left Column: Map
    const mapCol = document.createElement("div");
    mapCol.className = "shuffle-map-column";
    const mapShell = document.createElement("div");
    mapShell.className = "map-shell";
    mapShell.id = "shuffle-map-shell";
    mapShell.style.height = "560px";

    // Add Map Fullscreen Button
    const mapFsBtn = document.createElement("button");
    mapFsBtn.type = "button";
    mapFsBtn.className = "map-fullscreen-btn";
    mapFsBtn.textContent = "Fullscreen";
    mapFsBtn.addEventListener("click", () => {
      if (document.fullscreenElement) {
        document.exitFullscreen().catch(() => { });
      } else {
        mapShell.requestFullscreen().catch(() => { });
      }
    });

    mapShell.appendChild(mapFsBtn);
    mapCol.appendChild(mapShell);

    // Right Column: Cards List with Sequence Info Banner, Rank Buttons (NO PIN DROPDOWN)
    const cardsCol = document.createElement("div");
    cardsCol.className = "shuffle-photo-column";
    cardsCol.id = "shuffle-cards-list";

    boardEl.append(mapCol, cardsCol);
    uiContainer.appendChild(boardEl);

    renderShuffleMap(mapShell, questionData.batch_pins, questionData);
    renderPhotoCardsList(cardsCol, questionData);
  },

  buildAnswerPayload(questionData, timedOut) {
    const orderedIds = state.albumShuffleState ? state.albumShuffleState.orderedPhotoIds || [] : [];
    const pinAssignments = state.albumShuffleState ? state.albumShuffleState.pinAssignments || {} : {};

    const answers = orderedIds.map((photoId, timelineIndex) => {
      return {
        photo_id: photoId,
        assigned_pin_id: pinAssignments[photoId] || null,
        assigned_timeline_index: timelineIndex,
      };
    });

    return {
      match_id: state.matchId,
      question_id: questionData.question_id,
      album_shuffle_answers: answers,
      timed_out: timedOut,
    };
  },

  renderReveal(revealUi, revealData) {
    revealUi.replaceChildren();
    revealUi.classList.remove("hidden");

    const batchReveal = revealData.batch_reveal || [];
    const playerResults = revealData.results || [];
    const libraryName = revealData.library_name || (state.currentQuestion ? state.currentQuestion.library_name : "");

    // Title
    const heading = document.createElement("h2");
    heading.style.textAlign = "center";
    heading.style.marginBottom = "1rem";
    heading.textContent = `Round ${revealData.round_number} of ${revealData.total_rounds} - Reveal`;

    // Multi-Player Summary Score Cards Container
    const scoreContainer = document.createElement("div");
    scoreContainer.style.display = "grid";
    scoreContainer.style.gridTemplateColumns = "repeat(auto-fit, minmax(280px, 1fr))";
    scoreContainer.style.gap = "1rem";
    scoreContainer.style.marginBottom = "1.5rem";

    playerResults.forEach((pRes) => {
      const scoreCard = document.createElement("div");
      scoreCard.className = "card";
      scoreCard.style.padding = "1rem";
      scoreCard.style.background = "linear-gradient(135deg, #f0fdfa 0%, #e0f2fe 100%)";
      scoreCard.style.border = "2px solid #0f7c7f";

      const rScore = pRes.round_score ?? pRes.total_score ?? 0;
      const lScore = pRes.location_score ?? 0;
      const dScore = pRes.date_score ?? 0;

      scoreCard.innerHTML = `
        <h3 style="margin:0 0 0.5rem 0; font-size:1.1rem; color:var(--accent);">${pRes.player_name}: ${rScore} pts</h3>
        <div style="font-size:0.9rem; font-weight:600; display:flex; flex-direction:column; gap:0.2rem;">
          ${revealData.location_mode ? `<span>📍 Location Pins: <strong>${lScore} / 100 pts</strong></span>` : ""}
          ${revealData.date_mode ? `<span>📅 Chronological Order: <strong>${dScore} / 100 pts</strong></span>` : ""}
        </div>
      `;
      scoreContainer.appendChild(scoreCard);
    });

    // Grid Layout for Map & Reveal List
    const revealBoard = document.createElement("div");
    revealBoard.className = "shuffle-board";

    // Map Column
    const mapCol = document.createElement("div");
    mapCol.className = "shuffle-map-column";
    const mapShell = document.createElement("div");
    mapShell.className = "map-shell";
    mapShell.id = "reveal-shuffle-map-shell";
    mapShell.style.height = "480px";
    mapCol.appendChild(mapShell);

    // Photos Breakdown Column
    const listCol = document.createElement("div");
    listCol.className = "shuffle-photo-column";

    // Sort batch items in TRUE chronological order (reverse=True -> Newest #1 down to Oldest #5)
    const sortedTrueBatch = [...batchReveal].sort((a, b) => {
      const dateA = a.actual_date ? new Date(a.actual_date).getTime() : 0;
      const dateB = b.actual_date ? new Date(b.actual_date).getTime() : 0;
      return dateB - dateA;
    });

    sortedTrueBatch.forEach((item, trueRankIdx) => {
      const photoCard = document.createElement("div");
      photoCard.className = "shuffle-card-row";
      photoCard.style.cursor = "default";
      photoCard.style.marginBottom = "0.75rem";

      // Rank Badge
      const rankBadge = document.createElement("div");
      rankBadge.className = "shuffle-rank-badge";
      rankBadge.textContent = `#${trueRankIdx + 1}`;

      // Thumbnail
      const imgUrl = `/api/media/${item.photo_id}?library_name=${encodeURIComponent(libraryName)}`;
      const thumbWrap = document.createElement("div");
      thumbWrap.className = "shuffle-card-thumb-wrap";
      const img = document.createElement("img");
      img.className = "shuffle-card-thumb-lg";
      img.src = imgUrl;
      img.alt = `Photo ${trueRankIdx + 1}`;
      img.addEventListener("click", () => openPhotoLightbox(imgUrl));
      thumbWrap.appendChild(img);

      // Multi-Player Details Breakdown
      const details = document.createElement("div");
      details.className = "shuffle-card-details";

      const dateStr = item.actual_date ? new Date(item.actual_date).toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" }) : "Unknown date";

      let playerBadgesHtml = "";
      playerResults.forEach((pRes) => {
        const pGuesses = pRes.album_shuffle_guesses || [];
        const pGuess = pGuesses.find((g) => g.photo_id === item.photo_id);
        const isPinCorrect = pGuess && pGuess.assigned_pin_id === item.true_pin_id;
        const pSubmittedRank = pGuess ? pGuess.assigned_timeline_index : null;
        const isRankCorrect = pSubmittedRank === trueRankIdx;

        playerBadgesHtml += `
          <div style="margin-top:0.4rem; font-size:0.82rem;">
            <strong>${pRes.player_name}:</strong>
            ${revealData.location_mode ? `<span class="shuffle-badge-reveal ${isPinCorrect ? "correct" : "incorrect"}">Pin ${pGuess && pGuess.assigned_pin_id ? pGuess.assigned_pin_id : "None"} ${isPinCorrect ? "✓" : "✗"}</span>` : ""}
            ${revealData.date_mode ? `<span class="shuffle-badge-reveal ${isRankCorrect ? "correct" : "incorrect"}">Rank ${pSubmittedRank !== null ? `#${pSubmittedRank + 1}` : "None"} ${isRankCorrect ? "✓" : "✗"}</span>` : ""}
          </div>
        `;
      });

      details.innerHTML = `
        <div style="font-size: 0.85rem; color: #64748b; font-weight: 600;">📅 True Date: ${dateStr} | True Pin: 📍 Pin ${item.true_pin_id}</div>
        ${playerBadgesHtml}
      `;

      photoCard.append(rankBadge, thumbWrap, details);
      listCol.appendChild(photoCard);
    });

    revealBoard.append(mapCol, listCol);

    // Next Round / Final Results Button
    const nextBtn = document.createElement("button");
    nextBtn.id = "next-round";
    nextBtn.className = "btn-primary";
    nextBtn.style.marginTop = "1.5rem";
    nextBtn.textContent = revealData.match_finished ? t("reveal.see_results_btn") : t("reveal.next_round_btn");

    nextBtn.addEventListener("click", () => {
      if (window.handleNextRoundClick) {
        window.handleNextRoundClick(revealData.match_finished);
      } else if (el.nextRound) {
        el.nextRound.click();
      }
    });

    revealUi.append(heading, scoreContainer, revealBoard, nextBtn);

    renderBatchRevealMap(mapShell, batchReveal);
  },
};

function renderPhotoCardsList(containerEl, questionData) {
  containerEl.replaceChildren();

  // Informational Banner informing user of chronological sequence
  if (questionData.date_mode) {
    const banner = document.createElement("div");
    banner.className = "shuffle-info-banner";
    banner.textContent = "ℹ️ Order photos from newest (#1) at top to oldest (#5) at bottom";
    containerEl.appendChild(banner);
  }

  const photos = questionData.batch_photos || [];
  const photoById = new Map(photos.map((p) => [p.photo_id, p]));
  const orderedIds = state.albumShuffleState ? state.albumShuffleState.orderedPhotoIds || [] : [];
  const pinAssignments = state.albumShuffleState ? state.albumShuffleState.pinAssignments || {} : {};

  orderedIds.forEach((photoId, index) => {
    const photo = photoById.get(photoId);
    if (!photo) return;

    const card = document.createElement("div");
    card.className = "shuffle-card-row";
    if (photoId === state.albumShuffleState.selectedPhotoId) {
      card.classList.add("selected");
    }

    card.addEventListener("click", () => {
      state.albumShuffleState.selectedPhotoId = photoId;
      document.querySelectorAll(".shuffle-card-row").forEach((c) => c.classList.remove("selected"));
      card.classList.add("selected");
      highlightMapMarker(pinAssignments[photoId]);
    });

    // Clean Rank Badge (#1, #2, #3...)
    const rankBadge = document.createElement("div");
    rankBadge.className = "shuffle-rank-badge";
    rankBadge.textContent = `#${index + 1}`;

    // Thumbnail (50% Larger 220px x 150px preview with Fullscreen Lightbox button)
    const thumbWrap = document.createElement("div");
    thumbWrap.className = "shuffle-card-thumb-wrap";

    const img = document.createElement("img");
    img.className = "shuffle-card-thumb-lg";
    img.src = photo.media_url;
    img.alt = `Photo ${index + 1}`;

    const fsBtn = document.createElement("button");
    fsBtn.type = "button";
    fsBtn.className = "shuffle-card-fullscreen-btn";
    fsBtn.textContent = "🔍";
    fsBtn.title = "View fullscreen photo";
    fsBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      openPhotoLightbox(photo.media_url);
    });

    thumbWrap.append(img, fsBtn);

    // Assigned Pin Badge Indicator (NO DROPDOWN - Map Click Only!)
    const pinBadgeWrap = document.createElement("div");
    pinBadgeWrap.className = "shuffle-card-details";

    const assignedPin = pinAssignments[photoId];
    const pinBadge = document.createElement("div");
    pinBadge.className = `shuffle-assigned-pin-badge ${assignedPin ? "assigned" : "unassigned"}`;
    pinBadge.textContent = assignedPin ? `📍 Pin ${assignedPin}` : "📍 Map Pin Unassigned";

    pinBadgeWrap.appendChild(pinBadge);

    // Compact Arrow Buttons (▲ Move up / ▼ Move down)
    const rankControls = document.createElement("div");
    rankControls.className = "shuffle-rank-controls";

    if (!questionData.date_mode) {
      rankControls.style.display = "none";
      rankBadge.style.display = "none";
    }

    const upBtn = document.createElement("button");
    upBtn.type = "button";
    upBtn.className = "shuffle-rank-btn";
    upBtn.textContent = "▲";
    upBtn.title = "Move Up (Newer)";
    upBtn.disabled = index === 0;
    upBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      if (index > 0) {
        const temp = orderedIds[index - 1];
        orderedIds[index - 1] = orderedIds[index];
        orderedIds[index] = temp;
        renderPhotoCardsList(containerEl, questionData);
      }
    });

    const downBtn = document.createElement("button");
    downBtn.type = "button";
    downBtn.className = "shuffle-rank-btn";
    downBtn.textContent = "▼";
    downBtn.title = "Move Down (Older)";
    downBtn.disabled = index === orderedIds.length - 1;
    downBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      if (index < orderedIds.length - 1) {
        const temp = orderedIds[index + 1];
        orderedIds[index + 1] = orderedIds[index];
        orderedIds[index] = temp;
        renderPhotoCardsList(containerEl, questionData);
      }
    });

    rankControls.append(upBtn, downBtn);

    card.append(rankBadge, thumbWrap, pinBadgeWrap, rankControls);
    containerEl.appendChild(card);
  });

  updateSubmitState();
}

function renderShuffleMap(containerEl, pins, questionData) {
  if (!window.L) return;
  if (shuffleMap) {
    shuffleMap.remove();
    shuffleMap = null;
  }
  shuffleMarkers = {};

  const mapShell = containerEl.id ? containerEl : document.getElementById("shuffle-map-shell");
  const map = L.map(mapShell).setView([20, 0], 2);
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    attribution: "&copy; OpenStreetMap",
  }).addTo(map);

  shuffleMap = map;
  const bounds = L.latLngBounds();
  const pinAssignments = state.albumShuffleState ? state.albumShuffleState.pinAssignments || {} : {};

  pins.forEach((pin) => {
    const lat = pin.latitude;
    const lon = pin.longitude;
    bounds.extend([lat, lon]);

    const isTaken = Object.values(pinAssignments).includes(pin.pin_id);
    const bgColor = isTaken ? "#f59f00" : "#0f7c7f";
    const badgeText = isTaken ? `${pin.pin_id} ✓` : pin.pin_id;

    const icon = L.divIcon({
      className: "custom-pin-icon",
      html: `<div id="pin-marker-${pin.pin_id}" style="background:${bgColor};color:#fff;width:36px;height:36px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-weight:bold;font-size:0.9rem;border:2px solid #fff;box-shadow:0 3px 8px rgba(0,0,0,0.35);transition:all 0.25s ease;">${badgeText}</div>`,
      iconSize: [36, 36],
      iconAnchor: [18, 18],
    });

    const marker = L.marker([lat, lon], { icon }).addTo(map);
    shuffleMarkers[pin.pin_id] = marker;

    marker.on("click", () => {
      const selectedId = state.albumShuffleState ? state.albumShuffleState.selectedPhotoId : null;
      if (selectedId) {
        Object.keys(pinAssignments).forEach((pid) => {
          if (pinAssignments[pid] === pin.pin_id) {
            pinAssignments[pid] = null;
          }
        });
        pinAssignments[selectedId] = pin.pin_id;
        renderShuffleMap(mapShell, pins, questionData);
        const cardsList = document.getElementById("shuffle-cards-list");
        if (cardsList) {
          renderPhotoCardsList(cardsList, questionData);
        }
        highlightMapMarker(pin.pin_id);
      }
    });
  });

  if (pins.length > 0) {
    map.fitBounds(bounds, { padding: [50, 50] });
  }

  setTimeout(() => map.invalidateSize(), 150);
}

function highlightMapMarker(pinId) {
  if (!pinId) return;
  Object.keys(shuffleMarkers).forEach((pid) => {
    const el = document.getElementById(`pin-marker-${pid}`);
    if (el) {
      if (pid === pinId) {
        el.style.transform = "scale(1.3)";
        el.style.boxShadow = "0 0 0 4px rgba(245, 159, 0, 0.6), 0 4px 12px rgba(0,0,0,0.4)";
        el.style.borderColor = "#f59f00";
      } else {
        el.style.transform = "scale(1)";
        el.style.boxShadow = "0 3px 8px rgba(0,0,0,0.35)";
        el.style.borderColor = "#fff";
      }
    }
  });
}

function renderBatchRevealMap(containerEl, batchItems) {
  if (!window.L) return;
  if (revealShuffleMap) {
    revealShuffleMap.remove();
    revealShuffleMap = null;
  }

  const map = L.map(containerEl).setView([20, 0], 2);
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    attribution: "&copy; OpenStreetMap",
  }).addTo(map);

  revealShuffleMap = map;
  const bounds = L.latLngBounds();

  batchItems.forEach((item) => {
    const lat = item.actual_latitude || 0.0;
    const lon = item.actual_longitude || 0.0;
    bounds.extend([lat, lon]);

    const icon = L.divIcon({
      className: "custom-pin-icon",
      html: `<div style="background:#0f7c7f;color:#fff;width:36px;height:36px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-weight:bold;border:2px solid #fff;box-shadow:0 3px 8px rgba(0,0,0,0.35);">📍 ${item.true_pin_id}</div>`,
      iconSize: [36, 36],
      iconAnchor: [18, 18],
    });

    const dateStr = item.actual_date ? new Date(item.actual_date).toLocaleDateString() : "";
    L.marker([lat, lon], { icon })
      .bindPopup(`<b>Pin ${item.true_pin_id}</b><br>${dateStr}`)
      .addTo(map);
  });

  if (batchItems.length > 0) {
    map.fitBounds(bounds, { padding: [50, 50] });
  }

  setTimeout(() => map.invalidateSize(), 150);
}

function openPhotoLightbox(src) {
  let lightbox = document.getElementById("photo-lightbox");
  if (!lightbox) {
    lightbox = document.createElement("div");
    lightbox.id = "photo-lightbox";
    lightbox.className = "photo-lightbox-overlay";
    lightbox.innerHTML = `
      <div class="photo-lightbox-content">
        <button type="button" class="photo-lightbox-close">&times;</button>
        <img id="photo-lightbox-img" src="" alt="Fullscreen photo" />
      </div>
    `;
    document.body.appendChild(lightbox);

    const closeBtn = lightbox.querySelector(".photo-lightbox-close");
    closeBtn.addEventListener("click", () => lightbox.classList.remove("active"));
    lightbox.addEventListener("click", (e) => {
      if (e.target === lightbox) lightbox.classList.remove("active");
    });
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && lightbox.classList.contains("active")) {
        lightbox.classList.remove("active");
      }
    });
  }

  const imgEl = document.getElementById("photo-lightbox-img");
  if (imgEl) imgEl.src = src;
  lightbox.classList.add("active");
}

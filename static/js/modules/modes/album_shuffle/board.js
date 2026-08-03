import { t } from "../../i18n.js";
import { state } from "../../state.js";
import { updateSubmitState } from "../../maps.js";
import { openPhotoLightbox } from "../../components/lightbox.js";
import { updateShuffleMapMarkers, highlightMapMarker } from "./map.js";

export function renderPhotoCardsList(containerEl, questionData) {
  containerEl.replaceChildren();

  // Informational Banner informing user of chronological sequence
  if (questionData.date_mode) {
    const totalCount = (questionData.batch_photos || []).length || 5;
    const infoBanner = document.createElement("div");
    infoBanner.className = "shuffle-info-banner";
    infoBanner.innerHTML = `<span>${t("game.shuffle_info_banner", totalCount)}</span>`;
    containerEl.appendChild(infoBanner);
  }

  const orderedIds = state.albumShuffleState ? state.albumShuffleState.orderedPhotoIds || [] : [];
  const selectedPhotoId = state.albumShuffleState ? state.albumShuffleState.selectedPhotoId : null;
  const pinAssignments = state.albumShuffleState ? state.albumShuffleState.pinAssignments || {} : {};
  const photosMap = {};
  (questionData.batch_photos || []).forEach((p) => {
    photosMap[p.photo_id] = p;
  });

  orderedIds.forEach((photoId, index) => {
    const photo = photosMap[photoId];
    if (!photo) return;

    const card = document.createElement("div");
    card.className = `shuffle-card-row ${selectedPhotoId === photoId ? "selected" : ""}`;

    card.addEventListener("click", () => {
      if (state.albumShuffleState) {
        state.albumShuffleState.selectedPhotoId = photoId;
        renderPhotoCardsList(containerEl, questionData);

        const assignedPin = state.albumShuffleState.pinAssignments
          ? state.albumShuffleState.pinAssignments[photoId]
          : null;
        highlightMapMarker(assignedPin || null);
      }
    });

    // Rank Badge
    const rankBadge = document.createElement("div");
    rankBadge.className = "shuffle-rank-badge";
    rankBadge.textContent = `#${index + 1}`;

    // Thumbnail
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

    // Assigned Pin Badge Indicator
    const pinBadgeWrap = document.createElement("div");
    pinBadgeWrap.className = "shuffle-card-details";

    if (questionData.location_mode) {
      const assignedPin = pinAssignments[photoId];
      const pinBadge = document.createElement("div");
      pinBadge.className = `shuffle-assigned-pin-badge ${assignedPin ? "assigned" : "unassigned"}`;
      pinBadge.textContent = assignedPin ? `📍 ${assignedPin}` : "📍";
      pinBadgeWrap.appendChild(pinBadge);
    } else {
      pinBadgeWrap.style.display = "none";
    }

    // Compact Arrow Buttons
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

  if (questionData.location_mode && questionData.batch_pins) {
    updateShuffleMapMarkers(questionData.batch_pins);
  }

  updateSubmitState();
}

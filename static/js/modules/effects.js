import { t } from "./i18n.js";
import { playScoreRollupTick } from "./audio.js";

let activeRollupSession = null;

function registerRollupAnimation(durationMs) {
  const now = typeof performance !== "undefined" ? performance.now() : Date.now();
  if (!activeRollupSession || now - activeRollupSession.lastActivity > 200) {
    activeRollupSession = {
      startTime: now,
      maxDuration: durationMs,
      lastTickTime: 0,
      activeCount: 1,
      lastActivity: now,
    };
  } else {
    activeRollupSession.maxDuration = Math.max(activeRollupSession.maxDuration, durationMs);
    activeRollupSession.activeCount += 1;
    activeRollupSession.lastActivity = now;
  }
}

function unregisterRollupAnimation() {
  if (activeRollupSession) {
    activeRollupSession.activeCount = Math.max(0, activeRollupSession.activeCount - 1);
  }
}

function triggerRollupAudioTick(timestamp) {
  if (!activeRollupSession || activeRollupSession.activeCount <= 0) return;
  activeRollupSession.lastActivity = timestamp;
  const tickInterval = 45;
  if (timestamp - activeRollupSession.lastTickTime >= tickInterval) {
    activeRollupSession.lastTickTime = timestamp;
    const progress = Math.min(1, (timestamp - activeRollupSession.startTime) / activeRollupSession.maxDuration);
    playScoreRollupTick(progress);
  }
}

export function animateScoreRollup(cellElement, targetScore, maxPossibleScore = 200, suffix = "", skipAnimation = false, startScore = 0) {
  if (!cellElement) return;

  const scoreNum = typeof targetScore === "number" ? targetScore : parseInt(targetScore, 10);
  if (isNaN(scoreNum) || targetScore === null || targetScore === undefined || targetScore === "-") {
    return;
  }

  const initialNum = typeof startScore === "number" ? Math.max(0, startScore) : parseInt(startScore, 10) || 0;

  // Preserve existing non-text children (like badges and subtext)
  const existingExtraNodes = Array.from(cellElement.children).filter(
    (child) => !child.classList.contains("score-rollup")
  );

  const span = document.createElement("span");
  span.className = "score-rollup";

  const fragment = document.createDocumentFragment();
  fragment.appendChild(span);
  if (suffix) {
    fragment.appendChild(document.createTextNode(suffix));
  }
  existingExtraNodes.forEach((node) => fragment.appendChild(node));

  cellElement.replaceChildren(fragment);

  if (skipAnimation || scoreNum <= initialNum) {
    span.textContent = String(Math.max(0, scoreNum));
    return;
  }

  span.classList.add("is-rolling");
  span.textContent = String(initialNum);

  const delta = scoreNum - initialNum;
  const maxPossible = maxPossibleScore || 200;
  const scoreRatio = Math.max(0.05, Math.min(1, delta / maxPossible));
  const durationMs = Math.round(300 + scoreRatio * 1500);

  registerRollupAnimation(durationMs);

  let startTime = null;

  function step(timestamp) {
    if (!startTime) startTime = timestamp;
    const progress = Math.min(1, (timestamp - startTime) / durationMs);
    const currentVal = Math.floor(initialNum + progress * delta);
    span.textContent = String(currentVal);

    triggerRollupAudioTick(timestamp);

    if (progress < 1) {
      requestAnimationFrame(step);
    } else {
      span.textContent = String(scoreNum);
      span.classList.remove("is-rolling");
      unregisterRollupAnimation();
    }
  }

  requestAnimationFrame(step);
}

export function launchGoldConfetti() {
  const canvas = document.getElementById("confetti-canvas");
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  if (!ctx) return;

  const width = (canvas.width = window.innerWidth);
  const height = (canvas.height = window.innerHeight);

  const colors = ["#ffd700", "#ffae00", "#f59f00", "#fff3bf", "#e65100", "#ffffff"];
  const particles = [];
  const particleCount = 130;

  for (let i = 0; i < particleCount; i++) {
    particles.push({
      x: width / 2 + (Math.random() - 0.5) * (width * 0.6),
      y: height * 0.6 + (Math.random() - 0.5) * 120,
      vx: (Math.random() - 0.5) * 14,
      vy: -Math.random() * 15 - 5,
      size: Math.random() * 9 + 4,
      color: colors[Math.floor(Math.random() * colors.length)],
      rotation: Math.random() * Math.PI * 2,
      vRot: (Math.random() - 0.5) * 0.2,
      opacity: 1,
      isStar: Math.random() > 0.35,
    });
  }

  let startTime = null;
  const duration = 3200;

  function drawStar(c, cx, cy, spikes, outerRadius, innerRadius) {
    let rot = (Math.PI / 2) * 3;
    let x = cx;
    let y = cy;
    const step = Math.PI / spikes;

    c.beginPath();
    c.moveTo(cx, cy - outerRadius);
    for (let i = 0; i < spikes; i++) {
      x = cx + Math.cos(rot) * outerRadius;
      y = cy + Math.sin(rot) * outerRadius;
      c.lineTo(x, y);
      rot += step;

      x = cx + Math.cos(rot) * innerRadius;
      y = cy + Math.sin(rot) * innerRadius;
      c.lineTo(x, y);
      rot += step;
    }
    c.lineTo(cx, cy - outerRadius);
    c.closePath();
    c.fill();
  }

  function frame(timestamp) {
    if (!startTime) startTime = timestamp;
    const elapsed = timestamp - startTime;
    const progress = elapsed / duration;

    ctx.clearRect(0, 0, width, height);

    particles.forEach((p) => {
      p.x += p.vx;
      p.y += p.vy;
      p.vy += 0.35;
      p.vx *= 0.98;
      p.rotation += p.vRot;
      p.opacity = Math.max(0, 1 - progress);

      ctx.save();
      ctx.globalAlpha = p.opacity;
      ctx.fillStyle = p.color;
      ctx.translate(p.x, p.y);
      ctx.rotate(p.rotation);

      if (p.isStar) {
        drawStar(ctx, 0, 0, 5, p.size, p.size / 2);
      } else {
        ctx.fillRect(-p.size / 2, -p.size / 2, p.size, p.size * 0.6);
      }
      ctx.restore();
    });

    if (elapsed < duration) {
      requestAnimationFrame(frame);
    } else {
      ctx.clearRect(0, 0, width, height);
    }
  }

  requestAnimationFrame(frame);
}

export function createPerfectBadge() {
  const badge = document.createElement("span");
  badge.className = "perfect-badge";
  const star = document.createElement("span");
  star.className = "perfect-badge-star";
  star.textContent = "\u2605";
  const text = document.createElement("span");
  text.className = "perfect-badge-text";
  text.textContent = ` ${t("reveal.perfect_badge")}`;
  badge.append(star, text);
  return badge;
}

export function launchStarBurst(originX, originY) {
  const canvas = document.getElementById("confetti-canvas");
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  if (!ctx) return;

  const width = (canvas.width = window.innerWidth);
  const height = (canvas.height = window.innerHeight);

  const cx = originX !== undefined ? originX : width / 2;
  const cy = originY !== undefined ? originY : height / 2;

  const colors = ["#ffd700", "#ffea00", "#ffae00", "#ffffff"];
  const particles = [];
  const particleCount = 45;

  for (let i = 0; i < particleCount; i++) {
    const angle = Math.random() * Math.PI * 2;
    const speed = Math.random() * 10 + 4;
    particles.push({
      x: cx,
      y: cy,
      vx: Math.cos(angle) * speed,
      vy: Math.sin(angle) * speed - 2,
      size: Math.random() * 7 + 4,
      color: colors[Math.floor(Math.random() * colors.length)],
      rotation: Math.random() * Math.PI * 2,
      vRot: (Math.random() - 0.5) * 0.3,
      opacity: 1,
    });
  }

  let startTime = null;
  const duration = 1600;

  function frame(timestamp) {
    if (!startTime) startTime = timestamp;
    const elapsed = timestamp - startTime;
    const progress = elapsed / duration;

    ctx.clearRect(0, 0, width, height);

    particles.forEach((p) => {
      p.x += p.vx;
      p.y += p.vy;
      p.vy += 0.25;
      p.vx *= 0.96;
      p.rotation += p.vRot;
      p.opacity = Math.max(0, 1 - progress);

      ctx.save();
      ctx.globalAlpha = p.opacity;
      ctx.fillStyle = p.color;
      ctx.translate(p.x, p.y);
      ctx.rotate(p.rotation);

      // Star shape
      let rot = (Math.PI / 2) * 3;
      const spikes = 5;
      const outerRadius = p.size;
      const innerRadius = p.size / 2;
      const step = Math.PI / spikes;

      ctx.beginPath();
      ctx.moveTo(0, -outerRadius);
      for (let i = 0; i < spikes; i++) {
        let x = Math.cos(rot) * outerRadius;
        let y = Math.sin(rot) * outerRadius;
        ctx.lineTo(x, y);
        rot += step;

        x = Math.cos(rot) * innerRadius;
        let yInner = Math.sin(rot) * innerRadius;
        ctx.lineTo(x, yInner);
        rot += step;
      }
      ctx.lineTo(0, -outerRadius);
      ctx.closePath();
      ctx.fill();
      ctx.restore();
    });

    if (elapsed < duration) {
      requestAnimationFrame(frame);
    } else {
      ctx.clearRect(0, 0, width, height);
    }
  }

  requestAnimationFrame(frame);
}


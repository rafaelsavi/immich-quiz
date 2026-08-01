import { t } from "./i18n.js";

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
  badge.textContent = `\u2605 ${t("reveal.perfect_badge")}`;
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

export function spawnFloatingScorePop(targetElement, text, variant = "bullseye") {
  if (!targetElement) return;
  const rect = targetElement.getBoundingClientRect();
  const pop = document.createElement("div");
  pop.className = `floating-score-pop pop-variant-${variant}`;
  pop.textContent = text;

  // Position floating pop near center top of target element
  const x = rect.left + rect.width / 2;
  const y = rect.top + window.scrollY;

  pop.style.left = `${x}px`;
  pop.style.top = `${y}px`;

  document.body.appendChild(pop);

  setTimeout(() => {
    if (pop.parentNode) {
      pop.parentNode.removeChild(pop);
    }
  }, 1800);
}


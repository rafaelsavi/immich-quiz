# Phase 4: Admin Creator UI & Cloudflare Security Hardening

> **Prerequisites**: Phases 1–3 must be complete.

## Goal

1. Implement the **Admin Challenge Creator UI** with a customizable expiration dropdown.
2. Provide step-by-step instructions for configuring **Cloudflare Zero Trust** path-based rules.
3. Harden the Docker and network deployment for public capability link sharing.

---

## 1. Admin Challenge Creator Modal

Add a "Create Challenge" tab or button in the main setup screen that opens the Challenge Generator modal.

### UI Controls
- **Challenge Title:** (Optional, e.g. *"Summer 2024 Roadtrip"*, *"Friday Game Night"*). If blank, auto-generates from creator name and filter summary.
- **Creator Name:** (Default: saved name from `localStorage`).
- **Library Selection:** Dropdown of available Immich libraries.
- **Game Mode & Filters:** Uses existing `multi_select.js` and `range_slider.js` filter components.
- **Round Count:** 3, 5, 10, or custom.
- **Expiration Window Dropdown:**
  - `1 Hour` (Quick party match)
  - `6 Hours` (Evening game)
  - `24 Hours` (Default daily challenge)
  - `48 Hours` (Weekend challenge)
  - `7 Days` (Weekly league)
  - `Never / Indefinite` (Persistent family album quiz)

### "Copy & Share" Modal
When the host taps "Generate Challenge Link":
- Calls `POST /api/challenge/create`
- Displays a shareable link box with a 1-click **"Copy Link"** button and optional QR code for mobile scanning.

---

## 2. Cloudflare Zero Trust Setup Guide

```
                  [ Public Internet / Friends ]
                               │
               (HTTPS) quiz.yourdomain.com
                               │
                ▼                             ▼
       /admin* or /create*            /play/* or /media/*
      ┌─────────────────────┐       ┌───────────────────────┐
      │  Cloudflare Access  │       │   Cloudflare Access   │
      │   (Email: Host)     │       │ Bypass (Everyone)     │
      └──────────┬──────────┘       └───────────┬───────────┘
                 │                              │
                 └──────────────┬───────────────┘
                                │ (Cloudflare Tunnel pipe)
                                ▼
                   ┌─────────────────────────┐
                   │  Docker: immich-quiz    │
                   │  (user: 1000:1000)      │
                   └────────────┬────────────┘
                                │ (Internal Docker Network)
                                ▼
                   ┌─────────────────────────┐
                   │  Docker: immich-server  │
                   │  (Port 2283 Isolated)   │
                   └─────────────────────────┘
```

### Cloudflare Access Configuration (Zero Trust Dashboard)

1. **Rule 1: Protect Admin & Creation Routes**
   - **Path:** `quiz.yourdomain.com/admin*` and `quiz.yourdomain.com/api/challenge/create`
   - **Action:** `Allow`
   - **Rule:** `Include` -> `Emails` -> `your-email@gmail.com`
   - **Outcome:** Only you can access the configuration and create new matches.

2. **Rule 2: Frictionless Public Player Access**
   - **Path:** `quiz.yourdomain.com/play*`, `quiz.yourdomain.com/api/challenge/*`, `quiz.yourdomain.com/media/*`
   - **Action:** `Bypass` (Everyone)
   - **Outcome:** Friends click your link and immediately play without hitting an OAuth login barrier. Capability tokens prevent anyone from guessing active matches.

3. **Cloudflare WAF & Anti-Abuse (Edge Security)**
   - In Cloudflare Dashboard -> **Security** -> **WAF**:
     - Enable **Bot Fight Mode** to block automated web scrapers.
     - Add a **Rate Limiting Rule**: Max 100 requests per minute per IP on `/api/challenge/*`.

---

## 3. Docker & Homelab Hardening Checklist

| Security Control | Implementation | Purpose |
| :--- | :--- | :--- |
| **No Docker Socket** | Ensure `/var/run/docker.sock` is **never** mounted in `docker-compose.yml`. | Prevents container breakout to the host system. |
| **Non-Root Execution** | Add `user: "1000:1000"` to the `immich-quiz` service definition. | Restricts container process privileges. |
| **Network Isolation** | Use a dedicated Docker bridge network (`quiz-net`). Do **not** use `network_mode: "host"`. | Prevents unauthorized container communication with local LAN devices. |
| **Dedicated API Key** | Create a dedicated "Quiz" user in Immich with access only to intended albums. | Limits data exposure if the key were ever leaked. |

---

## Acceptance Criteria

1. Host can configure and generate a challenge link with custom expiration windows from the UI.
2. Capability URLs are securely shared without exposing host admin controls.
3. Cloudflare Access rules properly isolate `/admin*` while permitting frictionless access to `/play/*`.
4. Docker container executes under unprivileged credentials without host socket bindings.

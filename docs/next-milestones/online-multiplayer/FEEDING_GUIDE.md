# Sequential Phase Feeding Guide

## Strategy: Phased Execution

Each phase document is a **self-contained implementation brief** designed for an AI model or developer to execute in sequence across the upcoming online multiplayer milestones.

> **Foundation Status:** Stage 0 (Foundations & Modularization) is fully completed in v2.0.0 (Day-1 4-table schema, `PlayMode` enum, response time tracking, and modularized frontend).

---

## Stage 1: Challenge Mode (Asynchronous & Hybrid Multiplayer — Active Milestone)

Feed these 4 phases in order for the next release:

### 1. Phase 1: Storage & Models

- **Prompt:** `00_OVERVIEW.md` + `stage-1-challenge-mode/01_PHASE_CHALLENGE_STORAGE.md`
- **Files Created/Modified:** `src/storage/challenge.py`, `src/storage/leaderboard.py`, `src/models.py`
- **Verification:**

  ```bash
  uv run python -c "from src.storage.challenge import ChallengeStore; print('OK')"
  uv run pytest tests/test_leaderboard.py tests/test_metadata_storage.py
  ```

### 2. Phase 2: REST API & Fog of War

- **Prompt:** `00_OVERVIEW.md` + `stage-1-challenge-mode/02_PHASE_CHALLENGE_API.md`
- **Files Created/Modified:** `src/api/challenge_routes.py`, `src/api/routes.py`, `src/main.py`
- **Verification:**

  ```bash
  uv run python -c "from src.main import create_app; app = create_app(); print('App built OK')"
  uv run pytest
  ```

### 3. Phase 3: Frontend Challenge Experience

- **Prompt:** `00_OVERVIEW.md` + `stage-1-challenge-mode/03_PHASE_CHALLENGE_FRONTEND.md`
- **Files Created/Modified:** `static/js/modules/challenge.js`, `static/index.html`, `static/css/components/challenge.css`
- **Verification:**
  - Open browser to `http://localhost:8000/play/{test_token}`
  - Verify player entry form, question loop, 3s intermission polling, and grand reveal map/timeline.

### 4. Phase 4: Admin Creator UI & Security Hardening

- **Prompt:** `00_OVERVIEW.md` + `stage-1-challenge-mode/04_PHASE_ADMIN_AND_SECURITY.md`
- **Files Created/Modified:** `static/index.html`, `static/js/modules/admin.js`, `docker-compose.example.yml`
- **Verification:**
  - Verify "Create Challenge" modal in host UI with customizable expiration window.
  - Verify capability link generation and clipboard copy.

---

## Stage 2: Synchronous Live Lounge (Real-Time WebSockets — Future Extension)

Milestone 2 builds directly on the Stage 1 challenge seed engine when real-time room coordination is desired:

- **Phase 5:** `stage-2-live-room/05_PHASE_BACKEND_ROOM.md`
- **Phase 6:** `stage-2-live-room/06_PHASE_BACKEND_ROOM_ROUTES.md`
- **Phase 7:** `stage-2-live-room/07_PHASE_FRONTEND_ROOM_UI.md`
- **Phase 8:** `stage-2-live-room/08_PHASE_FRONTEND_LIVE_GAMEPLAY.md`
- **Phase 9:** `stage-2-live-room/09_PHASE_RECONNECTION_POLISH.md`

---

## Verification Commands

After completing each phase/stage, run the full test and lint suite:

```bash
uv run ruff check .
uv run mypy src
uv run pytest
```

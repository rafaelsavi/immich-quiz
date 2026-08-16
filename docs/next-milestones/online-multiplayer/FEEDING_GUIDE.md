# Sequential Phase Feeding Guide

## Strategy: Phased Execution

Each phase document is a **self-contained implementation brief** designed for an AI model or developer to execute in sequence.

---

## Milestone 1: Challenge Links & Fog-of-War Engine (Active Priority)

Feed these 4 phases in order:

### 1. Phase 1: Storage & Models
- **Prompt:** `00_OVERVIEW.md` + `01_PHASE_CHALLENGE_STORAGE.md`
- **Files Created/Modified:** `src/storage/challenge.py`, `src/storage/leaderboard.py`, `src/models.py`
- **Verification:**
  ```bash
  python -c "from src.storage.challenge import ChallengeStore; print('OK')"
  uv run pytest tests/test_metadata_storage.py
  ```

### 2. Phase 2: REST API & Fog of War
- **Prompt:** `00_OVERVIEW.md` + `02_PHASE_CHALLENGE_API.md`
- **Files Created/Modified:** `src/api/challenge_routes.py`, `src/api/routes.py`, `src/main.py`
- **Verification:**
  ```bash
  uv run python -c "from src.main import create_app; app = create_app(); print('App built OK')"
  ```

### 3. Phase 3: Frontend Challenge Experience
- **Prompt:** `00_OVERVIEW.md` + `03_PHASE_CHALLENGE_FRONTEND.md`
- **Files Created/Modified:** `static/js/modules/challenge.js`, `static/js/app.js`, `static/index.html`, `static/css/components/challenge.css`
- **Verification:**
  - Open browser to `http://localhost:8000/play/{test_token}`
  - Verify player entry form, question loop, 3s intermission polling, and grand reveal map/timeline.

### 4. Phase 4: Admin Creator UI & Security Hardening
- **Prompt:** `00_OVERVIEW.md` + `04_PHASE_ADMIN_AND_SECURITY.md`
- **Files Created/Modified:** `static/index.html`, `static/js/app.js`, `docker-compose.example.yml`
- **Verification:**
  - Verify "Create Challenge" modal in host UI with customizable expiration window.
  - Verify capability link generation and clipboard copy.

---

## Milestone 2: Synchronous Live Lounge (Future Extension)

Milestone 2 builds directly on the Milestone 1 challenge seed engine when real-time room coordination is desired:

- **Prompt 5:** `05_PHASE_BACKEND_ROOM.md`
- **Prompt 6:** `06_PHASE_BACKEND_ROOM_ROUTES.md`
- **Prompt 7:** `07_PHASE_FRONTEND_ROOM_UI.md`
- **Prompt 8:** `08_PHASE_FRONTEND_LIVE_GAMEPLAY.md`
- **Prompt 9:** `09_PHASE_RECONNECTION_POLISH.md`

---

## Verification Commands

After completing each milestone, run the full test and lint suite:

```bash
uv run ruff check src/ tests/
uv run pytest
```

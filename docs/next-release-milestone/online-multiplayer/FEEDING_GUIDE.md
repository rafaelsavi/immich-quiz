# How to Feed These Documents to a Less Powerful Model

## Strategy: Sequential Phase Execution

Each phase is a **self-contained implementation brief** designed for a model that:

- Needs explicit code rather than abstract descriptions
- Benefits from inline context instead of "go read file X"
- Works best with one focused task at a time
- May not track complex cross-file dependencies

## Step-by-Step Process

### 1. Always Start with the Overview

Every prompt should begin by attaching `00_OVERVIEW.md` as context. This gives the model:

- The overall goal and terminology
- The "DO NOT MODIFY" rules for existing files
- The project file structure

**Prompt pattern:**

```
Here is the overview for a feature I'm building:
[paste or attach 00_OVERVIEW.md]

Now implement this phase:
[paste or attach 01_PHASE_BACKEND_ROOM.md]
```

### 2. Feed One Phase at a Time

Do NOT give all 5 phases at once. Instead:

1. **Prompt 1**: `00_OVERVIEW.md` + `01_PHASE_BACKEND_ROOM.md`
   → Verify: files created, imports work, tests pass
2. **Prompt 2**: `00_OVERVIEW.md` + `02_PHASE_BACKEND_ROUTES.md`
   → Verify: server starts, room endpoints respond, WS connects
3. **Prompt 3**: `00_OVERVIEW.md` + `03_PHASE_FRONTEND_ROOM_UI.md`
   → Verify: UI renders, room client works, CSS loads
4. **Prompt 4**: `00_OVERVIEW.md` + `04_PHASE_FRONTEND_GAMEPLAY.md`
   → Verify: full online game flow works in two browser windows
5. **Prompt 5**: `00_OVERVIEW.md` + `05_PHASE_RECONNECTION_POLISH.md`
   → Verify: reconnect works, docs updated

### 3. Include Relevant Source Files as Context

For each phase, the model will benefit from seeing the actual current files it needs to modify. Attach them alongside the phase doc:

| Phase | Attach these source files alongside the phase doc |
| ------- | -------------------------------------------------- |
| Phase 1 | None (all new files) |
| Phase 2 | `src/main.py`, `src/models.py` |
| Phase 3 | `static/index.html`, `static/js/modules/state.js`, `static/js/modules/i18n.js`, `static/css/style.css` |
| Phase 4 | `static/js/app.js` (full file), `static/js/modules/room.js` (from Phase 3) |
| Phase 5 | `src/api/routes.py`, `src/api/room_routes.py` (from Phase 2), `docs/ARCHITECTURE.md`, `docs/GAMEPLAY.md` |

### 4. Verify Before Moving On

After each phase, run these checks before proceeding:

```bash
# Phase 1: imports work
python -c "from src.room import RoomManager, WebSocketManager; print('OK')"
uv run ruff check src/room/

# Phase 2: server starts
uv run -m src.main  # should start without errors

# Phase 3: visual check
# Open browser, verify new UI elements are visible

# Phase 4: functional test
# Open two browser windows, test full online flow

# Phase 5: all tests pass
uv run pytest
```

## Prompt Template

Here's a ready-to-use prompt template:

```
You are implementing a feature for the Immich Quiz project, a FastAPI + vanilla JS web app.

## Project Context
[paste 00_OVERVIEW.md here]

## Current Source Files
[paste any relevant source files the phase modifies — see table above]

## Task
[paste the phase document here, e.g. 01_PHASE_BACKEND_ROOM.md]

## Instructions
1. Create or modify ONLY the files described in the task document
2. Do NOT modify any file marked "DO NOT MODIFY" in the overview
3. Follow the exact code structure shown — do not reorganize or rename
4. After creating the files, show me the verification commands to run
```

## Tips for Less Powerful Models

1. **Don't ask it to "design" anything.** The design is done. It should just implement what's specified.
2. **If a phase is too large**, split it further (e.g., Phase 3 could be split into "3a: room.js", "3b: HTML changes", "3c: CSS + state").
3. **Paste code literally** rather than linking files — weaker models handle inline context better.
4. **Ask for one file at a time** if the model struggles with multiple files per prompt.
5. **Verify after each file**, not just each phase, to catch issues early.

## Here's my recommendation based on what each model is good at

Phase Assign to Why
Phase 1 — Backend Room infra Flash All new files, complete code provided verbatim. Pure file creation from spec.
Phase 2 — Backend Routes Flash Mostly a new file + small additive edits to main.py and models.py. Well-specified.
Phase 3 — Frontend Room UI Flash New files + additive inserts to HTML/CSS/state/i18n. No complex logic, just "add this block here."
Phase 4 — Frontend Gameplay Me Surgical edits throughout a 1,430-line app.js. Requires understanding the existing game cycle, conditional branching (online vs local), and preserving fragile UI state transitions.
Phase 5 — Reconnection/Polish Me Cross-module integration, modifying existing endpoints, async edge cases, and judgment calls on what to defer vs implement.
The logic: Flash gets the 3 "scaffolding" phases that are mostly creating new code from explicit specs. I get the 2 "integration" phases that require understanding and surgically modifying complex existing code — especially app.js, which is the riskiest file to edit and the one where a weaker model is most likely to break something.

Phase 4 alone is where 80% of the bugs will come from. That's where you want the stronger model.

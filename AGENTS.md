# AI Assistant Guidelines

This document provides context, architectural constraints, and standards for AI coding assistants working in this repository. Follow these guidelines strictly so fixes do not need to be retroactively applied in future conversations.

---

## 1. General Principles

- **Concise & Direct**: Keep explanations focused and code examples clear.
- **Maintain Code Integrity**: Avoid unnecessary refactors or deleting unrelated comments and docstrings.
- **Safety First**: Do not run destructive commands (deletions, truncations, force pushes) without explicit confirmation.
- **Clean Modern Architecture**: When refactoring or redesigning, prioritize clean, modular code over preserving dead shims or backward-compatibility baggage unless explicitly requested.

---

## 2. Code Quality & Style

- **Modularity**: Keep functions, screen controllers, and UI components small, focused, and single-responsibility.
- **Type Safety**: Use explicit Python type annotations and Pydantic validation on all models and endpoint signatures.
- **Error Handling**: Handle edge cases and potential failures gracefully with meaningful HTTP exceptions, structured logs, and localized frontend alerts.
- **Formatting & Linting**: Before concluding any task, verify that code passes:
  - `uv run ruff check`
  - `uv run ruff format --check`
  - `uv run mypy src`

---

## 3. Testing & Verification

- **Test Coverage**: Write unit/regression tests for new features, bug fixes, and edge cases.
- **Full Suite Validation**: Before concluding tasks, verify all relevant test suites pass:
  - Unit, API, storage, and frontend regressions: `uv run pytest tests/api tests/storage tests/frontend`
  - Playwright end-to-end suite: `uv run pytest tests/e2e/`
- **Reproducibility**: Ensure test fixtures and mocks are deterministic and isolated.

---

## 4. Internationalization (i18n) & Locale Parity

- **Strict 4-File Parity Mandate**: The application maintains exactly four locale files:
  1. `locales/en-US.json` (backend reference English)
  2. `locales/pt-BR.json` (backend reference Portuguese)
  3. `static/js/modules/locales/en_US.js` (frontend ES module English)
  4. `static/js/modules/locales/pt_BR.js` (frontend ES module Portuguese)
  Whenever any translation key is added, edited, or removed, **ALL FOUR FILES MUST BE UPDATED SIMULTANEOUSLY**. All four files must maintain 100% identical key counts and hierarchical structure.
- **Never Hardcode English Suffixes or Dynamic Counts**:
  - Never write string templates with hardcoded English units (e.g. `${count} players`, `${count} matches`, `${count} items`).
  - Always define singular and plural i18n keys with `{count}` interpolation:
    - `stats.player_count_single: "{count} player"`
    - `stats.player_count_plural: "{count} players"`
    - `replay.counter_single: "{count} match"`
    - `replay.counter_plural: "{count} matches"`
  - Format dynamically using `t("...", { count })`.
- **No English Fallbacks in Production**: When creating UI elements (buttons, badges, modals, tooltips, error toasts), provide complete and accurate translations for both English and Brazilian Portuguese immediately.

---

## 5. UI Architecture & Header Standardization

- **Shared Hub & Sub-Page Header**: All top-level cards and secondary views (Challenges Hub, Player Statistics & Directory, Match Replays & Viewer, Reported Photos Moderation, etc.) must use the standardized `.hub-page-header` pattern from `static/css/components/hub_header.css` and `.page-back-btn` from `static/css/base/layout.css`:
  ```html
  <div class="hub-page-header">
    <button class="page-back-btn" data-action="go-home" data-i18n-title="common.back">←</button>
    <div class="hub-page-title-group">
      <div class="hub-title-badge-row">
        <h2 class="hub-page-heading" data-i18n="...">Page Title</h2>
        <span class="hub-page-badge badge-{type}">Badge Text</span>
      </div>
      <p class="hub-page-desc" data-i18n="...">Descriptive subtitle</p>
    </div>
    <div class="hub-page-head-actions">
      <!-- Search inputs, filters, action buttons -->
    </div>
  </div>
  ```
- **Do Not Invent Ad-Hoc Headers**: Never write custom, one-off header markup or duplicated CSS rules for back buttons, titles, subtitles, and badges in component stylesheets. If a new badge color/theme is needed, add a semantic `.badge-{type}` token to `static/css/components/hub_header.css` with both light and dark mode styles.
- **Modular CSS Encapsulation (No Bloat)**:
  - When creating or moving a screen or component into its own ES module, place all related styles, card layouts, chips, responsive queries, and dark mode rules into its own dedicated stylesheet (e.g. `replay.css` for replay screens and catalog items, `stats.css` for player profiles and directories).
  - Never leave stranded styles in parent or previously shared stylesheets.
  - **Proactively Delete Dead CSS**: When removing UI elements (such as tab bars, obsolete buttons, or old layout containers), immediately delete the associated CSS rules, inline SVG data URIs, and dark mode blocks. Do not retain legacy shims or abandoned CSS classes.
  - Link any new stylesheet in `static/index.html` and document it in `docs/ARCHITECTURE.md`.

---

## 6. Database Schema, Migrations & SQLite Performance

- **Base Schema DDL & Migration Synchronization**:
  - Whenever a new index, table, or column is introduced in SQLite runtime migrations (`_apply_migrations`), **always declare the identical index/table directly in the base table schema definition** (`LEADERBOARD_SCHEMA_SQL` or `METADATA_SCHEMA_SQL`).
  - This ensures freshly created database instances (such as clean test runs or new deployments) instantiate all performance indices immediately without depending on historical migration steps.
- **Case-Insensitive Index Matching**:
  - If a query uses `COLLATE NOCASE` in its `WHERE` or `JOIN` clause (e.g. `WHERE player_name = ? COLLATE NOCASE`), SQLite **will not** use an index defined on `player_name` without `COLLATE NOCASE`.
  - Declare case-insensitive indexes explicitly:
    `CREATE INDEX IF NOT EXISTS idx_... ON table(column COLLATE NOCASE);`

---

## 7. Playwright E2E Test Resilience

- **Dynamic Maps & Canvas Interaction Readiness**:
  - Leaflet maps, dynamic canvas elements, and animated DOM views undergo initialization, tile rendering, and dimension stabilization (`invalidateSize`).
  - Never assume an interactive map or canvas accepts clicks instantaneously upon becoming visible.
  - When placing pins or clicking maps in E2E tests, verify that downstream action triggers (such as `is_enabled()` on the submit button) become active, or use short retry loops with small delays (`await page.wait_for_timeout(200)`) instead of naive single clicks that cause flaky timeouts under test runner load.

---

## 8. Documentation & Git Workflow

- **Changelog Maintenance**: Update `CHANGELOG.md` under `[Unreleased]` for any notable feature, fix, removal, or refactoring following the [Keep a Changelog](https://keepachangelog.com/en/1.0.0/) standard (`Added`, `Changed`, `Fixed`, `Removed`).
- **Synchronize Project Documentation**:
  - When modifying or adding API endpoints, update `docs/API.md` with request/response schemas, parameters, and descriptions.
  - When modifying architecture, components, ES modules, or stylesheets, update `docs/ARCHITECTURE.md`.
  - When adding top-level user-facing features or modes, update `README.md`.
- **Commit Messages**: Follow standard conventional commits format (e.g. `feat:`, `fix:`, `refactor:`, `docs:`, `test:`).

---

## 9. Toolchain & Environment Execution

- **Package Manager & Python Runtime**:
  - Always run Python commands, scripts, tests, and linters via **`uv`**:
    - Tests: `uv run pytest` (e.g. `uv run pytest tests/api tests/storage tests/frontend`)
    - Linting & Formatting: `uv run ruff check` and `uv run ruff format`
    - Type Checking: `uv run mypy src`
    - Running application / scripts: `uv run python -m src.main` or `uv run python path/to/script.py`
  - Python version is 3.13 (`.venv` managed by `uv`). Never invoke unmanaged global `python` or bare `pip`.
- **Git Binary & Sandbox Permissions**:
  - Git for Windows is installed at `C:\Program Files\Git\cmd\git.exe` (invoked as `git`).
  - In agent runner environments (such as the Antigravity sandbox on Windows), commands executing `git`, `uv`, `python`, `pytest`, or Playwright MUST run with sandbox isolation bypassed (`BypassSandbox: true`) because the Git repository metadata, the base Python runtime (`%LOCALAPPDATA%\Programs\Python\Python313\`), and Playwright caches live in user profile directories outside the workspace root.
- **Playwright & Browser Automation**:
  - Playwright is fully installed and managed inside the Python environment (`playwright>=1.50.0`, `pytest-playwright`).
  - Chromium browser binary is cached under `%LOCALAPPDATA%\ms-playwright` and can be provisioned at any time via:
    `uv run playwright install chromium`
  - **Running E2E tests**: Execute `uv run pytest tests/e2e/`.
  - **Ad-hoc Browser Automation / Screenshots**: When taking page screenshots, inspecting DOM, or verifying responsive layouts, always execute Python Playwright scripts via `uv run python` using `playwright.async_api` or `playwright.sync_api` with `headless=True` (pointing to the local dev server on port `8020` or dynamically launched test server). Never rely on external browser driver downloads.

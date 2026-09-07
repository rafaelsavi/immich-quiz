# AI Assistant Guidelines

This document provides context and guidelines for AI coding assistants working in this repository.

---

## 1. General Principles

- **Concise & Direct**: Keep explanations focused and code examples clear.
- **Maintain Code Integrity**: Avoid unnecessary refactors or deleting unrelated comments and docstrings.
- **Safety First**: Do not run destructive commands (deletions, truncations, force pushes) without explicit confirmation.

---

## 2. Code Quality & Style

- **Modularity**: Keep functions and components small, focused, and reusable.
- **Type Safety**: Use explicit type annotations and validation wherever applicable.
- **Error Handling**: Handle edge cases and potential failures gracefully with meaningful error messages and logging.
- **Formatting & Linting**: Adhere to the project's configured formatters and linters before committing changes.

---

## 3. Testing & Verification

- **Test Coverage**: Write unit tests for new features, bug fixes, and edge cases.
- **Validation**: Verify that existing test suites pass before concluding tasks.
- **Reproducibility**: Ensure test fixtures and mocks are deterministic and isolated.

---

## 4. Documentation & Git Workflow

- **Docstrings & Comments**: Document non-obvious logic, public APIs, and complex algorithms.
- **Changelog Maintenance**: Update `CHANGELOG.md` for notable features, fixes, or breaking changes following the [Keep a Changelog](https://keepachangelog.com/en/1.0.0/) standard (`Added`, `Changed`, `Fixed`, `Removed`).
- **Project Documentation**: Keep `README.md` and dedicated guides in `docs/` (e.g., `API.md`, `ARCHITECTURE.md`, `FILTERS.md`) in sync whenever configurations, APIs, or behaviors are modified.
- **Commit Messages**: Follow standard conventional commits format (e.g., `feat:`, `fix:`, `refactor:`, `docs:`).

---

## 5. Toolchain & Environment Execution

- **Package Manager & Python Runtime**:
  - Always run Python commands, scripts, tests, and linters via **`uv`**:
    - Tests: `uv run pytest` (e.g. `uv run pytest tests/frontend/test_frontend_regressions.py`)
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

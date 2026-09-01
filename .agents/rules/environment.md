# Toolchain & Environment Execution Rules

- **Package Manager & Python Runtime**:
  - Always run Python commands, scripts, tests, and linters via **`uv`**:
    - Tests: `uv run pytest` (e.g. `uv run pytest tests/test_frontend_regressions.py`)
    - Linting & Formatting: `uv run ruff check` and `uv run ruff format`
    - Type Checking: `uv run mypy`
    - Running application / scripts: `uv run python -m src.main` or `uv run python path/to/script.py`
  - Python version is 3.13 (`.venv` managed by `uv`). Never invoke unmanaged global `python` or bare `pip`.
- **Git Binary & Sandbox Permissions**:
  - Git for Windows is installed at `C:\Program Files\Git\cmd\git.exe` (invoked as `git`).
  - In agent runner environments (such as the Antigravity sandbox on Windows), commands executing `git`, `uv`, `python`, `pytest`, or Playwright MUST run with sandbox isolation bypassed (`BypassSandbox: true`) because Git repository metadata, the base Python runtime (`%LOCALAPPDATA%\Programs\Python\Python313\`), and Playwright caches live in user profile directories outside the workspace root.
- **Playwright & Browser Automation**:
  - Playwright is fully installed and managed inside the Python environment (`playwright>=1.50.0`, `pytest-playwright`).
  - Chromium browser binary is cached under `%LOCALAPPDATA%\ms-playwright` and can be provisioned at any time via:
    `uv run playwright install chromium`
  - **Running E2E tests**: Execute `uv run pytest tests/e2e/`.
  - **Ad-hoc Browser Automation / Screenshots**: When taking page screenshots, inspecting DOM, or verifying responsive layouts, always execute Python Playwright scripts via `uv run python` using `playwright.async_api` or `playwright.sync_api` with `headless=True` (pointing to the local dev server on port `8020` or dynamically launched test server). Never rely on external browser driver downloads.

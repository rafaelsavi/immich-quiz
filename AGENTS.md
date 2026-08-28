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

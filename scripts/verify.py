#!/usr/bin/env python3
"""Unified verification script for Immich Quiz.

Runs all linting, formatting, type checking, test suites, and version/changelog
validations identically both locally and in CI.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import time
from pathlib import Path

# Ensure robust UTF-8 console output across Windows cp1252 and Linux/macOS
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# ANSI Color Codes
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
CYAN = '\033[96m'
BOLD = '\033[1m'
RESET = '\033[0m'


def log_header(title: str) -> None:
    print(f'\n{BOLD}{CYAN}=== {title} ==={RESET}')


def log_step(name: str) -> None:
    print(f'[*] {BOLD}{name}{RESET}...', flush=True)


def log_success(msg: str) -> None:
    print(f'{GREEN}[+] {msg}{RESET}')


def log_error(msg: str) -> None:
    print(f'{RED}[-] {msg}{RESET}', file=sys.stderr)


REPO_ROOT = Path(__file__).resolve().parent.parent


def run_cmd(cmd: list[str], desc: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    log_step(desc)
    start = time.perf_counter()
    res = subprocess.run(cmd, capture_output=True, text=True, cwd=REPO_ROOT)
    duration = time.perf_counter() - start

    if res.returncode == 0:
        log_success(f'{desc} passed ({duration:.2f}s)')
        return res

    log_error(f'{desc} failed with exit code {res.returncode} ({duration:.2f}s)')
    if res.stdout.strip():
        print(f'\n{res.stdout.strip()}')
    if res.stderr.strip():
        print(f'\n{res.stderr.strip()}', file=sys.stderr)

    if check:
        sys.exit(res.returncode)
    return res


def check_formatting(fix: bool) -> None:
    cmd = ['uv', 'run', 'ruff', 'format']
    if not fix:
        cmd.append('--check')
    desc = 'Auto-formatting code' if fix else 'Checking code formatting (Ruff)'
    run_cmd(cmd, desc)


def check_linter(fix: bool) -> None:
    cmd = ['uv', 'run', 'ruff', 'check']
    if fix:
        cmd.append('--fix')
    cmd.append('.')
    desc = 'Fixing lint issues' if fix else 'Running static linter (Ruff)'
    run_cmd(cmd, desc)


def check_types() -> None:
    run_cmd(['uv', 'run', 'mypy', 'src'], 'Running type checker (Mypy)')


def run_tests(quick: bool = False, pytest_args: list[str] | None = None) -> None:
    cmd = ['uv', 'run', 'pytest']
    if not quick:
        cmd.extend(['--cov=src', '--cov-report=term-missing'])
    if pytest_args:
        cmd.extend(pytest_args)
    run_cmd(cmd, 'Running test suite (Pytest)')


def validate_version_and_changelog() -> None:
    import tomllib
    from packaging.version import Version

    log_step('Validating version bump & CHANGELOG.md consistency')

    # Determine base branch to compare against (origin/main or main)
    base_ref = 'origin/main'
    has_remote = (
        subprocess.run(
            ['git', 'rev-parse', '--verify', 'origin/main'],
            capture_output=True,
            cwd=REPO_ROOT,
        ).returncode
        == 0
    )
    if not has_remote:
        base_ref = 'main'

    # Find modified files comparing merge-base and working tree
    diff_committed = subprocess.run(
        ['git', 'diff', '--name-only', f'{base_ref}...HEAD'],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    if diff_committed.returncode != 0:
        diff_committed = subprocess.run(
            ['git', 'diff', '--name-only', base_ref, 'HEAD'],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
        )

    diff_working = subprocess.run(
        ['git', 'diff', '--name-only', 'HEAD'],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )

    committed_files = diff_committed.stdout.splitlines() if diff_committed.returncode == 0 else []
    working_files = diff_working.stdout.splitlines() if diff_working.returncode == 0 else []
    all_changed = list(dict.fromkeys([f.strip() for f in (committed_files + working_files) if f.strip()]))

    code_pattern = re.compile(r'^(docs/|\.vscode/|\.githooks/|\.github/|\.gitignore|.*\.md$)', re.IGNORECASE)
    code_changed = [f for f in all_changed if not code_pattern.match(f)]

    if not code_changed:
        log_success('Only documentation or non-code files modified. Version bump not required.')
        return

    # Check pyproject.toml version
    pyproject_path = REPO_ROOT / 'pyproject.toml'
    if not pyproject_path.exists():
        log_error('pyproject.toml not found!')
        sys.exit(1)

    with pyproject_path.open('rb') as f:
        new_version_str = tomllib.load(f)['project']['version']

    # Get old version from base_ref
    show_res = subprocess.run(
        ['git', 'show', f'{base_ref}:pyproject.toml'],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    if show_res.returncode != 0:
        log_success(f'Could not read {base_ref}:pyproject.toml (new repository or first commit). Skipping diff check.')
        return

    old_version_str = tomllib.loads(show_res.stdout)['project']['version']
    print(f'   Base version ({base_ref}): {old_version_str}')
    print(f'   Current branch version:  {new_version_str}')

    old_v = Version(old_version_str)
    new_v = Version(new_version_str)

    if new_v <= old_v:
        log_error(
            f'Code changes detected ({len(code_changed)} files), but version in pyproject.toml '
            f'({new_version_str}) is not strictly greater than {base_ref} ({old_version_str})!\n'
            f'Please bump the version in pyproject.toml and add notes in CHANGELOG.md before merging.'
        )
        sys.exit(1)

    # Validate official layout format
    if not re.match(r'^[0-9]+\.[0-9]+\.[0-9]+$', new_version_str):
        log_error(
            f"Version '{new_version_str}' does not follow strict MAJOR.MINOR.PATCH format "
            f'(e.g. 3.0.1). Pre-release suffixes are not permitted on main.'
        )
        sys.exit(1)

    # Validate CHANGELOG.md inclusion
    changelog_path = REPO_ROOT / 'CHANGELOG.md'
    if not changelog_path.exists():
        log_error('CHANGELOG.md not found!')
        sys.exit(1)

    changelog_content = changelog_path.read_text(encoding='utf-8')
    header_pattern = rf'##\s*\[?v?{re.escape(new_version_str)}\]?'
    match = re.search(header_pattern, changelog_content)
    if not match:
        log_error(
            f"Version '{new_version_str}' from pyproject.toml was not found in CHANGELOG.md!\n"
            f"Please document release changes under '## [{new_version_str}] - YYYY-MM-DD' in CHANGELOG.md."
        )
        sys.exit(1)

    # Verify notes content is not empty
    notes_pattern = rf'##\s*\[?v?{re.escape(new_version_str)}\]?[^\n]*\n(.*?)(?=\n##\s*\[|\Z)'
    notes_match = re.search(notes_pattern, changelog_content, re.DOTALL)
    if not notes_match or not notes_match.group(1).strip():
        log_error(f"Release section for '[{new_version_str}]' in CHANGELOG.md is empty!")
        sys.exit(1)

    log_success(f'Version bump ({old_version_str} -> {new_version_str}) and CHANGELOG.md entry verified!')


def main() -> None:
    parser = argparse.ArgumentParser(description='Unified verification runner for Immich Quiz')
    parser.add_argument('--fix', action='store_true', help='Auto-fix formatting and lint errors')
    parser.add_argument('--quick', action='store_true', help='Run tests without coverage')
    parser.add_argument('--skip-tests', action='store_true', help='Skip pytest test suite')
    parser.add_argument(
        '--ci',
        action='store_true',
        help='Run in strict CI mode (enforces version & changelog parity against main)',
    )
    parser.add_argument(
        '--check-version',
        action='store_true',
        help='Explicitly validate version bump and CHANGELOG.md',
    )
    parser.add_argument(
        'pytest_args',
        nargs='*',
        help='Optional additional arguments to pass through to pytest',
    )
    args = parser.parse_args()

    total_start = time.perf_counter()
    log_header('IMMICH QUIZ QUALITY VERIFICATION')

    # 1. Format
    check_formatting(args.fix)

    # 2. Lint
    check_linter(args.fix)

    # 3. Types
    check_types()

    # 4. Tests
    if not args.skip_tests:
        run_tests(quick=args.quick, pytest_args=args.pytest_args)
    else:
        print(f'\n{YELLOW}[!] Skipping tests (--skip-tests){RESET}')

    # 5. Version & Changelog check (if --ci or --check-version)
    if args.ci or args.check_version:
        validate_version_and_changelog()

    total_duration = time.perf_counter() - total_start
    print(f'\n{GREEN}{BOLD}======================================================{RESET}')
    print(f'{GREEN}{BOLD}[+] ALL VERIFICATION CHECKS PASSED ({total_duration:.2f}s){RESET}')
    print(f'{GREEN}{BOLD}======================================================{RESET}\n')


if __name__ == '__main__':
    main()

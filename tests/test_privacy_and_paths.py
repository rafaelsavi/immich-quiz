"""Tests for repository privacy hygiene and local path leak prevention.

Verifies that no tracked or project files contain hardcoded local machine paths,
Windows/macOS/Linux user home directories, AI assistant artifact paths, or personal
filesystem references.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import NamedTuple

REPO_ROOT = Path(__file__).resolve().parents[1]

# Patterns that indicate hardcoded local or personal machine paths
FORBIDDEN_PATH_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    (
        'Windows User Profile Path',
        re.compile(r'[a-zA-Z]:[/\\]+Users[/\\]+', re.IGNORECASE),
    ),
    (
        'Windows Development/Personal Folder Path',
        re.compile(r'[a-zA-Z]:[/\\]+(?:Projects|Development|Documents|Downloads|Desktop)[/\\]+', re.IGNORECASE),
    ),
    (
        'Linux/macOS User Home Directory Path',
        re.compile(r'(?:^|[\s"\'`=(])/(?:home|Users)/[a-zA-Z0-9_\-\.]+/(?!api/|users/)', re.IGNORECASE),
    ),
    (
        'AI Assistant Brain/Artifact Path',
        re.compile(
            r'(?:\.gemini[/\\]+antigravity-ide|antigravity-ide[/\\]+brain|brain[/\\]+[0-9a-fA-F-]{36})', re.IGNORECASE
        ),
    ),
]

# File patterns to exclude from privacy scans (e.g. test itself which contains regex patterns)
EXCLUDED_FILES = {
    'tests/test_privacy_and_paths.py',
}

# Directories to ignore if walking filesystem directly
IGNORED_DIRS = {
    '.git',
    '.venv',
    '.pytest_cache',
    '.ruff_cache',
    '.mypy_cache',
    '__pycache__',
    'dist',
    'build',
    'data',
}


class PathViolation(NamedTuple):
    file_path: str
    line_number: int
    rule_name: str
    line_content: str


def find_path_violations(file_path: Path, content: str) -> list[PathViolation]:
    """Scan content for forbidden local path patterns."""
    violations: list[PathViolation] = []
    lines = content.splitlines()

    for line_idx, line in enumerate(lines, 1):
        # Skip pure comments or URLs if necessary, but keep strict checks on code & docs
        for rule_name, pattern in FORBIDDEN_PATH_PATTERNS:
            if pattern.search(line):
                violations.append(
                    PathViolation(
                        file_path=str(file_path.relative_to(REPO_ROOT)).replace('\\', '/'),
                        line_number=line_idx,
                        rule_name=rule_name,
                        line_content=line.strip(),
                    )
                )
    return violations


def get_tracked_files() -> list[Path]:
    """Return all git-tracked files, or fall back to filesystem walk if git is unavailable."""
    try:
        res = subprocess.run(
            ['git', 'ls-files'],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            encoding='utf-8',
            check=True,
        )
        files = [
            REPO_ROOT / f.strip() for f in res.stdout.splitlines() if f.strip() and f.strip() not in EXCLUDED_FILES
        ]
        return [f for f in files if f.is_file()]
    except Exception:
        # Fallback to filesystem walk
        collected: list[Path] = []
        for p in REPO_ROOT.rglob('*'):
            if p.is_file():
                rel = p.relative_to(REPO_ROOT).as_posix()
                if not any(part in IGNORED_DIRS for part in p.parts) and rel not in EXCLUDED_FILES:
                    collected.append(p)
        return collected


def test_no_local_paths_in_repository() -> None:
    """Ensure no file in the repository contains hardcoded local paths or user home paths."""
    all_files = get_tracked_files()
    assert len(all_files) > 10, 'Expected to scan git tracked files'

    all_violations: list[PathViolation] = []
    for file_path in all_files:
        try:
            content = file_path.read_text(encoding='utf-8', errors='ignore')
        except Exception:
            continue

        violations = find_path_violations(file_path, content)
        all_violations.extend(violations)

    if all_violations:
        formatted = '\n'.join(
            f'  [{v.rule_name}] {v.file_path}:{v.line_number} -> {v.line_content}' for v in all_violations
        )
        raise AssertionError(
            f'Privacy violation: {len(all_violations)} hardcoded local path(s) detected:\n'
            f'{formatted}\n\n'
            'Please use relative paths (Path(__file__).parent), pytest tmp_path fixture, '
            'or environment variables (%LOCALAPPDATA%, %ProgramFiles%) instead.'
        )


def test_scanner_detects_violations_correctly() -> None:
    """Unit test for the scanner rules ensuring positive violation detection."""
    dummy_file = REPO_ROOT / 'tests' / 'dummy_test.py'

    sample_violations = [
        "screenshot_dir = Path('C:/Users/JohnDoe/.gemini/antigravity-ide/brain/12345')",
        'file_path = "D:\\Projects\\immich-quiz\\data\\test.db"',
        'cache_path = "/home/developer/.cache/app"',
        'artifact_dir = "C:\\\\Users\\\\Admin\\\\AppData"',
    ]

    for sample in sample_violations:
        violations = find_path_violations(dummy_file, sample)
        assert len(violations) > 0, f'Expected scanner to detect violation in: {sample}'


def test_scanner_allows_valid_api_routes_and_urls() -> None:
    """Ensure legitimate API routes, URLs, and relative paths are not flagged as violations."""
    dummy_file = REPO_ROOT / 'tests' / 'dummy_test.py'

    legitimate_samples = [
        "url = 'https://photos.example.com/api/users/me'",
        "path = Path(__file__).resolve().parent / 'locales'",
        "screenshot_path = tmp_path / 'sync_popup.png'",
        "git_path = '%ProgramFiles%\\Git\\cmd\\git.exe'",
        "data_dir = Path('data').resolve()",
    ]

    for sample in legitimate_samples:
        violations = find_path_violations(dummy_file, sample)
        assert len(violations) == 0, f'Legitimate sample falsely flagged as violation: {sample}'

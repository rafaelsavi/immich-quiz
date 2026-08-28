"""Application version retrieval and package metadata utilities."""

from __future__ import annotations

import importlib.metadata
from pathlib import Path

import tomllib

from src.app_logging import get_logger

logger = get_logger('version')


def get_app_version(ignore_rc: bool = False) -> str:
    """Retrieve application version from pyproject.toml or package metadata."""
    pyproject_path = Path(__file__).parent.parent / 'pyproject.toml'
    if pyproject_path.exists():
        try:
            with pyproject_path.open('rb') as f:
                data = tomllib.load(f)
                version = data.get('project', {}).get('version')
                if version:
                    if ignore_rc and 'rc' in version:
                        # Convert 2.0.0rc0 to 2.0.0
                        version = version.split('rc')[0]
                    return str(version)
        except Exception as exc:
            logger.warning('Failed to parse version from pyproject.toml: %s', exc)

    try:
        return importlib.metadata.version('immich-quiz')
    except Exception:
        pass

    return ''


APP_VERSION = get_app_version()

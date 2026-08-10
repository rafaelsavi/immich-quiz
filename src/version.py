from __future__ import annotations

import importlib.metadata
import logging
import tomllib
from pathlib import Path

logger = logging.getLogger(__name__)


def get_app_version() -> str:
    """Retrieve application version from package metadata or pyproject.toml."""
    try:
        return importlib.metadata.version('immich-quiz')
    except Exception:
        pass

    pyproject_path = Path(__file__).parent.parent / 'pyproject.toml'
    if pyproject_path.exists():
        try:
            with pyproject_path.open('rb') as f:
                data = tomllib.load(f)
                version = data.get('project', {}).get('version')
                if version:
                    return str(version)
        except Exception as exc:
            logger.warning('Failed to parse version from pyproject.toml: %s', exc)

    return ''


APP_VERSION = get_app_version()

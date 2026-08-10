from __future__ import annotations

from pathlib import Path

import tomllib
from fastapi.testclient import TestClient

from src.main import _render_index_html
from src.version import APP_VERSION, get_app_version


def test_get_app_version_matches_pyproject() -> None:
    pyproject_path = Path(__file__).parent.parent / 'pyproject.toml'
    assert pyproject_path.exists()

    with pyproject_path.open('rb') as f:
        data = tomllib.load(f)
        expected_version = data['project']['version']

    assert get_app_version() == expected_version
    assert expected_version == APP_VERSION


def test_get_app_version_returns_empty_on_failure(monkeypatch: object) -> None:
    import importlib.metadata

    def raise_err(name: str) -> str:
        raise importlib.metadata.PackageNotFoundError(name)

    monkeypatch.setattr(importlib.metadata, 'version', raise_err)

    # Point pyproject path check to a non-existent file
    original_exists = Path.exists
    monkeypatch.setattr(Path, 'exists', lambda p: False if 'pyproject.toml' in str(p) else original_exists(p))

    assert get_app_version() == ''


def test_render_index_html_includes_app_version(client: TestClient) -> None:
    app_settings = client.app.state.settings
    static_path = Path(__file__).parent.parent / 'static'
    rendered = _render_index_html(static_path, app_settings)

    assert f'v{APP_VERSION}' in rendered
    assert 'app-version-badge' in rendered
    assert 'app-footer' in rendered


def test_index_page_returns_version_badge(client: TestClient) -> None:
    response = client.get('/')
    assert response.status_code == 200
    assert f'v{APP_VERSION}' in response.text
    assert 'app-version-badge' in response.text


def test_health_endpoint_returns_version(client: TestClient) -> None:
    response = client.get('/api/health')
    assert response.status_code == 200
    data = response.json()
    assert data['status'] == 'ok'
    assert data['version'] == APP_VERSION


def test_ui_config_endpoint_returns_version(client: TestClient) -> None:
    response = client.get('/api/ui-config')
    assert response.status_code == 200
    data = response.json()
    assert data['version'] == APP_VERSION

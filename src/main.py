from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, Response
from fastapi.responses import FileResponse, HTMLResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

from src.api.routes import router
from src.config import AppSettings, ConfigError, load_settings
from src.immich.client import ImmichClient, ImmichClientError
from src.storage.db import DatabaseManager
from src.storage.leaderboard import LeaderboardStore
from src.storage.metadata import MetadataStore
from src.storage.session import SessionStore
from src.storage.sync import SyncEngine
from src.version import APP_VERSION

logger = logging.getLogger(__name__)


def _render_index_html(static_path: Path, settings: AppSettings) -> str:
    lang_code = 'pt-BR' if settings.language == 'PT' else 'en'
    template = (static_path / 'index.html').read_text(encoding='utf-8')
    version_badge = f'<span class="app-version-badge">v{APP_VERSION}</span>' if APP_VERSION else ''
    return (
        template.replace('{{APP_TITLE}}', settings.app_title)
        .replace('{{APP_HEADING}}', settings.app_title)
        .replace('{{APP_TAGLINE}}', settings.app_tagline)
        .replace('{{LANG_CODE}}', lang_code)
        .replace('{{APP_VERSION_BADGE}}', version_badge)
        .replace('{{APP_VERSION}}', APP_VERSION)
    )


def create_app(settings: AppSettings | None = None) -> FastAPI:
    if settings is None:
        settings = load_settings()

    metadata_db_manager = DatabaseManager(settings.metadata_db_path)
    leaderboard_db_manager = DatabaseManager(settings.leaderboard_db_path)
    metadata_store = MetadataStore(metadata_db_manager)
    immich_client = ImmichClient(settings.immich_server_url, settings.immich_libraries)
    sync_engine = SyncEngine(immich_client, metadata_store)
    leaderboard_store = LeaderboardStore(
        leaderboard_db_manager,
        score_max_points=settings.score_max_points,
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        immich: ImmichClient = app.state.immich_client
        available: list[str] = []
        unavailable: dict[str, str] = {}
        for library_name in immich.list_libraries():
            try:
                await immich.validate_access(library_name)
                available.append(library_name)
            except ImmichClientError as exc:
                unavailable[library_name] = str(exc)
                logger.warning('Library %r is unavailable and was hidden from setup: %s', library_name, exc)

        app.state.available_libraries = available
        app.state.unavailable_libraries = unavailable

        # Auto-trigger background metadata indexing on startup for available libraries
        if settings.auto_sync_on_startup:
            for lib_name in available:
                logger.info('Scheduling startup metadata sync for library: %s', lib_name)
                sync_engine.trigger_sync(lib_name)

        async def _periodic_cleanup() -> None:
            while True:
                await asyncio.sleep(900)
                cleaned = app.state.session_store.cleanup_expired_matches(ttl_seconds=7200)
                if cleaned > 0:
                    logger.info('Cleaned up %d expired match session(s)', cleaned)

        cleanup_task = asyncio.create_task(_periodic_cleanup())

        try:
            yield
        finally:
            cleanup_task.cancel()
            close = getattr(app.state.immich_client, 'aclose', None)
            if close is not None:
                await close()

    app = FastAPI(title='Immich Quiz', version=APP_VERSION, lifespan=lifespan)
    app.state.settings = settings
    app.state.session_store = SessionStore()
    app.state.immich_client = immich_client
    app.state.db_manager = metadata_db_manager
    app.state.metadata_db_manager = metadata_db_manager
    app.state.leaderboard_db_manager = leaderboard_db_manager
    app.state.metadata_store = metadata_store
    app.state.sync_engine = sync_engine
    app.state.leaderboard_store = leaderboard_store

    @app.middleware('http')
    async def add_security_headers(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        response: Response = await call_next(request)
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        if request.url.path.startswith('/static/'):
            response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        return response

    static_path = Path(__file__).parent.parent / 'static'
    app.mount('/static', StaticFiles(directory=static_path), name='static')

    @app.get('/')
    async def index() -> HTMLResponse:
        return HTMLResponse(_render_index_html(static_path, settings))

    @app.get('/audio-playground')
    async def audio_playground() -> FileResponse:
        return FileResponse(static_path / 'audio-playground.html', media_type='text/html')

    @app.get('/favicon.ico')
    async def favicon() -> FileResponse:
        return FileResponse(static_path / 'favicon.svg', media_type='image/svg+xml')

    app.include_router(router)
    return app


try:
    app = create_app()
except ConfigError as exc:
    app = FastAPI(title='Immich Quiz', version=APP_VERSION)
    config_error = str(exc)

    @app.get('/')
    async def config_error_index() -> PlainTextResponse:
        return PlainTextResponse(
            f'Configuration error: {config_error}. Set environment variables or a .env file before starting.',
            status_code=500,
        )


if __name__ == '__main__':
    import uvicorn

    _settings = load_settings()
    uvicorn.run('src.main:app', host=_settings.app_host, port=_settings.app_port)

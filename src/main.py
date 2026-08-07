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
from src.storage.leaderboard import LeaderboardStore
from src.storage.session import SessionStore

logger = logging.getLogger(__name__)


def _render_index_html(static_path: Path, settings: AppSettings) -> str:
    lang_code = 'pt-BR' if settings.language == 'PT' else 'en'
    template = (static_path / 'index.html').read_text(encoding='utf-8')
    return (
        template.replace('{{APP_TITLE}}', settings.app_title)
        .replace('{{APP_HEADING}}', settings.app_title)
        .replace('{{APP_TAGLINE}}', settings.app_tagline)
        .replace('{{LANG_CODE}}', lang_code)
    )


def create_app(settings: AppSettings | None = None) -> FastAPI:
    if settings is None:
        settings = load_settings()

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

    app = FastAPI(title='Immich Quiz', version='0.1.0', lifespan=lifespan)
    app.state.settings = settings
    app.state.session_store = SessionStore()
    app.state.immich_client = ImmichClient(settings.immich_server_url, settings.immich_libraries)
    app.state.leaderboard_store = LeaderboardStore(
        settings.leaderboard_csv_path,
        score_max_points=settings.score_max_points,
    )

    @app.middleware('http')
    async def add_security_headers(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        response: Response = await call_next(request)
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        if request.url.path.startswith('/static/js/'):
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
    app = FastAPI(title='Immich Quiz', version='0.1.0')
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

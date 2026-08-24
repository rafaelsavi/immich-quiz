FROM python:3.13-slim

# Copy uv binary for fast dependency resolution
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Copy dependency files first to leverage layer caching
COPY pyproject.toml uv.lock ./

# Install dependencies into virtual environment
RUN uv sync --frozen --no-dev

# Copy project source code and assets
COPY src ./src
COPY static ./static

# Create default data directory for SQLite persistence (metadata.db and leaderboard.db)
RUN mkdir -p data

EXPOSE 8010

# Bind to 0.0.0.0 inside container so network requests reach the app
ENV APP_HOST=0.0.0.0

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD /app/.venv/bin/python -c "import urllib.request, os; port = os.getenv('APP_PORT', '8010'); urllib.request.urlopen(f'http://127.0.0.1:{port}/api/health')" || exit 1

CMD ["/app/.venv/bin/python", "-m", "src.main"]

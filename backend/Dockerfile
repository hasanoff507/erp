# syntax=docker/dockerfile:1.7
# Multi-stage build (23 §9): locked deps via uv, non-root user, HEALTHCHECK.

FROM python:3.13-slim AS build
COPY --from=ghcr.io/astral-sh/uv:0.11 /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /srv/app
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./
COPY scripts ./scripts
RUN uv sync --locked --no-dev

FROM python:3.13-slim AS runtime
RUN groupadd --system app && useradd --system --gid app --home /srv/app app
WORKDIR /srv/app
COPY --from=build --chown=app:app /srv/app /srv/app
ENV PATH="/srv/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
USER app
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=3s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health/ready', timeout=2).status == 200 else 1)"
# Access log off: RequestContextMiddleware logs every request without the query string (15 §3).
# Deploy must set FORWARDED_ALLOW_IPS to the reverse proxy's address/CIDR (client IP for 14 §12).
CMD ["uvicorn", "app.main:app_factory", "--factory", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]

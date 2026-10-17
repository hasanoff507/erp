"""Telemetry (23 §8, 25 §5): prometheus-client metrics, OpenTelemetry traces, sentry-sdk.

Everything is gated by settings and off by default, so local runs and tests need no
collector:

- ``ERP_METRICS_ENABLED`` — HTTP metrics middleware + ``GET /metrics`` (17 §1: outside the
  ``/api/v1`` series, not in the OpenAPI schema). With ``ERP_METRICS_TOKEN`` set the scrape
  must send ``Authorization: Bearer <token>``; staging/prod refuse to start without a token
  (the Prometheus on the Ops VM scrapes over the network, 25 §5).
- ``ERP_WORKER_METRICS_PORT`` — the SAQ worker/scheduler process exposes the same registry
  on its own port (same bearer token rule).
- ``ERP_OTEL_ENABLED`` — OpenTelemetry traces (FastAPI + SQLAlchemy + httpx auto
  instrumentation, one span per SAQ job) exported over OTLP/HTTP to the self-hosted
  Grafana Tempo (23 §8, 26 #53).
- ``ERP_SENTRY_DSN`` — sentry-sdk error tracking; tenant id as a tag, no customer PII
  (``send_default_pii=False``, request bodies never sent, events pass the log redaction).

Metrics of modules that do not exist yet are deliberately not defined here (no dead
series); see the TODO block below for the names 23 §8 reserves.
"""

from __future__ import annotations

import asyncio
import hmac
import threading
import time
import weakref
from collections.abc import Callable, Iterable, Mapping
from typing import TYPE_CHECKING, Any, cast
from wsgiref.simple_server import WSGIRequestHandler, WSGIServer, make_server

import structlog
from fastapi import APIRouter, FastAPI, Request, Response
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
    make_wsgi_app,
)
from prometheus_client.core import GaugeMetricFamily, Metric
from prometheus_client.registry import Collector
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.context import request_id_var, tenant_id_var
from app.core.error_codes import ErrorCode
from app.core.errors import error_response
from app.core.logging import redact_pii, scrub_url

if TYPE_CHECKING:
    from wsgiref.types import StartResponse, WSGIEnvironment

    from redis.asyncio import Redis
    from sqlalchemy.engine import Engine

    from app.core.config import Settings

log = structlog.get_logger(__name__)

METRICS_PATH = "/metrics"
UNMATCHED_ROUTE = "<unmatched>"  # 404s: never the raw path (label cardinality)
QUEUE_STATES = ("queued", "active", "incomplete")
QUEUE_REFRESH_TIMEOUT_S = 1.0

# --- metrics (one registry per process; the default global registry is left alone) -----------

REGISTRY = CollectorRegistry(auto_describe=True)

# 25 §5 "So'rov soni/kechikish/xato": labelled by route *template* (`/api/v1/branches/{id}`)
HTTP_REQUESTS = Counter(
    "erp_http_requests_total",
    "HTTP requests by route template, method and status code",
    ["method", "route", "status"],
    registry=REGISTRY,
)
HTTP_LATENCY = Histogram(
    "erp_http_request_duration_seconds",
    "HTTP request latency by route template and method (API p95 SLO, 25 §1)",
    ["method", "route"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0),
    registry=REGISTRY,
)
HTTP_IN_PROGRESS = Gauge(
    "erp_http_requests_in_progress", "HTTP requests being served", ["method"], registry=REGISTRY
)
# 23 §8 "navbat chuqurligi": SAQ queue (Redis) — refreshed on every scrape
QUEUE_JOBS = Gauge("erp_queue_jobs", "SAQ jobs by queue and state", ["queue", "state"], registry=REGISTRY)
# 23 §8 "urinish soni" / navbat ishi muvaffaqiyatsizligi alerti (25 §5)
WORKER_JOBS = Counter(
    "erp_worker_jobs_total",
    "SAQ jobs processed by function and outcome (complete/retry/failed/aborted)",
    ["function", "outcome"],
    registry=REGISTRY,
)
WORKER_JOB_DURATION = Histogram(
    "erp_worker_job_duration_seconds",
    "SAQ job run time by function",
    ["function"],
    buckets=(0.01, 0.05, 0.1, 0.5, 1.0, 5.0, 15.0, 60.0, 300.0, 900.0),
    registry=REGISTRY,
)
WORKER_JOB_ATTEMPTS = Histogram(
    "erp_worker_job_attempts",
    "Attempt number at which a SAQ job finished processing",
    ["function"],
    buckets=(1, 2, 3, 5, 8, 13),
    registry=REGISTRY,
)

# TODO(23 §8, 25 §5) — metrics of modules that are not built yet; add them with the module:
#   erp_posting_duration_seconds        — posting transaction time (accounting posting service)
#   erp_outbox_jobs{kind,status}, erp_outbox_job_attempts — app.outbox_jobs depth/attempts (needs a
#       tenant-less SECURITY DEFINER counter function; outbox dispatcher not built yet)
#   erp_ai_cost_usd_total{tenant?,feature} — sum of ai_requests.cost_usd (AI layer, 22)
#   erp_fiscal_oldest_unacked_seconds   — oldest receipt without ofd_acked_at (alert 24/40/46/48 h)
#   erp_wal_archive_lag_seconds         — exported by the backup host (backend/ops), not the API
#   onec_* (Bosqich 7)                   — the nine 1C series listed in 23 §8 / 33 §15.4


class _PoolCollector(Collector):
    """``erp_db_pool_connections{pool,state}`` (25 §5 "DB pool") read at scrape time."""

    def __init__(self) -> None:
        self._engines: weakref.WeakValueDictionary[str, Engine] = weakref.WeakValueDictionary()

    def bind(self, name: str, engine: Engine) -> None:
        self._engines[name] = engine

    def collect(self) -> Iterable[Metric]:
        family = GaugeMetricFamily(
            "erp_db_pool_connections", "SQLAlchemy pool connections by state", labels=["pool", "state"]
        )
        for name, engine in list(self._engines.items()):
            pool = cast(Any, engine.pool)  # QueuePool / AsyncAdaptedQueuePool
            for state, getter in (
                ("size", "size"),
                ("checked_out", "checkedout"),
                ("checked_in", "checkedin"),
                ("overflow", "overflow"),
            ):
                method = getattr(pool, getter, None)
                if method is not None:
                    family.add_metric([name, state], float(method()))
        yield family

    def describe(self) -> Iterable[Metric]:
        return []


_POOLS = _PoolCollector()
REGISTRY.register(_POOLS)

_init_lock = threading.Lock()
_initialized: set[str] = set()
_tracer_provider: Any | None = None  # set once tracing is initialised (process-wide)


def observe_engine(name: str, engine: Engine) -> None:
    """Pool gauges ``erp_db_pool_connections{pool=name}`` (weak ref) + SQLAlchemy spans when tracing."""
    _POOLS.bind(name, engine)
    if _tracer_provider is not None and _once("otel_sqlalchemy"):
        from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor

        # one engine per process (api / worker); session.py imports create_async_engine by name,
        # so the engine is instrumented explicitly instead of patching the factory
        SQLAlchemyInstrumentor().instrument(
            engine=engine, tracer_provider=_tracer_provider, enable_commenter=False
        )


def saq_key(queue: str, state: str) -> str:
    """Redis key SAQ keeps a queue state in (``saq.queue.redis.RedisQueue.namespace``)."""
    return f"saq:{queue}:{state}"


async def refresh_queue_depth(redis: Redis, queue: str) -> None:
    """Read the SAQ queue lengths straight from Redis (no SAQ ``Queue`` in the API process)."""
    pipe = redis.pipeline(transaction=False)
    pipe.llen(saq_key(queue, "queued"))
    pipe.llen(saq_key(queue, "active"))
    pipe.zcard(saq_key(queue, "incomplete"))
    counts = await pipe.execute()
    for state, value in zip(QUEUE_STATES, counts, strict=True):
        QUEUE_JOBS.labels(queue=queue, state=state).set(float(value))


def render_metrics() -> bytes:
    return generate_latest(REGISTRY)


def token_matches(header: str | None, token: str | None) -> bool:
    """``Authorization: Bearer <token>`` check; no token configured → open (local/test only)."""
    if not token:
        return True
    if not header or not header.startswith("Bearer "):
        return False
    return hmac.compare_digest(header.removeprefix("Bearer ").encode(), token.encode())


def _metrics_token(settings: Settings) -> str | None:
    return settings.metrics_token.get_secret_value() if settings.metrics_token else None


# --- HTTP metrics middleware -------------------------------------------------------------------


def _route_template(scope: Scope) -> str:
    route = scope.get("route")
    path = getattr(route, "path", None)
    return path if isinstance(path, str) and path else UNMATCHED_ROUTE


class PrometheusMiddleware:
    """Pure ASGI: count/latency per route template; the route is known after routing ran."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        method = str(scope.get("method", "GET"))
        status_code = 500
        started = time.perf_counter()
        in_progress = HTTP_IN_PROGRESS.labels(method=method)
        in_progress.inc()

        async def send_wrapper(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = int(message["status"])
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            in_progress.dec()
            route = _route_template(scope)
            HTTP_REQUESTS.labels(method=method, route=route, status=str(status_code)).inc()
            HTTP_LATENCY.labels(method=method, route=route).observe(time.perf_counter() - started)


def metrics_router(settings: Settings) -> APIRouter:
    router = APIRouter()
    token = _metrics_token(settings)
    queue_name = settings.queue_name

    @router.get(METRICS_PATH, include_in_schema=False)
    async def metrics(request: Request) -> Response:
        if not token_matches(request.headers.get("authorization"), token):
            return error_response(ErrorCode.UNAUTHORIZED, 401, headers={"WWW-Authenticate": "Bearer"})
        redis = getattr(request.app.state, "redis", None)
        if redis is not None:
            try:
                await asyncio.wait_for(refresh_queue_depth(redis, queue_name), QUEUE_REFRESH_TIMEOUT_S)
            except Exception as exc:  # a scrape must not fail because Redis is down
                log.warning("metrics_queue_depth_failed", exc_type=type(exc).__name__)
        return Response(render_metrics(), media_type=CONTENT_TYPE_LATEST)

    return router


# --- tracing + error tracking ------------------------------------------------------------------


def _once(key: str) -> bool:
    with _init_lock:
        if key in _initialized:
            return False
        _initialized.add(key)
        return True


_SPAN_URL_KEYS = ("http.url", "url.full")  # old / stable HTTP semconv


def scrub_span_url(span: Any) -> None:
    """Rewrite the outbound URL attributes of an httpx span (SEC-06: Telegram ``/bot<token>/``)."""
    attributes = getattr(span, "attributes", None) or {}
    for key in _SPAN_URL_KEYS:
        value = attributes.get(key)
        if isinstance(value, str):
            clean = scrub_url(value)
            if clean != value:
                span.set_attribute(key, clean)


def _httpx_request_hook(span: Any, _request: Any) -> None:
    scrub_span_url(span)


def _httpx_response_hook(span: Any, _request: Any, _response: Any) -> None:
    scrub_span_url(span)


async def _httpx_async_request_hook(span: Any, _request: Any) -> None:
    scrub_span_url(span)


async def _httpx_async_response_hook(span: Any, _request: Any, _response: Any) -> None:
    scrub_span_url(span)


def _sentry_before_breadcrumb(crumb: Any, _hint: Any) -> Any:
    """httpx breadcrumbs carry ``data.url`` — the same redaction as events (SEC-06)."""
    return redact_pii(None, "sentry", crumb)


def _sentry_before_send(event: Any, _hint: Any) -> Any:
    # redact_pii also scrubs bot tokens / bearer values inside strings (breadcrumb URLs, exception texts).
    # The tags are added after it: they are our own ids, and a UUID whose groups are all digits
    # (e.g. 42022192-1331-4000-…) would otherwise be mangled by the card-number pattern.
    event = redact_pii(None, "sentry", event)
    tenant = tenant_id_var.get()
    request_id = request_id_var.get()
    tags = event.setdefault("tags", {})
    if tenant is not None:
        tags["tenant_id"] = str(tenant)
    if request_id is not None:
        tags["request_id"] = request_id
    # TODO(23 §8): branch tag once a branch context variable exists in app.core.context
    return event


def _init_sentry(settings: Settings, service: str) -> None:
    import sentry_sdk

    assert settings.sentry_dsn is not None
    sentry_sdk.init(
        dsn=settings.sentry_dsn.get_secret_value(),
        environment=settings.environment,
        server_name=service,
        send_default_pii=False,
        max_request_body_size="never",
        include_local_variables=False,
        traces_sample_rate=0.0,  # traces go to Tempo via OpenTelemetry
        before_send=_sentry_before_send,
        before_breadcrumb=_sentry_before_breadcrumb,
    )


def _init_tracing(settings: Settings, service: str) -> None:
    from opentelemetry import trace
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.sdk.trace.sampling import ParentBased, TraceIdRatioBased

    resource = Resource.create({"service.name": service, "deployment.environment": settings.environment})
    provider = TracerProvider(
        resource=resource, sampler=ParentBased(TraceIdRatioBased(settings.otel_sample_ratio))
    )
    endpoint = settings.otel_exporter_otlp_endpoint.rstrip("/") + "/v1/traces"
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint)))
    trace.set_tracer_provider(provider)
    HTTPXClientInstrumentor().instrument(  # every httpx client (outbound); URLs scrubbed (SEC-06)
        tracer_provider=provider,
        request_hook=_httpx_request_hook,
        response_hook=_httpx_response_hook,
        async_request_hook=_httpx_async_request_hook,
        async_response_hook=_httpx_async_response_hook,
    )
    global _tracer_provider
    _tracer_provider = provider


def setup_telemetry(settings: Settings, *, service: str) -> None:
    """Process-wide init (API and worker): Sentry and the OTel tracer provider. No-op when off."""
    if settings.sentry_dsn is not None and _once("sentry"):
        _init_sentry(settings, service)
    if settings.otel_enabled and _once("otel"):
        _init_tracing(settings, service)


def install_telemetry(app: FastAPI, settings: Settings) -> None:
    """Per-app wiring for the API (called from the composition root)."""
    setup_telemetry(settings, service=f"{settings.app_name}-api")
    if settings.otel_enabled:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

        FastAPIInstrumentor.instrument_app(app, excluded_urls="/health,/metrics")
    if settings.metrics_enabled:
        app.add_middleware(PrometheusMiddleware)
        app.include_router(metrics_router(settings))


# --- worker (SAQ) ------------------------------------------------------------------------------


class _QuietHandler(WSGIRequestHandler):
    def log_message(self, format: str, *args: Any) -> None:
        return


def _guarded_wsgi(token: str | None) -> Callable[[WSGIEnvironment, StartResponse], Iterable[bytes]]:
    inner = make_wsgi_app(REGISTRY)

    def app(environ: WSGIEnvironment, start_response: StartResponse) -> Iterable[bytes]:
        if environ.get("PATH_INFO") != METRICS_PATH:
            start_response("404 Not Found", [("Content-Type", "text/plain")])
            return [b"not found"]
        if not token_matches(environ.get("HTTP_AUTHORIZATION"), token):
            start_response("401 Unauthorized", [("WWW-Authenticate", "Bearer")])
            return [b"unauthorized"]
        body: Iterable[bytes] = inner(environ, start_response)
        return body

    return app


def start_worker_metrics_server(settings: Settings) -> WSGIServer | None:
    """Serve ``/metrics`` from a daemon thread of the worker process (``ERP_WORKER_METRICS_PORT``)."""
    if settings.worker_metrics_port is None or not _once("worker_metrics_server"):
        return None
    server = make_server(
        settings.worker_metrics_host,
        settings.worker_metrics_port,
        _guarded_wsgi(_metrics_token(settings)),
        handler_class=_QuietHandler,
    )
    threading.Thread(target=server.serve_forever, name="metrics", daemon=True).start()
    log.info("worker_metrics_listening", port=server.server_port)
    return server


def _job_function(ctx: Mapping[str, Any]) -> str:
    job = ctx.get("job")
    return str(getattr(job, "function", "unknown"))


async def job_started(ctx: dict[str, Any]) -> None:
    """SAQ ``before_process`` hook: start the timer and the job span."""
    from opentelemetry import trace

    ctx["_telemetry_started"] = time.perf_counter()
    span = trace.get_tracer("app.workers").start_span(f"saq.job {_job_function(ctx)}")
    ctx["_telemetry_span"] = span


def _outcome(ctx: Mapping[str, Any]) -> str:
    status = getattr(getattr(ctx.get("job"), "status", None), "value", None)
    if status in {"complete", "failed", "aborted"}:
        return str(status)
    return "retry" if ctx.get("exception") is not None else str(status or "unknown")


async def job_finished(ctx: dict[str, Any]) -> None:
    """SAQ ``after_process`` hook: outcome counter, duration, attempts, end the span."""
    function = _job_function(ctx)
    outcome = _outcome(ctx)
    WORKER_JOBS.labels(function=function, outcome=outcome).inc()
    started = ctx.pop("_telemetry_started", None)
    if started is not None:
        WORKER_JOB_DURATION.labels(function=function).observe(time.perf_counter() - started)
    attempts = getattr(ctx.get("job"), "attempts", None)
    if isinstance(attempts, int) and attempts > 0:
        WORKER_JOB_ATTEMPTS.labels(function=function).observe(attempts)
    span = ctx.pop("_telemetry_span", None)
    if span is not None:
        span.set_attribute("saq.outcome", outcome)
        exc = ctx.get("exception")
        if isinstance(exc, BaseException):
            span.record_exception(exc)
        span.end()

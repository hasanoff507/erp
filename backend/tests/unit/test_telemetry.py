"""Telemetry (23 §8, 25 §5): /metrics gating and access, route-template labels, no-op init."""

from __future__ import annotations

import io
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr, ValidationError
from redis.asyncio import Redis
from saq.queue.redis import RedisQueue

from app.core import telemetry
from app.core.config import Settings
from app.core.context import request_id_var, tenant_id_var
from app.core.db.session import make_engine
from app.core.logging import REDACTED
from app.main import create_app

TOKEN = "m" * 40
_HARDENED: dict[str, Any] = {
    "ai_mode": "api",
    "auth_secret": SecretStr("s" * 40),
    "kek": SecretStr("b3RoZXIta2VrLW9mLWV4YWN0bHktMzItYnl0ZXMhISE="),
    "web_bff_client_secret": SecretStr("w" * 40),
    "public_base_url": "https://app.example.uz",
}
# Redis that refuses at once: the scrape must still answer (queue depth is best-effort)
_DEAD_REDIS = SecretStr("redis://127.0.0.1:1/0")


def _app(**overrides: Any) -> Any:
    app = create_app(Settings(_env_file=None, redis_url=_DEAD_REDIS, log_json=False, **overrides))

    @app.get("/probe/items/{item_id}")
    async def probe(item_id: int) -> dict[str, int]:
        return {"item_id": item_id}

    return app


def _sample(text: str, name: str, **labels: str) -> float | None:
    """Value of the first exposition line of ``name`` carrying all ``labels``."""
    for line in text.splitlines():
        if line.startswith(f"{name}{{") and all(f'{k}="{v}"' in line for k, v in labels.items()):
            return float(line.rsplit(" ", 1)[1])
    return None


def test_metrics_disabled_by_default_returns_404_and_adds_no_middleware() -> None:
    app = _app()
    assert not any(m.cls is telemetry.PrometheusMiddleware for m in app.user_middleware)
    with TestClient(app) as client:
        assert client.get("/metrics").status_code == 404


def test_metrics_exposes_request_metrics_by_route_template() -> None:
    with TestClient(_app(metrics_enabled=True)) as client:
        for item in (101, 202, 303):
            assert client.get(f"/probe/items/{item}").status_code == 200
        assert client.get("/no/such/path/42").status_code == 404
        r = client.get("/metrics")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/plain")
    body = r.text
    count = _sample(
        body, "erp_http_requests_total", method="GET", route="/probe/items/{item_id}", status="200"
    )
    assert count is not None and count >= 3
    assert _sample(body, "erp_http_request_duration_seconds_count", route="/probe/items/{item_id}")
    # cardinality: raw paths never become label values
    assert "/probe/items/101" not in body and "/no/such/path/42" not in body
    assert _sample(body, "erp_http_requests_total", route=telemetry.UNMATCHED_ROUTE, status="404")
    assert "erp_db_pool_connections" in body


def test_metrics_endpoint_is_not_in_openapi() -> None:
    with TestClient(_app(metrics_enabled=True)) as client:
        paths = client.get("/api/v1/openapi.json").json()["paths"]
    assert "/metrics" not in paths


def test_metrics_bearer_token() -> None:
    with TestClient(_app(metrics_enabled=True, metrics_token=SecretStr(TOKEN))) as client:
        missing = client.get("/metrics")
        wrong = client.get("/metrics", headers={"Authorization": "Bearer nope"})
        ok = client.get("/metrics", headers={"Authorization": f"Bearer {TOKEN}"})
    assert missing.status_code == wrong.status_code == 401
    assert missing.headers["www-authenticate"] == "Bearer"
    assert missing.json()["error"]["code"] == "UNAUTHORIZED"
    assert ok.status_code == 200 and "erp_http_requests_total" in ok.text


@pytest.mark.parametrize("environment", ["staging", "prod"])
@pytest.mark.parametrize("exposure", [{"metrics_enabled": True}, {"worker_metrics_port": 9100}])
def test_hardened_environments_require_a_metrics_token(environment: str, exposure: dict[str, Any]) -> None:
    with pytest.raises(ValidationError, match="ERP_METRICS_TOKEN"):
        Settings(_env_file=None, environment=environment, **_HARDENED, **exposure)
    with pytest.raises(ValidationError, match="ERP_METRICS_TOKEN"):
        Settings(_env_file=None, environment=environment, **_HARDENED, **exposure, metrics_token="short")
    ok = Settings(
        _env_file=None, environment=environment, **_HARDENED, **exposure, metrics_token=SecretStr(TOKEN)
    )
    assert ok.metrics_token is not None
    # metrics off: no token needed
    assert Settings(_env_file=None, environment=environment, **_HARDENED).metrics_token is None


def test_setup_telemetry_is_a_noop_when_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    from opentelemetry import trace

    monkeypatch.setattr(telemetry, "_initialized", set())
    monkeypatch.setattr(telemetry, "_tracer_provider", None)
    provider_before = trace.get_tracer_provider()
    settings = Settings(_env_file=None)
    telemetry.setup_telemetry(settings, service="erp-test")
    assert telemetry.start_worker_metrics_server(settings) is None
    assert telemetry._initialized == set()
    assert telemetry._tracer_provider is None
    assert trace.get_tracer_provider() is provider_before


def test_setup_telemetry_initialises_each_backend_once(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []
    monkeypatch.setattr(telemetry, "_initialized", set())
    monkeypatch.setattr(telemetry, "_init_tracing", lambda _s, service: calls.append(f"otel:{service}"))
    monkeypatch.setattr(telemetry, "_init_sentry", lambda _s, service: calls.append(f"sentry:{service}"))
    settings = Settings(_env_file=None, otel_enabled=True, sentry_dsn=SecretStr("https://k@sentry.invalid/1"))
    telemetry.setup_telemetry(settings, service="erp-api")
    telemetry.setup_telemetry(settings, service="erp-api")
    assert calls == ["sentry:erp-api", "otel:erp-api"]


def test_db_pool_gauges() -> None:
    engine = make_engine("postgresql+asyncpg://u:p@127.0.0.1:1/x", pool_size=7, max_overflow=0)
    telemetry.observe_engine("unit", engine.sync_engine)
    body = telemetry.render_metrics().decode()
    assert _sample(body, "erp_db_pool_connections", pool="unit", state="size") == 7.0
    assert _sample(body, "erp_db_pool_connections", pool="unit", state="checked_out") == 0.0


def test_saq_key_matches_saq_redis_layout() -> None:
    queue = RedisQueue(Redis.from_url("redis://127.0.0.1:1/0"), name="erp-q")
    for state in telemetry.QUEUE_STATES:
        assert telemetry.saq_key("erp-q", state) == queue.namespace(state)


async def test_worker_hooks_record_outcome_duration_and_attempts() -> None:
    def ctx(status: str, attempts: int, exc: Exception | None = None) -> dict[str, Any]:
        job = SimpleNamespace(function="unit_job", status=SimpleNamespace(value=status), attempts=attempts)
        return {"job": job, **({"exception": exc} if exc else {})}

    before = {
        o: _sample(
            telemetry.render_metrics().decode(), "erp_worker_jobs_total", function="unit_job", outcome=o
        )
        or 0.0
        for o in ("complete", "retry", "failed")
    }
    for c in (ctx("complete", 1), ctx("queued", 1, RuntimeError("x")), ctx("failed", 3, RuntimeError("y"))):
        await telemetry.job_started(c)
        await telemetry.job_finished(c)
        assert "_telemetry_started" not in c and "_telemetry_span" not in c
    body = telemetry.render_metrics().decode()
    for outcome in ("complete", "retry", "failed"):
        after = _sample(body, "erp_worker_jobs_total", function="unit_job", outcome=outcome)
        assert after == before[outcome] + 1
    assert _sample(body, "erp_worker_job_duration_seconds_count", function="unit_job")
    assert _sample(body, "erp_worker_job_attempts_count", function="unit_job")


def _wsgi_get(app: Any, path: str, auth: str | None = None) -> tuple[str, bytes]:
    environ = {"PATH_INFO": path, "REQUEST_METHOD": "GET", "wsgi.input": io.BytesIO(), "QUERY_STRING": ""}
    if auth is not None:
        environ["HTTP_AUTHORIZATION"] = auth
    seen: list[str] = []

    def start_response(status: str, headers: list[tuple[str, str]], exc_info: Any = None) -> Any:
        seen.append(status)

    body = b"".join(app(environ, start_response))
    return seen[0], body


def test_worker_metrics_listener_guards_path_and_token() -> None:
    app = telemetry._guarded_wsgi(TOKEN)
    assert _wsgi_get(app, "/metrics")[0].startswith("401")
    assert _wsgi_get(app, "/metrics", "Bearer wrong")[0].startswith("401")
    assert _wsgi_get(app, "/other", f"Bearer {TOKEN}")[0].startswith("404")
    status, body = _wsgi_get(app, "/metrics", f"Bearer {TOKEN}")
    assert status.startswith("200") and b"erp_http_requests_total" in body


def test_sentry_event_gets_tenant_tag_and_is_redacted() -> None:
    from uuid import uuid4

    tenant = uuid4()
    t1, t2 = tenant_id_var.set(tenant), request_id_var.set("req-12345678")
    try:
        event = telemetry._sentry_before_send(
            {"message": "fail for +998 90 123 45 67", "request": {"headers": {"Authorization": "Bearer x"}}},
            None,
        )
    finally:
        tenant_id_var.reset(t1)
        request_id_var.reset(t2)
    assert event["tags"] == {"tenant_id": str(tenant), "request_id": "req-12345678"}
    assert "123 45 67" not in event["message"]
    assert event["request"]["headers"]["Authorization"] == REDACTED


BOT_URL = "https://api.telegram.org/bot123456:AAH-secret_Token/sendMessage"


def test_scrub_url_and_log_redaction_hide_bot_and_bearer_tokens() -> None:
    from app.core.logging import redact_pii, scrub_url

    assert scrub_url(BOT_URL) == "https://api.telegram.org/bot***/sendMessage"
    assert scrub_url("https://x.uz/api/v1/bottles/1") == "https://x.uz/api/v1/bottles/1"
    event = redact_pii(None, "info", {"event": f"POST {BOT_URL} failed", "detail": "Bearer eyJhbGc.x.y bad"})
    assert "AAH-secret_Token" not in event["event"]
    assert event["detail"] == f"Bearer {REDACTED} bad"


def _span_exporter() -> tuple[Any, Any]:
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    return provider, exporter


def _assert_span_urls_scrubbed(exporter: Any) -> None:
    spans = exporter.get_finished_spans()
    assert len(spans) == 1
    urls = [v for k, v in (spans[0].attributes or {}).items() if k in ("http.url", "url.full")]
    assert urls and all(u == "https://api.telegram.org/bot***/sendMessage" for u in urls)


def _ok_transport() -> Any:
    import httpx

    return httpx.MockTransport(lambda request: httpx.Response(200, json={"ok": True}))


async def test_httpx_async_spans_never_carry_the_bot_token() -> None:
    """SEC-06: the OTel httpx hooks rewrite ``http.url``/``url.full`` on outbound spans."""
    import httpx
    from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

    provider, exporter = _span_exporter()
    async with httpx.AsyncClient(transport=_ok_transport()) as client:
        HTTPXClientInstrumentor.instrument_client(
            client,
            tracer_provider=provider,
            request_hook=telemetry._httpx_async_request_hook,
            response_hook=telemetry._httpx_async_response_hook,
        )
        assert (await client.post(BOT_URL, json={"chat_id": 1})).status_code == 200
    _assert_span_urls_scrubbed(exporter)


def test_httpx_sync_spans_never_carry_the_bot_token() -> None:
    import httpx
    from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

    provider, exporter = _span_exporter()
    with httpx.Client(transport=_ok_transport()) as client:
        HTTPXClientInstrumentor.instrument_client(
            client,
            tracer_provider=provider,
            request_hook=telemetry._httpx_request_hook,
            response_hook=telemetry._httpx_response_hook,
        )
        assert client.get(BOT_URL).status_code == 200
    _assert_span_urls_scrubbed(exporter)


def test_sentry_breadcrumbs_and_events_drop_the_bot_token() -> None:
    crumb = telemetry._sentry_before_breadcrumb(
        {"type": "http", "category": "httplib", "data": {"url": BOT_URL, "method": "POST"}}, None
    )
    assert crumb["data"]["url"] == "https://api.telegram.org/bot***/sendMessage"
    event = telemetry._sentry_before_send(
        {"exception": {"values": [{"value": f"ConnectError for {BOT_URL}"}]},
         "breadcrumbs": {"values": [{"data": {"url": BOT_URL}}]}},
        None,
    )  # fmt: skip
    assert "AAH-secret_Token" not in repr(event)

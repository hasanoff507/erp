"""QT-AI-PII-01 (31-qabul-testlari.md): the token map never leaves the request.

22 §7: the token ↔ value map lives in memory for one AI call and is written
neither to ``tenant_glossary`` nor to ``ai_requests`` (nor anywhere else in the DB).
"""

from __future__ import annotations

import ast
import json
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.config import Settings
from app.modules.ai.application.ports import AiRequestContext
from app.modules.ai.infrastructure.fake_provider import FakeAiProvider
from app.modules.ai.wiring import build_ai_provider
from tests.conftest import scalar

pytestmark = pytest.mark.db

_PERSISTENCE_TABLES = ("app.tenant_glossary", "app.ai_requests")


async def _counts(engine: AsyncEngine) -> dict[str, object]:
    return {t: await scalar(engine, f"SELECT count(*) FROM {t}") for t in _PERSISTENCE_TABLES}


async def test_qt_ai_pii_01_token_map_is_not_persisted(admin_engine: AsyncEngine) -> None:
    provider = build_ai_provider(Settings(ai_mode="fake", _env_file=None))
    raw = provider._raw  # the composition root's own fake adapter
    assert isinstance(raw, FakeAiProvider)
    raw.reply = "mijoz A ning telefoni telefon A"

    before = await _counts(admin_engine)
    answer = await provider.complete(
        "s",
        "Aliyev Vali qancha qarz?",
        context=AiRequestContext(tenant_id=uuid4(), user_id=uuid4(), feature="AI-01"),
        tool_results={"debtors": [{"name": "Aliyev Vali", "phone": "901234567", "pinfl": "31234567890123"}]},
    )
    after = await _counts(admin_engine)

    assert after == before
    assert answer == "Aliyev Vali ning telefoni 901234567"
    sent = json.dumps(raw.sent, ensure_ascii=False)
    for value in ("Aliyev", "Vali", "901234567", "31234567890123"):
        assert value not in sent, value


def test_masking_layer_has_no_persistence_path() -> None:
    """The masker and its wrapper import nothing that could write the map anywhere."""
    app_dir = Path(__file__).resolve().parents[2] / "app" / "modules" / "ai"
    banned = ("sqlalchemy", "asyncpg", "redis", "app.core.db", "logging", "structlog")
    for path in (app_dir / "privacy" / "masking.py", app_dir / "application" / "provider.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            names: list[str] = []
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            assert not [n for n in names if n.startswith(banned)], (path.name, names)

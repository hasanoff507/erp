"""SEC-03: one lock order — transfer → outbox job → e-TTN — in transfer cancel and the e-TTN outbox
worker's record step (``_registered``/``_failed``/``_transient``), checked with recording fake repos."""

from __future__ import annotations

from collections.abc import AsyncIterator, Mapping, Sequence
from contextlib import asynccontextmanager
from datetime import UTC, date, datetime
from typing import Any, cast
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.auth.principal import Principal
from app.core.permissions import BranchScope
from app.modules.integrations.einvoice.application.ettn_outbox import (
    ClaimedJob,
    EttnOutboxService,
    EttnRow,
)
from app.modules.integrations.einvoice.application.ports import EInvoiceProviderError, ETtnResult
from app.modules.inventory.application.transfers import (
    EttnRef,
    OutboxConfig,
    Transfer,
    TransferService,
)

LOCKS = ("transfer", "outbox", "ettn")


class FakeSession:
    def __init__(self) -> None:
        self.info: dict[str, Any] = {}

    @asynccontextmanager
    async def begin(self) -> AsyncIterator[None]:
        yield

    async def execute(self, *_: Any, **__: Any) -> None:
        return None


def fake_factory() -> async_sessionmaker[AsyncSession]:
    @asynccontextmanager
    async def factory() -> AsyncIterator[FakeSession]:
        yield FakeSession()

    return cast(async_sessionmaker[AsyncSession], factory)


def lock_order(calls: Sequence[str]) -> list[str]:
    """The first acquisition of each lock, in call order."""
    seen: list[str] = []
    for call in calls:
        if call in LOCKS and call not in seen:
            seen.append(call)
    return seen


# --- outbox worker ---------------------------------------------------------------------------------
class RecordingOutboxRepo:
    def __init__(self, ettn: EttnRow, job: ClaimedJob) -> None:
        self.calls: list[str] = []
        self._ettn = ettn
        self._job = job
        self._status = ettn.status

    async def claim(self, s: AsyncSession, job_id: UUID | None) -> ClaimedJob | None:
        self.calls.append("claim")
        return self._job

    async def ettn(self, s: AsyncSession, ettn_id: UUID) -> EttnRow | None:
        self.calls.append("ettn")
        e = self._ettn
        return EttnRow(e.id, e.transfer_id, self._status, e.payload)

    async def signature(self, s: AsyncSession, ettn_id: UUID) -> None:
        return None  # unsigned (fake operator auto-send)

    async def lock_transfer(self, s: AsyncSession, transfer_id: UUID) -> None:
        self.calls.append("transfer")

    async def lock_job(self, s: AsyncSession, job_id: UUID) -> None:
        self.calls.append("outbox")

    async def set_ettn(
        self,
        s: AsyncSession,
        ettn_id: UUID,
        status: str,
        *,
        operator_doc_id: str | None,
        last_error: str | None,
    ) -> None:
        self.calls.append(f"set_ettn:{status}")
        self._status = status

    async def set_transfer_ref(self, s: AsyncSession, transfer_id: UUID, ref: str) -> None:
        self.calls.append("set_transfer_ref")

    async def finish(
        self,
        s: AsyncSession,
        job_id: UUID,
        status: str,
        last_error: str | None,
        run_at: datetime | None = None,
    ) -> None:
        self.calls.append(f"finish:{status}")


class FakePort:
    def __init__(self, outcome: ETtnResult | Exception) -> None:
        self._outcome = outcome

    async def send_ettn(self, ettn_id: UUID, payload: Mapping[str, Any], signature: Any = None) -> ETtnResult:
        if isinstance(self._outcome, Exception):
            raise self._outcome
        return self._outcome


def _worker(outcome: ETtnResult | Exception) -> tuple[EttnOutboxService, RecordingOutboxRepo]:
    ettn_id = uuid4()
    job = ClaimedJob(uuid4(), {"ettn_id": str(ettn_id)}, 1)
    repo = RecordingOutboxRepo(EttnRow(ettn_id, uuid4(), "pending_signature", {}), job)
    service = EttnOutboxService(fake_factory(), repo, cast(Any, FakePort(outcome)), rand=lambda: 0.5)
    return service, repo


def _record_step(calls: list[str]) -> list[str]:
    """Calls of the second (record) transaction: everything after the claim's ``set_ettn:sending``."""
    return calls[calls.index("set_ettn:sending") + 1 :]


async def test_registered_locks_transfer_then_outbox_then_ettn() -> None:
    service, repo = _worker(ETtnResult("registered", "OP-1"))
    outcome = await service.run(uuid4())
    assert outcome is not None and outcome.ettn_status == "registered"
    assert repo.calls[:3] == ["claim", "ettn", "set_ettn:sending"]  # claim: outbox → e-TTN
    record = _record_step(repo.calls)
    assert lock_order(record) == ["transfer", "outbox", "ettn"]
    assert record == [
        "transfer", "outbox", "ettn", "set_ettn:registered", "set_transfer_ref", "finish:done",
    ]  # fmt: skip


async def test_failed_and_transient_use_the_same_lock_order() -> None:
    service, repo = _worker(ETtnResult("failed", None, "bad payload", "validation"))
    assert (await service.run(uuid4())) is not None
    assert lock_order(_record_step(repo.calls)) == ["transfer", "outbox", "ettn"]

    service, repo = _worker(EInvoiceProviderError("timeout"))
    outcome = await service.run(uuid4())
    assert outcome is not None and outcome.status == "retry"
    assert lock_order(_record_step(repo.calls)) == ["transfer", "outbox", "ettn"]


# --- transfer cancel -------------------------------------------------------------------------------
def _transfer(ettn_id: UUID) -> Transfer:
    now = datetime.now(UTC)
    return Transfer(
        id=uuid4(), branch_id=uuid4(), number="P-01-1", doc_date=date(2026, 10, 1), status="posted",
        from_branch_id=uuid4(), to_branch_id=uuid4(), from_warehouse_id=uuid4(), to_warehouse_id=uuid4(),
        transport_mode="vehicle", vehicle_plate="01A123BC", driver_name=None, ettn_ref=None, sent_at=None,
        sent_by=None, received_at=None, received_by=None, created_by=uuid4(), created_at=now, posted_at=now,
        cancelled_at=None, cancel_reason=None, comment=None, ettn=EttnRef(ettn_id, "pending_signature", None),
    )  # fmt: skip


class RecordingTransferRepo:
    def __init__(self, doc: Transfer) -> None:
        self.calls: list[str] = []
        self._doc = doc

    async def get(self, s: AsyncSession, doc_id: UUID, *, lock: bool = False) -> Transfer | None:
        if lock:
            self.calls.append("transfer")
        return self._doc

    async def lock_outbox(self, s: AsyncSession, idempotency_key: str) -> None:
        self.calls.append("outbox")
        assert self._doc.ettn is not None and idempotency_key == f"ettn_send:{self._doc.ettn.id}"

    async def lock_ettn(self, s: AsyncSession, ettn_id: UUID) -> EttnRef | None:
        self.calls.append("ettn")
        return EttnRef(ettn_id, "pending_signature", None)

    async def set_ettn_status(self, s: AsyncSession, ettn_id: UUID, status: str) -> None:
        self.calls.append(f"set_ettn:{status}")

    async def close_outbox(self, s: AsyncSession, idempotency_key: str, note: str) -> None:
        self.calls.append("close_outbox")

    async def mark_cancelled(self, s: AsyncSession, doc_id: UUID, user_id: UUID, reason: str) -> None:
        self.calls.append("mark_cancelled")

    async def overdue_hours(self, s: AsyncSession) -> int:
        return 48


async def test_transfer_cancel_locks_transfer_then_outbox_then_ettn() -> None:
    doc = _transfer(uuid4())
    repo = RecordingTransferRepo(doc)
    service = TransferService(
        fake_factory(), cast(Any, repo), cast(Any, None), cast(Any, None), cast(Any, None), None,
        OutboxConfig(auto_send=True, job="ettn_send"),
    )  # fmt: skip
    actor = Principal(
        user_id=uuid4(), tenant_id=uuid4(), client_id="test", scopes=frozenset(), roles=("owner",),
        branch_ids=(), sid=None, device_id=None, jti="t", issued_at=0, expires_at=0, sub_status=None,
        via_cookie=False,
    )  # fmt: skip
    body = await service.cancel(actor, BranchScope((), None), doc.id, "test", None)
    assert body["warnings"] == []
    assert lock_order(repo.calls) == ["transfer", "outbox", "ettn"]
    assert repo.calls[:5] == ["transfer", "outbox", "ettn", "set_ettn:cancelled", "close_outbox"]

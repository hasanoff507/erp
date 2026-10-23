"""Bank statement import — ``POST /bank-settlements/imports`` (20 #55g, 26 #124, US-M11-04).

A 1CClientBankExchange ``.txt`` (≤ ``import_max_bytes``, ≤ ``import_max_rows`` lines) is parsed, its
account must equal ``tenants.settings.bank_account``; every **incoming** line (``ПолучательСчет`` = the
tenant account) is matched to the 5710 transit balance and becomes a ``bank_settlements`` **draft**
(``source='statement_import'``) — nothing is posted automatically (the accountant posts each with 55e).

Matching of one incoming line (credit ``C`` on ``entry_date``):

1. a duplicate (a non-cancelled settlement with the same ``bank_ref`` = ``Номер``, ``doc_date`` and
   ``net_amount`` = ``C``) is only counted (``duplicates``);
2. ``method`` from the payer / purpose keywords (else ``unknown_method``); branch from a terminal TID/MID in
   the purpose, else the request ``branch_id`` / the only branch (else ``branch_ambiguous``);
3. ``card`` with an RRN registry in the purpose — integrated purchases are matched by
   ``card_terminal_transactions.rrn`` (``gross`` = Σ their approved amounts; they are linked to the draft so
   no later line takes them again; integrated purchases of the same days missing from the registry are
   returned in ``unmatched_card_transactions``). Otherwise — by amount and date: the daily 5710 inflows of
   (branch, method) minus everything already settled or held by open drafts (oldest day first), then the
   smallest run of days with ``Σ ≥ C`` and ``(Σ − C)/Σ ≤ 5%`` (terminal-less card receipts have no RRN and
   are only ever matched this way, 21 §9.2). A card line without a registry whose purpose names a terminal
   TID/MID is first matched to that terminal's open settlement batches (``card_terminal_settlements``,
   oldest ``business_date`` first, ``Σ net_total`` within the same 5%; 13 §2.18a) — the batches are linked to
   the draft at once so no later line takes them;
4. ``commission = gross − C`` (``commission_invalid`` when ``< 0`` or ``≥ gross``), ``variance = 0``;
   ``gross`` must fit the transit balance (else ``no_transit_match``).
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.audit import record_audit
from app.core.auth.principal import Principal
from app.core.db.base import uuid7
from app.core.db.session import tenant_transaction
from app.core.error_codes import ErrorCode
from app.core.errors import AppError
from app.core.idempotency import stage_response
from app.core.permissions import BranchScope
from app.modules.cash.application.bank_settlements import DOC_TYPE, BankSettlementService, require_branch
from app.modules.cash.application.bank_settlements_ports import BankSettlementRepository, CardTx, FileStore
from app.modules.cash.application.common import m2
from app.modules.cash.domain.bank_matching import (
    detect_branches,
    detect_method,
    detect_terminals,
    match_batches,
    rrn_registry,
)
from app.modules.cash.domain.bank_settlements import (
    MATCH_TOLERANCE,
    ZERO,
    Amounts,
    match_days,
    remaining_after,
)
from app.modules.cash.domain.bank_statement import (
    Statement,
    StatementDoc,
    StatementError,
    StatementTooLargeError,
    parse,
)

TEXT_TYPES = frozenset({"text/plain", "application/octet-stream", ""})


@dataclass(frozen=True, slots=True)
class ImportLimits:
    max_bytes: int
    max_lines: int


def check_file_type(filename: str | None, content_type: str | None) -> None:
    name = (filename or "").lower()
    ctype = (content_type or "").split(";", 1)[0].strip().lower()
    if not name.endswith(".txt") and ctype != "text/plain":
        raise AppError(ErrorCode.UNSUPPORTED_FILE_TYPE, params={"allowed": ["txt"]})
    if ctype not in TEXT_TYPES:
        raise AppError(ErrorCode.UNSUPPORTED_FILE_TYPE, params={"allowed": ["txt"]})


def parse_statement(content: bytes, max_lines: int) -> Statement:
    try:
        return parse(content, max_lines=max_lines)
    except StatementTooLargeError as exc:
        raise AppError(ErrorCode.FILE_TOO_LARGE, params={"max_rows": exc.max_lines}) from exc
    except StatementError as exc:
        raise AppError(
            ErrorCode.BANK_IMPORT_FILE_INVALID, params={"line_no": exc.line_no, "reason": exc.reason}
        ) from exc


def _unmatched(doc: StatementDoc, reason: str) -> dict[str, Any]:
    return {
        "line_no": doc.line_no,
        "number": doc.number,
        "date": doc.entry_date.isoformat(),
        "amount": m2(doc.amount),
        "payer_name": doc.payer_name,
        "purpose": doc.purpose,
        "reason": reason,
    }


class BankStatementImportService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        repo: BankSettlementRepository,
        settlements: BankSettlementService,
        storage: FileStore,
        limits: ImportLimits,
    ) -> None:
        self._sf = session_factory
        self._repo = repo
        self._settlements = settlements
        self._storage = storage
        self.limits = limits

    async def upload(
        self,
        actor: Principal,
        scope: BranchScope,
        *,
        filename: str | None,
        content_type: str | None,
        content: bytes,
        branch_id: UUID | None,
        ip: str | None,
    ) -> dict[str, Any]:
        check_file_type(filename, content_type)
        if len(content) > self.limits.max_bytes:
            raise AppError(ErrorCode.FILE_TOO_LARGE, params={"max_bytes": self.limits.max_bytes})
        if branch_id is not None:
            require_branch(scope, branch_id)
        statement = parse_statement(content, self.limits.max_lines)
        sha = hashlib.sha256(content).hexdigest()
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            existing = await self._repo.import_by_sha(s, sha)
            if existing is not None:
                raise AppError(ErrorCode.BANK_IMPORT_DUPLICATE, params={"import_id": str(existing)})
            account = self._check_account(statement, (await self._repo.tenant_bank(s))[0])
            branches = await self._repo.branch_ids(s)
            if branch_id is not None and branch_id not in branches:
                raise AppError(ErrorCode.NOT_FOUND, params={"resource": "branch"})
        attachment_id, import_id = uuid7(), uuid7()
        key = f"tenants/{actor.tenant_id}/bank-statements/{attachment_id}.txt"
        await self._storage.put(key, content, "text/plain")
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            # SYNC-04 (23 §2.1): imports of a tenant serialise — the per-branch transit and doc_sequences
            # locks of two statements listing branches in opposite order cannot cycle
            await self._repo.lock_imports(s, actor.tenant_id)
            raced = await self._repo.import_by_sha(s, sha)  # a parallel upload of the same file won
            if raced is not None:
                raise AppError(ErrorCode.BANK_IMPORT_DUPLICATE, params={"import_id": str(raced)})
            await self._repo.insert_attachment(
                s,
                {
                    "id": attachment_id,
                    "tenant_id": actor.tenant_id,
                    "s3_key": key,
                    "content_type": "text/plain",
                    "original_name": (filename or "")[:255] or None,
                    "sha256": sha,
                    "kind": "import",
                    "size_bytes": len(content),
                    "uploaded_by": actor.user_id,
                },
            )
            await self._repo.insert_import(
                s,
                {
                    "id": import_id,
                    "tenant_id": actor.tenant_id,
                    "branch_id": branch_id,
                    "attachment_id": attachment_id,
                    "file_sha256": sha,
                    "account": account,
                    "period_from": statement.period_from,
                    "period_to": statement.period_to,
                    "created_by": actor.user_id,
                },
            )
            result = await self._match(
                s, actor, scope, statement, account, branch_id, branches, import_id, attachment_id, ip
            )
            await self._repo.finish_import(
                s,
                import_id,
                {
                    "rows_total": len(statement.documents),
                    "drafts_created": len(result["draft_ids"]),
                    "duplicates": result["duplicates"],
                    "ignored_outgoing": result["ignored_outgoing"],
                    "unmatched_lines": result["unmatched_lines"],
                },
            )
            body = {
                "import_id": str(import_id),
                "file_sha256": sha,
                "account": account,
                "period_from": None if statement.period_from is None else statement.period_from.isoformat(),
                "period_to": None if statement.period_to is None else statement.period_to.isoformat(),
                "drafts_created": len(result["draft_ids"]),
                "draft_ids": result["draft_ids"],
                "duplicates": result["duplicates"],
                "ignored_outgoing": result["ignored_outgoing"],
                "unmatched_lines": result["unmatched_lines"],
                "unmatched_card_transactions": result["unmatched_card_transactions"],
            }
            await record_audit(
                s,
                tenant_id=actor.tenant_id,
                user_id=actor.user_id,
                action="bank_statement_imported",
                entity=DOC_TYPE,
                entity_id=import_id,
                ip=ip,
                after={
                    "import_id": str(import_id),
                    "file_sha256": sha,
                    "drafts_created": len(result["draft_ids"]),
                    "duplicates": result["duplicates"],
                    "unmatched": len(result["unmatched_lines"]),
                },
            )
            stage_response(body, 201)
        return body

    @staticmethod
    def _check_account(statement: Statement, tenant_account: str | None) -> str:
        accounts = statement.account_numbers
        file_account = accounts[0] if len(accounts) == 1 else None
        if not tenant_account or file_account is None or file_account != tenant_account.strip():
            raise AppError(
                ErrorCode.BANK_IMPORT_ACCOUNT_MISMATCH,
                params={"file_account": ",".join(accounts) if accounts else None},
            )
        return file_account

    async def _match(
        self,
        s: AsyncSession,
        actor: Principal,
        scope: BranchScope,
        statement: Statement,
        account: str,
        default_branch: UUID | None,
        branches: Sequence[UUID],
        import_id: UUID,
        attachment_id: UUID,
        ip: str | None,
    ) -> dict[str, Any]:
        terminals = await self._repo.terminal_identifiers(s)
        acquirers = await self._repo.acquirer_inns(s)
        fallback = default_branch or (branches[0] if len(branches) == 1 else None)
        unmatched: list[dict[str, Any]] = []
        unmatched_txs: dict[UUID, CardTx] = {}
        draft_ids: list[str] = []
        duplicates = ignored = 0
        for doc in statement.documents:
            if (doc.recipient_account or "").strip() != account:
                ignored += 1
                continue
            if await self._repo.is_duplicate(s, doc.number, doc.entry_date, doc.amount):
                duplicates += 1
                continue
            method = detect_method(doc.purpose, doc.payer_name, doc.payer_inn, acquirers)
            if method is None:
                unmatched.append(_unmatched(doc, "unknown_method"))
                continue
            found = detect_branches(doc.purpose, terminals)
            branch = next(iter(found)) if len(found) == 1 else (fallback if not found else None)
            if branch is None or not _in_scope(scope, branch):
                unmatched.append(_unmatched(doc, "branch_ambiguous"))
                continue
            await self._repo.lock_transit(s, branch, method)
            rrns = rrn_registry(doc.purpose) if method == "card" else ()
            linked: list[CardTx] = []
            batch_ids: tuple[UUID, ...] = ()
            batch = None
            if not rrns and method == "card":  # 13 §2.18a: TID + business_date + batch total
                tids = detect_terminals(doc.purpose, terminals)
                batches = await self._repo.open_terminal_batches(s, branch, sorted(tids), doc.entry_date)
                batch = match_batches(batches, doc.amount, MATCH_TOLERANCE)
            if rrns:
                linked = [t for t in await self._repo.card_txs_by_rrn(s, rrns) if t.branch_id == branch]
                if not linked:
                    unmatched.append(_unmatched(doc, "no_transit_match"))
                    continue
                gross = sum((t.amount for t in linked), ZERO)
                days = sorted(t.business_date for t in linked)
                settled_from, settled_to = days[0], days[-1]
            elif batch is not None:
                gross, settled_from, settled_to = batch.gross, batch.settled_from, batch.settled_to
                batch_ids = batch.batch_ids
            else:
                inflows = await self._repo.daily_inflows(s, branch, method, doc.entry_date)
                holds = await self._repo.holds(s, branch, method)
                match = match_days(remaining_after(inflows, holds), doc.amount)
                if match is None:
                    unmatched.append(_unmatched(doc, "no_transit_match"))
                    continue
                gross, settled_from, settled_to = match.gross, match.settled_from, match.settled_to
            commission = gross - doc.amount
            if commission < 0 or commission >= gross:
                unmatched.append(_unmatched(doc, "commission_invalid"))
                continue
            settled_to = min(settled_to, doc.entry_date)
            settled_from = min(settled_from, settled_to)
            a = Amounts(method, doc.entry_date, settled_from, settled_to, gross, commission, Decimal("0.00"))
            available = await self._settlements.posting.available(s, branch, method, doc.entry_date)
            if gross > available:
                unmatched.append(_unmatched(doc, "no_transit_match"))
                continue
            row = await self._settlements.insert_draft(
                s,
                actor,
                branch_id=branch,
                a=a,
                source="statement_import",
                bank_ref=doc.number,
                attachment_id=attachment_id,
                statement_import_id=import_id,
                comment=None,
                ip=ip,
            )
            draft_ids.append(str(row.id))
            if batch_ids:
                await self._repo.link_batches(s, batch_ids, row.id)
            if linked:
                await self._repo.link_card_txs(s, [t.id for t in linked], row.id)
                taken = {t.id for t in linked}
                for t in await self._repo.open_card_txs(s, branch, settled_from, settled_to):
                    if t.id not in taken:
                        unmatched_txs[t.id] = t
        # a transaction listed later in the same file is no longer "unmatched"
        still_open = {
            t.id for t in await self._repo.card_txs_by_rrn(s, [t.rrn for t in unmatched_txs.values()])
        }
        return {
            "draft_ids": draft_ids,
            "duplicates": duplicates,
            "ignored_outgoing": ignored,
            "unmatched_lines": unmatched,
            "unmatched_card_transactions": [
                {
                    "card_terminal_transaction_id": str(t.id),
                    "rrn": t.rrn,
                    "amount": m2(t.amount),
                    "business_date": t.business_date.isoformat(),
                }
                for t in sorted(unmatched_txs.values(), key=lambda x: (x.business_date, str(x.id)))
                if t.id in still_open
            ],
        }


def _in_scope(scope: BranchScope, branch_id: UUID) -> bool:
    if scope.current is not None:
        return branch_id == scope.current
    return scope.unrestricted or branch_id in scope.allowed

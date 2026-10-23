"""Composition of the cloud print slice (23 §1 ``wiring.py``; qaror #21, 24 §6.1)."""

from __future__ import annotations

from app.core.config import Settings
from app.core.db.session import Database
from app.modules.integrations.cloud_print.application.module import CloudPrintModule
from app.modules.integrations.cloud_print.application.service import (
    CloudPrinterService,
    PrinterPollService,
    PrintJobService,
)
from app.modules.integrations.cloud_print.infrastructure.sql import SqlCloudPrintRepository

__all__ = ["CloudPrintModule", "build_cloud_print_module"]


def build_cloud_print_module(settings: Settings, db: Database) -> CloudPrintModule:
    repo = SqlCloudPrintRepository()
    return CloudPrintModule(
        printers=CloudPrinterService(db.session_factory, repo),
        jobs=PrintJobService(db.session_factory, repo),
        poll=PrinterPollService(db.session_factory, repo),
    )

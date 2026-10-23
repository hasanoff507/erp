"""The cloud print facade published on ``app.state.cloud_print`` (built by ``wiring.py``)."""

from __future__ import annotations

from dataclasses import dataclass

from app.modules.integrations.cloud_print.application.service import (
    CloudPrinterService,
    PrinterPollService,
    PrintJobService,
)


@dataclass(slots=True)
class CloudPrintModule:
    printers: CloudPrinterService
    jobs: PrintJobService
    poll: PrinterPollService

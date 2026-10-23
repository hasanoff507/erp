"""``onec_agents.capabilities`` (34 §14.2) — normalisation of A-01 ``hello`` and read helpers. Pure Python.

The agent declares which store-agent modules are installed and configured; the server queues a task of
a family only when ``capabilities.<family>.enabled is True`` (``AGENT_CAPABILITY_DISABLED`` otherwise).
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Final

from app.modules.onec_integration.domain.kinds import CAPABILITY_FAMILIES

# a hello without the field: only the 1C module (33 §9.3 A-01)
DEFAULT_CAPABILITIES: Final[dict[str, Any]] = {"onec": {"enabled": True, "version": 1}}

MAX_DEVICES: Final = 64
MAX_STR: Final = 256
_DEVICE_STR_FIELDS: Final = ("local_id", "transport", "host", "status", "driver", "tid", "name", "model")


class CapabilitiesError(ValueError):
    def __init__(self, field: str) -> None:
        super().__init__(field)
        self.field = field


def _device(raw: Any, path: str) -> dict[str, Any]:
    if not isinstance(raw, Mapping):
        raise CapabilitiesError(path)
    local_id = raw.get("local_id")
    if not isinstance(local_id, str) or not 1 <= len(local_id) <= 64:
        raise CapabilitiesError(f"{path}.local_id")
    device: dict[str, Any] = {}
    for key, value in raw.items():
        if not isinstance(key, str) or len(key) > 64:
            continue
        if key in _DEVICE_STR_FIELDS:
            if value is not None and (not isinstance(value, str) or len(value) > MAX_STR):
                raise CapabilitiesError(f"{path}.{key}")
            device[key] = value
        elif key == "port":
            if value is not None and (isinstance(value, bool) or not isinstance(value, int)):
                raise CapabilitiesError(f"{path}.port")
            device[key] = value
        elif isinstance(value, str | int | bool) or value is None:
            device[key] = value if not isinstance(value, str) else value[:MAX_STR]
    return device


def normalize_capabilities(raw: Any) -> dict[str, Any]:
    """Validated copy of the hello ``capabilities``; unknown families dropped, ``enabled`` boolean."""
    if raw is None:
        return {k: dict(v) for k, v in DEFAULT_CAPABILITIES.items()}
    if not isinstance(raw, Mapping):
        raise CapabilitiesError("capabilities")
    out: dict[str, Any] = {}
    for family in CAPABILITY_FAMILIES:
        entry = raw.get(family)
        if entry is None:
            continue
        path = f"capabilities.{family}"
        if not isinstance(entry, Mapping):
            raise CapabilitiesError(path)
        enabled = entry.get("enabled", False)
        if not isinstance(enabled, bool):
            raise CapabilitiesError(f"{path}.enabled")
        version = entry.get("version", 0)
        if isinstance(version, bool) or not isinstance(version, int) or not 0 <= version <= 1000:
            raise CapabilitiesError(f"{path}.version")
        item: dict[str, Any] = {"enabled": enabled, "version": version}
        provider = entry.get("provider")
        if provider is not None:
            if not isinstance(provider, str) or len(provider) > 64:
                raise CapabilitiesError(f"{path}.provider")
            item["provider"] = provider
        elif "provider" in entry:
            item["provider"] = None
        devices = entry.get("devices")
        if devices is not None:
            if not isinstance(devices, list) or len(devices) > MAX_DEVICES:
                raise CapabilitiesError(f"{path}.devices")
            item["devices"] = [_device(d, f"{path}.devices[{i}]") for i, d in enumerate(devices)]
        out[family] = item
    return out


def capability_enabled(capabilities: Mapping[str, Any] | None, family: str) -> bool:
    entry = (capabilities or {}).get(family)
    return isinstance(entry, Mapping) and entry.get("enabled") is True


def capability_devices(capabilities: Mapping[str, Any] | None, family: str) -> list[dict[str, Any]]:
    """``capabilities.<family>.devices`` (``[]`` when the family is absent or disabled)."""
    entry = (capabilities or {}).get(family)
    if not isinstance(entry, Mapping) or entry.get("enabled") is not True:
        return []
    devices = entry.get("devices")
    return [dict(d) for d in devices if isinstance(d, Mapping)] if isinstance(devices, list) else []

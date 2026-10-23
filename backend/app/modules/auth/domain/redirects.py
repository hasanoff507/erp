"""Registered OAuth redirect URIs (RFC 6749 §3.1.2, RFC 8252 §7.3; 14 §3). Pure Python.

``https://`` everywhere; plain ``http://`` only to the loopback host ``localhost`` / ``127.0.0.1`` (any
port) and only in the local/dev/test environments — never in staging/prod. No userinfo, no fragment.
"""

from __future__ import annotations

from typing import Final
from urllib.parse import urlsplit

DEV_ENVIRONMENTS: Final = frozenset({"local", "dev", "test"})
LOOPBACK_HOSTS: Final = frozenset({"localhost", "127.0.0.1"})


class InvalidRedirectUriError(ValueError):
    pass


def validate_redirect_uri(uri: str, environment: str) -> str:
    try:
        parts = urlsplit(uri)
        port = parts.port  # raises on a non-numeric/out-of-range port
    except ValueError as exc:
        raise InvalidRedirectUriError(f"invalid redirect URI: {uri}") from exc
    del port
    if parts.username is not None or parts.password is not None or "@" in parts.netloc:
        raise InvalidRedirectUriError(f"redirect URI must not carry userinfo: {uri}")
    if parts.fragment or "#" in uri:
        raise InvalidRedirectUriError(f"redirect URI must not have a fragment: {uri}")
    if not parts.hostname:
        raise InvalidRedirectUriError(f"redirect URI needs a host: {uri}")
    if parts.scheme == "https":
        return uri
    if parts.scheme == "http" and parts.hostname in LOOPBACK_HOSTS:
        if environment in DEV_ENVIRONMENTS:
            return uri
        raise InvalidRedirectUriError(f"http loopback redirect URIs are dev-only ({environment}): {uri}")
    raise InvalidRedirectUriError(f"redirect URI must be https: {uri}")

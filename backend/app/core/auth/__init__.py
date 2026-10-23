"""RS side of auth shared by every module (23 §1): principal, dependencies, CSRF/cookie signing.

The OAuth AS/RS implementation lives in ``app/modules/auth``.
"""

from app.core.auth.dependencies import (
    TenantSession,
    current_principal,
    require_subscription_ok,
    tenant_session,
)
from app.core.auth.principal import Principal

__all__ = ["Principal", "TenantSession", "current_principal", "require_subscription_ok", "tenant_session"]

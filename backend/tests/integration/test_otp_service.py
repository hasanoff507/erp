"""``AuthModule.otp`` — the cross-slice OTP contract (14 §4.2) on real Postgres/Redis."""

from __future__ import annotations

import re
from uuid import UUID

import pytest
from redis.asyncio import Redis

from app.core.errors import AppError
from app.modules.auth.wiring import AuthModule
from tests.conftest import MigratedDb
from tests.support.auth import auth_settings, new_phone, running_app

pytestmark = pytest.mark.db


async def test_otp_issue_and_verify_with_dev_fakes(
    oauth_platform: None, migrated_db: MigratedDb, redis_url: str, clean_redis: Redis
) -> None:
    settings = auth_settings(migrated_db, redis_url, otp_dev_fakes=True)
    async with running_app(settings) as (app, _):
        module: AuthModule = app.state.auth_module
        assert module.otp_dev_outbox is not None
        phone = new_phone()
        issued = await module.otp.issue(phone, "invite", ip="10.0.0.1")
        assert isinstance(issued.challenge_id, UUID)
        assert issued.channel_used == "sms"  # no Telegram link for a fresh phone
        message = module.otp_dev_outbox.last_to(phone)
        assert message is not None
        code = re.search(r"\b(\d{6})\b", message.text)
        assert code is not None
        with pytest.raises(AppError) as wrong:
            await module.otp.verify(
                issued.challenge_id, "000000" if code[1] != "000000" else "111111", ip=None
            )
        assert wrong.value.code == "OTP_INVALID"
        verified = await module.otp.verify(issued.challenge_id, code[1], ip=None)
        assert (verified.phone, verified.purpose) == (phone, "invite")
        with pytest.raises(AppError) as again:
            await module.otp.verify(issued.challenge_id, code[1], ip=None)
        assert again.value.code == "OTP_INVALID"  # 'used'


def test_dev_fakes_and_test_numbers_are_refused_in_staging_and_prod() -> None:
    from pydantic import ValidationError

    from app.core.config import Settings

    strong = {
        "auth_secret": "x" * 40,
        "kek": "c3Ryb25nLXByb2Qta2VrLTMyLWJ5dGVzLWxvbmctISE=",
        "web_bff_client_secret": "y" * 40,
        "public_base_url": "https://erp.example.uz",
        "ai_mode": "api",
    }
    for env in ("staging", "prod"):
        with pytest.raises(ValidationError, match="ERP_OTP_DEV_FAKES"):
            Settings(_env_file=None, environment=env, otp_dev_fakes=True, **strong)  # type: ignore[arg-type]
        with pytest.raises(ValidationError, match="ERP_OTP_DEV_FAKES"):
            Settings(
                _env_file=None, environment=env, otp_test_phones=["+998900000001"], otp_test_code="123456",
                **strong,  # type: ignore[arg-type]
            )  # fmt: skip
    with pytest.raises(ValidationError, match="ERP_OTP_TEST_CODE"):
        Settings(_env_file=None, environment="test", otp_test_phones=["+998900000001"])  # type: ignore[call-arg]

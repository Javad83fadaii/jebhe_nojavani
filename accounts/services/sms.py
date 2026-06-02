from __future__ import annotations

from dataclasses import dataclass

from django.conf import settings

from accounts.services.kavenegar import send_sms, send_verify_code


@dataclass(frozen=True)
class SMSSendResult:
    ok: bool
    provider: str
    message_id: str | None
    raw: dict | None


def send_password_reset_code(*, phone_number: str, code: str) -> SMSSendResult:
    backend = (getattr(settings, "SMS_BACKEND", "") or "").strip().casefold() or "dummy"

    if backend == "dummy":
        return SMSSendResult(ok=True, provider="dummy", message_id=None, raw={"dummy": True})

    if backend == "kavenegar":
        template = (getattr(settings, "KAVENEGAR_VERIFY_TEMPLATE", "") or "").strip()
        if template:
            result = send_verify_code(phone_number=phone_number, code=code)
        else:
            message_template = (
                getattr(settings, "PASSWORD_RESET_SMS_TEXT", "") or "کد بازیابی رمز عبور شما: {code}"
            )
            result = send_sms(phone_number=phone_number, message=message_template.format(code=code))
        return SMSSendResult(ok=result.ok, provider="kavenegar", message_id=result.message_id, raw=result.raw)

    raise RuntimeError("SMS_BACKEND is not supported")

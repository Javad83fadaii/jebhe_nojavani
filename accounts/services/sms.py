from __future__ import annotations

from dataclasses import dataclass

from django.conf import settings

from accounts.services.smsir import send_sms, send_verify_code


@dataclass(frozen=True)
class SMSSendResult:
    ok: bool
    provider: str
    message_id: str | None
    raw: dict | None


def _password_reset_message(code: str) -> str:
    message_template = getattr(settings, "PASSWORD_RESET_SMS_TEXT", "") or "کد بازیابی رمز عبور شما: {code}"
    return message_template.format(code=code)


def _build_attempt_payload(
    *,
    primary_channel: str,
    primary_result: dict | None = None,
    primary_error: str | None = None,
    fallback_channel: str | None = None,
    fallback_result: dict | None = None,
) -> dict:
    payload: dict[str, object] = {
        "primary_channel": primary_channel,
    }
    if primary_result is not None:
        payload["primary_result"] = primary_result
    if primary_error:
        payload["primary_error"] = primary_error
    if fallback_channel:
        payload["fallback_channel"] = fallback_channel
    if fallback_result is not None:
        payload["fallback_result"] = fallback_result
    return payload


def send_password_reset_code(*, phone_number: str, code: str) -> SMSSendResult:
    backend = (getattr(settings, "SMS_BACKEND", "") or "").strip().casefold() or "dummy"

    if backend == "dummy":
        return SMSSendResult(ok=True, provider="dummy", message_id=None, raw={"dummy": True})

    if backend in {"smsir", "sms.ir"}:
        template = (getattr(settings, "SMSIR_TEMPLATE_ID", "") or "").strip()
        if template:
            try:
                result = send_verify_code(phone_number=phone_number, code=code)
            except Exception as primary_exc:
                try:
                    fallback_result = send_sms(phone_number=phone_number, message=_password_reset_message(code))
                except Exception as fallback_exc:
                    raise RuntimeError(
                        f"SMS.ir verify send failed: {primary_exc}; fallback bulk send failed: {fallback_exc}"
                    ) from fallback_exc

                return SMSSendResult(
                    ok=fallback_result.ok,
                    provider="smsir",
                    message_id=fallback_result.message_id,
                    raw=_build_attempt_payload(
                        primary_channel="verify",
                        primary_error=str(primary_exc).strip(),
                        fallback_channel="bulk",
                        fallback_result=fallback_result.raw,
                    ),
                )

            if result.ok:
                return SMSSendResult(ok=result.ok, provider="smsir", message_id=result.message_id, raw=result.raw)

            try:
                fallback_result = send_sms(phone_number=phone_number, message=_password_reset_message(code))
            except Exception as fallback_exc:
                raise RuntimeError(
                    f"SMS.ir verify send returned unsuccessful response; fallback bulk send failed: {fallback_exc}"
                ) from fallback_exc
            return SMSSendResult(
                ok=fallback_result.ok,
                provider="smsir",
                message_id=fallback_result.message_id,
                raw=_build_attempt_payload(
                    primary_channel="verify",
                    primary_result=result.raw,
                    fallback_channel="bulk",
                    fallback_result=fallback_result.raw,
                ),
            )

        result = send_sms(phone_number=phone_number, message=_password_reset_message(code))
        return SMSSendResult(ok=result.ok, provider="smsir", message_id=result.message_id, raw=result.raw)

    raise RuntimeError("SMS_BACKEND is not supported")

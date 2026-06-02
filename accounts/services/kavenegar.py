from __future__ import annotations

import json
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from django.conf import settings


@dataclass(frozen=True)
class KavenegarSendResult:
    ok: bool
    status: int | None
    message: str | None
    message_id: str | None
    raw: dict | None


def _extract_result(data: dict | None) -> KavenegarSendResult:
    data = data or {}
    return_section = data.get("return") or {}
    status = return_section.get("status")
    message = return_section.get("message")

    entries = data.get("entries")
    message_id = None
    if isinstance(entries, list) and entries:
        message_id = str(entries[0].get("messageid") or entries[0].get("messageId") or "") or None
    elif isinstance(entries, dict):
        message_id = str(entries.get("messageid") or entries.get("messageId") or "") or None

    ok = int(status or 0) == 200
    return KavenegarSendResult(ok=ok, status=status, message=message, message_id=message_id, raw=data)


def _perform_get(path: str, params: dict[str, str]) -> KavenegarSendResult:
    api_key = getattr(settings, "KAVENEGAR_API_KEY", "") or ""
    if not api_key:
        raise RuntimeError("KAVENEGAR_API_KEY is not configured")

    url = f"https://api.kavenegar.com/v1/{api_key}/{path}?{urlencode(params)}"
    req = Request(url=url, method="GET")

    try:
        with urlopen(req, timeout=12) as resp:
            payload = resp.read().decode("utf-8", errors="replace")
    except HTTPError as exc:
        payload = exc.read().decode("utf-8", errors="replace")
        try:
            data = json.loads(payload or "{}")
        except json.JSONDecodeError as decode_error:
            raise RuntimeError(f"Kavenegar HTTP {exc.code}: {payload or exc.reason}") from decode_error
        result = _extract_result(data)
        return KavenegarSendResult(
            ok=False,
            status=result.status or exc.code,
            message=result.message or str(exc.reason),
            message_id=result.message_id,
            raw=data,
        )
    except URLError as exc:
        raise RuntimeError(f"Kavenegar connection error: {exc.reason}") from exc

    data = json.loads(payload or "{}")
    return _extract_result(data)


def send_verify_code(*, phone_number: str, code: str) -> KavenegarSendResult:
    template = getattr(settings, "KAVENEGAR_VERIFY_TEMPLATE", "") or ""
    verify_type = getattr(settings, "KAVENEGAR_VERIFY_TYPE", "sms") or "sms"
    if not template:
        raise RuntimeError("KAVENEGAR_VERIFY_TEMPLATE is not configured")

    return _perform_get(
        "verify/lookup.json",
        {
            "receptor": phone_number,
            "template": template,
            "token": code,
            "type": verify_type,
        },
    )


def send_sms(*, phone_number: str, message: str) -> KavenegarSendResult:
    sender = getattr(settings, "KAVENEGAR_SENDER", "") or ""
    if not sender:
        raise RuntimeError("KAVENEGAR_SENDER is not configured")

    return _perform_get(
        "sms/send.json",
        {
            "receptor": phone_number,
            "sender": sender,
            "message": message,
        },
    )

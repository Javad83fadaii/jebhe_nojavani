from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any

import requests
from django.conf import settings

DEFAULT_TIMEOUT_SECONDS = 15
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SMSIRSendResult:
    ok: bool
    message_id: str | None
    raw: dict[str, Any] | None


def _base_url() -> str:
    return (getattr(settings, "SMSIR_BASE_URL", "") or "https://api.sms.ir/v1").rstrip("/")


def _headers() -> dict[str, str]:
    api_key = (getattr(settings, "SMSIR_API_KEY", "") or "").strip()
    if not api_key:
        raise RuntimeError("SMSIR_API_KEY is not configured")

    return {
        "x-api-key": api_key,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def _timeout_seconds() -> int:
    raw_timeout = getattr(settings, "SMSIR_TIMEOUT_SECONDS", DEFAULT_TIMEOUT_SECONDS)
    try:
        return max(int(raw_timeout), 1)
    except (TypeError, ValueError):
        return DEFAULT_TIMEOUT_SECONDS


def _post(*, path: str, payload: dict[str, Any], accept: str = "application/json") -> dict[str, Any]:
    headers = _headers()
    headers["Accept"] = accept
    url = f"{_base_url()}/{path.lstrip('/')}"

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=_timeout_seconds())
    except requests.RequestException as exc:
        logger.exception("SMS.ir request failed", extra={"smsir_path": path, "smsir_url": url})
        raise RuntimeError(f"SMS.ir connection error: {exc}") from exc

    try:
        data = response.json()
    except ValueError:
        text = response.text.strip()
        logger.error(
            "SMS.ir returned non-JSON response",
            extra={
                "smsir_path": path,
                "smsir_url": url,
                "smsir_status_code": response.status_code,
                "smsir_response_text": text[:1000],
            },
        )
        raise RuntimeError(
            f"SMS.ir returned a non-JSON response (HTTP {response.status_code}): {text or 'empty body'}"
        )

    if not isinstance(data, dict):
        logger.error(
            "SMS.ir returned unexpected payload type",
            extra={
                "smsir_path": path,
                "smsir_url": url,
                "smsir_status_code": response.status_code,
                "smsir_payload_type": type(data).__name__,
            },
        )
        raise RuntimeError(f"SMS.ir returned an unexpected response payload: {data!r}")

    data.setdefault("http_status_code", response.status_code)
    try:
        if int(data.get("status")) != 1:
            logger.warning(
                "SMS.ir returned unsuccessful status",
                extra={
                    "smsir_path": path,
                    "smsir_url": url,
                    "smsir_status_code": response.status_code,
                    "smsir_response": data,
                },
            )
    except (TypeError, ValueError):
        logger.warning(
            "SMS.ir returned response without a valid status code",
            extra={
                "smsir_path": path,
                "smsir_url": url,
                "smsir_status_code": response.status_code,
                "smsir_response": data,
            },
        )
    return data


def _message_id_from_data(data: Any) -> str | None:
    if not isinstance(data, dict):
        return None

    direct_message_id = data.get("messageId")
    if direct_message_id not in (None, ""):
        return str(direct_message_id)

    message_ids = data.get("messageIds")
    if isinstance(message_ids, list) and message_ids:
        first_message_id = message_ids[0]
        if first_message_id not in (None, ""):
            return str(first_message_id)

    pack_id = data.get("packId")
    if pack_id not in (None, ""):
        return str(pack_id)

    return None


def _build_result(raw: dict[str, Any]) -> SMSIRSendResult:
    status_code = raw.get("status")
    ok = False
    try:
        ok = int(status_code) == 1
    except (TypeError, ValueError):
        ok = False

    return SMSIRSendResult(ok=ok, message_id=_message_id_from_data(raw.get("data")), raw=raw)


def send_sms(*, phone_number: str, message: str) -> SMSIRSendResult:
    line_number = (getattr(settings, "SMSIR_LINE_NUMBER", "") or "").strip()
    if not line_number:
        raise RuntimeError("SMSIR_LINE_NUMBER is not configured")

    payload = {
        "lineNumber": line_number,
        "messageText": message,
        "mobiles": [phone_number],
        "sendDateTime": None,
    }
    raw = _post(path="send/bulk", payload=payload)
    return _build_result(raw)


def send_verify_code(*, phone_number: str, code: str) -> SMSIRSendResult:
    template_id = (getattr(settings, "SMSIR_TEMPLATE_ID", "") or "").strip()
    if not template_id:
        raise RuntimeError("SMSIR_TEMPLATE_ID is not configured")
    try:
        normalized_template_id = int(template_id)
    except ValueError as exc:
        raise RuntimeError("SMSIR_TEMPLATE_ID must be an integer") from exc

    parameter_name = (getattr(settings, "SMSIR_VERIFY_PARAMETER_NAME", "") or "Code").strip() or "Code"
    payload = {
        "mobile": phone_number,
        "templateId": normalized_template_id,
        "parameters": [
            {
                "name": parameter_name,
                "value": code,
            }
        ],
    }
    raw = _post(path="send/verify", payload=payload, accept="text/plain")
    return _build_result(raw)

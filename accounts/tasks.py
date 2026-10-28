from __future__ import annotations

import logging
from threading import Thread

from django.conf import settings
from django.db import close_old_connections
from django.utils import timezone

from accounts.models import PasswordResetRequest
from accounts.services.sms import send_password_reset_code

logger = logging.getLogger(__name__)


def _mask_phone_number(phone_number: str) -> str:
    normalized = str(phone_number or "").strip()
    if len(normalized) < 4:
        return normalized
    return f"{normalized[:3]}****{normalized[-4:]}"


def _extract_provider_error(raw: dict | None) -> str:
    if not isinstance(raw, dict):
        return ""

    direct_error = raw.get("error")
    if direct_error:
        return str(direct_error).strip()

    status_code = raw.get("status")
    message = raw.get("message")
    try:
        if message and int(status_code) != 1:
            return str(message).strip()
    except (TypeError, ValueError):
        if message:
            return str(message).strip()

    return_section = raw.get("return")
    if isinstance(return_section, dict):
        message = return_section.get("message")
        status_code = return_section.get("status")
        if message and str(status_code or "") != "200":
            return str(message).strip()

    return ""


def _mark_request_failed(reset_request: PasswordResetRequest, *, provider: str, send_error: str, provider_response: dict | None):
    reset_request.status = PasswordResetRequest.Status.FAILED
    reset_request.provider = provider
    reset_request.send_attempted_at = timezone.now()
    reset_request.send_error = send_error
    reset_request.provider_response = provider_response
    reset_request.save(
        update_fields=[
            "status",
            "provider",
            "provider_response",
            "send_error",
            "send_attempted_at",
            "updated_at",
        ]
    )


def send_password_reset_code_task(*, reset_request_id: int, phone_number: str, code: str):
    close_old_connections()
    try:
        reset_request = PasswordResetRequest.objects.filter(pk=reset_request_id).first()
        if not reset_request or reset_request.status != PasswordResetRequest.Status.PENDING:
            return

        try:
            sms_result = send_password_reset_code(phone_number=phone_number, code=code)
        except Exception as exc:
            logger.exception(
                "Password reset SMS task crashed",
                extra={
                    "phone_number_masked": _mask_phone_number(phone_number),
                    "request_id": reset_request_id,
                },
            )
            _mark_request_failed(
                reset_request,
                provider="unknown",
                send_error=str(exc).strip(),
                provider_response={
                    "ok": False,
                    "error": str(exc).strip(),
                    "error_type": exc.__class__.__name__,
                },
            )
            return

        reset_request.provider = sms_result.provider
        reset_request.send_attempted_at = timezone.now()
        reset_request.provider_message_id = sms_result.message_id
        reset_request.provider_response = sms_result.raw

        if not sms_result.ok:
            provider_error = _extract_provider_error(sms_result.raw) or "ارسال پیامک ناموفق بود."
            logger.warning(
                "Password reset SMS task returned unsuccessful result",
                extra={
                    "phone_number_masked": _mask_phone_number(phone_number),
                    "request_id": reset_request_id,
                    "provider": sms_result.provider,
                    "provider_message_id": sms_result.message_id,
                    "provider_error": provider_error,
                    "provider_response": sms_result.raw,
                },
            )
            reset_request.status = PasswordResetRequest.Status.FAILED
            reset_request.send_error = provider_error
            reset_request.save(
                update_fields=[
                    "status",
                    "provider",
                    "provider_message_id",
                    "provider_response",
                    "send_error",
                    "send_attempted_at",
                    "updated_at",
                ]
            )
            return

        reset_request.save(
            update_fields=[
                "provider",
                "provider_message_id",
                "provider_response",
                "send_error",
                "send_attempted_at",
                "updated_at",
            ]
        )
    finally:
        close_old_connections()


def _enqueue_thread(*, reset_request_id: int, phone_number: str, code: str):
    Thread(
        target=send_password_reset_code_task,
        kwargs={
            "reset_request_id": reset_request_id,
            "phone_number": phone_number,
            "code": code,
        },
        daemon=True,
    ).start()


def enqueue_password_reset_code(*, reset_request_id: int, phone_number: str, code: str) -> str:
    backend = (getattr(settings, "SMS_TASK_BACKEND", "") or "sync").strip().casefold()

    if backend == "sync":
        send_password_reset_code_task(reset_request_id=reset_request_id, phone_number=phone_number, code=code)
        return "sync"

    if backend == "thread":
        _enqueue_thread(reset_request_id=reset_request_id, phone_number=phone_number, code=code)
        return "thread"

    if backend == "django_q":
        try:
            from django_q.tasks import async_task

            async_task(
                "accounts.tasks.send_password_reset_code_task",
                reset_request_id=reset_request_id,
                phone_number=phone_number,
                code=code,
            )
            return "django_q"
        except Exception:
            logger.exception(
                "Failed to enqueue password reset SMS on django-q; falling back to thread",
                extra={"request_id": reset_request_id},
            )
            _enqueue_thread(reset_request_id=reset_request_id, phone_number=phone_number, code=code)
            return "thread"

    raise RuntimeError("SMS_TASK_BACKEND is not supported")

from __future__ import annotations

from datetime import timedelta

from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from config.upload_security import validate_uploaded_file

from .models import Ticket, TicketEvent, TicketMessage
from .permissions import can_manage_ticket, can_staff_ticket


_MESSAGE_RATE_WINDOW_SECONDS = 60 * 60


def _validate_subject(subject: str) -> str:
    normalized_subject = (subject or "").strip()
    if not normalized_subject:
        raise ValidationError("موضوع تیکت نمی‌تواند خالی باشد.")
    if len(normalized_subject) > 200:
        raise ValidationError("موضوع تیکت نمی‌تواند بیشتر از ۲۰۰ کاراکتر باشد.")
    return normalized_subject


def _validate_category(category: str) -> str:
    if category not in Ticket.Category.values:
        raise ValidationError("دسته‌بندی انتخاب‌شده معتبر نیست.")
    return category


def _validate_priority(priority: str) -> str:
    if priority not in Ticket.Priority.values:
        raise ValidationError("اولویت انتخاب‌شده معتبر نیست.")
    return priority


def _validate_attachment(attachment):
    if attachment:
        validate_uploaded_file(attachment, "ticket_attachment")
    return attachment


def _get_locked_ticket(ticket_id: int) -> Ticket:
    try:
        return (
            Ticket.objects.select_related("user")
            .select_for_update(of=("self", "user"))
            .get(pk=ticket_id)
        )
    except Ticket.DoesNotExist as exc:
        raise ValidationError("تیکت موردنظر پیدا نشد.") from exc


def _create_event(ticket: Ticket, *, actor, event_type: str, detail: str = "") -> TicketEvent:
    return TicketEvent.objects.create(
        ticket=ticket,
        actor=actor,
        event_type=event_type,
        detail=detail,
    )


def check_message_rate_limit(user) -> None:
    limit = int(getattr(settings, "TICKET_MAX_MESSAGES_PER_HOUR", 10) or 0)
    if limit <= 0:
        return

    cache_key = f"tickets:message-rate:{user.pk}"
    if cache.add(cache_key, 1, timeout=_MESSAGE_RATE_WINDOW_SECONDS):
        return

    try:
        current_count = cache.incr(cache_key)
    except ValueError:
        cache.set(cache_key, 1, timeout=_MESSAGE_RATE_WINDOW_SECONDS)
        current_count = 1

    if current_count > limit:
        raise ValidationError(f"شما در هر ساعت حداکثر {limit} پیام می‌توانید ارسال کنید.")


def create_ticket(user, subject: str, category: str, priority: str, body: str, attachment=None) -> Ticket:
    normalized_subject = _validate_subject(subject)
    normalized_category = _validate_category(category)
    normalized_priority = _validate_priority(priority)
    normalized_attachment = _validate_attachment(attachment)
    if not getattr(user, "is_staff", False) and normalized_priority == Ticket.Priority.HIGH:
        normalized_priority = Ticket.Priority.MEDIUM

    with transaction.atomic():
        user.__class__.objects.select_for_update().filter(pk=user.pk).exists()
        open_ticket_count = (
            Ticket.objects.select_for_update()
            .filter(user=user)
            .exclude(status=Ticket.Status.CLOSED)
            .count()
        )
        max_open_tickets = int(getattr(settings, "TICKET_MAX_OPEN_PER_USER", 5) or 5)
        if open_ticket_count >= max_open_tickets:
            raise ValidationError("سقف تیکت‌های باز همزمان شما تکمیل شده است.")

        check_message_rate_limit(user)

        message_time = timezone.now()
        ticket = Ticket.objects.create(
            user=user,
            subject=normalized_subject,
            category=normalized_category,
            priority=normalized_priority,
            status=Ticket.Status.OPEN,
            last_reply_at=message_time,
            last_reply_by_staff=False,
        )
        TicketMessage.objects.create(
            ticket=ticket,
            author=user,
            body=body,
            attachment=normalized_attachment,
            is_staff_reply=False,
            is_internal_note=False,
        )
        _create_event(
            ticket,
            actor=user,
            event_type=TicketEvent.EventType.CREATED,
            detail="تیکت ایجاد شد.",
        )
        return ticket


def add_user_reply(ticket_id: int, user, body: str, attachment=None) -> TicketMessage:
    normalized_attachment = _validate_attachment(attachment)
    with transaction.atomic():
        ticket = _get_locked_ticket(ticket_id)
        if ticket.user_id != user.id:
            raise ValidationError("فقط صاحب تیکت می‌تواند پاسخ ثبت کند.")
        if ticket.status == Ticket.Status.CLOSED:
            raise ValidationError("امکان پاسخ به تیکت بسته وجود ندارد.")

        check_message_rate_limit(user)

        message = TicketMessage.objects.create(
            ticket=ticket,
            author=user,
            body=body,
            attachment=normalized_attachment,
            is_staff_reply=False,
            is_internal_note=False,
        )
        ticket.status = Ticket.Status.WAITING_STAFF
        ticket.last_reply_at = message.created_at
        ticket.last_reply_by_staff = False
        ticket.save(update_fields=["status", "last_reply_at", "last_reply_by_staff", "updated_at"])
        return message


def add_staff_reply(ticket_id: int, staff_user, body: str, is_internal_note: bool = False, attachment=None) -> TicketMessage:
    if not can_staff_ticket(staff_user):
        raise ValidationError("شما دسترسی پاسخ به تیکت‌ها را ندارید.")
    normalized_attachment = _validate_attachment(attachment)

    with transaction.atomic():
        ticket = _get_locked_ticket(ticket_id)
        if ticket.status == Ticket.Status.CLOSED:
            raise ValidationError("امکان پاسخ به تیکت بسته وجود ندارد.")

        acts_as_staff_in_ticket = ticket.user_id != staff_user.id
        if not acts_as_staff_in_ticket:
            message = TicketMessage.objects.create(
                ticket=ticket,
                author=staff_user,
                body=body,
                attachment=normalized_attachment,
                is_staff_reply=False,
                is_internal_note=False,
            )
            ticket.status = Ticket.Status.WAITING_STAFF
            ticket.last_reply_at = message.created_at
            ticket.last_reply_by_staff = False
            ticket.save(update_fields=["status", "last_reply_at", "last_reply_by_staff", "updated_at"])
            return message

        message = TicketMessage.objects.create(
            ticket=ticket,
            author=staff_user,
            body=body,
            attachment=normalized_attachment,
            is_staff_reply=True,
            is_internal_note=bool(is_internal_note),
        )
        if message.is_internal_note:
            return message

        ticket.status = Ticket.Status.ANSWERED
        ticket.last_reply_at = message.created_at
        ticket.last_reply_by_staff = True
        ticket.user_has_unread = True
        update_fields = ["status", "last_reply_at", "last_reply_by_staff", "user_has_unread", "updated_at"]
        if ticket.assigned_to_id is None:
            ticket.assigned_to = staff_user
            update_fields.append("assigned_to")
        ticket.save(update_fields=update_fields)
        return message


def close_ticket(ticket_id: int, actor) -> Ticket:
    with transaction.atomic():
        ticket = _get_locked_ticket(ticket_id)
        if ticket.user_id != actor.id and not can_staff_ticket(actor):
            raise ValidationError("شما اجازه بستن این تیکت را ندارید.")
        if ticket.status == Ticket.Status.CLOSED:
            raise ValidationError("این تیکت قبلاً بسته شده است.")

        ticket.status = Ticket.Status.CLOSED
        ticket.closed_at = timezone.now()
        ticket.save(update_fields=["status", "closed_at", "updated_at"])
        _create_event(
            ticket,
            actor=actor,
            event_type=TicketEvent.EventType.CLOSED,
            detail="تیکت بسته شد.",
        )
        return ticket


def reopen_ticket(ticket_id: int, actor) -> Ticket:
    with transaction.atomic():
        ticket = _get_locked_ticket(ticket_id)
        if ticket.user_id != actor.id and not can_staff_ticket(actor):
            raise ValidationError("شما اجازه بازگشایی این تیکت را ندارید.")
        if ticket.status != Ticket.Status.CLOSED:
            raise ValidationError("فقط تیکت بسته را می‌توان بازگشایی کرد.")
        if ticket.closed_at is None:
            raise ValidationError("زمان بسته شدن تیکت مشخص نیست.")

        reopen_days = int(getattr(settings, "TICKET_REOPEN_DAYS", 7) or 7)
        reopen_deadline = ticket.closed_at + timedelta(days=reopen_days)
        if timezone.now() > reopen_deadline:
            raise ValidationError("مهلت بازگشایی این تیکت به پایان رسیده است.")

        ticket.status = (
            Ticket.Status.WAITING_STAFF
            if not ticket.last_reply_by_staff
            else Ticket.Status.OPEN
        )
        ticket.closed_at = None
        ticket.save(update_fields=["status", "closed_at", "updated_at"])
        _create_event(
            ticket,
            actor=actor,
            event_type=TicketEvent.EventType.REOPENED,
            detail="تیکت بازگشایی شد.",
        )
        return ticket


def assign_ticket(ticket_id: int, actor, assignee) -> Ticket:
    if not can_manage_ticket(actor):
        raise ValidationError("شما اجازه ارجاع تیکت را ندارید.")
    if not can_staff_ticket(assignee):
        raise ValidationError("کاربر انتخاب‌شده امکان دریافت تیکت را ندارد.")

    with transaction.atomic():
        ticket = _get_locked_ticket(ticket_id)
        if ticket.assigned_to_id == assignee.id:
            return ticket

        ticket.assigned_to = assignee
        ticket.save(update_fields=["assigned_to", "updated_at"])
        _create_event(
            ticket,
            actor=actor,
            event_type=TicketEvent.EventType.ASSIGNED,
            detail=f"تیکت به {assignee.get_full_name() or assignee.phone_number} ارجاع شد.",
        )
        return ticket


def change_priority(ticket_id: int, actor, priority: str) -> Ticket:
    if not can_manage_ticket(actor):
        raise ValidationError("شما اجازه تغییر اولویت تیکت را ندارید.")

    normalized_priority = _validate_priority(priority)
    with transaction.atomic():
        ticket = _get_locked_ticket(ticket_id)
        if ticket.priority == normalized_priority:
            return ticket

        ticket.priority = normalized_priority
        ticket.save(update_fields=["priority", "updated_at"])
        _create_event(
            ticket,
            actor=actor,
            event_type=TicketEvent.EventType.PRIORITY_CHANGED,
            detail=f"اولویت به {ticket.get_priority_display()} تغییر کرد.",
        )
        return ticket


def mark_read_by_user(ticket: Ticket) -> None:
    Ticket.objects.filter(pk=ticket.pk, user_id=ticket.user_id).update(user_has_unread=False)
    ticket.user_has_unread = False

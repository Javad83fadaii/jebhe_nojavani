from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from accounts.models import TimestampedModel
from config.upload_security import (
    UploadPolicyValidator,
    private_ticket_attachment_storage,
    private_ticket_attachment_upload_to,
)


class Ticket(TimestampedModel):
    class Category(models.TextChoices):
        GENERAL = "general", "عمومی"
        TECHNICAL = "technical", "مشکل فنی"
        ACCOUNT = "account", "حساب کاربری"
        LEARNING = "learning", "سیر مطالعاتی و آزمون"
        CHALLENGES = "challenges", "چالش‌ها"
        BAZAR_ORDER = "bazar_order", "جبهه بازار/سفارش"
        WALLET = "wallet", "کیف پول و سکه"
        FEEDBACK = "feedback", "پیشنهاد/انتقاد"

    class Priority(models.TextChoices):
        LOW = "low", "کم"
        MEDIUM = "medium", "متوسط"
        HIGH = "high", "بالا"

    class Status(models.TextChoices):
        OPEN = "open", "باز"
        WAITING_STAFF = "waiting_staff", "در انتظار پاسخ پشتیبان"
        ANSWERED = "answered", "پاسخ داده شده"
        CLOSED = "closed", "بسته شده"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="tickets",
        verbose_name="کاربر",
    )
    subject = models.CharField(max_length=200, verbose_name="موضوع")
    category = models.CharField(max_length=30, choices=Category.choices, verbose_name="دسته‌بندی")
    priority = models.CharField(
        max_length=10,
        choices=Priority.choices,
        default=Priority.MEDIUM,
        verbose_name="اولویت",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.OPEN,
        verbose_name="وضعیت",
    )
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="assigned_tickets",
        verbose_name="ارجاع به",
    )
    last_reply_at = models.DateTimeField(null=True, blank=True, verbose_name="زمان آخرین پاسخ")
    last_reply_by_staff = models.BooleanField(default=False, verbose_name="آخرین پاسخ توسط پشتیبان")
    closed_at = models.DateTimeField(null=True, blank=True, verbose_name="زمان بسته شدن")
    user_has_unread = models.BooleanField(default=False, verbose_name="کاربر پیام خوانده‌نشده دارد")

    class Meta:
        ordering = ("-updated_at",)
        indexes = [
            models.Index(fields=["status", "updated_at"]),
            models.Index(fields=["user", "status"]),
        ]
        permissions = [
            ("reply_ticket", "می‌تواند به تیکت‌ها پاسخ دهد"),
            ("manage_ticket", "می‌تواند تیکت را ارجاع/بسته/بازگشایی کند"),
        ]
        verbose_name = "تیکت"
        verbose_name_plural = "تیکت‌ها"

    def __str__(self) -> str:
        return self.subject


class TicketMessage(TimestampedModel):
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name="messages", verbose_name="تیکت")
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="ticket_messages",
        verbose_name="نویسنده",
    )
    body = models.TextField(max_length=5000, verbose_name="متن پیام")
    attachment = models.FileField(
        upload_to=private_ticket_attachment_upload_to,
        storage=private_ticket_attachment_storage,
        null=True,
        blank=True,
        verbose_name="پیوست",
        validators=[UploadPolicyValidator("ticket_attachment")],
    )
    is_staff_reply = models.BooleanField(default=False, verbose_name="پاسخ پشتیبان")
    is_internal_note = models.BooleanField(default=False, verbose_name="یادداشت داخلی")

    class Meta:
        ordering = ("created_at",)
        verbose_name = "پیام تیکت"
        verbose_name_plural = "پیام‌های تیکت"

    def __str__(self) -> str:
        return f"#{self.ticket_id} - {self.author}"

    def clean(self):
        super().clean()
        self.body = (self.body or "").strip()
        if not self.body:
            raise ValidationError({"body": "متن پیام نمی‌تواند خالی باشد."})
        if len(self.body) > 5000:
            raise ValidationError({"body": "متن پیام نمی‌تواند بیشتر از ۵۰۰۰ کاراکتر باشد."})

    def save(self, *args, **kwargs):
        self.body = (self.body or "").strip()
        if not self.body:
            raise ValidationError({"body": "متن پیام نمی‌تواند خالی باشد."})
        if len(self.body) > 5000:
            raise ValidationError({"body": "متن پیام نمی‌تواند بیشتر از ۵۰۰۰ کاراکتر باشد."})
        super().save(*args, **kwargs)


class TicketEvent(TimestampedModel):
    class EventType(models.TextChoices):
        CREATED = "created", "ایجاد شد"
        STATUS_CHANGED = "status_changed", "وضعیت تغییر کرد"
        ASSIGNED = "assigned", "ارجاع شد"
        PRIORITY_CHANGED = "priority_changed", "اولویت تغییر کرد"
        CLOSED = "closed", "بسته شد"
        REOPENED = "reopened", "بازگشایی شد"

    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name="events", verbose_name="تیکت")
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="ticket_events",
        verbose_name="انجام‌دهنده",
    )
    event_type = models.CharField(max_length=20, choices=EventType.choices, verbose_name="نوع رویداد")
    detail = models.CharField(max_length=255, blank=True, verbose_name="جزئیات")

    class Meta:
        ordering = ("created_at",)
        verbose_name = "رویداد تیکت"
        verbose_name_plural = "رویدادهای تیکت"

    def __str__(self) -> str:
        return f"{self.ticket_id} - {self.get_event_type_display()}"

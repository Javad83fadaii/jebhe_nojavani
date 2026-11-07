import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Ticket",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("subject", models.CharField(max_length=200, verbose_name="موضوع")),
                (
                    "category",
                    models.CharField(
                        choices=[
                            ("general", "عمومی"),
                            ("technical", "مشکل فنی"),
                            ("account", "حساب کاربری"),
                            ("learning", "سیر مطالعاتی و آزمون"),
                            ("challenges", "چالش‌ها"),
                            ("bazar_order", "جبهه بازار/سفارش"),
                            ("wallet", "کیف پول و سکه"),
                            ("feedback", "پیشنهاد/انتقاد"),
                        ],
                        max_length=30,
                        verbose_name="دسته‌بندی",
                    ),
                ),
                (
                    "priority",
                    models.CharField(
                        choices=[("low", "کم"), ("medium", "متوسط"), ("high", "بالا")],
                        default="medium",
                        max_length=10,
                        verbose_name="اولویت",
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("open", "باز"),
                            ("waiting_staff", "در انتظار پاسخ پشتیبان"),
                            ("answered", "پاسخ داده شده"),
                            ("closed", "بسته شده"),
                        ],
                        default="open",
                        max_length=20,
                        verbose_name="وضعیت",
                    ),
                ),
                ("last_reply_at", models.DateTimeField(blank=True, null=True, verbose_name="زمان آخرین پاسخ")),
                ("last_reply_by_staff", models.BooleanField(default=False, verbose_name="آخرین پاسخ توسط پشتیبان")),
                ("closed_at", models.DateTimeField(blank=True, null=True, verbose_name="زمان بسته شدن")),
                ("user_has_unread", models.BooleanField(default=False, verbose_name="کاربر پیام خوانده‌نشده دارد")),
                (
                    "assigned_to",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="assigned_tickets",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="ارجاع به",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="tickets",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="کاربر",
                    ),
                ),
            ],
            options={
                "verbose_name": "تیکت",
                "verbose_name_plural": "تیکت‌ها",
                "ordering": ("-updated_at",),
                "permissions": [
                    ("reply_ticket", "می‌تواند به تیکت‌ها پاسخ دهد"),
                    ("manage_ticket", "می‌تواند تیکت را ارجاع/بسته/بازگشایی کند"),
                ],
                "indexes": [
                    models.Index(fields=["status", "updated_at"], name="tickets_tic_status_79b2ef_idx"),
                    models.Index(fields=["user", "status"], name="tickets_tic_user_id_464453_idx"),
                ],
            },
        ),
        migrations.CreateModel(
            name="TicketEvent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "event_type",
                    models.CharField(
                        choices=[
                            ("created", "ایجاد شد"),
                            ("status_changed", "وضعیت تغییر کرد"),
                            ("assigned", "ارجاع شد"),
                            ("priority_changed", "اولویت تغییر کرد"),
                            ("closed", "بسته شد"),
                            ("reopened", "بازگشایی شد"),
                        ],
                        max_length=20,
                        verbose_name="نوع رویداد",
                    ),
                ),
                ("detail", models.CharField(blank=True, max_length=255, verbose_name="جزئیات")),
                (
                    "actor",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="ticket_events",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="انجام‌دهنده",
                    ),
                ),
                (
                    "ticket",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="events",
                        to="tickets.ticket",
                        verbose_name="تیکت",
                    ),
                ),
            ],
            options={
                "verbose_name": "رویداد تیکت",
                "verbose_name_plural": "رویدادهای تیکت",
                "ordering": ("created_at",),
            },
        ),
        migrations.CreateModel(
            name="TicketMessage",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("body", models.TextField(max_length=5000, verbose_name="متن پیام")),
                ("is_staff_reply", models.BooleanField(default=False, verbose_name="پاسخ پشتیبان")),
                ("is_internal_note", models.BooleanField(default=False, verbose_name="یادداشت داخلی")),
                (
                    "author",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="ticket_messages",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="نویسنده",
                    ),
                ),
                (
                    "ticket",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="messages",
                        to="tickets.ticket",
                        verbose_name="تیکت",
                    ),
                ),
            ],
            options={
                "verbose_name": "پیام تیکت",
                "verbose_name_plural": "پیام‌های تیکت",
                "ordering": ("created_at",),
            },
        ),
    ]

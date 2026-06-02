from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0005_user_grade_level_alter_user_birth_date"),
    ]

    operations = [
        migrations.CreateModel(
            name="PasswordResetRequest",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("phone_number", models.CharField(db_index=True, max_length=11)),
                ("code", models.CharField(max_length=6)),
                ("code_salt", models.CharField(max_length=32)),
                ("code_hash", models.CharField(db_index=True, max_length=64)),
                (
                    "status",
                    models.CharField(
                        choices=[("pending", "در انتظار"), ("used", "استفاده شده"), ("failed", "ناموفق")],
                        db_index=True,
                        default="pending",
                        max_length=10,
                    ),
                ),
                ("requested_at", models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
                ("expires_at", models.DateTimeField(db_index=True)),
                ("used_at", models.DateTimeField(blank=True, null=True)),
                ("provider", models.CharField(default="kavenegar", max_length=30)),
                ("provider_message_id", models.CharField(blank=True, max_length=64, null=True)),
                ("provider_response", models.JSONField(blank=True, null=True)),
                ("send_attempted_at", models.DateTimeField(blank=True, null=True)),
                ("ip_address", models.GenericIPAddressField(blank=True, null=True)),
                ("user_agent", models.TextField(blank=True, default="")),
                (
                    "user",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="password_reset_requests",
                        to="accounts.user",
                    ),
                ),
            ],
            options={
                "verbose_name": "درخواست بازیابی رمز",
                "verbose_name_plural": "درخواست‌های بازیابی رمز",
                "ordering": ("-requested_at", "-created_at"),
            },
        ),
        migrations.AddIndex(
            model_name="passwordresetrequest",
            index=models.Index(fields=["phone_number", "status", "expires_at"], name="prr_phone_status_exp_idx"),
        ),
    ]

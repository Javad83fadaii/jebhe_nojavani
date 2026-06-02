from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0006_password_reset_request"),
    ]

    operations = [
        migrations.AddField(
            model_name="passwordresetrequest",
            name="send_error",
            field=models.TextField(blank=True, default=""),
        ),
    ]

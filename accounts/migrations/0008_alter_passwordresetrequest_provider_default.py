from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0007_passwordresetrequest_send_error"),
    ]

    operations = [
        migrations.AlterField(
            model_name="passwordresetrequest",
            name="provider",
            field=models.CharField(default="smsir", max_length=30),
        ),
    ]

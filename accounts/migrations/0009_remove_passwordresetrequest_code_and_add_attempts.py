from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0008_alter_passwordresetrequest_provider_default"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="passwordresetrequest",
            name="code",
        ),
        migrations.AddField(
            model_name="passwordresetrequest",
            name="attempts",
            field=models.PositiveSmallIntegerField(default=0),
        ),
    ]

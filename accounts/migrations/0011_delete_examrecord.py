from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0010_alter_cointransaction_transaction_type"),
    ]

    operations = [
        migrations.DeleteModel(
            name="ExamRecord",
        ),
    ]

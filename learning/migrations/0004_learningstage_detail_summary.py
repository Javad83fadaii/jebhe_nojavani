from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("learning", "0003_learningstage_required_points"),
    ]

    operations = [
        migrations.AddField(
            model_name="learningstage",
            name="detail_summary",
            field=models.TextField(blank=True, verbose_name="متن باکس توضیحات مرحله"),
        ),
    ]

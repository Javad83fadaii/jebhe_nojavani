from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("challenges", "0003_alter_challengeparticipation_evidence_and_more"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="challenge",
            name="points_reward",
        ),
        migrations.RemoveField(
            model_name="challengeparticipation",
            name="points_received",
        ),
    ]

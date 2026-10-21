from django.db import migrations, models


def split_learning_stage_content_field(apps, schema_editor):
    LearningStage = apps.get_model("learning", "LearningStage")
    for stage in LearningStage.objects.exclude(content_link_or_file="").iterator():
        raw_value = (stage.content_link_or_file or "").strip()
        if not raw_value:
            continue

        update_fields = []
        if raw_value.startswith(("http://", "https://")):
            if not getattr(stage, "content_url", ""):
                stage.content_url = raw_value
                update_fields.append("content_url")
        else:
            normalized_name = raw_value
            if normalized_name.startswith("/media/"):
                normalized_name = normalized_name[len("/media/") :]
            normalized_name = normalized_name.lstrip("/")
            if normalized_name and not getattr(stage, "content_file", ""):
                stage.content_file = normalized_name
                update_fields.append("content_file")

        if update_fields:
            stage.save(update_fields=update_fields)


class Migration(migrations.Migration):

    dependencies = [
        ("learning", "0007_normalize_stage_points_to_100"),
    ]

    operations = [
        migrations.AddField(
            model_name="learningstage",
            name="content_url",
            field=models.URLField(blank=True, verbose_name="لینک محتوا"),
        ),
        migrations.AddField(
            model_name="learningstage",
            name="content_file",
            field=models.FileField(blank=True, null=True, upload_to="learning/stages/content/", verbose_name="فایل محتوا"),
        ),
        migrations.RunPython(split_learning_stage_content_field, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name="learningstage",
            name="content_link_or_file",
        ),
    ]

from django.db import migrations


GROUP_NAME = "پشتیبان تیکت"
PERMISSIONS = (
    ("reply_ticket", "می‌تواند به تیکت‌ها پاسخ دهد"),
    ("manage_ticket", "می‌تواند تیکت را ارجاع/بسته/بازگشایی کند"),
)


def create_support_group(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")
    ContentType = apps.get_model("contenttypes", "ContentType")

    ticket_content_type, _ = ContentType.objects.get_or_create(
        app_label="tickets",
        model="ticket",
    )

    permissions = []
    for codename, name in PERMISSIONS:
        permission, _ = Permission.objects.get_or_create(
            content_type=ticket_content_type,
            codename=codename,
            defaults={"name": name},
        )
        if permission.name != name:
            permission.name = name
            permission.save(update_fields=["name"])
        permissions.append(permission)

    group, _ = Group.objects.get_or_create(name=GROUP_NAME)
    group.permissions.add(*permissions)


def remove_support_group(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Group.objects.filter(name=GROUP_NAME).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("contenttypes", "0002_remove_content_type_name"),
        ("auth", "0012_alter_user_first_name_max_length"),
        ("tickets", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(create_support_group, remove_support_group),
    ]

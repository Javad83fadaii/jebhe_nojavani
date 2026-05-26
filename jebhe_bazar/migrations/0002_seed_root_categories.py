from django.db import migrations


ROOT_CATEGORIES = (
    ("رستوران", "رستوران"),
    ("مراکز تفریحی", "مراکز-تفریحی"),
    ("فروشگاه", "فروشگاه"),
)


def seed_root_categories(apps, schema_editor):
    Category = apps.get_model("jebhe_bazar", "Category")

    for name, slug in ROOT_CATEGORIES:
        category, created = Category.objects.get_or_create(
            name=name,
            defaults={
                "slug": slug,
                "is_active": True,
                "parent": None,
            },
        )

        if created:
            continue

        update_fields = []
        if not category.slug:
            category.slug = slug
            update_fields.append("slug")
        if not category.is_active:
            category.is_active = True
            update_fields.append("is_active")
        if category.parent_id is not None:
            category.parent = None
            update_fields.append("parent")

        if update_fields:
            category.save(update_fields=update_fields)


class Migration(migrations.Migration):

    dependencies = [
        ("jebhe_bazar", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_root_categories, migrations.RunPython.noop),
    ]

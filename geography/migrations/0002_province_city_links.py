from __future__ import annotations

from django.db import migrations, models


def forwards_create_links(apps, schema_editor):
    Province = apps.get_model("geography", "Province")
    City = apps.get_model("geography", "City")
    School = apps.get_model("geography", "School")
    Mosque = apps.get_model("geography", "Mosque")

    province_cache: dict[str, object] = {}
    city_cache: dict[tuple[int, str], object] = {}

    def normalize(value):
        return str(value or "").strip()

    def get_province(name: str):
        normalized = normalize(name)
        if not normalized:
            return None
        province = province_cache.get(normalized)
        if province is not None:
            return province
        province, _ = Province.objects.get_or_create(name=normalized)
        province_cache[normalized] = province
        return province

    def get_city(province, name: str):
        if province is None:
            return None
        normalized = normalize(name)
        if not normalized:
            return None
        key = (province.pk, normalized)
        city = city_cache.get(key)
        if city is not None:
            return city
        city, _ = City.objects.get_or_create(province=province, name=normalized)
        city_cache[key] = city
        return city

    schools_to_update = []
    for school in School.objects.all().only("id", "province", "city"):
        province = get_province(school.province)
        city = get_city(province, school.city)
        if province is not None:
            school.province_ref_id = province.pk
        if city is not None:
            school.city_ref_id = city.pk
        if province is not None or city is not None:
            schools_to_update.append(school)
    if schools_to_update:
        School.objects.bulk_update(schools_to_update, ["province_ref", "city_ref"])

    mosques_to_update = []
    for mosque in Mosque.objects.all().only("id", "province", "city"):
        province = get_province(mosque.province)
        city = get_city(province, mosque.city)
        if province is not None:
            mosque.province_ref_id = province.pk
        if city is not None:
            mosque.city_ref_id = city.pk
        if province is not None or city is not None:
            mosques_to_update.append(mosque)
    if mosques_to_update:
        Mosque.objects.bulk_update(mosques_to_update, ["province_ref", "city_ref"])


def backwards_remove_links(apps, schema_editor):
    School = apps.get_model("geography", "School")
    Mosque = apps.get_model("geography", "Mosque")
    School.objects.update(province_ref=None, city_ref=None)
    Mosque.objects.update(province_ref=None, city_ref=None)


class Migration(migrations.Migration):
    dependencies = [
        ("geography", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="Province",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=50, unique=True)),
            ],
            options={
                "ordering": ("name",),
            },
        ),
        migrations.CreateModel(
            name="City",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=50)),
                (
                    "province",
                    models.ForeignKey(on_delete=models.deletion.CASCADE, related_name="cities", to="geography.province"),
                ),
            ],
            options={
                "ordering": ("province__name", "name"),
            },
        ),
        migrations.AddConstraint(
            model_name="city",
            constraint=models.UniqueConstraint(fields=("province", "name"), name="unique_city_per_province"),
        ),
        migrations.AddField(
            model_name="school",
            name="province_ref",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=models.deletion.SET_NULL,
                related_name="schools",
                to="geography.province",
            ),
        ),
        migrations.AddField(
            model_name="school",
            name="city_ref",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=models.deletion.SET_NULL,
                related_name="schools",
                to="geography.city",
            ),
        ),
        migrations.AddField(
            model_name="mosque",
            name="province_ref",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=models.deletion.SET_NULL,
                related_name="mosques",
                to="geography.province",
            ),
        ),
        migrations.AddField(
            model_name="mosque",
            name="city_ref",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=models.deletion.SET_NULL,
                related_name="mosques",
                to="geography.city",
            ),
        ),
        migrations.RunPython(forwards_create_links, backwards_remove_links),
    ]


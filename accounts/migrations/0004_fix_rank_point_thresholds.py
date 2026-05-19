from django.db import migrations


def fix_rank_thresholds(apps, schema_editor):
    Rank = apps.get_model("accounts", "Rank")
    User = apps.get_model("accounts", "User")

    points_per_level = 1000
    total_levels = 13

    for rank in Rank.objects.all():
        rank.min_points = (rank.level - 1) * points_per_level
        if rank.level < total_levels:
            rank.max_points = (rank.level * points_per_level) - 1
        else:
            rank.max_points = None
        rank.save(update_fields=["min_points", "max_points", "updated_at"])

    ordered_ranks = list(Rank.objects.order_by("level"))
    users_to_update = []
    for user in User.objects.all().only("id", "total_points", "current_rank"):
        normalized_points = max(user.total_points or 0, 0)
        matched_rank = None
        for rank in ordered_ranks:
            if rank.min_points is not None and rank.min_points > normalized_points:
                break
            if rank.max_points is None or rank.max_points >= normalized_points:
                matched_rank = rank
        if getattr(user, "current_rank_id", None) != getattr(matched_rank, "id", None):
            user.current_rank_id = getattr(matched_rank, "id", None)
            users_to_update.append(user)

    if users_to_update:
        User.objects.bulk_update(users_to_update, ["current_rank"])


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0003_update_rank_point_thresholds"),
    ]

    operations = [
        migrations.RunPython(fix_rank_thresholds, migrations.RunPython.noop),
    ]

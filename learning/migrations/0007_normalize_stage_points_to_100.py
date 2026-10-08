from decimal import Decimal

from django.db import migrations
from django.db.models import Count
from django.utils import timezone


def normalize_stage_points(apps, schema_editor):
    LearningPath = apps.get_model("learning", "LearningPath")
    LearningStage = apps.get_model("learning", "LearningStage")
    UserLearningProgress = apps.get_model("learning", "UserLearningProgress")
    UserStageProgress = apps.get_model("learning", "UserStageProgress")
    User = apps.get_model("accounts", "User")
    Rank = apps.get_model("accounts", "Rank")

    stage_points = 100
    now = timezone.now()

    stages_to_update = []
    for stage in LearningStage.objects.all().only("id", "stage_number", "stage_points", "required_points"):
        required_points = max((stage.stage_number - 1) * stage_points, 0)
        if stage.stage_points != stage_points or stage.required_points != required_points:
            stage.stage_points = stage_points
            stage.required_points = required_points
            stages_to_update.append(stage)
    if stages_to_update:
        LearningStage.objects.bulk_update(stages_to_update, ["stage_points", "required_points"])

    stage_counts = {
        row["learning_path_id"]: row["total_stages"]
        for row in LearningStage.objects.filter(is_active=True)
        .values("learning_path_id")
        .annotate(total_stages=Count("id"))
    }
    paths_to_update = []
    for path in LearningPath.objects.all().only("id", "total_stages", "total_points"):
        total_stages = stage_counts.get(path.id, 0)
        total_points = total_stages * stage_points
        if path.total_stages != total_stages or path.total_points != total_points:
            path.total_stages = total_stages
            path.total_points = total_points
            paths_to_update.append(path)
    if paths_to_update:
        LearningPath.objects.bulk_update(paths_to_update, ["total_stages", "total_points"])

    stage_progress_to_update = []
    for stage_progress in UserStageProgress.objects.select_related("learning_stage").only(
        "id",
        "status",
        "score_earned",
        "learning_stage__stage_points",
    ):
        expected_score = stage_progress.learning_stage.stage_points if stage_progress.status == "passed" else 0
        if stage_progress.score_earned != expected_score:
            stage_progress.score_earned = expected_score
            stage_progress_to_update.append(stage_progress)
    if stage_progress_to_update:
        UserStageProgress.objects.bulk_update(stage_progress_to_update, ["score_earned"])

    progress_stage_statuses = {}
    for stage_progress in UserStageProgress.objects.select_related("learning_stage").order_by(
        "user_learning_progress_id",
        "learning_stage__stage_number",
    ):
        progress_stage_statuses.setdefault(stage_progress.user_learning_progress_id, []).append(stage_progress)

    path_stage_ids = {}
    for stage in LearningStage.objects.filter(is_active=True).only("id", "learning_path_id", "stage_number").order_by(
        "learning_path_id",
        "stage_number",
    ):
        path_stage_ids.setdefault(stage.learning_path_id, []).append(stage.id)

    progresses_to_update = []
    for progress in UserLearningProgress.objects.all().only(
        "id",
        "learning_path_id",
        "status",
        "completed_at",
        "completed_stages_count",
        "total_score",
        "progress_percentage",
        "current_stage_id",
    ):
        stage_progresses = progress_stage_statuses.get(progress.id, [])
        completed_count = sum(1 for item in stage_progresses if item.status == "passed")
        total_score = sum(item.score_earned for item in stage_progresses if item.status == "passed")
        total_stage_count = len(path_stage_ids.get(progress.learning_path_id, []))
        current_stage_id = next((item.learning_stage_id for item in stage_progresses if item.status != "passed"), None)

        if total_stage_count:
            progress_percentage = (Decimal(completed_count) / Decimal(total_stage_count)) * Decimal("100.00")
        else:
            progress_percentage = Decimal("0.00")

        status = progress.status
        completed_at = progress.completed_at
        if total_stage_count and completed_count == total_stage_count:
            status = "completed"
            completed_at = completed_at or now
            current_stage_id = None
        elif status == "completed":
            status = "in_progress"
            completed_at = None

        if (
            progress.completed_stages_count != completed_count
            or progress.total_score != total_score
            or progress.progress_percentage != progress_percentage
            or progress.current_stage_id != current_stage_id
            or progress.status != status
            or progress.completed_at != completed_at
        ):
            progress.completed_stages_count = completed_count
            progress.total_score = total_score
            progress.progress_percentage = progress_percentage
            progress.current_stage_id = current_stage_id
            progress.status = status
            progress.completed_at = completed_at
            progresses_to_update.append(progress)
    if progresses_to_update:
        UserLearningProgress.objects.bulk_update(
            progresses_to_update,
            [
                "completed_stages_count",
                "total_score",
                "progress_percentage",
                "current_stage_id",
                "status",
                "completed_at",
            ],
        )

    ordered_ranks = list(Rank.objects.order_by("level"))
    users_to_update = []
    for user in User.objects.all().only("id", "total_points", "current_rank"):
        total_points = UserStageProgress.objects.filter(user_id=user.id, status="passed").count() * stage_points
        matched_rank = None
        for rank in ordered_ranks:
            if rank.min_points is not None and rank.min_points > total_points:
                break
            if rank.max_points is None or rank.max_points >= total_points:
                matched_rank = rank
        if user.total_points != total_points or getattr(user, "current_rank_id", None) != getattr(matched_rank, "id", None):
            user.total_points = total_points
            user.current_rank_id = getattr(matched_rank, "id", None)
            users_to_update.append(user)
    if users_to_update:
        User.objects.bulk_update(users_to_update, ["total_points", "current_rank"])


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0008_alter_passwordresetrequest_provider_default"),
        ("learning", "0006_alter_stagequestionset_set_number"),
    ]

    operations = [
        migrations.RunPython(normalize_stage_points, migrations.RunPython.noop),
    ]

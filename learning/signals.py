from django.core.cache import cache
from django.db import transaction
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from learning.models import LearningPath, LearningStage, UserLearningProgress, UserStageProgress


_LEARNING_PATH_SYNC_LOCK_KEY = "learning:path-sync-lock:{learning_path_id}"
_LEARNING_PATH_SYNC_LOCK_TIMEOUT = 60


def _run_learning_path_sync(learning_path_id: int) -> None:
    lock_key = _LEARNING_PATH_SYNC_LOCK_KEY.format(learning_path_id=learning_path_id)
    try:
        learning_path = LearningPath.objects.filter(pk=learning_path_id).first()
        if learning_path is None:
            return

        progress_queryset = UserLearningProgress.objects.filter(
            learning_path_id=learning_path_id
        ).select_related("user", "learning_path")
        first_progress = progress_queryset.first()
        if first_progress is not None:
            first_progress.learning_path.sync_totals()
            for user_progress in progress_queryset:
                user_progress.sync_stage_progresses()
        else:
            learning_path.sync_totals()
    finally:
        cache.delete(lock_key)


def _queue_learning_path_sync(learning_path_id: int) -> None:
    lock_key = _LEARNING_PATH_SYNC_LOCK_KEY.format(learning_path_id=learning_path_id)
    if not cache.add(lock_key, True, timeout=_LEARNING_PATH_SYNC_LOCK_TIMEOUT):
        return

    transaction.on_commit(lambda: _run_learning_path_sync(learning_path_id))


@receiver(post_save, sender=UserLearningProgress)
def unlock_first_stage_on_enrollment(sender, instance, created, **kwargs):
    if created and instance.status == UserLearningProgress.ProgressStatus.IN_PROGRESS:
        with transaction.atomic():
            instance.learning_path.sync_totals()
            instance.sync_stage_progresses()


@receiver(post_save, sender=LearningStage)
def sync_learning_path_after_stage_save(sender, instance, **kwargs):
    _queue_learning_path_sync(instance.learning_path_id)


@receiver(post_delete, sender=LearningStage)
def sync_learning_path_after_stage_delete(sender, instance, **kwargs):
    _queue_learning_path_sync(instance.learning_path_id)


@receiver(post_save, sender=UserStageProgress)
def handle_stage_completion_and_next_stage_unlock(sender, instance, created, **kwargs):
    if not created and instance.status == UserStageProgress.StageStatus.PASSED:
        user_learning_progress = instance.user_learning_progress

        with transaction.atomic():
            user_learning_progress.sync_stage_progresses()

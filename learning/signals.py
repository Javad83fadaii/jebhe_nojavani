from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver
from django.db import transaction

from learning.models import LearningStage, UserLearningProgress, UserStageProgress


@receiver(post_save, sender=UserLearningProgress)
def unlock_first_stage_on_enrollment(sender, instance, created, **kwargs):
    if instance.status == UserLearningProgress.ProgressStatus.IN_PROGRESS:
        with transaction.atomic():
            instance.learning_path.sync_totals()
            instance.sync_stage_progresses()


@receiver(post_save, sender=LearningStage)
def sync_learning_path_after_stage_save(sender, instance, **kwargs):
    learning_path = instance.learning_path
    with transaction.atomic():
        learning_path.sync_totals()
        for user_progress in learning_path.user_progress.select_related("user", "learning_path"):
            user_progress.sync_stage_progresses()


@receiver(post_delete, sender=LearningStage)
def sync_learning_path_after_stage_delete(sender, instance, **kwargs):
    learning_path = instance.learning_path
    with transaction.atomic():
        learning_path.sync_totals()
        for user_progress in learning_path.user_progress.select_related("user", "learning_path"):
            user_progress.sync_stage_progresses()


@receiver(post_save, sender=UserStageProgress)
def handle_stage_completion_and_next_stage_unlock(sender, instance, created, **kwargs):
    if not created and instance.status == UserStageProgress.StageStatus.PASSED:
        user_learning_progress = instance.user_learning_progress

        with transaction.atomic():
            user_learning_progress.sync_stage_progresses()
            next_stage = user_learning_progress.get_next_stage()
            if next_stage:
                next_stage_progress, created_next_stage = UserStageProgress.objects.get_or_create(
                    user=instance.user,
                    learning_stage=next_stage,
                    user_learning_progress=user_learning_progress,
                    defaults={"status": UserStageProgress.StageStatus.UNLOCKED},
                )
                if not created_next_stage and next_stage_progress.status == UserStageProgress.StageStatus.LOCKED:
                    next_stage_progress.unlock()
            else:
                user_learning_progress.complete_path()

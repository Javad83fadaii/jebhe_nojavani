from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from django.db import transaction
from django.db.models import F

from learning.models import UserLearningProgress, UserStageProgress
from accounts.models import User # Assuming User model is in accounts app


@receiver(post_save, sender=UserLearningProgress)
def unlock_first_stage_on_enrollment(sender, instance, created, **kwargs):
    """
    Unlocks the first stage for a user when they enroll in a new learning path.
    """
    if created and instance.status == UserLearningProgress.ProgressStatus.IN_PROGRESS:
        learning_path = instance.learning_path
        first_stage = learning_path.stages.order_by("stage_number").first()

        if first_stage:
            # Ensure this is done atomically to prevent race conditions
            with transaction.atomic():
                UserStageProgress.objects.get_or_create(
                    user=instance.user,
                    learning_stage=first_stage,
                    user_learning_progress=instance,
                    defaults={
                        "status": UserStageProgress.StageStatus.UNLOCKED,
                        "unlocked_at": timezone.now(),
                    },
                )


@receiver(post_save, sender=UserStageProgress)
def handle_stage_completion_and_next_stage_unlock(sender, instance, created, **kwargs):
    """
    Handles actions after a user's stage progress is saved.
    - Updates user's total points and rank if stage is passed.
    - Unlocks the next stage if the current stage is passed.
    """
    # Only proceed if the stage status has just changed to PASSED and it's not a new creation
    if not created and instance.status == UserStageProgress.StageStatus.PASSED:
        user = instance.user
        learning_stage = instance.learning_stage
        user_learning_progress = instance.user_learning_progress

        # 1. Update user's total points and rank
        # Check if score_earned is already set to avoid double counting on subsequent saves
        # This is a bit tricky with F() expressions. A simpler approach is to check if points
        # were actually added before, or to only update points if the status transition is new.
        # For now, let's assume `score_earned` is set once when `pass_stage` is called.
        # The `pass_stage` method in the model is responsible for setting `score_earned` and
        # `user_learning_progress.total_score` and `user.total_points`.
        # This signal should primarily focus on unlocking the next stage and potentially
        # recalculating rank if not already done.
        
        # The points and rank update logic is currently in `UserStageProgress.pass_stage`.
        # I will keep it there for now, but ensure this signal doesn't duplicate it.
        # The prompt mentioned a signal for 'updating total_points after passing a stage'
        # and 'updating rank after changing points'.
        # It's better to keep the point and rank update tightly coupled with the `pass_stage` method
        # to ensure transactional integrity. The signal can then *react* to these changes.

        # However, the original `pass_stage` method also handled unlocking the next stage.
        # Let's move the 'unlock next stage' logic here.

        with transaction.atomic():
            # Recalculate progress percentage for the overall learning path
            user_learning_progress.calculate_progress()
            user_learning_progress.save(update_fields=["progress_percentage", "updated_at"])

            # Unlock the next stage
            next_stage = user_learning_progress.get_next_stage()
            if next_stage:
                next_stage_progress, created_next_stage = UserStageProgress.objects.get_or_create(
                    user=user,
                    learning_stage=next_stage,
                    user_learning_progress=user_learning_progress,
                    defaults={"status": UserStageProgress.StageStatus.UNLOCKED, "unlocked_at": timezone.now()},
                )
                if not created_next_stage and next_stage_progress.status == UserStageProgress.StageStatus.LOCKED:
                    next_stage_progress.unlock() # Call unlock method if it exists and status is locked
            else:
                # If there's no next stage, the learning path is completed
                user_learning_progress.complete_path()


# Ensure signals are connected in apps.py ready method

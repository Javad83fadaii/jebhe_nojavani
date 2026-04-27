from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Iterable

from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models, transaction
from django.db.models import F
from django.utils import timezone

if TYPE_CHECKING:
    from accounts.models import User, Rank


class TimestampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class LearningPath(TimestampedModel):
    class Difficulty(models.TextChoices):
        BEGINNER = "beginner", "مقدماتی"
        INTERMEDIATE = "intermediate", "متوسط"
        ADVANCED = "advanced", "پیشرفته"

    class PublishStatus(models.TextChoices):
        DRAFT = "draft", "پیش‌نویس"
        PUBLISHED = "published", "منتشر شده"
        ARCHIVED = "archived", "آرشیو شده"

    title = models.CharField(max_length=255, verbose_name="عنوان سیر مطالعاتی")
    description = models.TextField(blank=True, verbose_name="توضیحات")
    cover_image = models.ImageField(upload_to="learning_paths/covers/", null=True, blank=True, verbose_name="تصویر کاور")
    difficulty = models.CharField(
        max_length=20, choices=Difficulty.choices, default=Difficulty.BEGINNER, verbose_name="سطح دشواری"
    )
    publish_status = models.CharField(
        max_length=20, choices=PublishStatus.choices, default=PublishStatus.DRAFT, verbose_name="وضعیت انتشار"
    )
    display_order = models.PositiveSmallIntegerField(default=0, verbose_name="ترتیب نمایش")
    total_stages = models.PositiveSmallIntegerField(default=0, verbose_name="تعداد کل مراحل")
    total_points = models.PositiveIntegerField(default=0, verbose_name="کل امتیاز قابل کسب")

    class Meta:
        ordering = ("display_order", "title")
        verbose_name = "سیر مطالعاتی"
        verbose_name_plural = "سیرهای مطالعاتی"

    def __str__(self) -> str:
        return self.title


class LearningStage(TimestampedModel):
    class ContentType(models.TextChoices):
        PODCAST = "podcast", "پادکست"
        LECTURE = "lecture", "سخنرانی"
        BOOK = "book", "کتاب"
        VIDEO = "video", "فیلم"
        DOCUMENTARY = "documentary", "مستند"
        ARTICLE = "article", "مقاله" # Added for completeness

    learning_path = models.ForeignKey(LearningPath, on_delete=models.CASCADE, related_name="stages", verbose_name="سیر مطالعاتی")
    title = models.CharField(max_length=255, verbose_name="عنوان مرحله")
    stage_number = models.PositiveSmallIntegerField(verbose_name="شماره مرحله")
    content_type = models.CharField(max_length=20, choices=ContentType.choices, verbose_name="نوع محتوا")
    content_link_or_file = models.CharField(max_length=500, blank=True, verbose_name="لینک یا فایل محتوا")
    estimated_study_time = models.PositiveSmallIntegerField(default=0, verbose_name="مدت زمان تقریبی مطالعه (دقیقه)")
    description = models.TextField(blank=True, verbose_name="توضیحات مرحله")
    stage_points = models.PositiveIntegerField(default=100, verbose_name="امتیاز مرحله")
    min_passing_score = models.PositiveSmallIntegerField(
        default=14, validators=[MinValueValidator(0), MaxValueValidator(20)], verbose_name="حداقل نمره قبولی آزمون"
    )
    is_active = models.BooleanField(default=True, verbose_name="وضعیت فعال بودن")

    class Meta:
        ordering = ("learning_path", "stage_number")
        unique_together = ("learning_path", "stage_number")
        verbose_name = "مرحله سیر مطالعاتی"
        verbose_name_plural = "مراحل سیر مطالعاتی"

    def __str__(self) -> str:
        return f"{self.learning_path.title} - مرحله {self.stage_number}: {self.title}"


class StageQuestionSet(TimestampedModel):
    learning_stage = models.ForeignKey(LearningStage, on_delete=models.CASCADE, related_name="question_sets", verbose_name="مرحله سیر مطالعاتی")
    set_number = models.PositiveSmallIntegerField(verbose_name="شماره نمونه سوال")
    title = models.CharField(max_length=255, verbose_name="عنوان نمونه سوال")
    is_active = models.BooleanField(default=True, verbose_name="وضعیت فعال بودن")

    class Meta:
        ordering = ("learning_stage", "set_number")
        unique_together = ("learning_stage", "set_number")
        verbose_name = "مجموعه سوالات مرحله"
        verbose_name_plural = "مجموعه‌های سوالات مرحله"

    def __str__(self) -> str:
        return f"{self.learning_stage.title} - مجموعه سوال {self.set_number}: {self.title}"


class StageQuestion(TimestampedModel):
    class QuestionType(models.TextChoices):
        MULTIPLE_CHOICE = "multiple_choice", "چهارگزینه‌ای"
        TRUE_FALSE = "true_false", "صحیح-غلط"
        SHORT_ANSWER = "short_answer", "کوتاه پاسخ"

    class Difficulty(models.TextChoices):
        EASY = "easy", "آسان"
        MEDIUM = "medium", "متوسط"
        HARD = "hard", "سخت"

    question_set = models.ForeignKey(StageQuestionSet, on_delete=models.CASCADE, related_name="questions", verbose_name="مجموعه سوال")
    text = models.TextField(verbose_name="متن سوال")
    question_number = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(10)], verbose_name="شماره سوال"
    )
    question_type = models.CharField(max_length=20, choices=QuestionType.choices, verbose_name="نوع سوال")
    option1 = models.CharField(max_length=500, blank=True, verbose_name="گزینه 1")
    option2 = models.CharField(max_length=500, blank=True, verbose_name="گزینه 2")
    option3 = models.CharField(max_length=500, blank=True, verbose_name="گزینه 3")
    option4 = models.CharField(max_length=500, blank=True, verbose_name="گزینه 4")
    correct_answer = models.CharField(max_length=500, verbose_name="پاسخ صحیح")
    question_points = models.PositiveSmallIntegerField(default=2, verbose_name="نمره سوال")
    answer_explanation = models.TextField(blank=True, verbose_name="توضیحات پاسخ")
    difficulty = models.CharField(max_length=10, choices=Difficulty.choices, default=Difficulty.MEDIUM, verbose_name="سطح دشواری")

    class Meta:
        ordering = ("question_set", "question_number")
        unique_together = ("question_set", "question_number")
        verbose_name = "سوال آزمون"
        verbose_name_plural = "سوالات آزمون"

    def __str__(self) -> str:
        return f"{self.question_set.title} - سوال {self.question_number}"


class UserLearningProgress(TimestampedModel):
    class ProgressStatus(models.TextChoices):
        IN_PROGRESS = "in_progress", "در حال انجام"
        COMPLETED = "completed", "تکمیل شده"
        STOPPED = "stopped", "متوقف شده"

    user = models.ForeignKey("accounts.User", on_delete=models.CASCADE, related_name="learning_progresses", verbose_name="کاربر")
    learning_path = models.ForeignKey(LearningPath, on_delete=models.CASCADE, related_name="user_progress", verbose_name="سیر مطالعاتی")
    started_at = models.DateTimeField(auto_now_add=True, verbose_name="تاریخ شروع")
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name="تاریخ اتمام")
    status = models.CharField(max_length=20, choices=ProgressStatus.choices, default=ProgressStatus.IN_PROGRESS, verbose_name="وضعیت")
    current_stage = models.ForeignKey(
        LearningStage, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="آخرین مرحله فعال"
    )
    completed_stages_count = models.PositiveSmallIntegerField(default=0, verbose_name="تعداد مراحل تکمیل شده")
    total_score = models.PositiveIntegerField(default=0, verbose_name="کل امتیاز کسب شده")
    progress_percentage = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal("0.00"), verbose_name="درصد پیشرفت"
    )

    class Meta:
        ordering = ("-started_at",)
        unique_together = ("user", "learning_path")
        verbose_name = "پیشرفت کاربر در سیر مطالعاتی"
        verbose_name_plural = "پیشرفت کاربران در سیرهای مطالعاتی"

    def __str__(self) -> str:
        return f"{self.user.get_full_name()} - {self.learning_path.title} ({self.get_status_display()})"

    def get_current_stage(self) -> LearningStage | None:
        if self.current_stage:
            return self.current_stage
        # If no current stage is set, try to find the first one
        first_stage = self.learning_path.stages.order_by("stage_number").first()
        if first_stage:
            self.current_stage = first_stage
            self.save(update_fields=["current_stage", "updated_at"])
        return self.current_stage

    def get_next_stage(self) -> LearningStage | None:
        if not self.current_stage:
            return self.learning_path.stages.order_by("stage_number").first()

        next_stage_number = self.current_stage.stage_number + 1
        return self.learning_path.stages.filter(stage_number=next_stage_number).first()

    def calculate_progress(self):
        if not self.learning_path.total_stages:
            self.progress_percentage = Decimal("0.00")
        else:
            self.progress_percentage = (Decimal(self.completed_stages_count) / self.learning_path.total_stages) * Decimal("100.00")
        self.save(update_fields=["progress_percentage", "updated_at"])

    def complete_path(self):
        if self.completed_stages_count == self.learning_path.total_stages and self.status != self.ProgressStatus.COMPLETED:
            self.status = self.ProgressStatus.COMPLETED
            self.completed_at = timezone.now()
            self.save(update_fields=["status", "completed_at", "updated_at"])


class UserStageProgress(TimestampedModel):
    class StageStatus(models.TextChoices):
        LOCKED = "locked", "قفل شده"
        UNLOCKED = "unlocked", "باز شده"
        IN_STUDY = "in_study", "در حال مطالعه"
        READY_FOR_EXAM = "ready_for_exam", "آماده آزمون"
        PASSED = "passed", "قبول شده"
        FAILED_PREVIOUSLY = "failed_previously", "قبلاً مردود شده" # Added for clarity

    user = models.ForeignKey("accounts.User", on_delete=models.CASCADE, verbose_name="کاربر")
    learning_stage = models.ForeignKey(LearningStage, on_delete=models.CASCADE, related_name="user_progress", verbose_name="مرحله سیر مطالعاتی")
    user_learning_progress = models.ForeignKey(
        UserLearningProgress, on_delete=models.CASCADE, related_name="stage_progress", verbose_name="پیشرفت کلی کاربر"
    )
    status = models.CharField(max_length=20, choices=StageStatus.choices, default=StageStatus.LOCKED, verbose_name="وضعیت")
    unlocked_at = models.DateTimeField(null=True, blank=True, verbose_name="تاریخ باز شدن مرحله")
    started_studying_at = models.DateTimeField(null=True, blank=True, verbose_name="تاریخ شروع مطالعه")
    completed_studying_at = models.DateTimeField(null=True, blank=True, verbose_name="تاریخ اتمام مطالعه")
    exam_attempts = models.PositiveSmallIntegerField(default=0, verbose_name="تعداد دفعات تلاش برای آزمون")
    best_score = models.PositiveSmallIntegerField(default=0, verbose_name="بهترین نمره کسب شده")
    last_question_set_used = models.ForeignKey(
        StageQuestionSet, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="آخرین نمونه سوال استفاده شده"
    )
    score_earned = models.PositiveIntegerField(default=0, verbose_name="امتیاز کسب شده")
    passed_at = models.DateTimeField(null=True, blank=True, verbose_name="تاریخ قبولی")

    class Meta:
        ordering = ("user_learning_progress", "learning_stage__stage_number")
        unique_together = ("user_learning_progress", "learning_stage")
        verbose_name = "پیشرفت کاربر در مرحله"
        verbose_name_plural = "پیشرفت کاربران در مراحل"

    def __str__(self) -> str:
        return f"{self.user.get_full_name()} - {self.learning_stage.title} ({self.get_status_display()})"

    def unlock(self):
        if self.status == self.StageStatus.LOCKED:
            self.status = self.StageStatus.UNLOCKED
            self.unlocked_at = timezone.now()
            self.save(update_fields=["status", "unlocked_at", "updated_at"])

    def start_study(self):
        if self.status in [self.StageStatus.UNLOCKED, self.StageStatus.READY_FOR_EXAM, self.StageStatus.FAILED_PREVIOUSLY]:
            self.status = self.StageStatus.IN_STUDY
            if not self.started_studying_at:
                self.started_studying_at = timezone.now()
            self.save(update_fields=["status", "started_studying_at", "updated_at"])

    def complete_study(self):
        if self.status == self.StageStatus.IN_STUDY:
            self.status = self.StageStatus.READY_FOR_EXAM
            self.completed_studying_at = timezone.now()
            self.save(update_fields=["status", "completed_studying_at", "updated_at"])

    def can_take_exam(self) -> bool:
        return self.status == self.StageStatus.READY_FOR_EXAM or (
            self.status == self.StageStatus.UNLOCKED and self.learning_stage.stage_number == 1
        ) or self.status == self.StageStatus.FAILED_PREVIOUSLY

    def get_next_question_set(self) -> StageQuestionSet | None:
        """
        Determines the next question set based on the number of attempts.
        Attempt 1: Set 1
        Attempt 2: Set 2
        Attempt 3: Set 1
        And so on...
        If not enough question sets, repeat from the beginning.
        """
        question_sets = list(self.learning_stage.question_sets.filter(is_active=True).order_by("set_number"))
        if not question_sets:
            return None

        # Cycle through available question sets
        index = (self.exam_attempts % len(question_sets))
        return question_sets[index]

    def pass_stage(self, score: int):
        if score >= self.learning_stage.min_passing_score:
            self.status = self.StageStatus.PASSED
            self.passed_at = timezone.now()
            self.score_earned = self.learning_stage.stage_points

            self.user_learning_progress.completed_stages_count = F("completed_stages_count") + 1
            self.user_learning_progress.total_score = F("total_score") + self.learning_stage.stage_points
            self.user_learning_progress.save(update_fields=["completed_stages_count", "total_score", "updated_at"])

            self.user.total_points = F("total_points") + self.learning_stage.stage_points
            self.user.save(update_fields=["total_points", "updated_at"])
            self.user.calculate_rank() # Recalculate rank

            self.save(update_fields=["status", "passed_at", "score_earned", "updated_at"]) # To reflect current_stage update if any
        else:
            self.status = self.StageStatus.FAILED_PREVIOUSLY
            self.save(update_fields=["status", "updated_at"])


class UserStageExam(TimestampedModel):
    class ExamStatus(models.TextChoices):
        IN_PROGRESS = "in_progress", "در حال انجام"
        PASSED = "passed", "قبول"
        FAILED = "failed", "مردود"

    user = models.ForeignKey("accounts.User", on_delete=models.CASCADE, verbose_name="کاربر")
    user_stage_progress = models.ForeignKey(UserStageProgress, on_delete=models.CASCADE, related_name="exams", verbose_name="پیشرفت کاربر در مرحله")
    question_set = models.ForeignKey(StageQuestionSet, on_delete=models.CASCADE, verbose_name="نمونه سوال استفاده شده")
    attempt_number = models.PositiveSmallIntegerField(default=1, verbose_name="شماره تلاش")
    started_at = models.DateTimeField(auto_now_add=True, verbose_name="تاریخ شروع آزمون")
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name="تاریخ اتمام آزمون")
    score = models.PositiveSmallIntegerField(default=0, verbose_name="نمره کسب شده (از 20)")
    status = models.CharField(max_length=20, choices=ExamStatus.choices, default=ExamStatus.IN_PROGRESS, verbose_name="وضعیت")
    time_spent = models.PositiveIntegerField(default=0, verbose_name="زمان صرف شده (ثانیه)")

    class Meta:
        ordering = ("-started_at",)
        verbose_name = "آزمون کاربر در مرحله"
        verbose_name_plural = "آزمون‌های کاربران در مراحل"

    def __str__(self) -> str:
        return f"{self.user.get_full_name()} - {self.user_stage_progress.learning_stage.title} - تلاش {self.attempt_number}"

    def start_exam(self, question_set: StageQuestionSet):
        if self.status != self.ExamStatus.IN_PROGRESS:
            self.status = self.ExamStatus.IN_PROGRESS
            self.question_set = question_set
            self.started_at = timezone.now()
            self.save(update_fields=["status", "question_set", "started_at", "updated_at"])
            self.user_stage_progress.exam_attempts = F("exam_attempts") + 1
            self.user_stage_progress.last_question_set_used = question_set
            self.user_stage_progress.save(update_fields=["exam_attempts", "last_question_set_used", "updated_at"])
        # else: raise error or log that exam is already in progress

    def submit_answer(self, question: StageQuestion, user_answer: str):
        if self.status != self.ExamStatus.IN_PROGRESS:
            raise ValidationError("آزمون در حال انجام نیست.")

        is_correct = (user_answer == question.correct_answer)
        score_earned = question.question_points if is_correct else 0

        # Create UserExamAnswer
        UserExamAnswer.objects.create(
            exam=self,
            question=question,
            user_answer=user_answer,
            is_correct=is_correct,
            score_earned=score_earned,
            answered_at=timezone.now(),
        )
        return is_correct, score_earned

    def calculate_score(self) -> int:
        total_score = self.answers.aggregate(models.Sum("score_earned"))["score_earned__sum"] or 0
        self.score = total_score
        self.save(update_fields=["score", "updated_at"])
        return total_score

    def finish_exam(self):
        if self.status != self.ExamStatus.IN_PROGRESS:
            raise ValidationError("آزمون در حال انجام نیست.")

        self.completed_at = timezone.now()
        if self.started_at and self.completed_at:
            self.time_spent = int((self.completed_at - self.started_at).total_seconds())
        
        self.calculate_score() # Calculate final score

        min_passing_score = self.user_stage_progress.learning_stage.min_passing_score
        if self.score >= min_passing_score:
            self.status = self.ExamStatus.PASSED
            # Update best_score in UserStageProgress
            if self.score > self.user_stage_progress.best_score:
                self.user_stage_progress.best_score = self.score
                self.user_stage_progress.save(update_fields=["best_score", "updated_at"])
            
            self.user_stage_progress.pass_stage(self.score) # Pass the stage and update overall progress
        else:
            self.status = self.ExamStatus.FAILED
            # Update best_score if this attempt is better, even if failed
            if self.score > self.user_stage_progress.best_score:
                self.user_stage_progress.best_score = self.score
                self.user_stage_progress.save(update_fields=["best_score", "updated_at"])
            self.user_stage_progress.status = UserStageProgress.StageStatus.FAILED_PREVIOUSLY
            self.user_stage_progress.save(update_fields=["status", "updated_at"])

        self.save(update_fields=["completed_at", "time_spent", "status", "updated_at"])


class UserExamAnswer(TimestampedModel):
    exam = models.ForeignKey(UserStageExam, on_delete=models.CASCADE, related_name="answers", verbose_name="آزمون کاربر")
    question = models.ForeignKey(StageQuestion, on_delete=models.CASCADE, verbose_name="سوال")
    user_answer = models.CharField(max_length=500, blank=True, verbose_name="پاسخ کاربر")
    is_correct = models.BooleanField(default=False, verbose_name="صحیح بودن پاسخ")
    score_earned = models.PositiveSmallIntegerField(default=0, verbose_name="نمره کسب شده")
    answered_at = models.DateTimeField(auto_now_add=True, verbose_name="زمان پاسخ")

    class Meta:
        ordering = ("exam", "question__question_number")
        unique_together = ("exam", "question")
        verbose_name = "پاسخ کاربر به سوال"
        verbose_name_plural = "پاسخ‌های کاربران به سوالات"

    def __str__(self) -> str:
        return f"پاسخ {self.exam.user.get_full_name()} به {self.question.text[:50]}..."

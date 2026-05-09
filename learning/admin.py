from django.contrib import admin
from learning.models import (
    LearningPath,
    LearningStage,
    StageQuestionSet,
    StageQuestion,
    UserLearningProgress,
    UserStageProgress,
    UserStageExam,
    UserExamAnswer,
)


class StageQuestionInline(admin.TabularInline):
    model = StageQuestion
    extra = 0
    fields = ("question_number", "text", "question_type", "option1", "option2", "option3", "option4", "correct_answer", "question_points", "difficulty")
    readonly_fields = ("created_at", "updated_at")


class StageQuestionSetInline(admin.TabularInline):
    model = StageQuestionSet
    extra = 0
    fields = ("set_number", "title", "is_active")
    readonly_fields = ("created_at", "updated_at")
    show_change_link = True


class LearningStageInline(admin.TabularInline):
    model = LearningStage
    extra = 0
    fields = (
        "stage_number",
        "title",
        "content_type",
        "content_link_or_file",
        "estimated_study_time",
        "required_points",
        "stage_points",
        "min_passing_score",
        "is_active",
    )
    readonly_fields = ("created_at", "updated_at")
    show_change_link = True


class UserStageExamInline(admin.TabularInline):
    model = UserStageExam
    extra = 0
    fields = (
        "user",
        "question_set",
        "attempt_number",
        "score",
        "status",
        "time_spent",
        "started_at",
        "completed_at",
    )
    readonly_fields = (
        "user",
        "question_set",
        "attempt_number",
        "score",
        "status",
        "time_spent",
        "started_at",
        "completed_at",
        "created_at",
        "updated_at",
    )
    show_change_link = True


class UserExamAnswerInline(admin.TabularInline):
    model = UserExamAnswer
    extra = 0
    fields = (
        "question",
        "user_answer",
        "is_correct",
        "score_earned",
        "answered_at",
    )
    readonly_fields = fields + ("created_at", "updated_at")


@admin.register(LearningPath)
class LearningPathAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "rank",
        "difficulty",
        "total_stages",
        "publish_status",
        "created_at",
        "updated_at",
    )
    list_filter = ("rank", "difficulty", "publish_status")
    list_select_related = ("rank",)
    search_fields = ("title", "description")
    autocomplete_fields = ("rank",)
    inlines = [LearningStageInline]
    readonly_fields = ("total_stages", "total_points", "created_at", "updated_at")


@admin.register(LearningStage)
class LearningStageAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "learning_path",
        "stage_number",
        "content_type",
        "required_points",
        "stage_points",
        "is_active",
        "min_passing_score",
    )
    list_filter = ("content_type", "is_active", "learning_path")
    search_fields = ("title", "description", "learning_path__title")
    inlines = [StageQuestionSetInline]
    readonly_fields = ("created_at", "updated_at")


@admin.register(StageQuestionSet)
class StageQuestionSetAdmin(admin.ModelAdmin):
    list_display = ("title", "learning_stage", "set_number", "is_active")
    list_filter = ("is_active", "learning_stage")
    search_fields = (
        "title",
        "learning_stage__title",
        "learning_stage__learning_path__title",
    )
    inlines = [StageQuestionInline]
    readonly_fields = ("created_at", "updated_at")


@admin.register(StageQuestion)
class StageQuestionAdmin(admin.ModelAdmin):
    list_display = (
        "text",
        "question_set",
        "question_number",
        "question_type",
        "question_points",
        "difficulty",
    )
    list_filter = ("question_type", "difficulty", "question_set__learning_stage")
    search_fields = ("text", "correct_answer", "question_set__title")
    readonly_fields = ("created_at", "updated_at")


@admin.register(UserLearningProgress)
class UserLearningProgressAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "learning_path",
        "status",
        "progress_percentage",
        "started_at",
        "completed_at",
    )
    list_filter = ("status", "learning_path")
    search_fields = (
        "user__phone_number",
        "user__first_name",
        "user__last_name",
        "learning_path__title",
    )
    readonly_fields = (
        "progress_percentage",
        "total_score",
        "completed_stages_count",
        "created_at",
        "updated_at",
    )


@admin.register(UserStageProgress)
class UserStageProgressAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "learning_stage",
        "status",
        "exam_attempts",
        "best_score",
        "score_earned",
    )
    list_filter = ("status", "learning_stage", "user_learning_progress__learning_path")
    search_fields = (
        "user__phone_number",
        "user__first_name",
        "user__last_name",
        "learning_stage__title",
    )
    readonly_fields = (
        "exam_attempts",
        "best_score",
        "score_earned",
        "unlocked_at",
        "started_studying_at",
        "completed_studying_at",
        "passed_at",
        "created_at",
        "updated_at",
    )
    inlines = [UserStageExamInline]


@admin.register(UserStageExam)
class UserStageExamAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "user_stage_progress",
        "question_set",
        "attempt_number",
        "score",
        "status",
        "time_spent",
        "started_at",
        "completed_at",
    )
    list_filter = ("status", "user_stage_progress__learning_stage")
    search_fields = (
        "user__phone_number",
        "user__first_name",
        "user__last_name",
        "user_stage_progress__learning_stage__title",
    )
    readonly_fields = ("score", "time_spent", "created_at", "updated_at")
    inlines = [UserExamAnswerInline]


@admin.register(UserExamAnswer)
class UserExamAnswerAdmin(admin.ModelAdmin):
    list_display = ("exam", "question", "user_answer", "is_correct", "score_earned", "answered_at")
    list_filter = ("is_correct", "exam__status")
    search_fields = (
        "exam__user__phone_number",
        "exam__user__first_name",
        "exam__user__last_name",
        "question__text",
        "user_answer",
    )
    readonly_fields = ("score_earned", "answered_at", "created_at", "updated_at")

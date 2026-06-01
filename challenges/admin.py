from django.contrib import admin, messages
from django.core.exceptions import ValidationError
from .models import Challenge, ChallengeParticipation

class ChallengeParticipationInline(admin.TabularInline):
    model = ChallengeParticipation
    extra = 0
    readonly_fields = (
        "participated_at",
        "submitted_at",
        "reviewed_at",
        "status",
        "is_completed",
        "completed_at",
        "reward_awarded",
        "coins_received",
    )
    can_delete = False
    fields = (
        "user",
        "status",
        "participated_at",
        "submitted_at",
        "reviewed_at",
        "attended",
        "submission_text",
        "evidence",
        "reward_awarded",
        "coins_received",
    )

@admin.register(Challenge)
class ChallengeAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "submission_type",
        "coin_reward",
        "start_date",
        "end_date",
        "is_active",
        "is_currently_active",
    )
    list_filter = ("is_active", "submission_type", "start_date", "end_date")
    search_fields = ("title", "description")
    inlines = [ChallengeParticipationInline]
    date_hierarchy = 'start_date'
    
    def is_currently_active(self, obj):
        return obj.is_currently_active
    is_currently_active.boolean = True
    is_currently_active.short_description = "فعال در حال حاضر"

@admin.register(ChallengeParticipation)
class ChallengeParticipationAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "challenge",
        "challenge_submission_type",
        "status",
        "attended",
        "participated_at",
        "submitted_at",
        "reviewed_at",
        "reward_awarded",
        "coins_received",
    )
    list_filter = (
        "challenge",
        "status",
        "reward_awarded",
        "participated_at",
        "submitted_at",
        "reviewed_at",
        "challenge__submission_type",
    )
    search_fields = ("user__phone_number", "user__first_name", "user__last_name", "challenge__title")
    readonly_fields = ("participated_at", "submitted_at", "reviewed_at", "completed_at", "coins_received", "reward_awarded")
    actions = ("approve_and_award_selected", "reject_selected")

    @admin.display(description="نوع", ordering="challenge__submission_type")
    def challenge_submission_type(self, obj):
        return obj.challenge.get_submission_type_display()

    def save_model(self, request, obj, form, change):
        if not change:
            super().save_model(request, obj, form, change)
            return

        previous = ChallengeParticipation.objects.get(pk=obj.pk)
        requested_status = obj.status

        if requested_status == ChallengeParticipation.Status.APPROVED and previous.status != ChallengeParticipation.Status.APPROVED:
            obj.status = previous.status
            super().save_model(request, obj, form, change)
            try:
                obj.approve_and_award()
                messages.success(request, "ارسال کاربر تایید شد و سکه به حساب او اضافه شد.")
            except ValidationError as e:
                messages.error(request, str(e))
            return

        if requested_status == ChallengeParticipation.Status.REJECTED and previous.status != ChallengeParticipation.Status.REJECTED:
            obj.status = previous.status
            super().save_model(request, obj, form, change)
            try:
                obj.reject()
                messages.success(request, "ارسال کاربر رد شد.")
            except ValidationError as e:
                messages.error(request, str(e))
            return

        super().save_model(request, obj, form, change)

    @admin.action(description="تایید و پرداخت پاداش (بعد از پایان چالش)")
    def approve_and_award_selected(self, request, queryset):
        success_count = 0
        error_count = 0
        for participation in queryset.select_related("challenge", "user"):
            try:
                participation.approve_and_award()
                success_count += 1
            except ValidationError as e:
                error_count += 1
                messages.error(request, f"{participation}: {e}")
        if success_count:
            messages.success(request, f"{success_count} مورد تایید شد و پاداش پرداخت شد.")
        if error_count and not success_count:
            messages.warning(request, "هیچ موردی تایید نشد.")

    @admin.action(description="رد کردن ارسال")
    def reject_selected(self, request, queryset):
        success_count = 0
        error_count = 0
        for participation in queryset.select_related("challenge", "user"):
            try:
                participation.reject()
                success_count += 1
            except ValidationError as e:
                error_count += 1
                messages.error(request, f"{participation}: {e}")
        if success_count:
            messages.success(request, f"{success_count} مورد رد شد.")
        if error_count and not success_count:
            messages.warning(request, "هیچ موردی رد نشد.")

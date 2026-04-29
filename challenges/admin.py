from django.contrib import admin
from .models import Challenge, ChallengeParticipation

class ChallengeParticipationInline(admin.TabularInline):
    model = ChallengeParticipation
    extra = 0
    readonly_fields = ('participated_at', 'completed_at', 'coins_received')
    can_delete = False

@admin.register(Challenge)
class ChallengeAdmin(admin.ModelAdmin):
    list_display = ('title', 'coin_reward', 'start_date', 'end_date', 'is_active', 'is_currently_active')
    list_filter = ('is_active', 'start_date', 'end_date')
    search_fields = ('title', 'description')
    inlines = [ChallengeParticipationInline]
    date_hierarchy = 'start_date'
    
    def is_currently_active(self, obj):
        return obj.is_currently_active
    is_currently_active.boolean = True
    is_currently_active.short_description = "فعال در حال حاضر"

@admin.register(ChallengeParticipation)
class ChallengeParticipationAdmin(admin.ModelAdmin):
    list_display = ('user', 'challenge', 'participated_at', 'is_completed', 'completed_at', 'coins_received')
    list_filter = ('is_completed', 'participated_at', 'completed_at')
    search_fields = ('user__username', 'user__phone_number', 'challenge__title')
    readonly_fields = ('participated_at',)

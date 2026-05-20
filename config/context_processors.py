from django.db.models import Count, Sum


def user_points(request):
    """
    Context processor to make user points and related data available in all templates.
    """
    if request.user.is_authenticated:
        user = request.user
        total_points = int(getattr(user, "total_points", 0) or 0)
        current_rank = user.current_rank
        rank_name = current_rank.name if current_rank else None
        points_per_level = 100
        level_points = total_points % points_per_level
        level_number = (total_points // points_per_level) + 1
        level_progress_percent = int(round((level_points / points_per_level) * 100)) if points_per_level else 0
        return {
            "user_total_points": total_points,
            "user_current_rank": rank_name,
            "user_points_per_level": points_per_level,
            "user_level_points": level_points,
            "user_level_number": level_number,
            "user_level_progress_percent": level_progress_percent,
        }
    return {}

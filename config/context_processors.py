from django.db.models import Count, Sum


def user_points(request):
    """
    Context processor to make user points and related data available in all templates.
    """
    if request.user.is_authenticated:
        user = request.user
        total_points = user.total_points
        current_rank = user.current_rank
        rank_name = current_rank.name if current_rank else None
        return {
            "user_total_points": total_points,
            "user_current_rank": rank_name,
        }
    return {}


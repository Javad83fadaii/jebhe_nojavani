from django.db.models import Count, Sum

from accounts.models import Rank


def user_points(request):
    """
    Context processor to make user points and related data available in all templates.
    """
    if request.user.is_authenticated:
        user = request.user
        total_points = int(getattr(user, "total_points", 0) or 0)
        progress_metrics = Rank.get_progress_metrics(total_points)
        current_rank = progress_metrics["current_rank"]
        return {
            "user_total_points": total_points,
            "user_current_rank": current_rank.name if current_rank else None,
            "user_points_per_level": progress_metrics["points_per_level"],
            "user_level_points": progress_metrics["level_points"],
            "user_level_number": progress_metrics["level_number"],
            "user_level_progress_percent": progress_metrics["level_progress_percent"],
        }
    return {}


def seller_ui(request):
    is_seller = bool(getattr(request.user, "is_authenticated", False) and getattr(request.user, "is_seller", False))
    seller_site_view = bool(request.session.get("seller_site_view", False)) if is_seller else False
    return {
        "seller_site_view": seller_site_view,
        "seller_panel_mode": is_seller and not seller_site_view,
    }


def cart_ui(request):
    if not getattr(request.user, "is_authenticated", False):
        return {
            "cart_total_quantity": 0,
            "cart_has_items": False,
        }

    from jebhe_bazar.models import Cart

    cart_totals = Cart.objects.filter(user=request.user).aggregate(total_quantity=Sum("items__quantity"))
    total_quantity = int(cart_totals["total_quantity"] or 0)
    return {
        "cart_total_quantity": total_quantity,
        "cart_has_items": total_quantity > 0,
    }

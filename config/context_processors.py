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

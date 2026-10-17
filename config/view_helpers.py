from __future__ import annotations

from django.http import HttpRequest
from django.shortcuts import redirect


def redirect_seller_to_panel(request: HttpRequest):
    if request.user.is_authenticated and request.user.is_seller and not request.session.get("seller_site_view", False):
        return redirect("bazar:seller-dashboard")
    return None

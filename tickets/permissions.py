from __future__ import annotations

from functools import wraps

from django.contrib.auth.mixins import AccessMixin
from django.contrib.auth.models import Permission
from django.db.models import Q
from django.http import Http404
from django.shortcuts import redirect


SUPPORT_GROUP_NAME = "پشتیبان تیکت"


def can_staff_ticket(user) -> bool:
    if not getattr(user, "is_authenticated", False):
        return False
    if getattr(user, "is_superuser", False):
        return True
    return bool(getattr(user, "is_staff", False) and user.has_perm("tickets.reply_ticket"))


def can_manage_ticket(user) -> bool:
    if not getattr(user, "is_authenticated", False):
        return False
    if getattr(user, "is_superuser", False):
        return True
    return bool(getattr(user, "is_staff", False) and user.has_perm("tickets.manage_ticket"))


def staff_ticket_users_queryset(user_model):
    reply_permission = Permission.objects.get(codename="reply_ticket", content_type__app_label="tickets")
    return (
        user_model.objects.filter(
            Q(is_superuser=True)
            | Q(is_staff=True, user_permissions=reply_permission)
            | Q(is_staff=True, groups__permissions=reply_permission)
        )
        .select_related("current_rank")
        .distinct()
        .order_by("first_name", "last_name", "phone_number")
    )


def staff_ticket_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("index")
        if not can_staff_ticket(request.user):
            raise Http404("صفحه موردنظر پیدا نشد.")
        return view_func(request, *args, **kwargs)

    return _wrapped_view


class StaffTicketRequiredMixin(AccessMixin):
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("index")
        if not can_staff_ticket(request.user):
            raise Http404("صفحه موردنظر پیدا نشد.")
        return super().dispatch(request, *args, **kwargs)

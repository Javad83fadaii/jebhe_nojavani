from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Case, Count, IntegerField, Prefetch, Q, Value, When
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_http_methods, require_POST
from pathlib import Path

from config.views import _redirect_guest_to_index
from config.upload_security import private_ticket_attachment_storage

from .forms import (
    StaffTicketAssignForm,
    StaffTicketPriorityForm,
    StaffTicketReplyForm,
    TicketCreateForm,
    TicketReplyForm,
)
from .models import Ticket, TicketEvent, TicketMessage
from .permissions import can_manage_ticket, can_staff_ticket, staff_ticket_required
from .services import (
    add_staff_reply,
    add_user_reply,
    assign_ticket,
    change_priority,
    close_ticket,
    create_ticket,
    mark_read_by_user,
    reopen_ticket,
)


def _get_user_ticket_queryset(user):
    return Ticket.objects.filter(user=user).select_related("assigned_to")


def _get_user_ticket_detail_queryset(user):
    visible_messages = TicketMessage.objects.filter(is_internal_note=False).select_related("author")
    return _get_user_ticket_queryset(user).prefetch_related(
        Prefetch("messages", queryset=visible_messages, to_attr="visible_messages")
    )


def _get_staff_ticket_queryset():
    return Ticket.objects.select_related("user", "user__current_rank", "assigned_to")


def _get_staff_ticket_detail_queryset():
    all_messages = TicketMessage.objects.select_related("author", "author__current_rank")
    all_events = TicketEvent.objects.select_related("actor", "actor__current_rank")
    return _get_staff_ticket_queryset().prefetch_related(
        Prefetch("messages", queryset=all_messages, to_attr="staff_messages"),
        Prefetch("events", queryset=all_events, to_attr="staff_events"),
    )


def _redirect_guest(request):
    return _redirect_guest_to_index(request)


def _add_form_errors(request, form):
    for errors in form.errors.values():
        for error in errors:
            messages.error(request, error)


def _get_staff_status_counts():
    return Ticket.objects.aggregate(
        total_count=Count("id"),
        open_count=Count("id", filter=Q(status=Ticket.Status.OPEN)),
        waiting_staff_count=Count("id", filter=Q(status=Ticket.Status.WAITING_STAFF)),
        answered_count=Count("id", filter=Q(status=Ticket.Status.ANSWERED)),
        closed_count=Count("id", filter=Q(status=Ticket.Status.CLOSED)),
    )


def _apply_staff_dashboard_filters(queryset, request):
    status_filter = (request.GET.get("status") or "").strip()
    category_filter = (request.GET.get("category") or "").strip()
    priority_filter = (request.GET.get("priority") or "").strip()
    assignment_filter = (request.GET.get("assignment") or "").strip()
    search_query = (request.GET.get("q") or "").strip()

    if status_filter in Ticket.Status.values:
        queryset = queryset.filter(status=status_filter)
    else:
        status_filter = ""

    if category_filter in Ticket.Category.values:
        queryset = queryset.filter(category=category_filter)
    else:
        category_filter = ""

    if priority_filter in Ticket.Priority.values:
        queryset = queryset.filter(priority=priority_filter)
    else:
        priority_filter = ""

    if assignment_filter == "me":
        queryset = queryset.filter(assigned_to=request.user)
    elif assignment_filter == "unassigned":
        queryset = queryset.filter(assigned_to__isnull=True)
    else:
        assignment_filter = ""

    if search_query:
        queryset = queryset.filter(
            Q(subject__icontains=search_query)
            | Q(user__first_name__icontains=search_query)
            | Q(user__last_name__icontains=search_query)
            | Q(user__phone_number__icontains=search_query)
        )

    return queryset, {
        "status_filter": status_filter,
        "category_filter": category_filter,
        "priority_filter": priority_filter,
        "assignment_filter": assignment_filter,
        "search_query": search_query,
    }


def _get_staff_dashboard_ordering():
    return Case(
        When(status=Ticket.Status.WAITING_STAFF, then=Value(0)),
        When(status=Ticket.Status.OPEN, then=Value(1)),
        When(status=Ticket.Status.ANSWERED, then=Value(2)),
        When(status=Ticket.Status.CLOSED, then=Value(3)),
        default=Value(4),
        output_field=IntegerField(),
    )


@require_GET
def ticket_list(request):
    guest_redirect = _redirect_guest(request)
    if guest_redirect:
        return guest_redirect

    status_filter = (request.GET.get("status") or "").strip()
    status_filter_label = ""
    queryset = _get_user_ticket_queryset(request.user).order_by("-updated_at")
    if status_filter in Ticket.Status.values:
        queryset = queryset.filter(status=status_filter)
        status_filter_label = dict(Ticket.Status.choices).get(status_filter, "")
    else:
        status_filter = ""

    paginator = Paginator(queryset, 10)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(
        request,
        "tickets/list.html",
        {
            "page_name": "tickets",
            "page_title": "تیکت‌های من",
            "tickets": page_obj.object_list,
            "page_obj": page_obj,
            "is_paginated": page_obj.has_other_pages(),
            "status_filter": status_filter,
            "status_filter_label": status_filter_label,
            "status_choices": Ticket.Status.choices,
        },
    )


@require_http_methods(["GET", "POST"])
def ticket_create_view(request):
    guest_redirect = _redirect_guest(request)
    if guest_redirect:
        return guest_redirect

    form = TicketCreateForm(request.POST or None, request.FILES or None)
    if request.method == "POST":
        if not form.is_valid():
            _add_form_errors(request, form)
            return redirect("tickets:create")
        try:
            ticket = create_ticket(
                request.user,
                subject=form.cleaned_data["subject"],
                category=form.cleaned_data["category"],
                priority=form.cleaned_data["priority"],
                body=form.cleaned_data["body"],
                attachment=form.cleaned_data["attachment"],
            )
        except ValidationError as exc:
            messages.error(request, "; ".join(exc.messages))
            return redirect("tickets:create")
        messages.success(request, "تیکت شما با موفقیت ثبت شد.")
        return redirect("tickets:detail", pk=ticket.pk)

    return render(
        request,
        "tickets/create.html",
        {
            "page_name": "tickets",
            "page_title": "ایجاد تیکت جدید",
            "form": form,
        },
    )


@require_http_methods(["GET", "POST"])
def ticket_detail_view(request, pk):
    guest_redirect = _redirect_guest(request)
    if guest_redirect:
        return guest_redirect

    ticket = get_object_or_404(_get_user_ticket_detail_queryset(request.user), pk=pk)
    if request.method == "GET":
        mark_read_by_user(ticket)
        form = TicketReplyForm()
    else:
        form = TicketReplyForm(request.POST, request.FILES)
        if not form.is_valid():
            _add_form_errors(request, form)
            return redirect("tickets:detail", pk=ticket.pk)
        try:
            add_user_reply(
                ticket.id,
                request.user,
                form.cleaned_data["body"],
                attachment=form.cleaned_data["attachment"],
            )
        except ValidationError as exc:
            messages.error(request, "; ".join(exc.messages))
        else:
            messages.success(request, "پاسخ شما ثبت شد.")
        return redirect("tickets:detail", pk=ticket.pk)

    return render(
        request,
        "tickets/detail.html",
        {
            "page_name": "tickets",
            "page_title": ticket.subject,
            "ticket": ticket,
            "ticket_messages": getattr(ticket, "visible_messages", []),
            "reply_form": form,
            "can_close_ticket": ticket.status != Ticket.Status.CLOSED,
            "can_reopen_ticket": ticket.status == Ticket.Status.CLOSED,
        },
    )


@require_POST
def ticket_close_view(request, pk):
    guest_redirect = _redirect_guest(request)
    if guest_redirect:
        return guest_redirect

    ticket = get_object_or_404(_get_user_ticket_queryset(request.user), pk=pk)
    try:
        close_ticket(ticket.id, request.user)
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages))
    else:
        messages.success(request, "تیکت بسته شد.")
    return redirect("tickets:detail", pk=ticket.pk)


@require_POST
def ticket_reopen_view(request, pk):
    guest_redirect = _redirect_guest(request)
    if guest_redirect:
        return guest_redirect

    ticket = get_object_or_404(_get_user_ticket_queryset(request.user), pk=pk)
    try:
        reopen_ticket(ticket.id, request.user)
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages))
    else:
        messages.success(request, "تیکت دوباره باز شد.")
    return redirect("tickets:detail", pk=ticket.pk)


@staff_ticket_required
@require_GET
def staff_dashboard_view(request):
    counts = _get_staff_status_counts()
    queryset, filter_state = _apply_staff_dashboard_filters(_get_staff_ticket_queryset(), request)
    queryset = queryset.order_by(_get_staff_dashboard_ordering(), "created_at", "pk")

    paginator = Paginator(queryset, 20)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(
        request,
        "tickets/staff_dashboard.html",
        {
            "page_name": "tickets",
            "page_title": "پنل پشتیبانی تیکت",
            "page_obj": page_obj,
            "tickets": page_obj.object_list,
            "is_paginated": page_obj.has_other_pages(),
            "status_choices": Ticket.Status.choices,
            "category_choices": Ticket.Category.choices,
            "priority_choices": Ticket.Priority.choices,
            "status_counts": counts,
            **filter_state,
        },
    )


@staff_ticket_required
@require_http_methods(["GET", "POST"])
def staff_ticket_detail_view(request, pk):
    ticket = get_object_or_404(_get_staff_ticket_detail_queryset(), pk=pk)

    if request.method == "POST":
        action = (request.POST.get("action") or "").strip()

        if action == "reply":
            reply_form = StaffTicketReplyForm(request.POST, request.FILES)
            if not reply_form.is_valid():
                _add_form_errors(request, reply_form)
                return redirect("tickets:staff-detail", pk=ticket.pk)
            try:
                add_staff_reply(
                    ticket.id,
                    request.user,
                    reply_form.cleaned_data["body"],
                    is_internal_note=reply_form.cleaned_data["is_internal_note"],
                    attachment=reply_form.cleaned_data["attachment"],
                )
            except ValidationError as exc:
                messages.error(request, "; ".join(exc.messages))
            else:
                if reply_form.cleaned_data["is_internal_note"]:
                    messages.success(request, "یادداشت داخلی ثبت شد.")
                else:
                    messages.success(request, "پاسخ پشتیبان ثبت شد.")
            return redirect("tickets:staff-detail", pk=ticket.pk)

        if action == "close":
            try:
                close_ticket(ticket.id, request.user)
            except ValidationError as exc:
                messages.error(request, "; ".join(exc.messages))
            else:
                messages.success(request, "تیکت بسته شد.")
            return redirect("tickets:staff-detail", pk=ticket.pk)

        if action == "reopen":
            try:
                reopen_ticket(ticket.id, request.user)
            except ValidationError as exc:
                messages.error(request, "; ".join(exc.messages))
            else:
                messages.success(request, "تیکت بازگشایی شد.")
            return redirect("tickets:staff-detail", pk=ticket.pk)

        if action == "assign":
            assign_form = StaffTicketAssignForm(request.POST, actor=request.user)
            if not assign_form.is_valid():
                _add_form_errors(request, assign_form)
                return redirect("tickets:staff-detail", pk=ticket.pk)
            try:
                assign_ticket(ticket.id, request.user, assign_form.cleaned_data["assigned_to"])
            except ValidationError as exc:
                messages.error(request, "; ".join(exc.messages))
            else:
                messages.success(request, "تیکت با موفقیت ارجاع شد.")
            return redirect("tickets:staff-detail", pk=ticket.pk)

        if action == "priority":
            priority_form = StaffTicketPriorityForm(request.POST, actor=request.user)
            if not priority_form.is_valid():
                _add_form_errors(request, priority_form)
                return redirect("tickets:staff-detail", pk=ticket.pk)
            try:
                change_priority(ticket.id, request.user, priority_form.cleaned_data["priority"])
            except ValidationError as exc:
                messages.error(request, "; ".join(exc.messages))
            else:
                messages.success(request, "اولویت تیکت به‌روزرسانی شد.")
            return redirect("tickets:staff-detail", pk=ticket.pk)

        messages.error(request, "درخواست نامعتبر است.")
        return redirect("tickets:staff-detail", pk=ticket.pk)

    reply_form = StaffTicketReplyForm()
    assign_form = StaffTicketAssignForm(actor=request.user, initial={"assigned_to": ticket.assigned_to_id})
    priority_form = StaffTicketPriorityForm(actor=request.user, initial={"priority": ticket.priority})

    return render(
        request,
        "tickets/staff_detail.html",
        {
            "page_name": "tickets",
            "page_title": f"پنل پشتیبانی | {ticket.subject}",
            "ticket": ticket,
            "ticket_messages": getattr(ticket, "staff_messages", []),
            "ticket_events": getattr(ticket, "staff_events", []),
            "reply_form": reply_form,
            "assign_form": assign_form,
            "priority_form": priority_form,
            "can_manage_ticket": can_manage_ticket(request.user),
        },
    )


@require_GET
def ticket_attachment_download_view(request, message_pk):
    guest_redirect = _redirect_guest(request)
    if guest_redirect:
        return guest_redirect

    message = (
        TicketMessage.objects.select_related("ticket", "ticket__user")
        .filter(pk=message_pk)
        .first()
    )
    if message is None or not message.attachment:
        raise Http404("صفحه موردنظر پیدا نشد.")

    user = request.user
    can_access = can_staff_ticket(user) or (message.ticket.user_id == user.id and not message.is_internal_note)
    if not can_access:
        raise Http404("صفحه موردنظر پیدا نشد.")

    attachment_name = message.attachment.name
    if not private_ticket_attachment_storage.exists(attachment_name):
        raise Http404("صفحه موردنظر پیدا نشد.")

    response = FileResponse(
        private_ticket_attachment_storage.open(attachment_name, "rb"),
        as_attachment=True,
        filename=Path(attachment_name).name,
        content_type="application/octet-stream",
    )
    response["X-Content-Type-Options"] = "nosniff"
    response["Cache-Control"] = "private, no-store"
    return response

from django.urls import path

from . import views

app_name = "tickets"

urlpatterns = [
    path("", views.ticket_list, name="list"),
    path("new/", views.ticket_create_view, name="create"),
    path("attachment/<int:message_pk>/", views.ticket_attachment_download_view, name="attachment-download"),
    path("staff/", views.staff_dashboard_view, name="staff-dashboard"),
    path("staff/<int:pk>/", views.staff_ticket_detail_view, name="staff-detail"),
    path("<int:pk>/", views.ticket_detail_view, name="detail"),
    path("<int:pk>/close/", views.ticket_close_view, name="close"),
    path("<int:pk>/reopen/", views.ticket_reopen_view, name="reopen"),
]

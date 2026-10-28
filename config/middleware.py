from __future__ import annotations

from django.conf import settings
from django.http import HttpResponseForbidden


class AdminAccessMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        admin_path = f"/{str(getattr(settings, 'ADMIN_URL', 'admin/')).lstrip('/')}"
        if request.path.startswith(admin_path) and not settings.DEBUG:
            allowlist = set(getattr(settings, "ADMIN_IP_ALLOWLIST", ()) or ())
            if allowlist:
                forwarded = (request.META.get("HTTP_X_FORWARDED_FOR") or "").split(",")[0].strip()
                client_ip = forwarded or (request.META.get("REMOTE_ADDR") or "").strip()
                if client_ip not in allowlist:
                    return HttpResponseForbidden("Admin access is restricted.")

        return self.get_response(request)

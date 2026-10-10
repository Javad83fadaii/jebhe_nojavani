from __future__ import annotations

from rest_framework.throttling import ScopedRateThrottle


PERSIAN_DIGITS = "۰۱۲۳۴۵۶۷۸۹"
ARABIC_DIGITS = "٠١٢٣٤٥٦٧٨٩"
ENGLISH_DIGITS = "0123456789"
DIGIT_TRANSLATION_TABLE = str.maketrans(
    PERSIAN_DIGITS + ARABIC_DIGITS,
    ENGLISH_DIGITS + ENGLISH_DIGITS,
)


def _normalize_digits(value: str | None) -> str:
    return str(value or "").translate(DIGIT_TRANSLATION_TABLE).strip()


class IPScopedRateThrottle(ScopedRateThrottle):
    scope_attr = "ip_throttle_scope"

    def get_cache_key(self, request, view):
        if not self.scope:
            return None

        return self.cache_format % {
            "scope": self.scope,
            "ident": self.get_ident(request),
        }


class PhoneNumberScopedRateThrottle(ScopedRateThrottle):
    scope_attr = "phone_throttle_scope"

    def get_cache_key(self, request, view):
        if not self.scope:
            return None

        phone_number = _normalize_digits(request.data.get("phone_number"))
        if not phone_number:
            return None

        return self.cache_format % {
            "scope": self.scope,
            "ident": phone_number,
        }

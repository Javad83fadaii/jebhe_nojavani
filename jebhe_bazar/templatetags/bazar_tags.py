from datetime import date, datetime
from urllib.parse import urlencode

from django import template
from django.utils import timezone

register = template.Library()

_PERSIAN_DIGITS_TRANSLATION = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")


def _to_persian_digits(value: str) -> str:
    return value.translate(_PERSIAN_DIGITS_TRANSLATION)


def _gregorian_to_jalali(gy: int, gm: int, gd: int) -> tuple[int, int, int]:
    g_d_m = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]
    if gy > 1600:
        jy = 979
        gy -= 1600
    else:
        jy = 0
        gy -= 621

    gy2 = gy + 1 if gm > 2 else gy
    days = 365 * gy + (gy2 + 3) // 4 - (gy2 + 99) // 100 + (gy2 + 399) // 400 - 80 + gd + g_d_m[gm - 1]

    jy += 33 * (days // 12053)
    days %= 12053
    jy += 4 * (days // 1461)
    days %= 1461

    if days > 365:
        jy += (days - 1) // 365
        days = (days - 1) % 365

    if days < 186:
        jm = 1 + days // 31
        jd = 1 + days % 31
    else:
        jm = 7 + (days - 186) // 30
        jd = 1 + (days - 186) % 30

    return jy, jm, jd


def _normalize_datetime(value: datetime) -> datetime:
    if timezone.is_aware(value):
        return timezone.localtime(value)
    return value


@register.filter
def toman(value):
    try:
        return f"{int(value):,}".translate(_PERSIAN_DIGITS_TRANSLATION)
    except (TypeError, ValueError):
        return value


@register.filter
def multiply(value, arg):
    try:
        return int(value) * int(arg)
    except (TypeError, ValueError):
        return 0


@register.filter
def jalali_date(value):
    if value is None:
        return ""
    if isinstance(value, datetime):
        value = _normalize_datetime(value).date()
    if not isinstance(value, date):
        return value

    jy, jm, jd = _gregorian_to_jalali(value.year, value.month, value.day)
    return _to_persian_digits(f"{jy:04d}/{jm:02d}/{jd:02d}")


@register.filter
def jalali_datetime(value):
    if value is None:
        return ""
    if not isinstance(value, datetime):
        return jalali_date(value)

    value = _normalize_datetime(value)
    jy, jm, jd = _gregorian_to_jalali(value.year, value.month, value.day)
    return _to_persian_digits(f"{jy:04d}/{jm:02d}/{jd:02d} {value.hour:02d}:{value.minute:02d}")


@register.filter
def status_badge_class(status: str) -> str:
    mapping = {
        "paid": "is-success",
        "pending": "is-warning",
        "failed": "is-danger",
        "cancelled": "is-muted",
    }
    return mapping.get(status, "is-muted")


@register.simple_tag(takes_context=True)
def query_transform(context, **kwargs):
    request = context.get("request")
    if request is None:
        return ""

    query = request.GET.copy()
    for key, value in kwargs.items():
        if value in (None, ""):
            query.pop(key, None)
        else:
            query[key] = value
    return urlencode(query, doseq=True)

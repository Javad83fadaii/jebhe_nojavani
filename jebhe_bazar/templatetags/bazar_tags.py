from datetime import date, datetime
from urllib.parse import urlencode

from django import template
from config.jalali import format_jalali_date, format_jalali_datetime

register = template.Library()

_PERSIAN_DIGITS_TRANSLATION = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")
def _to_persian_digits(value: str) -> str:
    return value.translate(_PERSIAN_DIGITS_TRANSLATION)


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
def sub(value, arg):
    try:
        return int(value) - int(arg)
    except (TypeError, ValueError):
        return 0


@register.filter
def jalali_date(value):
    return format_jalali_date(value)


@register.filter
def jalali_datetime(value):
    return format_jalali_datetime(value)


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

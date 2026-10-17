from datetime import date, datetime

from django import template
from config.jalali import format_jalali_date, format_jalali_datetime

register = template.Library()

@register.filter
def get_item(dictionary, key):
    return dictionary.get(key)


@register.filter
def jalali_date(value):
    return format_jalali_date(value)


@register.filter
def jalali_datetime(value):
    return format_jalali_datetime(value)

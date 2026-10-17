from __future__ import annotations

from datetime import date, datetime

from django.utils import timezone

_PERSIAN_DIGITS_TRANSLATION = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")


def to_persian_digits(value: str) -> str:
    return value.translate(_PERSIAN_DIGITS_TRANSLATION)


def gregorian_to_jalali(gy: int, gm: int, gd: int) -> tuple[int, int, int]:
    g_d_m = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]

    if gy > 1600:
        jy = 979
        gy -= 1600
    else:
        jy = 0
        gy -= 621

    gy2 = gy + 1 if gm > 2 else gy
    days = (
        365 * gy
        + (gy2 + 3) // 4
        - (gy2 + 99) // 100
        + (gy2 + 399) // 400
        - 80
        + gd
        + g_d_m[gm - 1]
    )

    jy += 33 * (days // 12053)
    days %= 12053
    jy += 4 * (days // 1461)
    days %= 1461

    if days > 365:
        jy += (days - 1) // 365
        days = (days - 1) % 365

    if days < 186:
        jm = 1 + days // 31
        jd = 1 + (days % 31)
    else:
        jm = 7 + (days - 186) // 30
        jd = 1 + ((days - 186) % 30)

    return jy, jm, jd


def jalali_to_gregorian(jy: int, jm: int, jd: int) -> tuple[int, int, int]:
    jy += 1595
    days = -355668 + (365 * jy) + (jy // 33) * 8 + ((jy % 33) + 3) // 4 + jd
    if jm < 7:
        days += (jm - 1) * 31
    else:
        days += 186 + ((jm - 7) * 30)

    gy = 400 * (days // 146097)
    days %= 146097

    if days > 36524:
        gy += 100 * ((days - 1) // 36524)
        days = (days - 1) % 36524
        if days >= 365:
            days += 1

    gy += 4 * (days // 1461)
    days %= 1461

    if days > 365:
        gy += (days - 1) // 365
        days = (days - 1) % 365

    gd = days + 1
    february_days = 29 if ((gy % 4 == 0 and gy % 100 != 0) or (gy % 400 == 0)) else 28
    gregorian_month_days = [0, 31, february_days, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    gm = 1
    while gm <= 12 and gd > gregorian_month_days[gm]:
        gd -= gregorian_month_days[gm]
        gm += 1

    return gy, gm, gd


def normalize_datetime(value: datetime) -> datetime:
    if timezone.is_aware(value):
        return timezone.localtime(value)
    return value


def format_jalali_date(value: date | datetime | None):
    if value is None:
        return ""
    if isinstance(value, datetime):
        value = normalize_datetime(value).date()
    if not isinstance(value, date):
        return value

    jy, jm, jd = gregorian_to_jalali(value.year, value.month, value.day)
    return to_persian_digits(f"{jy:04d}/{jm:02d}/{jd:02d}")


def format_jalali_datetime(value: date | datetime | None):
    if value is None:
        return ""
    if not isinstance(value, datetime):
        return format_jalali_date(value)

    value = normalize_datetime(value)
    jy, jm, jd = gregorian_to_jalali(value.year, value.month, value.day)
    return to_persian_digits(f"{jy:04d}/{jm:02d}/{jd:02d} {value.hour:02d}:{value.minute:02d}")

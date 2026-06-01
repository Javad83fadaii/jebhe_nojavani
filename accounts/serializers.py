from __future__ import annotations

import re
from datetime import date

from django.contrib.auth import authenticate
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied

from accounts.models import Rank, Seller, User, validate_birth_date_range
from geography.models import Mosque, School


class RankSerializer(serializers.ModelSerializer):
    class Meta:
        model = Rank
        fields = ["id", "name", "level", "min_points", "max_points", "icon", "color"]


class SchoolSerializer(serializers.ModelSerializer):
    class Meta:
        model = School
        fields = ["id", "name", "address", "city", "province", "location", "phone", "principal_name"]


class MosqueSerializer(serializers.ModelSerializer):
    class Meta:
        model = Mosque
        fields = ["id", "name", "address", "city", "province", "location", "phone", "imam_name"]


class NestedWritablePKField(serializers.PrimaryKeyRelatedField):
    def __init__(self, *, serializer_class: type[serializers.ModelSerializer], **kwargs):
        self.serializer_class = serializer_class
        super().__init__(**kwargs)

    def use_pk_only_optimization(self):
        return False

    def to_representation(self, value):
        return self.serializer_class(value, context=self.context).data


def _validate_iranian_national_code(value: str) -> bool:
    if not re.fullmatch(r"\d{10}", value or ""):
        return False
    if len(set(value)) == 1:
        return False
    check_digit = int(value[9])
    s = sum(int(value[i]) * (10 - i) for i in range(9))
    remainder = s % 11
    if remainder < 2:
        return check_digit == remainder
    return check_digit == (11 - remainder)


_DIGIT_TRANSLATION_TABLE = str.maketrans(
    {
        "۰": "0",
        "۱": "1",
        "۲": "2",
        "۳": "3",
        "۴": "4",
        "۵": "5",
        "۶": "6",
        "۷": "7",
        "۸": "8",
        "۹": "9",
        "٠": "0",
        "١": "1",
        "٢": "2",
        "٣": "3",
        "٤": "4",
        "٥": "5",
        "٦": "6",
        "٧": "7",
        "٨": "8",
        "٩": "9",
    }
)


def _normalize_digits(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip().translate(_DIGIT_TRANSLATION_TABLE)
    return normalized


def _normalize_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def _jalali_to_gregorian(jy: int, jm: int, jd: int) -> tuple[int, int, int]:
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


class FlexibleBirthDateField(serializers.DateField):
    default_error_messages = {
        "invalid": "تاریخ تولد معتبر نیست.",
    }

    def to_internal_value(self, value):
        if value in (None, ""):
            return None

        if isinstance(value, date):
            return value

        normalized = _normalize_digits(str(value))
        normalized = re.sub(r"\s+", "", normalized or "").replace(".", "/")

        if not normalized:
            return None

        match = re.fullmatch(r"(?P<year>\d{4})[-/](?P<month>\d{1,2})[-/](?P<day>\d{1,2})", normalized)
        if not match:
            self.fail("invalid")

        year = int(match.group("year"))
        month = int(match.group("month"))
        day = int(match.group("day"))

        try:
            if 1300 <= year <= 1600:
                if month < 1 or month > 12:
                    self.fail("invalid")
                if day < 1 or day > 31:
                    self.fail("invalid")
                if month > 6 and day > 30:
                    self.fail("invalid")
                gregorian_year, gregorian_month, gregorian_day = _jalali_to_gregorian(year, month, day)
                return date(gregorian_year, gregorian_month, gregorian_day)

            return date(year, month, day)
        except ValueError:
            self.fail("invalid")


def _validate_allowed_birth_date(value: date | None):
    if value in (None, ""):
        return value

    try:
        validate_birth_date_range(value)
    except DjangoValidationError as exc:
        message = getattr(exc, "message", None) or (exc.messages[0] if getattr(exc, "messages", None) else None) or str(exc)
        raise serializers.ValidationError(message)
    except Exception:
        raise serializers.ValidationError("تاریخ تولد معتبر نیست.")
    return value


def _extract_place_geography(place) -> tuple[str | None, str | None]:
    if place is None:
        return None, None

    city_name = getattr(getattr(place, "city_ref", None), "name", None) or getattr(place, "city", None)
    province_name = getattr(getattr(place, "province_ref", None), "name", None) or getattr(
        getattr(getattr(place, "city_ref", None), "province", None), "name", None
    ) or getattr(place, "province", None)

    return _normalize_text(city_name), _normalize_text(province_name)


def _same_text(left: str | None, right: str | None) -> bool:
    return bool(left and right and left.casefold() == right.casefold())


def _sync_user_geography(attrs, instance: User | None = None):
    school_in_payload = "school" in attrs
    mosque_in_payload = "mosque" in attrs
    city_in_payload = "city" in attrs
    province_in_payload = "province" in attrs

    school = attrs["school"] if school_in_payload else getattr(instance, "school", None)
    mosque = attrs["mosque"] if mosque_in_payload else getattr(instance, "mosque", None)
    city = _normalize_text(attrs["city"]) if city_in_payload else None
    province = _normalize_text(attrs["province"]) if province_in_payload else None

    if not city_in_payload and not (school_in_payload or mosque_in_payload):
        city = _normalize_text(getattr(instance, "city", None))
    if not province_in_payload and not (school_in_payload or mosque_in_payload):
        province = _normalize_text(getattr(instance, "province", None))

    school_city, school_province = _extract_place_geography(school)
    mosque_city, mosque_province = _extract_place_geography(mosque)

    errors = {}

    if school and province and school_province and not _same_text(school_province, province):
        errors["school"] = "مدرسه انتخاب شده با استان وارد شده همخوانی ندارد."
    if school and city and school_city and not _same_text(school_city, city):
        errors["school"] = "مدرسه انتخاب شده با شهر وارد شده همخوانی ندارد."

    if mosque and province and mosque_province and not _same_text(mosque_province, province):
        errors["mosque"] = "مسجد انتخاب شده با استان وارد شده همخوانی ندارد."
    if mosque and city and mosque_city and not _same_text(mosque_city, city):
        errors["mosque"] = "مسجد انتخاب شده با شهر وارد شده همخوانی ندارد."

    if school and mosque:
        if school_province and mosque_province and not _same_text(school_province, mosque_province):
            errors["mosque"] = "مسجد و مدرسه انتخاب شده باید در یک استان باشند."
        if school_city and mosque_city and not _same_text(school_city, mosque_city):
            errors["mosque"] = "مسجد و مدرسه انتخاب شده باید در یک شهر باشند."

    if errors:
        raise serializers.ValidationError(errors)

    attrs["province"] = province or school_province or mosque_province
    attrs["city"] = city or school_city or mosque_city
    return attrs


class UserRegistrationSerializer(serializers.ModelSerializer):
    phone_number = serializers.CharField(
        max_length=11,
        error_messages={
            "blank": "شماره تلفن الزامی است.",
            "required": "شماره تلفن الزامی است.",
            "null": "شماره تلفن الزامی است.",
        },
    )
    first_name = serializers.CharField(
        max_length=50,
        error_messages={
            "blank": "نام الزامی است.",
            "required": "نام الزامی است.",
            "null": "نام الزامی است.",
        }
    )
    last_name = serializers.CharField(
        max_length=50,
        error_messages={
            "blank": "نام خانوادگی الزامی است.",
            "required": "نام خانوادگی الزامی است.",
            "null": "نام خانوادگی الزامی است.",
        }
    )
    password = serializers.CharField(
        write_only=True,
        min_length=8,
        error_messages={
            "blank": "رمز عبور الزامی است.",
            "required": "رمز عبور الزامی است.",
            "min_length": "رمز عبور باید حداقل ۸ کاراکتر داشته باشد.",
        },
    )
    national_code = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
        error_messages={
            "invalid": "کد ملی معتبر نیست.",
        },
    )
    birth_date = FlexibleBirthDateField(
        required=False,
        allow_null=True,
        error_messages={
            "invalid": "تاریخ تولد معتبر نیست.",
        },
    )
    gender = serializers.ChoiceField(
        choices=User.Gender.choices,
        required=False,
        allow_null=True,
        error_messages={"invalid_choice": "جنسیت انتخاب شده معتبر نیست."},
    )
    grade_level = serializers.ChoiceField(
        choices=User.GradeLevel.choices,
        required=False,
        allow_null=True,
        error_messages={"invalid_choice": "پایه تحصیلی انتخاب شده معتبر نیست."},
    )
    city = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    province = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    school = serializers.PrimaryKeyRelatedField(
        queryset=School.objects.all(),
        required=False,
        allow_null=True,
        error_messages={
            "does_not_exist": "مدرسه انتخاب شده معتبر نیست.",
            "incorrect_type": "مدرسه انتخاب شده معتبر نیست.",
        },
    )
    mosque = serializers.PrimaryKeyRelatedField(
        queryset=Mosque.objects.all(),
        required=False,
        allow_null=True,
        error_messages={
            "does_not_exist": "مسجد انتخاب شده معتبر نیست.",
            "incorrect_type": "مسجد انتخاب شده معتبر نیست.",
        },
    )

    class Meta:
        model = User
        fields = [
            "phone_number",
            "first_name",
            "last_name",
            "password",
            "national_code",
            "birth_date",
            "grade_level",
            "gender",
            "school",
            "mosque",
            "city",
            "province",
        ]

    def validate_phone_number(self, value: str) -> str:
        value = _normalize_digits(value) or ""
        if not re.fullmatch(r"09\d{9}", value):
            raise serializers.ValidationError("شماره تلفن باید ۱۱ رقمی و با ۰۹ شروع شود.")
        if User.objects.filter(phone_number=value).exists():
            raise serializers.ValidationError("این شماره تلفن قبلاً ثبت شده است.")
        return value

    def validate_national_code(self, value: str | None):
        value = _normalize_digits(value)
        if value in (None, ""):
            return None
        if not _validate_iranian_national_code(value):
            raise serializers.ValidationError("کد ملی معتبر نیست.")
        if User.objects.exclude(national_code__isnull=True).exclude(national_code="").filter(national_code=value).exists():
            raise serializers.ValidationError("این کد ملی قبلاً ثبت شده است.")
        return value

    def validate_birth_date(self, value: date | None):
        return _validate_allowed_birth_date(value)

    def validate_grade_level(self, value):
        if value in (None, ""):
            return User.GradeLevel.TWELFTH
        return value

    def validate(self, attrs):
        return _sync_user_geography(attrs)

    def create(self, validated_data):
        password = validated_data.pop("password")
        user = User.objects.create_user(password=password, **validated_data)
        return user


class UserLoginSerializer(serializers.Serializer):
    phone_number = serializers.CharField(
        error_messages={
            "blank": "شماره تلفن الزامی است.",
            "required": "شماره تلفن الزامی است.",
        }
    )
    password = serializers.CharField(
        error_messages={
            "blank": "رمز عبور الزامی است.",
            "required": "رمز عبور الزامی است.",
        }
    )

    def validate(self, attrs):
        phone_number = attrs.get("phone_number")
        password = attrs.get("password")

        user = authenticate(request=self.context.get("request"), username=phone_number, password=password)
        if not user:
            raise serializers.ValidationError("شماره تلفن یا رمز عبور اشتباه است.")
        seller_profile = getattr(user, "seller_profile", None)
        if seller_profile and not seller_profile.verified:
            raise PermissionDenied("حساب فروشنده شما هنوز تایید نشده است.")
        if seller_profile and not seller_profile.is_active:
            raise serializers.ValidationError("حساب فروشنده شما غیرفعال است.")
        if not user.is_active:
            raise serializers.ValidationError("حساب کاربری شما غیرفعال است.")
        attrs["user"] = user
        attrs["user_type"] = "seller" if seller_profile else "user"
        return attrs


class PasswordResetRequestSerializer(serializers.Serializer):
    phone_number = serializers.CharField(
        error_messages={
            "blank": "شماره تلفن الزامی است.",
            "required": "شماره تلفن الزامی است.",
        }
    )

    def validate_phone_number(self, value: str) -> str:
        normalized_value = _normalize_digits(value) or ""
        if not re.fullmatch(r"09\d{9}", normalized_value):
            raise serializers.ValidationError("شماره تلفن باید ۱۱ رقمی و با ۰۹ شروع شود.")
        if not User.objects.filter(phone_number=normalized_value).exists():
            raise serializers.ValidationError("کاربری با این شماره تلفن یافت نشد.")
        return normalized_value


class PasswordResetConfirmSerializer(serializers.Serializer):
    phone_number = serializers.CharField(
        error_messages={
            "blank": "شماره تلفن الزامی است.",
            "required": "شماره تلفن الزامی است.",
        }
    )
    code = serializers.CharField(
        min_length=4,
        max_length=6,
        error_messages={
            "blank": "کد تایید الزامی است.",
            "required": "کد تایید الزامی است.",
        },
    )
    new_password = serializers.CharField(
        write_only=True,
        min_length=8,
        error_messages={
            "blank": "رمز عبور جدید الزامی است.",
            "required": "رمز عبور جدید الزامی است.",
            "min_length": "رمز عبور جدید باید حداقل ۸ کاراکتر داشته باشد.",
        },
    )
    new_password_confirm = serializers.CharField(
        write_only=True,
        min_length=8,
        error_messages={
            "blank": "تکرار رمز عبور جدید الزامی است.",
            "required": "تکرار رمز عبور جدید الزامی است.",
            "min_length": "تکرار رمز عبور جدید باید حداقل ۸ کاراکتر داشته باشد.",
        },
    )

    def validate_phone_number(self, value: str) -> str:
        normalized_value = _normalize_digits(value) or ""
        if not re.fullmatch(r"09\d{9}", normalized_value):
            raise serializers.ValidationError("شماره تلفن باید ۱۱ رقمی و با ۰۹ شروع شود.")
        if not User.objects.filter(phone_number=normalized_value).exists():
            raise serializers.ValidationError("کاربری با این شماره تلفن یافت نشد.")
        return normalized_value

    def validate_code(self, value: str) -> str:
        normalized_value = _normalize_digits(value) or ""
        if not re.fullmatch(r"\d{4,6}", normalized_value):
            raise serializers.ValidationError("کد تایید باید فقط شامل اعداد باشد.")
        return normalized_value

    def validate(self, attrs):
        if attrs["new_password"] != attrs["new_password_confirm"]:
            raise serializers.ValidationError({"new_password_confirm": "رمز عبور و تکرار آن باید یکسان باشند."})
        return attrs


class UserProfileSerializer(serializers.ModelSerializer):
    total_points = serializers.IntegerField(read_only=True)
    challenge_coins = serializers.IntegerField(read_only=True)
    wallet_balance = serializers.DecimalField(max_digits=10, decimal_places=0, read_only=True)
    date_joined = serializers.DateTimeField(read_only=True)
    current_rank = RankSerializer(read_only=True)
    birth_date = FlexibleBirthDateField(required=False, allow_null=True)
    grade_level = serializers.ChoiceField(
        choices=User.GradeLevel.choices,
        required=False,
        allow_null=True,
        error_messages={"invalid_choice": "پایه تحصیلی انتخاب شده معتبر نیست."},
    )
    school = NestedWritablePKField(
        serializer_class=SchoolSerializer,
        queryset=School.objects.all(),
        required=False,
        allow_null=True,
    )
    mosque = NestedWritablePKField(
        serializer_class=MosqueSerializer,
        queryset=Mosque.objects.all(),
        required=False,
        allow_null=True,
    )

    class Meta:
        model = User
        fields = [
            "id",
            "phone_number",
            "first_name",
            "last_name",
            "national_code",
            "birth_date",
            "grade_level",
            "gender",
            "profile_image",
            "total_points",
            "challenge_coins",
            "wallet_balance",
            "current_rank",
            "school",
            "mosque",
            "city",
            "province",
            "date_joined",
        ]

    def validate(self, attrs):
        return _sync_user_geography(attrs, instance=self.instance)

    def validate_birth_date(self, value: date | None):
        return _validate_allowed_birth_date(value)

    def validate_grade_level(self, value):
        if value in (None, ""):
            return User.GradeLevel.TWELFTH
        return value


class SellerRegistrationSerializer(serializers.Serializer):
    password = serializers.CharField(
        write_only=True,
        min_length=8,
        error_messages={
            "blank": "رمز عبور الزامی است.",
            "required": "رمز عبور الزامی است.",
            "min_length": "رمز عبور باید حداقل ۸ کاراکتر داشته باشد.",
        },
    )
    phone_number = serializers.CharField(
        error_messages={
            "blank": "شماره تلفن الزامی است.",
            "required": "شماره تلفن الزامی است.",
        }
    )
    first_name = serializers.CharField(
        max_length=50,
        error_messages={
            "blank": "نام الزامی است.",
            "required": "نام الزامی است.",
        }
    )
    last_name = serializers.CharField(
        max_length=50,
        error_messages={
            "blank": "نام خانوادگی الزامی است.",
            "required": "نام خانوادگی الزامی است.",
        }
    )
    seller_shop_name = serializers.CharField(
        max_length=150,
        error_messages={
            "blank": "نام فروشگاه الزامی است.",
            "required": "نام فروشگاه الزامی است.",
        }
    )
    seller_shop_address = serializers.CharField(
        error_messages={
            "blank": "آدرس فروشگاه الزامی است.",
            "required": "آدرس فروشگاه الزامی است.",
        }
    )
    seller_shop_phone_number = serializers.CharField(required=False, allow_blank=True, max_length=20)
    seller_shop_description = serializers.CharField(required=False, allow_blank=True)
    city = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    province = serializers.CharField(required=False, allow_blank=True, allow_null=True)

    def validate_phone_number(self, value: str) -> str:
        if not re.fullmatch(r"09\d{9}", value or ""):
            raise serializers.ValidationError("شماره تلفن باید ۱۱ رقمی و با ۰۹ شروع شود.")
        return value

    def create(self, validated_data):
        password = validated_data.pop("password")
        shop_name = validated_data.pop("seller_shop_name")
        shop_address = validated_data.pop("seller_shop_address")
        shop_phone_number = validated_data.pop("seller_shop_phone_number", "")
        shop_description = validated_data.pop("seller_shop_description", "")

        with transaction.atomic():
            user = User.objects.create_user(password=password, **validated_data)
            Seller.objects.create(
                user=user,
                shop_name=shop_name,
                shop_address=shop_address,
                shop_phone_number=shop_phone_number,
                shop_description=shop_description,
                verified=False,
            )
        return user


class SellerLoginSerializer(serializers.Serializer):
    phone_number = serializers.CharField(
        error_messages={
            "blank": "شماره تلفن الزامی است.",
            "required": "شماره تلفن الزامی است.",
        }
    )
    password = serializers.CharField(
        error_messages={
            "blank": "رمز عبور الزامی است.",
            "required": "رمز عبور الزامی است.",
        }
    )

    def validate(self, attrs):
        phone_number = attrs.get("phone_number")
        password = attrs.get("password")

        user = authenticate(request=self.context.get("request"), username=phone_number, password=password)
        if not user:
            raise serializers.ValidationError("شماره تلفن یا رمز عبور اشتباه است.")
        seller_profile = getattr(user, "seller_profile", None)
        if not seller_profile:
            raise serializers.ValidationError("این حساب کاربری فروشنده نیست.")
        if not seller_profile.verified:
            raise PermissionDenied("حساب فروشنده شما هنوز تایید نشده است.")
        if not user.is_active:
            raise serializers.ValidationError("حساب کاربری شما غیرفعال است.")
        attrs["user"] = user
        return attrs


class SellerProfileSerializer(serializers.ModelSerializer):
    phone_number = serializers.CharField(source="user.phone_number", read_only=True)
    first_name = serializers.CharField(source="user.first_name", read_only=True)
    last_name = serializers.CharField(source="user.last_name", read_only=True)
    city = serializers.CharField(source="user.city", read_only=True)
    province = serializers.CharField(source="user.province", read_only=True)
    date_joined = serializers.DateTimeField(source="user.date_joined", read_only=True)
    seller_shop_name = serializers.CharField(source="shop_name")
    seller_shop_address = serializers.CharField(source="shop_address")
    seller_shop_phone_number = serializers.CharField(source="shop_phone_number", required=False, allow_blank=True)
    seller_shop_description = serializers.CharField(source="shop_description", required=False, allow_blank=True)
    seller_verified = serializers.BooleanField(source="verified", read_only=True)
    rating = serializers.DecimalField(max_digits=3, decimal_places=2, read_only=True)
    total_revenue = serializers.DecimalField(max_digits=14, decimal_places=0, read_only=True)

    class Meta:
        model = Seller
        fields = [
            "id",
            "phone_number",
            "first_name",
            "last_name",
            "seller_shop_name",
            "seller_shop_address",
            "seller_shop_phone_number",
            "seller_shop_description",
            "seller_verified",
            "logo",
            "rating",
            "sales_count",
            "total_revenue",
            "platform_commission_percent",
            "is_active",
            "city",
            "province",
            "date_joined",
            "registered_at",
            "verified_at",
        ]

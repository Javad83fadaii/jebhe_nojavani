from __future__ import annotations

import re

from django.contrib.auth import authenticate
from django.db import transaction
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied

from accounts.models import Rank, Seller, User
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
            "min_length": "رمز عبور باید حداقل ۸ کاراکتر باشد.",
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
    birth_date = serializers.DateField(
        required=False,
        allow_null=True,
        input_formats=["%Y-%m-%d"],
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

    def validate(self, attrs):
        return _sync_user_geography(attrs)

    def create(self, validated_data):
        password = validated_data.pop("password")
        user = User.objects.create_user(password=password, **validated_data)
        return user


class UserLoginSerializer(serializers.Serializer):
    phone_number = serializers.CharField()
    password = serializers.CharField()

    def validate(self, attrs):
        phone_number = attrs.get("phone_number")
        password = attrs.get("password")

        user = authenticate(request=self.context.get("request"), username=phone_number, password=password)
        if not user:
            raise serializers.ValidationError("شماره تلفن یا رمز عبور اشتباه است.")
        if hasattr(user, "seller_profile"):
            raise serializers.ValidationError("این حساب کاربری فروشنده است.")
        if not user.is_active:
            raise serializers.ValidationError("حساب کاربری غیرفعال است.")
        attrs["user"] = user
        return attrs


class UserProfileSerializer(serializers.ModelSerializer):
    total_points = serializers.IntegerField(read_only=True)
    challenge_coins = serializers.IntegerField(read_only=True)
    wallet_balance = serializers.DecimalField(max_digits=10, decimal_places=0, read_only=True)
    date_joined = serializers.DateTimeField(read_only=True)
    current_rank = RankSerializer(read_only=True)
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


class SellerRegistrationSerializer(serializers.Serializer):
    password = serializers.CharField(write_only=True, min_length=8)
    phone_number = serializers.CharField()
    first_name = serializers.CharField(max_length=50)
    last_name = serializers.CharField(max_length=50)
    seller_shop_name = serializers.CharField(max_length=150)
    seller_shop_address = serializers.CharField()
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
    phone_number = serializers.CharField()
    password = serializers.CharField()

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
            raise PermissionDenied("حساب شما هنوز تایید نشده است")
        if not user.is_active:
            raise serializers.ValidationError("حساب کاربری غیرفعال است.")
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

from django import forms
from django.contrib import admin, messages
from django.contrib.auth.forms import ReadOnlyPasswordHashField
from django.db.models import Q

from accounts.models import CoinToWalletTransfer, CoinTransaction, ExamRecord, Rank, Seller, User
from geography.models import City, Mosque, Province, School


class UserCreationForm(forms.ModelForm):
    password1 = forms.CharField(label="Password", widget=forms.PasswordInput)
    password2 = forms.CharField(label="Password confirmation", widget=forms.PasswordInput)

    class Meta:
        model = User
        fields = ("phone_number", "first_name", "last_name")

    def clean_password2(self):
        password1 = self.cleaned_data.get("password1")
        password2 = self.cleaned_data.get("password2")
        if password1 and password2 and password1 != password2:
            raise forms.ValidationError("Passwords don't match")
        return password2

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password1"])
        if commit:
            user.save()
        return user


class UserChangeForm(forms.ModelForm):
    password = ReadOnlyPasswordHashField()

    class Meta:
        model = User
        fields = "__all__"


class UserAdminForm(UserChangeForm):
    province_ref = forms.ModelChoiceField(label="استان", queryset=Province.objects.none(), required=False)
    city_ref = forms.ModelChoiceField(label="شهر", queryset=City.objects.none(), required=False)

    class Media:
        js = ("js/geography_admin_chained.js",)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["province_ref"].queryset = Province.objects.all().order_by("name")
        self.fields["city_ref"].queryset = City.objects.none()
        self.fields["school"].queryset = School.objects.none()
        self.fields["mosque"].queryset = Mosque.objects.none()

        province = self._get_selected_province()
        city = self._get_selected_city(province)

        if province is not None:
            self.fields["province_ref"].initial = province
            self.fields["city_ref"].queryset = City.objects.filter(province=province).order_by("name")
        if city is not None:
            self.fields["city_ref"].initial = city

        self._set_place_querysets(province=province, city=city)

    def _get_selected_province(self):
        if "province_ref" in self.data:
            try:
                return Province.objects.filter(pk=int(self.data.get("province_ref") or 0)).first()
            except (TypeError, ValueError):
                return None

        instance = self.instance
        if not instance or not instance.pk:
            return None

        if instance.school_id:
            school_province = instance.school.province_ref or getattr(instance.school.city_ref, "province", None)
            if school_province is not None:
                return school_province

        if instance.mosque_id:
            mosque_province = instance.mosque.province_ref or getattr(instance.mosque.city_ref, "province", None)
            if mosque_province is not None:
                return mosque_province

        if instance.province:
            return Province.objects.filter(name__iexact=instance.province.strip()).first()

        return None

    def _get_selected_city(self, province):
        if "city_ref" in self.data:
            try:
                queryset = City.objects.all()
                city_id = int(self.data.get("city_ref") or 0)
                if province is not None:
                    queryset = queryset.filter(province=province)
                return queryset.filter(pk=city_id).first()
            except (TypeError, ValueError):
                return None

        instance = self.instance
        if not instance or not instance.pk:
            return None

        if instance.school_id and instance.school.city_ref_id:
            return instance.school.city_ref

        if instance.mosque_id and instance.mosque.city_ref_id:
            return instance.mosque.city_ref

        if instance.city:
            queryset = City.objects.filter(name__iexact=instance.city.strip())
            if province is not None:
                queryset = queryset.filter(province=province)
            return queryset.first()

        return None

    def _set_place_querysets(self, *, province, city):
        school_queryset = School.objects.all()
        mosque_queryset = Mosque.objects.all()

        if city is not None:
            school_filter = Q(city_ref=city) | Q(city__iexact=city.name)
            mosque_filter = Q(city_ref=city) | Q(city__iexact=city.name)
            if province is not None:
                school_filter &= Q(province_ref=province) | Q(province__iexact=province.name) | Q(city_ref__province=province)
                mosque_filter &= Q(province_ref=province) | Q(province__iexact=province.name) | Q(city_ref__province=province)
            school_queryset = school_queryset.filter(school_filter)
            mosque_queryset = mosque_queryset.filter(mosque_filter)
        elif province is not None:
            school_queryset = school_queryset.filter(
                Q(province_ref=province) | Q(province__iexact=province.name) | Q(city_ref__province=province)
            )
            mosque_queryset = mosque_queryset.filter(
                Q(province_ref=province) | Q(province__iexact=province.name) | Q(city_ref__province=province)
            )
        else:
            school_queryset = school_queryset.none()
            mosque_queryset = mosque_queryset.none()

        self.fields["school"].queryset = school_queryset.order_by("name").distinct()
        self.fields["mosque"].queryset = mosque_queryset.order_by("name").distinct()

    @staticmethod
    def _extract_place_names(place):
        if place is None:
            return None, None

        city_name = getattr(getattr(place, "city_ref", None), "name", None) or getattr(place, "city", None)
        province_name = getattr(getattr(place, "province_ref", None), "name", None) or getattr(
            getattr(getattr(place, "city_ref", None), "province", None), "name", None
        ) or getattr(place, "province", None)

        city_name = str(city_name).strip() if city_name else None
        province_name = str(province_name).strip() if province_name else None
        return city_name, province_name

    @staticmethod
    def _matches_name(actual, expected):
        if not actual or not expected:
            return False
        return str(actual).strip().casefold() == str(expected).strip().casefold()

    def clean(self):
        cleaned = super().clean()
        province = cleaned.get("province_ref")
        city = cleaned.get("city_ref")
        school = cleaned.get("school")
        mosque = cleaned.get("mosque")

        if city and province and city.province_id != province.id:
            self.add_error("city_ref", "شهر انتخاب شده با استان انتخاب شده همخوانی ندارد.")

        if school:
            school_city, school_province = self._extract_place_names(school)
            if province and school_province and not self._matches_name(school_province, province.name):
                self.add_error("school", "مدرسه انتخاب شده متعلق به استان انتخاب شده نیست.")
            if city and school_city and not self._matches_name(school_city, city.name):
                self.add_error("school", "مدرسه انتخاب شده متعلق به شهر انتخاب شده نیست.")

        if mosque:
            mosque_city, mosque_province = self._extract_place_names(mosque)
            if province and mosque_province and not self._matches_name(mosque_province, province.name):
                self.add_error("mosque", "مسجد انتخاب شده متعلق به استان انتخاب شده نیست.")
            if city and mosque_city and not self._matches_name(mosque_city, city.name):
                self.add_error("mosque", "مسجد انتخاب شده متعلق به شهر انتخاب شده نیست.")

        resolved_city = city.name if city else cleaned.get("city") or None
        resolved_province = province.name if province else cleaned.get("province") or None

        if school:
            school_city, school_province = self._extract_place_names(school)
            resolved_city = resolved_city or school_city
            resolved_province = resolved_province or school_province

        if mosque:
            mosque_city, mosque_province = self._extract_place_names(mosque)
            resolved_city = resolved_city or mosque_city
            resolved_province = resolved_province or mosque_province

        cleaned["city"] = resolved_city
        cleaned["province"] = resolved_province
        return cleaned

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.city = self.cleaned_data.get("city") or None
        instance.province = self.cleaned_data.get("province") or None
        if commit:
            instance.save()
            self.save_m2m()
        return instance


class SellerInline(admin.StackedInline):
    model = Seller
    extra = 0
    can_delete = False
    readonly_fields = ("rating", "sales_count", "total_revenue", "registered_at", "verified_at", "created_at", "updated_at")


class ExamRecordInline(admin.TabularInline):
    model = ExamRecord
    extra = 0
    fields = ("exam_name", "score", "max_score", "status", "exam_date", "rank_at_exam")
    readonly_fields = ("created_at", "updated_at")
    show_change_link = True


class CoinTransactionInline(admin.TabularInline):
    model = CoinTransaction
    extra = 0
    fields = ("amount", "transaction_type", "challenge", "transaction_date")
    readonly_fields = ("amount", "transaction_type", "challenge", "transaction_date")
    can_delete = False
    show_change_link = True


@admin.action(description="تایید فروشنده‌های انتخاب‌شده")
def verify_sellers(modeladmin, request, queryset):
    updated = 0
    for seller in queryset:
        if not seller.verified:
            seller.verified = True
            seller.save(update_fields=["verified", "updated_at"])
            updated += 1
    modeladmin.message_user(request, f"{updated} فروشنده تایید شد.", level=messages.SUCCESS)


@admin.action(description="تایید درخواست‌های انتقال انتخاب‌شده")
def approve_transfers(modeladmin, request, queryset):
    updated = 0
    for transfer in queryset.exclude(status=CoinToWalletTransfer.TransferStatus.APPROVED):
        transfer.status = CoinToWalletTransfer.TransferStatus.APPROVED
        transfer.save(update_fields=["status", "updated_at"])
        updated += 1
    modeladmin.message_user(request, f"{updated} درخواست انتقال تایید شد.", level=messages.SUCCESS)


@admin.action(description="رد درخواست‌های انتقال انتخاب‌شده")
def reject_transfers(modeladmin, request, queryset):
    updated = 0
    for transfer in queryset.exclude(status=CoinToWalletTransfer.TransferStatus.REJECTED):
        transfer.status = CoinToWalletTransfer.TransferStatus.REJECTED
        transfer.save(update_fields=["status", "updated_at"])
        updated += 1
    modeladmin.message_user(request, f"{updated} درخواست انتقال رد شد.", level=messages.WARNING)


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    form = UserAdminForm
    add_form = UserCreationForm
    inlines = [SellerInline, ExamRecordInline, CoinTransactionInline]

    list_display = (
        "phone_number",
        "first_name",
        "last_name",
        "is_seller_display",
        "seller_verified_display",
        "is_active",
        "total_points",
        "challenge_coins",
        "current_rank",
    )
    list_filter = ("is_active", "is_staff", "gender", "province", "current_rank")
    search_fields = ("phone_number", "first_name", "last_name", "national_code")
    ordering = ("-date_joined",)
    readonly_fields = ("current_rank", "city", "province", "date_joined", "updated_at", "last_login")

    fieldsets = (
        ("اطلاعات شخصی", {"fields": ("phone_number", "password", "first_name", "last_name", "national_code", "birth_date", "gender", "profile_image")}),
        ("گیمیفیکیشن", {"fields": ("total_points", "challenge_coins", "wallet_balance", "current_rank")}),
        ("جغرافیایی", {"fields": (("province_ref", "city_ref"), ("school", "mosque"), ("province", "city"))}),
        ("دسترسی‌ها", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        ("تاریخ‌ها", {"fields": ("last_login", "date_joined", "updated_at")}),
    )

    @admin.display(boolean=True, description="فروشنده")
    def is_seller_display(self, obj):
        return obj.is_seller

    @admin.display(boolean=True, description="تایید فروشنده")
    def seller_verified_display(self, obj):
        return obj.seller_verified


@admin.register(Rank)
class RankAdmin(admin.ModelAdmin):
    list_display = ("name", "level", "min_points", "max_points", "color", "updated_at")
    list_filter = ("level",)
    search_fields = ("name",)
    readonly_fields = ("created_at", "updated_at")


@admin.register(ExamRecord)
class ExamRecordAdmin(admin.ModelAdmin):
    list_display = ("exam_name", "user", "score", "max_score", "status", "rank_at_exam", "exam_date")
    list_filter = ("status", "rank_at_exam", "exam_date")
    search_fields = ("exam_name", "user__phone_number", "user__first_name", "user__last_name")
    readonly_fields = ("created_at", "updated_at")
    autocomplete_fields = ("user", "rank_at_exam")


@admin.register(CoinTransaction)
class CoinTransactionAdmin(admin.ModelAdmin):
    list_display = ("user", "amount", "transaction_type", "challenge", "transaction_date")
    list_filter = ("transaction_type", "transaction_date")
    search_fields = ("user__phone_number", "user__first_name", "user__last_name", "description", "challenge")
    readonly_fields = ("created_at", "updated_at", "transaction_date")
    autocomplete_fields = ("user",)


@admin.register(CoinToWalletTransfer)
class CoinToWalletTransferAdmin(admin.ModelAdmin):
    list_display = ("user", "coin_amount", "amount_toman", "status", "requested_at", "processed_at")
    list_filter = ("status", "requested_at", "processed_at")
    search_fields = ("user__phone_number", "user__first_name", "user__last_name")
    readonly_fields = ("amount_toman", "requested_at", "processed_at", "created_at", "updated_at")
    autocomplete_fields = ("user",)
    actions = [approve_transfers, reject_transfers]


@admin.register(Seller)
class SellerAdmin(admin.ModelAdmin):
    list_display = ("shop_name", "user", "verified", "is_active", "rating", "sales_count", "total_revenue", "registered_at")
    list_filter = ("verified", "is_active", "registered_at")
    search_fields = ("shop_name", "user__phone_number", "user__first_name", "user__last_name", "shop_phone_number")
    readonly_fields = ("rating", "sales_count", "total_revenue", "registered_at", "verified_at", "created_at", "updated_at")
    autocomplete_fields = ("user",)
    actions = [verify_sellers]

from django import forms
from django.contrib import admin, messages
from django.contrib.auth.forms import ReadOnlyPasswordHashField

from accounts.models import CoinToWalletTransfer, CoinTransaction, ExamRecord, Rank, Seller, User


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
    form = UserChangeForm
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
    readonly_fields = ("current_rank", "date_joined", "updated_at", "last_login")

    fieldsets = (
        ("اطلاعات شخصی", {"fields": ("phone_number", "password", "first_name", "last_name", "national_code", "birth_date", "gender", "profile_image")}),
        ("گیمیفیکیشن", {"fields": ("total_points", "challenge_coins", "wallet_balance", "current_rank")}),
        ("جغرافیایی", {"fields": ("school", "mosque", "city", "province")}),
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

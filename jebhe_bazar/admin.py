from django.contrib import admin

from .models import Cart, CartItem, Category, Order, OrderItem, Product, Transaction, WalletChargeRequest


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "parent", "is_active")
    list_filter = ("is_active", "parent")
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "seller",
        "category",
        "payment_method",
        "price",
        "coin_price",
        "stock",
        "discount_percent",
        "discount_active",
        "is_ticket",
        "is_active",
        "created_at",
    )
    list_filter = ("payment_method", "is_active", "discount_active", "is_ticket", "category", "seller")
    search_fields = ("title", "slug", "description", "seller__shop_name")
    autocomplete_fields = ("seller", "category")
    prepopulated_fields = {"slug": ("title",)}


class CartItemInline(admin.TabularInline):
    model = CartItem
    extra = 0


@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ("user", "created_at", "updated_at", "total_quantity", "total_amount")
    list_filter = ("created_at", "updated_at")
    search_fields = ("user__phone_number", "user__first_name", "user__last_name")
    inlines = [CartItemInline]


@admin.register(CartItem)
class CartItemAdmin(admin.ModelAdmin):
    list_display = ("cart", "product", "quantity", "selected_payment_method", "item_total")
    list_filter = ("selected_payment_method", "product__category")
    search_fields = ("cart__user__phone_number", "product__title")
    autocomplete_fields = ("cart", "product")


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "total_amount", "coins_used", "wallet_used", "online_paid", "status", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("id", "user__phone_number", "user__first_name", "user__last_name")
    autocomplete_fields = ("user",)
    inlines = [OrderItemInline]


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ("order", "product", "quantity", "paid_with", "unit_price", "unit_coins", "line_total", "seller_commission")
    list_filter = ("paid_with", "product__category", "product__seller")
    search_fields = ("order__id", "product__title", "product__seller__shop_name")
    autocomplete_fields = ("order", "product")


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ("user", "order", "amount", "transaction_type", "created_at")
    list_filter = ("transaction_type", "created_at")
    search_fields = ("user__phone_number", "user__first_name", "user__last_name", "description")
    autocomplete_fields = ("user", "order")


@admin.action(description="تایید و شارژ مستقیم کیف پول برای درخواست‌های انتخاب‌شده")
def approve_wallet_charge_requests(modeladmin, request, queryset):
    from django.contrib import messages
    updated = 0
    for charge_request in queryset.exclude(status=WalletChargeRequest.Status.COMPLETED):
        charge_request.status = WalletChargeRequest.Status.COMPLETED
        charge_request.save()
        updated += 1
    modeladmin.message_user(request, f"{updated} درخواست افزایش اعتبار تایید شد و کیف پول کاربران شارژ شد.", level=messages.SUCCESS)


@admin.register(WalletChargeRequest)
class WalletChargeRequestAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "requested_amount",
        "status",
        "created_at",
        "reviewed_at",
        "completed_at",
    )
    list_filter = ("status", "created_at", "reviewed_at", "completed_at")
    search_fields = ("user__phone_number", "user__first_name", "user__last_name", "admin_note", "payment_reference")
    readonly_fields = ("requested_coins", "coins_granted_at", "created_at", "updated_at", "reviewed_at", "completed_at")
    autocomplete_fields = ("user",)
    actions = [approve_wallet_charge_requests]

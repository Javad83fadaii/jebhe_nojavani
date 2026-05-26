from django.contrib import admin

from .models import Cart, CartItem, Category, Order, OrderItem, Product, Transaction


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
        "price",
        "stock",
        "discount_percent",
        "discount_active",
        "is_ticket",
        "is_active",
        "created_at",
    )
    list_filter = ("is_active", "discount_active", "is_ticket", "category", "seller")
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
    list_display = ("cart", "product", "quantity", "item_total")
    list_filter = ("product__category",)
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
    list_display = ("order", "product", "quantity", "unit_price", "line_total", "seller_commission")
    list_filter = ("product__category", "product__seller")
    search_fields = ("order__id", "product__title", "product__seller__shop_name")
    autocomplete_fields = ("order", "product")


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ("user", "order", "amount", "transaction_type", "created_at")
    list_filter = ("transaction_type", "created_at")
    search_fields = ("user__phone_number", "user__first_name", "user__last_name", "description")
    autocomplete_fields = ("user", "order")

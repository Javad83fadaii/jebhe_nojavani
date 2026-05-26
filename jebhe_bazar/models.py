from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.urls import reverse
from django.utils.text import slugify

from accounts.models import CoinTransaction, Seller


def _build_unique_slug(instance: models.Model, source_value: str, slug_field: str = "slug") -> str:
    base_slug = slugify(source_value, allow_unicode=True)[:180] or "item"
    slug = base_slug
    model_class = instance.__class__
    counter = 2

    while model_class.objects.filter(**{slug_field: slug}).exclude(pk=instance.pk).exists():
        slug = f"{base_slug[:170]}-{counter}"
        counter += 1

    return slug


class Category(models.Model):
    name = models.CharField(max_length=120, unique=True, verbose_name="نام")
    slug = models.SlugField(max_length=200, unique=True, blank=True, verbose_name="اسلاگ")
    parent = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="children",
        verbose_name="دسته والد",
    )
    image = models.ImageField(upload_to="bazar/categories/", null=True, blank=True, verbose_name="تصویر")
    is_active = models.BooleanField(default=True, verbose_name="فعال")

    class Meta:
        ordering = ("name",)
        verbose_name = "دسته‌بندی بازار"
        verbose_name_plural = "دسته‌بندی‌های بازار"

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = _build_unique_slug(self, self.name)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("bazar:category-products", kwargs={"slug": self.slug})

    def get_descendant_ids(self) -> list[int]:
        descendant_ids: list[int] = []
        for child in self.children.filter(is_active=True):
            descendant_ids.append(child.pk)
            descendant_ids.extend(child.get_descendant_ids())
        return descendant_ids


class Product(models.Model):
    seller = models.ForeignKey(
        Seller,
        on_delete=models.CASCADE,
        related_name="bazar_products",
        verbose_name="فروشنده",
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name="products",
        verbose_name="دسته‌بندی",
    )
    title = models.CharField(max_length=200, verbose_name="عنوان")
    slug = models.SlugField(max_length=220, unique=True, blank=True, verbose_name="اسلاگ")
    description = models.TextField(verbose_name="توضیحات")
    price = models.IntegerField(validators=[MinValueValidator(0)], verbose_name="قیمت")
    stock = models.PositiveIntegerField(default=0, verbose_name="موجودی")
    discount_percent = models.PositiveSmallIntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name="درصد تخفیف",
    )
    discount_active = models.BooleanField(default=False, verbose_name="تخفیف فعال")
    is_ticket = models.BooleanField(default=False, verbose_name="بلیط تفریحی")
    image = models.ImageField(upload_to="bazar/products/", null=True, blank=True, verbose_name="تصویر")
    is_active = models.BooleanField(default=True, verbose_name="فعال")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="تاریخ ایجاد")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="تاریخ بروزرسانی")

    class Meta:
        ordering = ("-created_at",)
        verbose_name = "محصول بازار"
        verbose_name_plural = "محصولات بازار"

    def __str__(self) -> str:
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = _build_unique_slug(self, self.title)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("bazar:product-detail", kwargs={"slug": self.slug})

    @property
    def final_price(self) -> int:
        if not self.discount_active or self.discount_percent <= 0:
            return int(self.price)
        discounted_value = Decimal(self.price) * (Decimal(100) - Decimal(self.discount_percent)) / Decimal(100)
        return int(discounted_value.quantize(Decimal("1"), rounding=ROUND_HALF_UP))

    @property
    def is_in_stock(self) -> bool:
        return self.is_active and self.stock > 0


class Cart(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="bazar_carts",
        verbose_name="کاربر",
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="تاریخ ایجاد")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="تاریخ بروزرسانی")

    class Meta:
        ordering = ("-updated_at",)
        constraints = [
            models.UniqueConstraint(fields=["user"], name="unique_bazar_cart_per_user"),
        ]
        verbose_name = "سبد خرید"
        verbose_name_plural = "سبدهای خرید"

    def __str__(self) -> str:
        return f"سبد خرید {self.user}"

    @property
    def total_amount(self) -> int:
        return sum(item.item_total for item in self.items.select_related("product"))

    @property
    def total_quantity(self) -> int:
        return sum(item.quantity for item in self.items.all())


class CartItem(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name="items", verbose_name="سبد خرید")
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="cart_items", verbose_name="محصول")
    quantity = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)], verbose_name="تعداد")

    class Meta:
        ordering = ("id",)
        constraints = [
            models.UniqueConstraint(fields=["cart", "product"], name="unique_cart_product_item"),
        ]
        verbose_name = "آیتم سبد خرید"
        verbose_name_plural = "آیتم‌های سبد خرید"

    def __str__(self) -> str:
        return f"{self.product.title} x {self.quantity}"

    @property
    def item_total(self) -> int:
        return self.quantity * self.product.final_price


class Order(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "در انتظار"
        PAID = "paid", "پرداخت شده"
        FAILED = "failed", "ناموفق"
        CANCELLED = "cancelled", "لغو شده"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="bazar_orders",
        verbose_name="کاربر",
    )
    total_amount = models.IntegerField(default=0, validators=[MinValueValidator(0)], verbose_name="مبلغ کل")
    coins_used = models.IntegerField(default=0, validators=[MinValueValidator(0)], verbose_name="سکه مصرفی")
    wallet_used = models.IntegerField(default=0, validators=[MinValueValidator(0)], verbose_name="کیف پول مصرفی")
    online_paid = models.IntegerField(default=0, validators=[MinValueValidator(0)], verbose_name="پرداخت آنلاین")
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING, verbose_name="وضعیت")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="تاریخ ایجاد")

    class Meta:
        ordering = ("-created_at",)
        verbose_name = "سفارش"
        verbose_name_plural = "سفارش‌ها"

    def __str__(self) -> str:
        return f"سفارش #{self.pk} - {self.user}"


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items", verbose_name="سفارش")
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="order_items", verbose_name="محصول")
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)], verbose_name="تعداد")
    unit_price = models.IntegerField(validators=[MinValueValidator(0)], verbose_name="قیمت واحد")

    class Meta:
        ordering = ("id",)
        verbose_name = "آیتم سفارش"
        verbose_name_plural = "آیتم‌های سفارش"

    def __str__(self) -> str:
        return f"{self.product.title} - {self.quantity}"

    @property
    def line_total(self) -> int:
        return self.quantity * self.unit_price

    @property
    def seller_commission(self) -> int:
        commission_percent = Decimal(self.product.seller.platform_commission_percent)
        commission_value = Decimal(self.line_total) * commission_percent / Decimal(100)
        return int(commission_value.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


class Transaction(models.Model):
    class TransactionType(models.TextChoices):
        CHARGE = "charge", "شارژ"
        PURCHASE = "purchase", "خرید"
        COMMISSION = "commission", "کمیسیون"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="bazar_transactions",
        verbose_name="کاربر",
    )
    order = models.ForeignKey(
        Order,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="transactions",
        verbose_name="سفارش",
    )
    amount = models.IntegerField(verbose_name="مبلغ")
    transaction_type = models.CharField(max_length=20, choices=TransactionType.choices, verbose_name="نوع تراکنش")
    description = models.TextField(blank=True, verbose_name="توضیحات")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="تاریخ ایجاد")

    class Meta:
        ordering = ("-created_at",)
        verbose_name = "تراکنش بازار"
        verbose_name_plural = "تراکنش‌های بازار"

    def __str__(self) -> str:
        return f"{self.user} | {self.get_transaction_type_display()} | {self.amount}"


def record_coin_spend(user, amount: int, description: str):
    if amount <= 0:
        return

    CoinTransaction.objects.create(
        user=user,
        amount=-amount,
        transaction_type=CoinTransaction.TransactionType.PENALTY,
        description=description,
        challenge="bazar-checkout",
    )

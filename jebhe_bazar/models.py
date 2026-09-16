from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models, transaction
from django.db.models import F
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify

from accounts.models import CoinTransaction, Seller, User


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
    class PaymentMethod(models.TextChoices):
        COIN = "coin", "فقط با سکه چالش"
        MONEY = "money", "فقط با پول / اعتبار کیف پول"
        BOTH = "both", "هر دو (سکه یا پول - به انتخاب خریدار)"

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
    price = models.IntegerField(validators=[MinValueValidator(0)], verbose_name="قیمت (تومان)")
    coin_price = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="قیمت به سکه چالش",
        help_text="در صورتی که خالی باشد، از قیمت اصلی برای سکه استفاده می‌شود.",
    )
    payment_method = models.CharField(
        max_length=10,
        choices=PaymentMethod.choices,
        default=PaymentMethod.BOTH,
        verbose_name="روش پرداخت",
    )
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
    def final_coin_price(self) -> int:
        base_coin = self.coin_price if (self.coin_price is not None and self.coin_price > 0) else self.price
        if not self.discount_active or self.discount_percent <= 0:
            return int(base_coin)
        discounted_value = Decimal(base_coin) * (Decimal(100) - Decimal(self.discount_percent)) / Decimal(100)
        return int(discounted_value.quantize(Decimal("1"), rounding=ROUND_HALF_UP))

    @property
    def allows_coins(self) -> bool:
        return self.payment_method in {self.PaymentMethod.COIN, self.PaymentMethod.BOTH}

    @property
    def allows_money(self) -> bool:
        return self.payment_method in {self.PaymentMethod.MONEY, self.PaymentMethod.BOTH}

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
    def total_money(self) -> int:
        return sum(item.item_total_money for item in self.items.select_related("product"))

    @property
    def total_coins(self) -> int:
        return sum(item.item_total_coins for item in self.items.select_related("product"))

    @property
    def total_quantity(self) -> int:
        return sum(item.quantity for item in self.items.all())


class CartItem(models.Model):
    class SelectedPaymentMethod(models.TextChoices):
        MONEY = "money", "پول / کیف پول"
        COIN = "coin", "سکه چالش"

    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name="items", verbose_name="سبد خرید")
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="cart_items", verbose_name="محصول")
    quantity = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)], verbose_name="تعداد")
    selected_payment_method = models.CharField(
        max_length=10,
        choices=SelectedPaymentMethod.choices,
        default=SelectedPaymentMethod.MONEY,
        verbose_name="روش پرداخت انتخابی",
    )

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
    def is_paid_with_coins(self) -> bool:
        if self.product.payment_method == Product.PaymentMethod.COIN:
            return True
        if self.product.payment_method == Product.PaymentMethod.MONEY:
            return False
        return self.selected_payment_method == self.SelectedPaymentMethod.COIN

    @property
    def item_unit_price(self) -> int:
        if self.is_paid_with_coins:
            return self.product.final_coin_price
        return self.product.final_price

    @property
    def item_total(self) -> int:
        return self.quantity * self.item_unit_price

    @property
    def item_total_money(self) -> int:
        return 0 if self.is_paid_with_coins else (self.quantity * self.product.final_price)

    @property
    def item_total_coins(self) -> int:
        return (self.quantity * self.product.final_coin_price) if self.is_paid_with_coins else 0


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
    total_amount = models.IntegerField(default=0, validators=[MinValueValidator(0)], verbose_name="مبلغ کل (تومان)")
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
    unit_price = models.IntegerField(default=0, validators=[MinValueValidator(0)], verbose_name="قیمت واحد (تومان)")
    unit_coins = models.PositiveIntegerField(default=0, verbose_name="قیمت واحد (سکه)")
    paid_with = models.CharField(
        max_length=10,
        choices=[("money", "پول / کیف پول"), ("coin", "سکه چالش")],
        default="money",
        verbose_name="پرداخت شده با",
    )

    class Meta:
        ordering = ("id",)
        verbose_name = "آیتم سفارش"
        verbose_name_plural = "آیتم‌های سفارش"

    def __str__(self) -> str:
        return f"{self.product.title} - {self.quantity}"

    @property
    def line_total(self) -> int:
        if self.paid_with == "coin":
            return self.quantity * self.unit_coins
        return self.quantity * self.unit_price

    @property
    def seller_commission(self) -> int:
        commission_percent = Decimal(self.product.seller.platform_commission_percent)
        base_amount = self.quantity * self.unit_price
        commission_value = Decimal(base_amount) * commission_percent / Decimal(100)
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


class WalletChargeRequest(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "در انتظار بررسی"
        REVIEWING = "reviewing", "در حال بررسی"
        CARD_SENT = "card_sent", "شماره کارت ارسال شد"
        COMPLETED = "completed", "کیف پول شارژ شد"
        REJECTED = "rejected", "رد شده"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="bazar_charge_requests",
        verbose_name="کاربر",
    )
    requested_amount = models.PositiveIntegerField(
        validators=[MinValueValidator(1)],
        verbose_name="مبلغ درخواستی (تومان)",
    )
    requested_coins = models.PositiveIntegerField(
        default=0,
        blank=True,
        verbose_name="سکه درخواستی (قدیمی)",
    )
    granted_coins = models.PositiveIntegerField(
        default=0,
        blank=True,
        verbose_name="مبلغ شارژ تایید شده (تومان)",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        verbose_name="وضعیت",
    )
    admin_card_number = models.CharField(max_length=64, blank=True, verbose_name="شماره کارت اعلامی")
    admin_note = models.TextField(blank=True, verbose_name="یادداشت ادمین")
    payment_reference = models.CharField(max_length=120, blank=True, verbose_name="شناسه یا توضیح پرداخت")
    reviewed_at = models.DateTimeField(null=True, blank=True, verbose_name="زمان بررسی")
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name="زمان شارژ کیف پول")
    coins_granted_at = models.DateTimeField(null=True, blank=True, verbose_name="زمان ثبت شارژ")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="تاریخ ایجاد")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="تاریخ بروزرسانی")

    class Meta:
        ordering = ("-created_at",)
        verbose_name = "درخواست افزایش اعتبار بازار"
        verbose_name_plural = "درخواست‌های افزایش اعتبار بازار"

    def __str__(self) -> str:
        return f"{self.user} - {self.requested_amount} تومان"

    def clean(self):
        if self.requested_amount <= 0:
            raise ValidationError({"requested_amount": "مبلغ درخواستی باید بیشتر از صفر باشد."})

    def save(self, *args, **kwargs):
        previous_status = None
        if self.pk:
            previous_status = type(self).objects.filter(pk=self.pk).values_list("status", flat=True).first()

        if self.status in {self.Status.REVIEWING, self.Status.CARD_SENT, self.Status.COMPLETED, self.Status.REJECTED}:
            self.reviewed_at = self.reviewed_at or timezone.now()
        if self.status == self.Status.COMPLETED:
            self.completed_at = self.completed_at or timezone.now()

        self.full_clean()
        super().save(*args, **kwargs)

        if self.status != self.Status.COMPLETED or self.coins_granted_at is not None:
            return
        if previous_status == self.Status.COMPLETED:
            return

        granted_at = timezone.now()
        with transaction.atomic():
            updated = (
                type(self)
                .objects.select_for_update()
                .filter(pk=self.pk, coins_granted_at__isnull=True)
                .update(coins_granted_at=granted_at)
            )
            if not updated:
                return

            credit_amount = self.granted_coins if self.granted_coins > 0 else self.requested_amount
            User.objects.filter(pk=self.user_id).update(wallet_balance=F("wallet_balance") + Decimal(credit_amount))
            Transaction.objects.create(
                user=self.user,
                amount=credit_amount,
                transaction_type=Transaction.TransactionType.CHARGE,
                description=f"شارژ مستقیم کیف پول بابت درخواست افزایش اعتبار بازار #{self.pk}",
                created_at=granted_at,
            )

        self.coins_granted_at = granted_at


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

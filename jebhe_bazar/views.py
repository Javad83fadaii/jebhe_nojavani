from __future__ import annotations

from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Case, Count, ExpressionWrapper, F, IntegerField, Prefetch, Q, Sum, Value, When
from django.db.models.functions import Coalesce
from django.http import Http404, HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils.decorators import method_decorator
from django.views.decorators.http import require_http_methods, require_POST
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from accounts.models import Seller, User

from .forms import CartQuantityForm, CoinApplyForm, ProductForm, WalletChargeRequestForm
from .models import Cart, CartItem, Category, Order, OrderItem, Product, Transaction, WalletChargeRequest, record_coin_spend


CHECKOUT_COINS_SESSION_KEY = "bazar_checkout_coins"
_PERSIAN_DIGITS_TRANSLATION = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")


def _get_cart(request_user: User) -> Cart:
    cart, _ = Cart.objects.get_or_create(user=request_user)
    return cart


def _get_cart_items(cart: Cart):
    return cart.items.select_related("product", "product__seller", "product__category", "product__seller__user")


def _get_cart_total(cart: Cart) -> int:
    return sum(item.item_total for item in _get_cart_items(cart))


def _get_available_coins(user: User, cart_total: int) -> int:
    return min(int(user.challenge_coins or 0), int(cart_total))


def _format_toman(value: int) -> str:
    return f"{int(value):,}".translate(_PERSIAN_DIGITS_TRANSLATION)


def _build_cart_item_response(cart: Cart, item: CartItem, message: str, *, status: int = 200) -> JsonResponse:
    cart_total = _get_cart_total(cart)
    payload = {
        "message": message,
        "item_id": item.pk,
        "quantity": item.quantity,
        "quantity_display": _format_toman(item.quantity),
        "stock": item.product.stock,
        "item_total": item.item_total,
        "item_total_display": _format_toman(item.item_total),
        "unit_price": item.product.final_price,
        "unit_price_display": _format_toman(item.product.final_price),
        "cart_total": cart_total,
        "cart_total_display": _format_toman(cart_total),
        "cart_total_quantity": cart.total_quantity,
        "cart_total_quantity_display": _format_toman(cart.total_quantity),
        "can_increment": item.quantity < item.product.stock,
        "can_decrement": item.quantity > 1,
    }
    return JsonResponse(payload, status=status)


def _get_applied_coins(request: HttpRequest, user: User, cart_total: int) -> int:
    available = _get_available_coins(user, cart_total)
    applied = int(request.session.get(CHECKOUT_COINS_SESSION_KEY, 0) or 0)
    if applied > available:
        applied = available
        request.session[CHECKOUT_COINS_SESSION_KEY] = applied
    return applied


def _clear_checkout_session(request: HttpRequest):
    request.session.pop(CHECKOUT_COINS_SESSION_KEY, None)


def _redirect_seller_to_panel(request: HttpRequest):
    if request.user.is_authenticated and request.user.is_seller and not request.session.get("seller_site_view", False):
        return redirect("bazar:seller-dashboard")
    return None


def _require_seller(user: User) -> Seller:
    seller = getattr(user, "seller_profile", None)
    if seller is None or not seller.is_active or not seller.verified:
        raise Http404("Seller profile not found.")
    return seller


def _build_checkout_context(request: HttpRequest) -> dict:
    cart = _get_cart(request.user)
    cart_items = list(_get_cart_items(cart))
    cart_total = sum(item.item_total for item in cart_items)
    available_coins = _get_available_coins(request.user, cart_total)
    applied_coins = _get_applied_coins(request, request.user, cart_total)

    return {
        "cart": cart,
        "cart_items": cart_items,
        "cart_total": cart_total,
        "available_coins": available_coins,
        "applied_coins": applied_coins,
        "remaining_amount": max(cart_total - applied_coins, 0),
    }


@method_decorator(login_required, name="dispatch")
class ProductListView(ListView):
    model = Product
    template_name = "jebhe_bazar/product_list.html"
    context_object_name = "products"
    paginate_by = 12

    SORT_OPTIONS = {
        "newest": ("-created_at",),
        "cheap": ("final_price_sort", "-created_at"),
        "expensive": ("-final_price_sort", "-created_at"),
        "discount": ("-discount_percent", "final_price_sort", "-created_at"),
        "popular": ("-total_orders", "-created_at"),
    }

    def dispatch(self, request, *args, **kwargs):
        seller_redirect = _redirect_seller_to_panel(request)
        if seller_redirect:
            return seller_redirect
        return super().dispatch(request, *args, **kwargs)

    def _get_root_category(self, category: Category | None) -> Category | None:
        while category and category.parent_id:
            category = category.parent
        return category

    def _get_clean_int(self, key: str) -> int | None:
        raw_value = self.request.GET.get(key, "").strip()
        if not raw_value:
            return None
        try:
            return max(int(raw_value), 0)
        except (TypeError, ValueError):
            return None

    def get_queryset(self):
        discounted_price = ExpressionWrapper(
            F("price") - (F("price") * F("discount_percent") / Value(100)),
            output_field=IntegerField(),
        )
        queryset = (
            Product.objects.select_related("category", "seller", "seller__user")
            .annotate(
                final_price_sort=Case(
                    When(
                        discount_active=True,
                        discount_percent__gt=0,
                        then=discounted_price,
                    ),
                    default=F("price"),
                    output_field=IntegerField(),
                ),
                total_orders=Count("order_items"),
            )
            .filter(is_active=True, category__is_active=True, seller__is_active=True)
        )

        category_slug = self.kwargs.get("slug")
        top_category_slug = self.request.GET.get("top", "").strip()
        query = self.request.GET.get("q", "").strip()
        self.selected_category = None
        self.selected_top_category = None

        if category_slug:
            self.selected_category = get_object_or_404(Category, slug=category_slug, is_active=True)
            category_ids = [self.selected_category.pk, *self.selected_category.get_descendant_ids()]
            queryset = queryset.filter(category_id__in=category_ids)
            self.selected_top_category = self._get_root_category(self.selected_category)
        elif top_category_slug:
            self.selected_top_category = get_object_or_404(
                Category,
                slug=top_category_slug,
                is_active=True,
                parent__isnull=True,
            )
            category_ids = [self.selected_top_category.pk, *self.selected_top_category.get_descendant_ids()]
            queryset = queryset.filter(category_id__in=category_ids)

        if query:
            queryset = queryset.filter(Q(title__icontains=query) | Q(description__icontains=query))

        self.discount_only = self.request.GET.get("discount") == "1"
        self.in_stock_only = self.request.GET.get("in_stock") == "1"
        self.selected_kind = self.request.GET.get("kind", "").strip()
        self.min_price = self._get_clean_int("min_price")
        self.max_price = self._get_clean_int("max_price")
        self.current_sort = self.request.GET.get("sort", "newest").strip()

        if self.discount_only:
            queryset = queryset.filter(discount_active=True, discount_percent__gt=0)

        if self.in_stock_only:
            queryset = queryset.filter(stock__gt=0)

        if self.selected_kind == "ticket":
            queryset = queryset.filter(is_ticket=True)
        elif self.selected_kind == "product":
            queryset = queryset.filter(is_ticket=False)

        if self.min_price is not None:
            queryset = queryset.filter(final_price_sort__gte=self.min_price)

        if self.max_price is not None:
            queryset = queryset.filter(final_price_sort__lte=self.max_price)

        if self.current_sort not in self.SORT_OPTIONS:
            self.current_sort = "newest"

        return queryset.order_by(*self.SORT_OPTIONS[self.current_sort])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["categories"] = Category.objects.filter(is_active=True, parent__isnull=True).prefetch_related("children")
        context["selected_category"] = getattr(self, "selected_category", None)
        context["selected_top_category"] = getattr(self, "selected_top_category", None)
        context["search_query"] = self.request.GET.get("q", "").strip()
        context["current_sort"] = getattr(self, "current_sort", "newest")
        context["sort_options"] = [
            ("newest", "جدیدترین"),
            ("cheap", "ارزان ترین"),
            ("expensive", "گران ترین"),
            ("discount", "بیشترین تخفیف"),
            ("popular", "پرفروش ترین"),
        ]
        context["discount_only"] = getattr(self, "discount_only", False)
        context["in_stock_only"] = getattr(self, "in_stock_only", False)
        context["selected_kind"] = getattr(self, "selected_kind", "")
        context["min_price"] = self.request.GET.get("min_price", "").strip()
        context["max_price"] = self.request.GET.get("max_price", "").strip()
        context["active_filters_count"] = sum(
            1
            for value in (
                context["search_query"],
                context["selected_top_category"],
                context["selected_category"],
                context["discount_only"],
                context["in_stock_only"],
                context["selected_kind"],
                context["min_price"],
                context["max_price"],
                context["current_sort"] != "newest",
            )
            if value
        )
        context["page_name"] = "bazar"
        context["page_title"] = "جبهه بازار | جبهه نوجوانی"
        return context


@method_decorator(login_required, name="dispatch")
class ProductDetailView(DetailView):
    model = Product
    template_name = "jebhe_bazar/product_detail.html"
    slug_field = "slug"
    slug_url_kwarg = "slug"
    context_object_name = "product"

    def dispatch(self, request, *args, **kwargs):
        seller_redirect = _redirect_seller_to_panel(request)
        if seller_redirect:
            return seller_redirect
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        return Product.objects.select_related("category", "seller", "seller__user").filter(
            is_active=True,
            category__is_active=True,
            seller__is_active=True,
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_name"] = "bazar"
        context["page_title"] = f"{self.object.title} | جبهه بازار"
        context["related_products"] = (
            Product.objects.select_related("seller", "category")
            .filter(category=self.object.category, is_active=True)
            .exclude(pk=self.object.pk)[:4]
        )
        return context


@login_required
@require_http_methods(["GET", "POST"])
def cart_view(request: HttpRequest) -> HttpResponse:
    seller_redirect = _redirect_seller_to_panel(request)
    if seller_redirect:
        return seller_redirect
    cart = _get_cart(request.user)

    if request.method == "POST":
        item = get_object_or_404(CartItem, pk=request.POST.get("item_id"), cart=cart)
        form = CartQuantityForm(request.POST)
        if form.is_valid():
            new_quantity = form.cleaned_data["quantity"]
            if new_quantity > item.product.stock:
                messages.error(request, "تعداد انتخابی بیشتر از موجودی محصول است.")
            else:
                item.quantity = new_quantity
                item.save(update_fields=["quantity"])
                messages.success(request, "سبد خرید بروزرسانی شد.")
        else:
            messages.error(request, "مقدار وارد شده معتبر نیست.")
        return redirect("bazar:cart")

    cart_items = list(_get_cart_items(cart))
    context = {
        "cart": cart,
        "cart_items": cart_items,
        "cart_total": sum(item.item_total for item in cart_items),
        "page_name": "bazar",
        "page_title": "سبد خرید | جبهه بازار",
        "quantity_form": CartQuantityForm(),
    }
    return render(request, "jebhe_bazar/cart.html", context)


@login_required
@require_POST
def update_cart_item_quantity(request: HttpRequest, item_id: int) -> JsonResponse:
    seller_redirect = _redirect_seller_to_panel(request)
    if seller_redirect:
        return JsonResponse({"message": "دسترسی به سبد خرید از این بخش ممکن نیست."}, status=403)

    cart = _get_cart(request.user)
    item = get_object_or_404(
        CartItem.objects.select_related("product"),
        pk=item_id,
        cart=cart,
    )
    form = CartQuantityForm(request.POST)

    if not form.is_valid():
        return _build_cart_item_response(cart, item, "مقدار وارد شده معتبر نیست.", status=400)

    new_quantity = form.cleaned_data["quantity"]
    if new_quantity > item.product.stock:
        return _build_cart_item_response(cart, item, "تعداد انتخابی بیشتر از موجودی محصول است.", status=400)

    item.quantity = new_quantity
    item.save(update_fields=["quantity"])
    item.refresh_from_db()
    return _build_cart_item_response(cart, item, "سبد خرید بروزرسانی شد.")


@login_required
@require_POST
def add_to_cart(request: HttpRequest, product_id: int) -> HttpResponse:
    seller_redirect = _redirect_seller_to_panel(request)
    if seller_redirect:
        return seller_redirect
    cart = _get_cart(request.user)
    product = get_object_or_404(Product, pk=product_id, is_active=True, seller__is_active=True, category__is_active=True)
    quantity = int(request.POST.get("quantity", 1) or 1)
    quantity = max(1, quantity)

    if product.stock <= 0:
        messages.error(request, "این محصول در حال حاضر موجود نیست.")
        return redirect(product.get_absolute_url())

    item, created = CartItem.objects.get_or_create(cart=cart, product=product, defaults={"quantity": 0})
    new_quantity = min(item.quantity + quantity, product.stock)
    item.quantity = new_quantity
    item.save(update_fields=["quantity"])

    if created:
        messages.success(request, "محصول به سبد خرید اضافه شد.")
    else:
        messages.success(request, "تعداد محصول در سبد خرید بروزرسانی شد.")

    next_url = request.POST.get("next")
    return redirect(next_url or "bazar:cart")


@login_required
def remove_from_cart(request: HttpRequest, item_id: int) -> HttpResponse:
    seller_redirect = _redirect_seller_to_panel(request)
    if seller_redirect:
        return seller_redirect
    cart = _get_cart(request.user)
    item = get_object_or_404(CartItem, pk=item_id, cart=cart)
    item.delete()
    messages.success(request, "محصول از سبد خرید حذف شد.")
    return redirect("bazar:cart")


@login_required
@require_POST
def update_cart_quantity(request: HttpRequest, item_id: int) -> HttpResponse:
    seller_redirect = _redirect_seller_to_panel(request)
    if seller_redirect:
        return seller_redirect

    cart = _get_cart(request.user)
    item = get_object_or_404(CartItem, pk=item_id, cart=cart)
    is_ajax = request.headers.get("x-requested-with") == "XMLHttpRequest"

    try:
        quantity = int(request.POST.get("quantity", item.quantity))
    except (TypeError, ValueError):
        quantity = item.quantity

    quantity = max(quantity, 1)
    error = None
    if quantity > item.product.stock:
        quantity = max(item.product.stock, 1)
        error = "تعداد انتخابی بیشتر از موجودی محصول است."

    item.quantity = quantity
    item.save(update_fields=["quantity"])

    if is_ajax:
        cart_items = list(_get_cart_items(cart))
        return JsonResponse({
            "ok": error is None,
            "error": error,
            "item_id": item.id,
            "quantity": item.quantity,
            "item_total": item.item_total,
            "cart_total": sum(i.item_total for i in cart_items),
        })

    if error:
        messages.error(request, error)
    else:
        messages.success(request, "سبد خرید بروزرسانی شد.")
    return redirect("bazar:cart")


@login_required
def checkout_view(request: HttpRequest) -> HttpResponse:
    seller_redirect = _redirect_seller_to_panel(request)
    if seller_redirect:
        return seller_redirect
    context = _build_checkout_context(request)
    if not context["cart_items"]:
        messages.error(request, "سبد خرید شما خالی است.")
        return redirect("bazar:product-list")

    context["page_name"] = "bazar"
    context["page_title"] = "تسویه حساب | جبهه بازار"
    return render(request, "jebhe_bazar/checkout.html", context)


@login_required
@require_http_methods(["GET", "POST"])
def apply_coins_view(request: HttpRequest) -> HttpResponse:
    seller_redirect = _redirect_seller_to_panel(request)
    if seller_redirect:
        return seller_redirect
    cart = _get_cart(request.user)
    cart_items = list(_get_cart_items(cart))
    cart_total = sum(item.item_total for item in cart_items)
    if not cart_items:
        messages.error(request, "سبد خرید شما خالی است.")
        return redirect("bazar:cart")

    max_coins = _get_available_coins(request.user, cart_total)
    initial_value = _get_applied_coins(request, request.user, cart_total)

    if request.method == "POST":
        form = CoinApplyForm(request.POST, max_coins=max_coins)
        if form.is_valid():
            request.session[CHECKOUT_COINS_SESSION_KEY] = form.cleaned_data["coins_to_use"]
            messages.success(request, "مقدار سکه مصرفی ثبت شد.")
            return redirect("bazar:checkout")
    else:
        form = CoinApplyForm(initial={"coins_to_use": initial_value}, max_coins=max_coins)

    context = {
        "cart_items": cart_items,
        "cart_total": cart_total,
        "available_coins": max_coins,
        "form": form,
        "page_name": "bazar",
        "page_title": "استفاده از سکه | جبهه بازار",
    }
    return render(request, "jebhe_bazar/checkout_coins.html", context)


@login_required
@require_POST
def pay_view(request: HttpRequest) -> HttpResponse:
    seller_redirect = _redirect_seller_to_panel(request)
    if seller_redirect:
        return seller_redirect
    with transaction.atomic():
        user = User.objects.select_for_update().get(pk=request.user.pk)
        cart = Cart.objects.select_for_update().filter(user=user).first()
        if cart is None:
            messages.error(request, "سبد خرید شما خالی است.")
            _clear_checkout_session(request)
            return redirect("bazar:cart")
        cart_items = list(
            cart.items.select_for_update()
            .select_related("product", "product__seller", "product__seller__user", "product__category")
            .order_by("id")
        )

        if not cart_items:
            messages.error(request, "سبد خرید شما خالی است.")
            _clear_checkout_session(request)
            return redirect("bazar:cart")

        for item in cart_items:
            if not item.product.is_active or not item.product.category.is_active or not item.product.seller.is_active:
                messages.error(request, f"محصول {item.product.title} دیگر قابل خرید نیست.")
                return redirect("bazar:cart")
            if item.quantity > item.product.stock:
                messages.error(request, f"موجودی {item.product.title} کافی نیست.")
                return redirect("bazar:cart")

        cart_total = sum(item.item_total for item in cart_items)
        coins_used = min(_get_applied_coins(request, user, cart_total), int(user.challenge_coins or 0), cart_total)
        remaining_amount = max(cart_total - coins_used, 0)
        if remaining_amount > 0:
            context = {
                "status": "insufficient_coins",
                "shortage": remaining_amount,
                "charge_request_url": f"{reverse('bazar:wallet-charge')}?amount={remaining_amount}",
                "page_name": "bazar",
                "page_title": "عدم کفایت سکه | جبهه بازار",
            }
            return render(request, "jebhe_bazar/payment.html", context)

        if coins_used > 0:
            user.challenge_coins -= coins_used
            record_coin_spend(user, coins_used, f"استفاده از {coins_used} سکه برای خرید از جبهه بازار")

        user.save(update_fields=["challenge_coins"])

        order = Order.objects.create(
            user=user,
            total_amount=cart_total,
            coins_used=coins_used,
            wallet_used=0,
            online_paid=0,
            status=Order.Status.PAID,
        )

        Transaction.objects.create(
            user=user,
            order=order,
            amount=cart_total,
            transaction_type=Transaction.TransactionType.PURCHASE,
            description=(
                f"پرداخت سفارش #{order.pk}. "
                f"سکه مصرفی: {coins_used} تومان."
            ),
        )

        commission_totals: dict[int, int] = {}
        for item in cart_items:
            OrderItem.objects.create(
                order=order,
                product=item.product,
                quantity=item.quantity,
                unit_price=item.product.final_price,
            )
            item.product.stock -= item.quantity
            item.product.save(update_fields=["stock"])

            seller_id = item.product.seller_id
            item_total = item.quantity * item.product.final_price
            commission_value = Decimal(item_total) * Decimal(item.product.seller.platform_commission_percent) / Decimal(100)
            commission_totals[seller_id] = commission_totals.get(seller_id, 0) + int(
                commission_value.quantize(Decimal("1"))
            )

        for seller_id, commission_amount in commission_totals.items():
            seller = Seller.objects.select_related("user").get(pk=seller_id)
            Transaction.objects.create(
                user=seller.user,
                order=order,
                amount=commission_amount,
                transaction_type=Transaction.TransactionType.COMMISSION,
                description=f"کمیسیون سفارش #{order.pk} برای فروشگاه {seller.shop_name}",
            )

        cart.items.all().delete()
        _clear_checkout_session(request)

    messages.success(request, "پرداخت با موفقیت انجام شد.")
    context = {
        "status": "success",
        "order": order,
        "page_name": "bazar",
        "page_title": "پرداخت موفق | جبهه بازار",
    }
    return render(request, "jebhe_bazar/payment.html", context)


@login_required
@require_http_methods(["GET", "POST"])
def wallet_charge_view(request: HttpRequest) -> HttpResponse:
    seller_redirect = _redirect_seller_to_panel(request)
    if seller_redirect:
        return seller_redirect
    suggested_amount = int(request.GET.get("amount", 0) or 0)
    recent_requests = WalletChargeRequest.objects.filter(user=request.user).order_by("-created_at")[:5]

    if request.method == "POST":
        form = WalletChargeRequestForm(request.POST, suggested_amount=suggested_amount)
        if form.is_valid():
            amount = form.cleaned_data["amount"]
            WalletChargeRequest.objects.create(
                user=request.user,
                requested_amount=amount,
                requested_coins=amount,
            )
            messages.success(request, "درخواست افزایش اعتبار ثبت شد و پس از بررسی، شماره کارت برای شما ارسال می‌شود.")
            return redirect("bazar:wallet-charge")
    else:
        form = WalletChargeRequestForm(suggested_amount=suggested_amount)

    context = {
        "form": form,
        "suggested_amount": suggested_amount,
        "recent_requests": recent_requests,
        "page_name": "bazar",
        "page_title": "درخواست افزایش اعتبار | جبهه بازار",
    }
    return render(request, "jebhe_bazar/wallet_charge.html", context)


@method_decorator(login_required, name="dispatch")
class OrderHistoryView(ListView):
    model = Order
    template_name = "jebhe_bazar/order_history.html"
    context_object_name = "orders"
    paginate_by = 10

    def dispatch(self, request, *args, **kwargs):
        seller_redirect = _redirect_seller_to_panel(request)
        if seller_redirect:
            return seller_redirect
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        return (
            Order.objects.filter(user=self.request.user)
            .prefetch_related(
                Prefetch(
                    "items",
                    queryset=OrderItem.objects.select_related("product", "product__seller", "product__seller__user"),
                )
            )
            .order_by("-created_at")
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_name"] = "bazar"
        context["page_title"] = "سوابق سفارش | جبهه بازار"
        return context


class SellerContextMixin:
    @property
    def seller(self) -> Seller:
        return _require_seller(self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["seller_profile"] = self.seller
        context["page_name"] = "bazar"
        return context


@method_decorator(login_required, name="dispatch")
class SellerDashboardView(SellerContextMixin, ListView):
    model = OrderItem
    template_name = "jebhe_bazar/seller/dashboard.html"
    context_object_name = "recent_items"
    paginate_by = 8

    def get_queryset(self):
        return (
            OrderItem.objects.select_related("order", "product", "product__seller", "order__user")
            .filter(product__seller=self.seller, order__status=Order.Status.PAID)
            .order_by("-order__created_at")
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        paid_items = OrderItem.objects.filter(product__seller=self.seller, order__status=Order.Status.PAID)
        revenue_expression = ExpressionWrapper(F("quantity") * F("unit_price"), output_field=IntegerField())
        totals = paid_items.aggregate(
            total_sales=Coalesce(Sum("quantity"), 0),
            total_revenue=Coalesce(Sum(revenue_expression), 0),
        )
        commission_paid = (
            Transaction.objects.filter(
                user=self.seller.user,
                transaction_type=Transaction.TransactionType.COMMISSION,
            ).aggregate(total=Coalesce(Sum("amount"), 0))["total"]
            or 0
        )
        context.update(
            {
                "page_title": "پنل فروشنده | جبهه بازار",
                "total_sales": totals["total_sales"],
                "total_revenue": totals["total_revenue"],
                "commission_paid": commission_paid,
                "seller_orders_count": paid_items.values("order_id").distinct().count(),
                "qr_code": getattr(self.seller, "qr_code", None),
            }
        )
        return context


@method_decorator(login_required, name="dispatch")
class SellerProductListView(SellerContextMixin, ListView):
    model = Product
    template_name = "jebhe_bazar/seller/product_list.html"
    context_object_name = "products"
    paginate_by = 12

    def get_queryset(self):
        return Product.objects.select_related("category").filter(seller=self.seller).order_by("-created_at")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "محصولات فروشنده | جبهه بازار"
        return context


@method_decorator(login_required, name="dispatch")
class SellerProductCreateView(SellerContextMixin, CreateView):
    model = Product
    form_class = ProductForm
    template_name = "jebhe_bazar/seller/product_form.html"
    success_url = reverse_lazy("bazar:seller-product-list")

    def form_valid(self, form):
        form.instance.seller = self.seller
        messages.success(self.request, "محصول جدید با موفقیت ثبت شد.")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "افزودن محصول | جبهه بازار"
        context["form_title"] = "افزودن محصول جدید"
        return context


@method_decorator(login_required, name="dispatch")
class SellerProductUpdateView(SellerContextMixin, UpdateView):
    model = Product
    form_class = ProductForm
    template_name = "jebhe_bazar/seller/product_form.html"
    success_url = reverse_lazy("bazar:seller-product-list")

    def get_queryset(self):
        return Product.objects.filter(seller=self.seller)

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        if "_delete" in request.POST:
            product_title = self.object.title
            self.object.delete()
            messages.success(request, f"محصول {product_title} حذف شد.")
            return redirect(self.success_url)
        return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        messages.success(self.request, "محصول با موفقیت بروزرسانی شد.")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "ویرایش محصول | جبهه بازار"
        context["form_title"] = f"ویرایش {self.object.title}"
        return context


@method_decorator(login_required, name="dispatch")
class SellerOrderListView(SellerContextMixin, ListView):
    model = Order
    template_name = "jebhe_bazar/seller/order_list.html"
    context_object_name = "orders"
    paginate_by = 10

    def get_queryset(self):
        seller_items = OrderItem.objects.select_related("product", "product__seller").filter(product__seller=self.seller)
        return (
            Order.objects.filter(items__product__seller=self.seller)
            .prefetch_related(Prefetch("items", queryset=seller_items))
            .select_related("user")
            .distinct()
            .order_by("-created_at")
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "سفارش‌های فروشنده | جبهه بازار"
        return context
